# WHAT THIS FILE DOES: Checks that no sample material has the word "sample" in its name any more (team decision 2026-11-27),
#   that the five renamed demo hardware items keep everything else (type, colour, unit, stock, supplier offer), and that the
#   one-line command for an EXISTING database renames them without touching stock movements, dates or printer settings.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import csv
import os
import sqlite3
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import setup_database   # noqa: E402

NEW_NAMES = {"M009": "M4 Socket Head Screws", "M010": "Compression Springs 8mm", "M011": "Nickel Disc Magnets 6x3mm",
             "M012": "Fidget Clicker Kit", "M013": "Keychain Rings 25mm"}
OLD_NAMES = {"M009": "SAMPLE M4 Socket Screws", "M010": "SAMPLE Compression Springs 8mm", "M011": "SAMPLE Magnets 6x3mm",
             "M012": "SAMPLE Fidget Clicker Kit", "M013": "SAMPLE Keychain Rings 25mm"}

# The exact command given to the team for an existing database (the database file is the one argument after it).
ONE_LINER = (
    "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);"
    "m={'SAMPLE M4 Socket Screws':'M4 Socket Head Screws','SAMPLE Compression Springs 8mm':'Compression Springs 8mm',"
    "'SAMPLE Magnets 6x3mm':'Nickel Disc Magnets 6x3mm','SAMPLE Fidget Clicker Kit':'Fidget Clicker Kit',"
    "'SAMPLE Keychain Rings 25mm':'Keychain Rings 25mm'};"
    "n=sum(c.execute('UPDATE materials SET name=?, updated_at=CURRENT_TIMESTAMP WHERE name=?',(v,k)).rowcount for k,v in m.items());"
    "c.commit();print('renamed',n,'row(s). Names still containing sample:',"
    "c.execute(\"SELECT id,name FROM materials WHERE lower(name) LIKE '%sample%'\").fetchall())"
)


# Returns the rows of sample_data/materials.csv.
def seed_rows():
    path = os.path.join(setup_database.SAMPLE_FOLDER, "materials.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# Builds a database from the real seed files in a temporary folder.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "names.db")
    connection = sqlite3.connect(path)
    with open(setup_database.SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    for table_name in setup_database.TABLES_TO_LOAD:
        setup_database.load_table(connection, table_name)
    connection.commit()
    connection.close()
    return path


# Runs the one-line command on a database file and returns its printed text.
def run_one_liner(database_file):
    result = subprocess.run([sys.executable, "-c", ONE_LINER, database_file], capture_output=True, text=True, check=True)
    return result.stdout.strip()


# ---------- the seed data ----------

def test_no_sample_material_name_contains_the_word_sample():
    assert [row["name"] for row in seed_rows() if "sample" in row["name"].lower()] == []


def test_the_five_demo_hardware_items_have_their_new_names_and_nothing_else_changed():
    rows = {row["id"]: row for row in seed_rows()}
    for material_id, name in NEW_NAMES.items():
        row = rows[material_id]
        assert row["name"] == name and row["unit"] == "pcs" and row["material_type"] == "Hardware"
    assert rows["M011"]["colour"] == "Silver" and rows["M012"]["colour"] == "Black" and rows["M009"]["quantity_on_hand"] == "240"


def test_all_material_names_are_unique_so_nothing_is_confused_in_the_list():
    names = [row["name"] + "|" + row["colour"] for row in seed_rows()]
    assert len(names) == len(set(names))


def test_every_renamed_item_still_has_exactly_one_active_offer_in_the_same_unit(database_file):
    connection = sqlite3.connect(database_file)
    for material_id in NEW_NAMES:
        offers = connection.execute("SELECT pack_unit FROM supplier_offers WHERE material_id = ? AND is_active = 1", (material_id,)).fetchall()
        assert offers == [("pcs",)], material_id
    connection.close()


def test_sync_suppliers_still_works_and_never_renames_materials(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET name = 'My own name' WHERE id = 'M009'")
    connection.commit()
    connection.close()
    setup_database.sync_sample_suppliers(database_file)
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT name FROM materials WHERE id = 'M009'").fetchone()[0] == "My own name"
    assert connection.execute("SELECT COUNT(*) FROM supplier_offers WHERE is_active = 1").fetchone()[0] == 39
    connection.close()


# ---------- the one-line command for an existing database ----------

# Puts a database into the OLD state: the old SAMPLE names, plus a spool, printer settings and extra stock history.
def make_old_database(path):
    connection = sqlite3.connect(path)
    for material_id, name in OLD_NAMES.items():
        connection.execute("UPDATE materials SET name = ? WHERE id = ?", (name, material_id))
    connection.execute("UPDATE materials SET opened_date = '2026-11-20', nozzle_temp = 215, bed_temp = 60, flow_rate = 0.97, "
                       "drying_note = '50 C / 4h', last_dried_date = '2026-11-22' WHERE id = 'M001'")
    connection.execute("INSERT INTO materials (id, name, unit, quantity_on_hand, reorder_level) VALUES ('M900', 'My own sample jar', 'pcs', 5, 2)")
    connection.commit()
    connection.close()


# Reads the facts the command must never change.
def facts(database_file):
    connection = sqlite3.connect(database_file)
    result = {
        "movements": connection.execute("SELECT * FROM stock_movements ORDER BY id").fetchall(),
        "events": connection.execute("SELECT COUNT(*) FROM low_stock_events").fetchone()[0],
        "offers": connection.execute("SELECT * FROM supplier_offers ORDER BY id").fetchall(),
        "settings": connection.execute("SELECT id, opened_date, last_dried_date, nozzle_temp, bed_temp, flow_rate, drying_note, "
                                       "quantity_on_hand, reorder_level, unit, colour, material_type, is_active FROM materials ORDER BY id").fetchall(),
        "count": connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0],
    }
    connection.close()
    return result


def test_the_one_liner_renames_the_five_items_and_changes_nothing_else(database_file):
    make_old_database(database_file)
    before = facts(database_file)
    output = run_one_liner(database_file)
    connection = sqlite3.connect(database_file)
    names = dict(connection.execute("SELECT id, name FROM materials WHERE id IN ('M009','M010','M011','M012','M013')"))
    connection.close()
    assert names == NEW_NAMES
    assert output.startswith("renamed 5 row(s).")
    assert facts(database_file) == before                                   # movements, dates, settings, offers, stock: all untouched


def test_the_one_liner_leaves_other_names_alone_and_reports_them(database_file):
    make_old_database(database_file)
    output = run_one_liner(database_file)
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT name FROM materials WHERE id = 'M900'").fetchone()[0] == "My own sample jar"
    connection.close()
    assert "M900" in output and "My own sample jar" in output               # shown to the person, not guessed at


def test_the_one_liner_can_be_run_twice_and_on_an_already_clean_database(database_file):
    make_old_database(database_file)
    run_one_liner(database_file)
    again = run_one_liner(database_file)
    assert again.startswith("renamed 0 row(s).")
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT name FROM materials WHERE id = 'M011'").fetchone()[0] == "Nickel Disc Magnets 6x3mm"
    connection.close()


def test_the_one_liner_updates_the_changed_date_so_the_edit_is_traceable(database_file):
    make_old_database(database_file)
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET updated_at = '2020-01-01 00:00:00' WHERE id = 'M009'")
    connection.commit()
    connection.close()
    run_one_liner(database_file)
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT updated_at FROM materials WHERE id = 'M009'").fetchone()[0] > "2020-01-01 00:00:00"
    connection.close()

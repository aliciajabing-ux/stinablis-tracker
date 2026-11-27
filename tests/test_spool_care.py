# WHAT THIS FILE DOES: Automatic checks for the spool-care experiment (2026-11-26): the "Sealed / Open Xd" chips, the
#   "Open Spool Today" and "Mark Dried Today" buttons, the saved printer settings line, the dryer notifications on Home,
#   the optional filament columns in the database and their upgrade, and the rules for who can press what.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import os
import sqlite3
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, setup_database, spool_care   # noqa: E402

PASSWORD = "test-password-123"
TODAY = spool_care.today_malaysia()
FILAMENT_ID = "M001"        # PLA Basic White, grams: sample data has it opened and with printer settings
SEALED_ID = "M002"          # PLA Basic Black, grams: never opened in the sample data
HARDWARE_ID = "M020"        # M3x8 socket cap screw, pieces: spool care never applies


# Returns a day as the text the database stores, for example days_ago(3) = three days before today (Malaysia date).
def days_ago(days):
    return (TODAY - timedelta(days=days)).strftime("%Y-%m-%d")


# Builds a temporary database from schema.sql and the real sample_data files, with passwords for the sample users.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "spool.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    with open(setup_database.SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    for table_name in setup_database.TABLES_TO_LOAD:
        setup_database.load_table(connection, table_name)
    for user in connection.execute("SELECT username FROM users").fetchall():
        auth.set_password(connection, user["username"], PASSWORD)
    connection.close()
    return path


# Returns a test browser logged in as the first active user with this role (role None = nobody logged in).
def browser_for(database_file, role, csrf=False):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": csrf})
    browser = website.test_client()
    if role:
        connection = sqlite3.connect(database_file)
        username = connection.execute("SELECT username FROM users WHERE role = ? AND is_active = 1", (role,)).fetchone()[0]
        connection.close()
        browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


@pytest.fixture
def admin(database_file):
    return browser_for(database_file, "ADMIN")


@pytest.fixture
def employee(database_file):
    return browser_for(database_file, "EMPLOYEE")


# Reads one material row straight from the database file.
def read_material(database_file, material_id):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    connection.close()
    return row


# Changes columns of one material straight in the database file (used to set up a situation).
def set_material(database_file, material_id, **columns):
    connection = sqlite3.connect(database_file)
    assignments = ", ".join(f"{name} = ?" for name in columns)
    connection.execute(f"UPDATE materials SET {assignments} WHERE id = ?", (*columns.values(), material_id))
    connection.commit()
    connection.close()


# Makes every spool in the sample data sealed again, so a test only sees the spools it sets up itself.
def seal_all_spools(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET opened_date = NULL, last_dried_date = NULL")
    connection.commit()
    connection.close()


# Returns the activity-log actions written so far.
def log_actions(database_file):
    connection = sqlite3.connect(database_file)
    actions = [row[0] for row in connection.execute("SELECT action FROM activity_log")]
    connection.close()
    return actions


# Returns the HTML of the one table row of the Materials page whose data-name starts with the given lower-case text.
def row_html(page, name_start):
    start = page.index(f'<tr data-name="{name_start}')
    return page[start:page.index("</tr>", start)]


# ---------- the rules in spool_care.py (no website needed) ----------

def filament(**columns):
    base = {"unit": "g", "opened_date": None, "last_dried_date": None, "nozzle_temp": None, "bed_temp": None,
            "flow_rate": None, "drying_note": None}
    return {**base, **columns}


def test_a_never_opened_spool_is_sealed_and_can_only_be_opened():
    care = spool_care.get_spool_care(filament(), TODAY)
    assert care["chip"] == "Sealed" and care["can_open"] and not care["can_dry"] and care["days"] is None


@pytest.mark.parametrize("days, state, chip", [
    (0, "open", "Open 0d"), (6, "open", "Open 6d"),
    (7, "dry_box", "Open 7d · Dry box recommended"), (20, "dry_box", "Open 20d · Dry box recommended"),
    (21, "dryer", "Open 21d · Put in dryer before use"), (60, "dryer", "Open 60d · Put in dryer before use")])
def test_the_chip_follows_the_7_and_21_day_limits(days, state, chip):
    care = spool_care.get_spool_care(filament(opened_date=days_ago(days)), TODAY)
    assert (care["state"], care["chip"], care["days"]) == (state, chip, days)
    assert care["needs_dryer"] is (state == "dryer") and care["can_dry"] and not care["can_open"]


def test_drying_restarts_the_clock():
    care = spool_care.get_spool_care(filament(opened_date=days_ago(30), last_dried_date=days_ago(2)), TODAY)
    assert care["days"] == 2 and care["state"] == "open"


def test_a_date_in_the_future_never_gives_negative_days():
    assert spool_care.get_spool_care(filament(opened_date=days_ago(-3)), TODAY)["days"] == 0


def test_hardware_in_pieces_has_no_spool_care_and_no_settings_line():
    hardware = filament(unit="pcs", opened_date=days_ago(40), nozzle_temp=200)
    assert spool_care.get_spool_care(hardware, TODAY) is None
    assert spool_care.format_printer_settings(hardware) is None


def test_bad_or_empty_dates_count_as_sealed():
    for text in ["", "  ", "20-11-2026", "2026-13-45", "soon"]:
        assert spool_care.get_spool_care(filament(opened_date=text), TODAY)["chip"] == "Sealed"


def test_printer_settings_line_shows_only_what_was_saved():
    full = filament(nozzle_temp=235, bed_temp=75, flow_rate=0.96, drying_note="65 °C / 6h")
    assert spool_care.format_printer_settings(full) == "Nozzle 235 °C · Bed 75 °C · Flow 0.96 · Dry 65 °C / 6h"
    assert spool_care.format_printer_settings(filament(bed_temp=0, flow_rate=1.0)) == "Bed 0 °C · Flow 1"
    assert spool_care.format_printer_settings(filament(drying_note="  ")) is None
    assert spool_care.format_printer_settings(filament()) is None


# ---------- the database ----------

def test_fresh_database_has_the_six_optional_filament_columns_and_the_sample_data_fills_them(database_file):
    row = read_material(database_file, FILAMENT_ID)
    for column in ["opened_date", "last_dried_date", "nozzle_temp", "bed_temp", "flow_rate", "drying_note"]:
        assert column in row.keys()
    assert row["nozzle_temp"] == 210 and row["opened_date"] and not row["last_dried_date"]


def test_sample_hardware_never_has_spool_columns_filled_and_sample_filament_is_in_range(database_file):
    connection = sqlite3.connect(database_file)
    hardware_with_data = connection.execute(
        "SELECT id FROM materials WHERE unit = 'pcs' AND (opened_date IS NOT NULL OR nozzle_temp IS NOT NULL OR bed_temp IS NOT NULL "
        "OR flow_rate IS NOT NULL OR drying_note IS NOT NULL OR last_dried_date IS NOT NULL)").fetchall()
    out_of_range = connection.execute(
        "SELECT id FROM materials WHERE (nozzle_temp NOT BETWEEN 100 AND 400) OR (bed_temp NOT BETWEEN 0 AND 150) "
        "OR (flow_rate NOT BETWEEN 0.5 AND 1.5)").fetchall()
    connection.close()
    assert hardware_with_data == [] and out_of_range == []


def test_the_database_refuses_silly_printer_settings(database_file):
    connection = sqlite3.connect(database_file)
    for column, bad in (("nozzle_temp", 50), ("bed_temp", 200), ("flow_rate", 3.0)):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE materials SET {column} = ? WHERE id = ?", (bad, FILAMENT_ID))
    connection.close()


# Builds a database in the OLD layout (before spool care) with one material in it.
def make_old_database(path):
    connection = sqlite3.connect(path)
    with open(setup_database.SCHEMA_FILE, encoding="utf-8") as schema:
        sql = schema.read()
    start = sql.index("    -- EXPERIMENT 2026-11-26 (filament only")
    end = sql.index(");", start)
    old_sql = sql[:start].rstrip().rstrip(",") + "\n" + sql[end:]
    connection.executescript(old_sql)
    connection.execute("INSERT INTO materials (id, name, unit, quantity_on_hand, reorder_level) VALUES ('M1', 'Old PLA', 'g', 500, 100)")
    connection.commit()
    connection.close()


def test_upgrade_adds_the_columns_to_an_old_database_keeps_the_data_and_can_be_repeated(tmp_path):
    path = str(tmp_path / "old.db")
    make_old_database(path)
    assert "opened_date" not in read_material(path, "M1").keys()
    setup_database.upgrade_database(path)
    setup_database.upgrade_database(path)                                   # safe to repeat
    row = read_material(path, "M1")
    assert row["name"] == "Old PLA" and row["quantity_on_hand"] == 500
    assert all(row[column] is None for column in ["opened_date", "last_dried_date", "nozzle_temp", "bed_temp", "flow_rate", "drying_note"])


# ---------- the two buttons ----------

def test_open_spool_today_saves_todays_malaysia_date_and_writes_the_log(employee, database_file):
    response = employee.post(f"/materials/{SEALED_ID}/spool/open")
    assert response.status_code == 302 and response.headers["Location"].endswith("/materials/")
    assert read_material(database_file, SEALED_ID)["opened_date"] == TODAY.strftime("%Y-%m-%d")
    assert "SPOOL_OPENED" in log_actions(database_file)


def test_pressing_open_twice_changes_nothing_the_second_time(employee, database_file):
    employee.post(f"/materials/{SEALED_ID}/spool/open")
    set_material(database_file, SEALED_ID, opened_date=days_ago(4))
    page = employee.post(f"/materials/{SEALED_ID}/spool/open", follow_redirects=True).get_data(as_text=True)
    assert "was already opened" in page and read_material(database_file, SEALED_ID)["opened_date"] == days_ago(4)
    assert log_actions(database_file).count("SPOOL_OPENED") == 1


def test_mark_dried_needs_an_opened_spool_first(employee, database_file):
    page = employee.post(f"/materials/{SEALED_ID}/spool/dried", follow_redirects=True).get_data(as_text=True)
    assert 'Press "Open Spool Today" first' in page.replace("&#34;", '"')
    assert read_material(database_file, SEALED_ID)["last_dried_date"] is None and "SPOOL_DRIED" not in log_actions(database_file)


def test_mark_dried_saves_today_restarts_the_chip_clock_and_writes_the_log(admin, database_file):
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(30))
    admin.post(f"/materials/{FILAMENT_ID}/spool/dried")
    assert read_material(database_file, FILAMENT_ID)["last_dried_date"] == TODAY.strftime("%Y-%m-%d")
    assert "SPOOL_DRIED" in log_actions(database_file)
    assert "Open 0d" in row_html(admin.get("/materials/").get_data(as_text=True), "pla basic white")


def test_hardware_and_unknown_actions_are_refused(admin, database_file):
    assert admin.post(f"/materials/{HARDWARE_ID}/spool/open").status_code == 404
    assert admin.post(f"/materials/{FILAMENT_ID}/spool/steal").status_code == 404
    assert admin.post("/materials/NOPE/spool/open").status_code == 404
    assert read_material(database_file, HARDWARE_ID)["opened_date"] is None


def test_visitors_are_sent_to_login_and_the_buttons_are_post_only(database_file):
    nobody = browser_for(database_file, None)
    assert nobody.post(f"/materials/{SEALED_ID}/spool/open").status_code == 302
    assert read_material(database_file, SEALED_ID)["opened_date"] is None
    assert browser_for(database_file, "ADMIN").get(f"/materials/{SEALED_ID}/spool/open").status_code == 405


def test_a_form_without_the_security_code_is_refused_when_csrf_is_on(database_file):
    browser = browser_for(database_file, "EMPLOYEE", csrf=True)
    assert browser.post(f"/materials/{SEALED_ID}/spool/open").status_code == 400
    assert read_material(database_file, SEALED_ID)["opened_date"] is None


# ---------- the Materials page ----------

@pytest.mark.parametrize("who", ["employee", "admin"])
def test_materials_page_shows_chip_buttons_and_settings_for_filament_only(who, request):
    page = request.getfixturevalue(who).get("/materials/").get_data(as_text=True)
    sealed, opened = row_html(page, "pla basic black"), row_html(page, "pla basic white")
    assert ">Sealed<" in sealed and "Open Spool Today" in sealed and "Mark Dried Today" not in sealed
    assert "Mark Dried Today" in opened and "Open Spool Today" not in opened and "Nozzle 210" in opened
    hardware = row_html(page, "m3x8 socket cap screw")
    for word in ["chip", "Open Spool Today", "Mark Dried Today", "Nozzle"]:
        assert word not in hardware


def test_materials_page_chip_words_name_the_dry_advice(admin, database_file):
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(10))
    set_material(database_file, "M003", opened_date=days_ago(25))
    page = admin.get("/materials/").get_data(as_text=True)
    assert "Dry box recommended" in row_html(page, "petg clear") or "Dry box recommended" in row_html(page, "pla basic white")
    assert "Put in dryer before use" in row_html(page, "petg clear")


def test_spool_care_and_the_supplier_line_and_option_2_layout_live_together(admin):
    page = admin.get("/materials/").get_data(as_text=True)
    row = row_html(page, "pla basic white")
    assert 'class="m-name"' in row and "Supplier: " in row and 'class="spool"' in row and "settings-line" in row
    assert "OPTION 2 LAYOUT v2" in page and "Not bought through this app yet" not in page


# ---------- Home notifications ----------

def test_home_lists_a_spool_that_needs_the_dryer_and_the_button_clears_it(admin, database_file):
    seal_all_spools(database_file)
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(30))
    home = admin.get("/").get_data(as_text=True)
    assert "DRY" in home and "open 30 days" in home and 'name="back" value="home"' in home
    response = admin.post(f"/materials/{FILAMENT_ID}/spool/dried", data={"back": "home"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/")
    assert "open 30 days" not in admin.get("/").get_data(as_text=True)


def test_home_does_not_list_young_spools_or_hardware(admin, database_file):
    seal_all_spools(database_file)
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(20))
    set_material(database_file, HARDWARE_ID, opened_date=days_ago(90))     # nonsense for hardware: must be ignored
    home = admin.get("/").get_data(as_text=True)
    assert "<strong>DRY</strong>" not in home and "No notifications" not in home      # the LOW / OUT items are still listed


def test_home_says_all_is_ok_only_when_nothing_is_low_out_or_waiting_for_the_dryer(admin, database_file):
    seal_all_spools(database_file)
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET quantity_on_hand = reorder_level + 1000")
    connection.commit()
    connection.close()
    assert "No notifications. All materials are OK." in admin.get("/").get_data(as_text=True)
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(40))
    home = admin.get("/").get_data(as_text=True)
    assert "No notifications" not in home and "<strong>DRY</strong>" in home


def test_home_keeps_the_low_and_out_boxes_next_to_the_dryer_lines(employee, database_file):
    seal_all_spools(database_file)
    set_material(database_file, FILAMENT_ID, opened_date=days_ago(30))
    home = employee.get("/").get_data(as_text=True)
    assert 'class="tag tag-OUT"' in home and "Find supplier" in home and "Mark Dried Today" in home
    assert "MYR" not in home


# ---------- printer settings on the Add / Edit material forms ----------

GOOD_NEW_FILAMENT = {"name": "ASA Test", "material_type": "ASA", "colour": "Red", "unit": "g", "starting_quantity": "800",
                     "reorder_level": "200", "nozzle_temp": "250", "bed_temp": "95", "flow_rate": "0.95", "drying_note": "70 °C / 8h"}


def test_admin_adds_a_filament_with_printer_settings_and_the_line_shows_on_the_page(admin, database_file):
    assert admin.post("/materials/new", data=GOOD_NEW_FILAMENT).status_code == 302
    connection = sqlite3.connect(database_file)
    row = connection.execute("SELECT nozzle_temp, bed_temp, flow_rate, drying_note, opened_date FROM materials WHERE name = 'ASA Test'").fetchone()
    connection.close()
    assert row == (250, 95, 0.95, "70 °C / 8h", None)                      # a new spool starts sealed
    assert "Nozzle 250 °C · Bed 95 °C · Flow 0.95" in admin.get("/materials/").get_data(as_text=True)


@pytest.mark.parametrize("field, bad, words", [
    ("nozzle_temp", "50", "nozzle temperature"), ("nozzle_temp", "hot", "nozzle temperature"),
    ("bed_temp", "151", "bed temperature"), ("flow_rate", "2.5", "flow rate"), ("flow_rate", "fast", "flow rate"),
    ("drying_note", "x" * 150, "drying note")])
def test_bad_printer_settings_are_refused_in_plain_words_and_nothing_is_saved(admin, database_file, field, bad, words):
    response = admin.post("/materials/new", data={**GOOD_NEW_FILAMENT, field: bad})
    assert response.status_code == 400 and words in response.get_data(as_text=True)
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT COUNT(*) FROM materials WHERE name = 'ASA Test'").fetchone()[0] == 0
    connection.close()


def test_settings_typed_for_a_hardware_item_are_ignored(admin, database_file):
    data = {**GOOD_NEW_FILAMENT, "name": "Test Washers", "unit": "pcs"}
    assert admin.post("/materials/new", data=data).status_code == 302
    connection = sqlite3.connect(database_file)
    row = connection.execute("SELECT nozzle_temp, bed_temp, flow_rate, drying_note FROM materials WHERE name = 'Test Washers'").fetchone()
    connection.close()
    assert row == (None, None, None, None)


def test_edit_form_shows_settings_and_dates_for_filament_but_not_for_hardware(admin):
    filament_page = admin.get(f"/materials/{FILAMENT_ID}/edit").get_data(as_text=True)
    for name in ["nozzle_temp", "bed_temp", "flow_rate", "drying_note", "opened_date", "last_dried_date"]:
        assert f'name="{name}"' in filament_page
    hardware_page = admin.get(f"/materials/{HARDWARE_ID}/edit").get_data(as_text=True)
    assert 'name="nozzle_temp"' not in hardware_page and "filament-fields" not in hardware_page


def test_admin_can_correct_settings_and_dates_and_the_change_is_logged(admin, database_file):
    form = {"name": "PLA Basic", "material_type": "PLA", "colour": "White", "reorder_level": "1000", "nozzle_temp": "215",
            "bed_temp": "60", "flow_rate": "0.97", "drying_note": "50 °C / 4h", "opened_date": days_ago(9), "last_dried_date": days_ago(5)}
    assert admin.post(f"/materials/{FILAMENT_ID}/edit", data=form).status_code == 302
    row = read_material(database_file, FILAMENT_ID)
    assert (row["nozzle_temp"], row["flow_rate"], row["opened_date"], row["last_dried_date"]) == (215, 0.97, days_ago(9), days_ago(5))
    assert "MATERIAL_CHANGED" in log_actions(database_file)


@pytest.mark.parametrize("opened, dried, words", [
    ("20-11-2026", "", "year-month-day"), (days_ago(-2), "", "in the future"),
    ("", days_ago(1), "opened too"), (days_ago(2), days_ago(6), "earlier than")])
def test_wrong_spool_dates_are_refused_in_plain_words(admin, database_file, opened, dried, words):
    form = {"name": "PLA Basic", "material_type": "PLA", "colour": "White", "reorder_level": "1000",
            "opened_date": opened, "last_dried_date": dried}
    before = read_material(database_file, FILAMENT_ID)["opened_date"]
    response = admin.post(f"/materials/{FILAMENT_ID}/edit", data=form)
    assert response.status_code == 400 and words in response.get_data(as_text=True)
    assert read_material(database_file, FILAMENT_ID)["opened_date"] == before


def test_employee_cannot_open_the_add_or_edit_forms_so_settings_stay_admin_only(employee, database_file):
    assert employee.get("/materials/new").status_code == 403
    assert employee.post("/materials/new", data=GOOD_NEW_FILAMENT).status_code == 403
    assert employee.post(f"/materials/{FILAMENT_ID}/edit", data={"name": "X", "nozzle_temp": "300"}).status_code == 403
    assert read_material(database_file, FILAMENT_ID)["nozzle_temp"] == 210

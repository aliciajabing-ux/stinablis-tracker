# WHAT THIS FILE DOES: Checks the ShopGuard sample materials (M014 to M039, including PLA+ Orange and PETG Grey for Test 2)
#   and the two sections of the Materials list ("Filament" and "Other materials").
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import csv
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, setup_database   # noqa: E402

PASSWORD = "test-password-123"
PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Returns the rows of sample_data/materials.csv.
def read_sample_materials():
    with open(os.path.join(PROJECT_FOLDER, "sample_data", "materials.csv"), newline="", encoding="utf-8") as sample_file:
        return list(csv.DictReader(sample_file))


# Builds a temporary database from schema.sql and the real sample_data files, with passwords for the sample users.
@pytest.fixture
def sample_database_file(tmp_path):
    path = str(tmp_path / "sample.db")
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


# Returns a test browser logged in as the first active user with this role.
def logged_in_as(database_file, role):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    connection = sqlite3.connect(database_file)
    username = connection.execute("SELECT username FROM users WHERE role = ? AND is_active = 1", (role,)).fetchone()[0]
    connection.close()
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


# Returns the part of the page that belongs to one section (from its heading to the next heading or the end).
def section_text(page, heading_start, next_heading_start=None):
    start = page.index(heading_start)
    end = page.index(next_heading_start) if next_heading_start else len(page)
    return page[start:end]


def test_sample_file_has_the_26_new_materials_with_unique_ids():
    rows = read_sample_materials()
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids)) and len(rows) == 39
    assert {f"M{number:03d}" for number in range(14, 40)} <= set(ids)


def test_test_2_items_exist_pla_orange_and_petg_grey():
    rows = {(row["name"], row["colour"]) for row in read_sample_materials()}
    assert ("PLA+ 1.75mm", "Orange") in rows and ("PETG 1.75mm", "Grey") in rows


def test_every_sample_material_loads_into_the_database(sample_database_file):
    connection = sqlite3.connect(sample_database_file)
    count = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
    connection.close()
    assert count == 39


@pytest.mark.parametrize("role", ["ADMIN", "EMPLOYEE"])
def test_materials_list_has_two_sections_with_the_right_items(sample_database_file, role):
    page = logged_in_as(sample_database_file, role).get("/materials/").get_data(as_text=True)
    assert page.index("<h2>Filament &amp; Resin") < page.index("<h2>Other materials")
    filament = section_text(page, "<h2>Filament &amp; Resin", "<h2>Other materials")
    hardware = section_text(page, "<h2>Other materials")
    assert "PLA+ 1.75mm" in filament and "PETG 1.75mm" in filament and "Standard Resin" in filament and "Isopropyl Alcohol 99%" not in filament
    assert "Isopropyl Alcohol 99%" in hardware and "Standard Resin" not in hardware
    assert "608ZZ bearing" in hardware and "Stick-On Rubber Feet" in hardware
    assert "608ZZ bearing" not in filament and "PLA+ 1.75mm" not in hardware


def test_section_headings_show_the_right_counts(sample_database_file):
    rows = read_sample_materials()
    spools = sum(1 for row in rows if row["unit"] == "g" or "resin" in row["material_type"].lower())   # grams + resin bottles
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert f"<h2>Filament &amp; Resin <small>({spools})</small>" in page
    assert f"<h2>Other materials <small>({len(rows) - spools})</small>" in page


def test_searching_for_orange_finds_pla_orange_in_the_filament_section_only(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/?q=orange").get_data(as_text=True)
    assert "PLA+ 1.75mm" in page and "<h2>Filament &amp; Resin" in page
    assert "<h2>Other materials" not in page            # a section with no matches is not drawn


def test_a_search_with_no_match_says_so_in_plain_words(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/?q=zzzz-nothing").get_data(as_text=True)
    assert "No materials found" in page and "<h2>" not in page.split("No materials found")[0].split("legend")[-1]


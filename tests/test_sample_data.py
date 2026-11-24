# WHAT THIS FILE DOES: Builds a database from the real sample_data files (the same way setup_database.py does)
#   and checks that the pages which read the history dates do not crash.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# Why: the other tests build their own data, so a wrong date format in sample_data/ went unnoticed.

import os
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, setup_database           # noqa: E402

PASSWORD = "test-password-123"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")   # the format the app reads (auth.TIME_FORMAT)


# Builds a temporary database from schema.sql and the sample_data CSV files, with passwords for the sample users.
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
def logged_in_as(sample_database_file, role):
    website = create_app({"DATABASE": sample_database_file, "SECRET_KEY": "test-only-key", "TESTING": True})
    connection = sqlite3.connect(sample_database_file)
    username = connection.execute("SELECT username FROM users WHERE role = ? AND is_active = 1", (role,)).fetchone()[0]
    connection.close()
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


def test_every_sample_history_date_uses_the_app_format(sample_database_file):
    connection = sqlite3.connect(sample_database_file)
    dates = [row[0] for row in connection.execute("SELECT created_at FROM stock_movements")]
    connection.close()
    assert dates, "the sample data should contain some history"
    assert all(DATE_PATTERN.match(text) for text in dates), dates


def test_record_page_opens_for_material_with_sample_history(sample_database_file):
    connection = sqlite3.connect(sample_database_file)
    material_id = connection.execute("SELECT material_id FROM stock_movements LIMIT 1").fetchone()[0]
    connection.close()
    admin = logged_in_as(sample_database_file, "ADMIN")
    assert admin.get(f"/materials/{material_id}/record/used").status_code == 200
    assert admin.get(f"/materials/{material_id}/record/received").status_code == 200


def test_usage_data_and_csv_work_on_sample_database(sample_database_file):
    admin = logged_in_as(sample_database_file, "ADMIN")
    assert admin.get("/stats/data/usage").status_code == 200
    assert admin.get("/stats/export.csv").status_code == 200

# WHAT THIS FILE DOES: Checks the fixed DEMO passwords of the two sample accounts (team decision 2026-11-27, guide rule C6):
#   a fresh database built by setup_database.py lets sample_admin log in with sampleadmin and sample_employee with
#   sampleemployee; the passwords are stored scrambled; and "upgrade" / "sync-suppliers" never change a password.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, setup_database   # noqa: E402


# Builds a fresh database with setup_database.build_database in a temporary folder and returns its path.
@pytest.fixture
def fresh_database(tmp_path):
    path = str(tmp_path / "data" / "tracker.db")
    setup_database.build_database(path)
    return path


# Returns a test browser on the database (CSRF off, like the other tests).
def browser_for(database_file):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    return website.test_client()


# Reads the stored password hashes of the two sample accounts.
def read_hashes(database_file):
    connection = sqlite3.connect(database_file)
    rows = dict(connection.execute("SELECT username, password_hash FROM users").fetchall())
    connection.close()
    return rows


def test_the_fixed_demo_passwords_are_the_ones_the_team_agreed():
    assert setup_database.SAMPLE_PASSWORDS == {"sample_admin": "sampleadmin", "sample_employee": "sampleemployee"}


def test_fresh_database_lets_the_admin_log_in_with_sampleadmin(fresh_database):
    browser = browser_for(fresh_database)
    response = browser.post("/login", data={"username": "sample_admin", "password": "sampleadmin"})
    assert response.status_code == 302 and "/login" not in response.headers["Location"]
    assert browser.get("/users/").status_code == 200                       # really the Admin


def test_fresh_database_lets_the_employee_log_in_with_sampleemployee_but_not_as_admin(fresh_database):
    browser = browser_for(fresh_database)
    response = browser.post("/login", data={"username": "sample_employee", "password": "sampleemployee"})
    assert response.status_code == 302 and "/login" not in response.headers["Location"]
    assert browser.get("/materials/").status_code == 200
    assert browser.get("/users/").status_code == 403 and browser.get("/suppliers/S001/edit").status_code == 403


@pytest.mark.parametrize("username, wrong", [("sample_admin", "sampleemployee"), ("sample_employee", "sampleadmin"),
                                             ("sample_admin", "password"), ("sample_admin", "SAMPLEADMIN")])
def test_wrong_or_swapped_passwords_are_refused(fresh_database, username, wrong):
    browser = browser_for(fresh_database)
    page = browser.post("/login", data={"username": username, "password": wrong})
    assert page.status_code == 401                                         # refused with the plain login message, not a redirect
    assert browser.get("/materials/").status_code == 302                   # still not logged in


def test_passwords_are_stored_scrambled_and_differently_for_each_account(fresh_database):
    hashes = read_hashes(fresh_database)
    for username, password in setup_database.SAMPLE_PASSWORDS.items():
        assert hashes[username] and password not in hashes[username] and hashes[username] != password
    assert hashes["sample_admin"] != hashes["sample_employee"]


def test_the_sample_users_file_itself_contains_no_password_or_hash():
    path = os.path.join(setup_database.SAMPLE_FOLDER, "users.csv")
    text = open(path, encoding="utf-8").read().lower()
    assert "sampleadmin" not in text and "sampleemployee" not in text and "password" not in text and "scrypt" not in text and "pbkdf2" not in text


def test_upgrade_and_sync_suppliers_never_change_a_password(fresh_database):
    before = read_hashes(fresh_database)
    setup_database.upgrade_database(fresh_database)
    setup_database.sync_sample_suppliers(fresh_database)
    assert read_hashes(fresh_database) == before


def test_a_second_build_on_an_existing_database_stops_and_keeps_the_passwords(fresh_database):
    before = read_hashes(fresh_database)
    setup_database.build_database(fresh_database)                          # refuses: the file already exists
    assert read_hashes(fresh_database) == before

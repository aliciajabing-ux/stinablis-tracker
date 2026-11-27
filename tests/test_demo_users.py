# WHAT THIS FILE DOES: Proves the "demo-users" command adds or updates the presentation accounts admin and employee safely.
# WHO CAN USE IT: Developers (automatic checks).

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, setup_database  # noqa: E402


# Builds a fresh sample database in a temporary folder and returns its path.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "tracker.db")
    setup_database.build_database(path)
    return path


# Returns every row of every table except users and activity_log, so we can prove nothing else changed.
def snapshot_other_tables(path):
    connection = sqlite3.connect(path)
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('users', 'activity_log') "
        "AND name NOT LIKE 'sqlite_%'")]
    result = {name: connection.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall() for name in tables}
    connection.close()
    return result


# Logs in through the real app and returns the response.
def try_login(path, username, password):
    app = create_app({"TESTING": True, "DATABASE": path, "CSRF_ENABLED": False, "SECRET_KEY": "test"})
    return app.test_client().post("/login", data={"username": username, "password": password})


# Reads the two demo users as (role, is_active) by username.
def read_users(path):
    connection = sqlite3.connect(path)
    rows = connection.execute("SELECT username, role, is_active FROM users").fetchall()
    connection.close()
    return {name: (role, active) for name, role, active in rows}


def test_fresh_build_has_no_demo_users(database_file):
    users = read_users(database_file)
    assert "admin" not in users and "employee" not in users
    assert users["sample_admin"][0] == "ADMIN" and users["sample_employee"][0] == "EMPLOYEE"


def test_command_adds_both_users_with_right_roles(database_file):
    setup_database.add_demo_users(database_file)
    users = read_users(database_file)
    assert users["admin"] == ("ADMIN", 1)
    assert users["employee"] == ("EMPLOYEE", 1)


def test_demo_logins_work_and_sample_logins_still_work(database_file):
    setup_database.add_demo_users(database_file)
    for username, password in [("admin", "stinablis2026"), ("employee", "stinablis2026"),
                               ("sample_admin", "sampleadmin"), ("sample_employee", "sampleemployee")]:
        assert try_login(database_file, username, password).status_code == 302, username
    assert try_login(database_file, "admin", "wrong-password").status_code != 302


def test_passwords_are_stored_scrambled(database_file):
    setup_database.add_demo_users(database_file)
    connection = sqlite3.connect(database_file)
    hashes = [row[0] for row in connection.execute("SELECT password_hash FROM users WHERE username IN ('admin','employee')")]
    connection.close()
    assert len(hashes) == 2 and all("stinablis2026" not in value and value for value in hashes)


def test_command_is_repeatable_and_changes_nothing_else(database_file):
    before = snapshot_other_tables(database_file)
    setup_database.add_demo_users(database_file)
    setup_database.add_demo_users(database_file)
    connection = sqlite3.connect(database_file)
    assert connection.execute("SELECT COUNT(*) FROM users WHERE username IN ('admin','employee')").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 4
    connection.close()
    assert snapshot_other_tables(database_file) == before


def test_command_repairs_changed_demo_accounts(database_file):
    setup_database.add_demo_users(database_file)
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE users SET role = 'EMPLOYEE', is_active = 0, failed_login_count = 5, "
                       "locked_until = '2999-01-01 00:00:00' WHERE username = 'admin'")
    connection.commit()
    connection.close()
    setup_database.add_demo_users(database_file)
    assert read_users(database_file)["admin"] == ("ADMIN", 1)
    assert try_login(database_file, "admin", "stinablis2026").status_code == 302


def test_off_command_switches_off_without_deleting(database_file):
    setup_database.add_demo_users(database_file)
    setup_database.switch_demo_users_off(database_file)
    users = read_users(database_file)
    assert users["admin"][1] == 0 and users["employee"][1] == 0
    assert users["sample_admin"][1] == 1
    assert try_login(database_file, "admin", "stinablis2026").status_code != 302


def test_missing_database_is_not_created(tmp_path, capsys):
    path = str(tmp_path / "none.db")
    setup_database.add_demo_users(path)
    setup_database.switch_demo_users_off(path)
    assert not os.path.exists(path)

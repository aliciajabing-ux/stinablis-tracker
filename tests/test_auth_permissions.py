# WHAT THIS FILE DOES: Automatic checks for login, the account lock, and the Admin / Employee rules.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db) and a tiny test website.

import os
import sqlite3
import sys
from datetime import timedelta

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth                                    # noqa: E402
from app.permissions import (admin_required, can_see_prices,   # noqa: E402
                             login_required)

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
ADMIN_PASSWORD = "test-admin-pass-1"
EMPLOYEE_PASSWORD = "test-employee-pass-1"


# Builds a temporary database with one admin, one employee and one switched-off user.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "test.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    for user_id, username, role, active in [("U1", "boss", "ADMIN", 1), ("U2", "worker", "EMPLOYEE", 1),
                                             ("U3", "gone", "EMPLOYEE", 0)]:
        connection.execute("INSERT INTO users (id, username, role, is_active) VALUES (?, ?, ?, ?)",
                           (user_id, username, role, active))
    auth.set_password(connection, "boss", ADMIN_PASSWORD)
    auth.set_password(connection, "worker", EMPLOYEE_PASSWORD)
    auth.set_password(connection, "gone", EMPLOYEE_PASSWORD)
    connection.close()
    return path


# Builds a tiny website with one open page, one logged-in page and two admin-only pages.
@pytest.fixture
def client(database_file):
    app = Flask(__name__)
    app.config.update(DATABASE=database_file, SECRET_KEY="test-only-key", TESTING=True)
    app.register_blueprint(auth.auth_blueprint)

    @app.route("/")
    @login_required
    def home():
        return "home"

    @app.route("/suppliers/edit")
    @admin_required
    def suppliers_edit():
        return "edit suppliers"

    @app.route("/prices", methods=["GET", "POST"])
    @admin_required
    def prices():
        return "secret prices"

    return app.test_client()


# Logs in through the real login form.
def log_in(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


# Reads one user row straight from the database file.
def read_user(database_file, username):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    connection.close()
    return row


def test_login_page_opens(client):
    assert client.get("/login").status_code == 200


def test_good_login_reaches_home(client):
    response = log_in(client, "boss", ADMIN_PASSWORD)
    assert response.status_code == 302
    assert client.get("/").data == b"home"


def test_not_logged_in_is_sent_to_login(client):
    for address in ["/", "/suppliers/edit", "/prices"]:
        response = client.get(address)
        assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_wrong_password_and_wrong_username_look_the_same(client):
    wrong_password = log_in(client, "boss", "nope-nope-nope")
    wrong_username = log_in(client, "nobody", "nope-nope-nope")
    assert wrong_password.status_code == wrong_username.status_code == 401
    assert wrong_password.data == wrong_username.data.replace(b"nobody", b"boss")


def test_switched_off_account_cannot_log_in(client):
    assert log_in(client, "gone", EMPLOYEE_PASSWORD).status_code == 401


def test_account_without_password_cannot_log_in(client, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO users (id, username, role) VALUES ('U9', 'nopass', 'EMPLOYEE')")
    connection.commit()
    connection.close()
    assert log_in(client, "nopass", "").status_code == 401


def test_five_wrong_passwords_lock_the_account(client, database_file):
    for _ in range(5):
        log_in(client, "worker", "wrong-wrong")
    assert read_user(database_file, "worker")["locked_until"] is not None
    # Even the CORRECT password is refused while locked.
    response = log_in(client, "worker", EMPLOYEE_PASSWORD)
    assert response.status_code == 401 and b"locked" in response.data
    assert client.get("/").status_code == 302


def test_four_wrong_passwords_do_not_lock(client, database_file):
    for _ in range(4):
        log_in(client, "worker", "wrong-wrong")
    assert read_user(database_file, "worker")["locked_until"] is None
    assert log_in(client, "worker", EMPLOYEE_PASSWORD).status_code == 302


def test_lock_ends_after_15_minutes(client, database_file):
    for _ in range(5):
        log_in(client, "worker", "wrong-wrong")
    connection = sqlite3.connect(database_file)
    old_time = (auth.utc_now() - timedelta(minutes=1)).strftime(auth.TIME_FORMAT)
    connection.execute("UPDATE users SET locked_until = ? WHERE username = 'worker'", (old_time,))
    connection.commit()
    connection.close()
    assert log_in(client, "worker", EMPLOYEE_PASSWORD).status_code == 302


def test_lock_lasts_about_15_minutes(client, database_file):
    for _ in range(5):
        log_in(client, "worker", "wrong-wrong")
    from datetime import datetime
    locked_until = datetime.strptime(read_user(database_file, "worker")["locked_until"], auth.TIME_FORMAT)
    minutes = (locked_until - auth.utc_now()).total_seconds() / 60
    assert 14 <= minutes <= 15


def test_good_login_resets_wrong_password_count(client, database_file):
    for _ in range(3):
        log_in(client, "worker", "wrong-wrong")
    log_in(client, "worker", EMPLOYEE_PASSWORD)
    assert read_user(database_file, "worker")["failed_login_count"] == 0


def test_passwords_are_stored_scrambled(database_file):
    for username, password in [("boss", ADMIN_PASSWORD), ("worker", EMPLOYEE_PASSWORD)]:
        stored = read_user(database_file, username)["password_hash"]
        assert stored and password not in stored


def test_short_password_is_refused(database_file):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    with pytest.raises(ValueError):
        auth.set_password(connection, "worker", "short")
    connection.close()


def test_logout_ends_the_session(client):
    log_in(client, "boss", ADMIN_PASSWORD)
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302


def test_logout_by_link_is_refused(client):
    assert client.get("/logout").status_code == 405


def test_admin_can_open_admin_pages(client):
    log_in(client, "boss", ADMIN_PASSWORD)
    assert client.get("/suppliers/edit").status_code == 200
    assert client.get("/prices").data == b"secret prices"


def test_employee_is_blocked_from_admin_pages_by_typing_the_address(client):
    log_in(client, "worker", EMPLOYEE_PASSWORD)
    assert client.get("/").status_code == 200            # normal page works
    for address in ["/suppliers/edit", "/prices"]:
        response = client.get(address)
        assert response.status_code == 403
        assert b"secret" not in response.data and b"edit suppliers" not in response.data
    assert client.post("/prices").status_code == 403     # also blocked when sending data


def test_account_switched_off_while_logged_in_loses_access(client, database_file):
    log_in(client, "worker", EMPLOYEE_PASSWORD)
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE users SET is_active = 0 WHERE username = 'worker'")
    connection.commit()
    connection.close()
    assert client.get("/").status_code == 302


def test_only_admin_can_see_prices(client, database_file):
    assert can_see_prices(read_user(database_file, "boss")) is True
    assert can_see_prices(read_user(database_file, "worker")) is False
    assert can_see_prices(None) is False


def test_login_and_lock_are_written_to_activity_log(client, database_file):
    log_in(client, "boss", ADMIN_PASSWORD)
    for _ in range(5):
        log_in(client, "worker", "wrong-wrong")
    connection = sqlite3.connect(database_file)
    actions = [row[0] for row in connection.execute("SELECT action FROM activity_log")]
    connection.close()
    assert "LOGIN" in actions and "LOGIN_FAILED" in actions and "ACCOUNT_LOCKED" in actions


# Checks the real application (create_app): home needs login, and a missing secret key stops startup.
def test_real_app_home_and_logout(database_file):
    from app import create_app
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True})
    real_client = website.test_client()
    assert real_client.get("/").status_code == 302
    log_in(real_client, "worker", EMPLOYEE_PASSWORD)
    page = real_client.get("/")
    assert page.status_code == 200 and b"Log out" in page.data


def test_real_app_refuses_to_start_without_secret_key(monkeypatch):
    from app import create_app
    monkeypatch.delenv("STINABLIS_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


# Checks the menu links (Home, Materials, Suppliers) show when logged in, and not on the login page.
def test_menu_links_show_only_when_logged_in(database_file):
    from app import create_app
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True})
    menu_client = website.test_client()
    login_page = menu_client.get("/login").data
    for link_text in [b">Home<", b">Materials<", b">Suppliers<"]:
        assert link_text not in login_page
    log_in(menu_client, "worker", EMPLOYEE_PASSWORD)
    home_page = menu_client.get("/").data
    for link_text in [b">Home<", b">Materials<", b">Suppliers<"]:
        assert link_text in home_page
    assert b'href="/materials/"' in home_page or b'href="/materials"' in home_page

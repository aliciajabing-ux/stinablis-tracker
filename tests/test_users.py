# WHAT THIS FILE DOES: Automatic checks for the Users screens (guide F8): add, change role, reset password,
#   switch off/on, the safety rules, and that Employees are blocked on the server.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db).

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app                       # noqa: E402

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
PASSWORD = "test-password-123"


# Builds a temporary database with two admins and one employee.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "test.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    for user_id, name, role in [("U1", "boss", "ADMIN"), ("U2", "worker", "EMPLOYEE"), ("U3", "boss2", "ADMIN")]:
        connection.execute("INSERT INTO users (id, username, role) VALUES (?, ?, ?)", (user_id, name, role))
        auth.set_password(connection, name, PASSWORD)
    connection.close()
    return path


@pytest.fixture
def website(database_file):
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True})


# Returns a test browser logged in as the given user (or not logged in when username is None).
def logged_in(website, username):
    browser = website.test_client()
    if username:
        browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


# Reads one row from the temporary database.
def ask(database_file, sql, parameters=()):
    connection = sqlite3.connect(database_file)
    row = connection.execute(sql, parameters).fetchone()
    connection.close()
    return row


# ---------- Who may reach the screens ----------

USER_ADDRESSES = [("get", "/users/"), ("get", "/users/add"), ("post", "/users/add"),
                  ("post", "/users/U2/role"), ("get", "/users/U2/password"), ("post", "/users/U2/password"),
                  ("post", "/users/U2/active")]


@pytest.mark.parametrize("method,address", USER_ADDRESSES)
def test_employee_is_blocked_everywhere(website, method, address):
    reply = getattr(logged_in(website, "worker"), method)(address, data={"username": "x", "role": "ADMIN",
                                                                         "password": "abcdefgh1", "turn": "off"})
    assert reply.status_code == 403


@pytest.mark.parametrize("method,address", USER_ADDRESSES)
def test_logged_out_visitor_goes_to_login(website, method, address):
    reply = getattr(logged_in(website, None), method)(address)
    assert reply.status_code == 302 and "/login" in reply.headers["Location"]


def test_employee_cannot_promote_themselves(website, database_file):
    logged_in(website, "worker").post("/users/U2/role", data={"role": "ADMIN"})
    assert ask(database_file, "SELECT role FROM users WHERE id = 'U2'")[0] == "EMPLOYEE"


def test_menu_link_only_for_admin(website):
    assert "/users/" in logged_in(website, "boss").get("/").get_data(as_text=True)
    assert "/users/" not in logged_in(website, "worker").get("/").get_data(as_text=True)


# ---------- Admin actions ----------

def test_admin_sees_list_without_password_hashes(website):
    page = logged_in(website, "boss").get("/users/").get_data(as_text=True)
    assert "worker" in page and "scrypt" not in page and "pbkdf2" not in page


def test_add_user_can_log_in_and_is_logged(website, database_file):
    admin = logged_in(website, "boss")
    reply = admin.post("/users/add", data={"username": "newbie", "role": "EMPLOYEE", "password": "long-enough-1"})
    assert reply.status_code == 302
    assert ask(database_file, "SELECT role, password_hash FROM users WHERE username = 'newbie'")[0] == "EMPLOYEE"
    assert "long-enough-1" not in ask(database_file, "SELECT password_hash FROM users WHERE username = 'newbie'")[0]
    assert logged_in_ok(website, "newbie", "long-enough-1")
    assert ask(database_file, "SELECT user_id FROM activity_log WHERE action = 'USER_ADDED'")[0] == "U1"


# Returns True if this username and password reach the home page.
def logged_in_ok(website, username, password):
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": password})
    return browser.get("/").status_code == 200


@pytest.mark.parametrize("username,role,password,words", [
    ("worker", "EMPLOYEE", "long-enough-1", "already used"),
    ("a b", "EMPLOYEE", "long-enough-1", "3 to 50"),
    ("fine", "EMPLOYEE", "short", "at least 8"),
    ("fine", "BOSS", "long-enough-1", "choose a role"),
])
def test_add_user_rejects_bad_input_in_plain_words(website, database_file, username, role, password, words):
    reply = logged_in(website, "boss").post("/users/add", data={"username": username, "role": role,
                                                                "password": password})
    assert reply.status_code == 200 and words in reply.get_data(as_text=True)
    assert ask(database_file, "SELECT COUNT(*) FROM users")[0] == 3


def test_change_role_is_saved_and_logged(website, database_file):
    logged_in(website, "boss").post("/users/U2/role", data={"role": "ADMIN"})
    assert ask(database_file, "SELECT role FROM users WHERE id = 'U2'")[0] == "ADMIN"
    assert "from EMPLOYEE to ADMIN" in ask(database_file, "SELECT details FROM activity_log WHERE action = 'ROLE_CHANGED'")[0]


def test_admin_cannot_lower_own_role(website, database_file):
    logged_in(website, "boss").post("/users/U1/role", data={"role": "EMPLOYEE"})
    assert ask(database_file, "SELECT role FROM users WHERE id = 'U1'")[0] == "ADMIN"


def test_reset_password_works_and_unlocks(website, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE users SET locked_until = '2999-01-01 00:00:00' WHERE id = 'U2'")
    connection.commit()
    connection.close()
    logged_in(website, "boss").post("/users/U2/password", data={"password": "brand-new-pass"})
    assert logged_in_ok(website, "worker", "brand-new-pass")
    assert not logged_in_ok(website, "worker", PASSWORD)
    assert ask(database_file, "SELECT COUNT(*) FROM activity_log WHERE action = 'PASSWORD_RESET'")[0] == 1


def test_reset_password_rejects_short_password(website):
    reply = logged_in(website, "boss").post("/users/U2/password", data={"password": "short"})
    assert reply.status_code == 200 and "at least 8" in reply.get_data(as_text=True)
    assert logged_in_ok(website, "worker", PASSWORD)


def test_switch_off_blocks_login_and_keeps_row_then_on_again(website, database_file):
    admin = logged_in(website, "boss")
    worker = logged_in(website, "worker")
    admin.post("/users/U2/active", data={"turn": "off"})
    assert ask(database_file, "SELECT is_active FROM users WHERE id = 'U2'")[0] == 0
    assert worker.get("/materials/").status_code == 302          # already-open session is cut off too
    assert not logged_in_ok(website, "worker", PASSWORD)
    admin.post("/users/U2/active", data={"turn": "on"})
    assert logged_in_ok(website, "worker", PASSWORD)


def test_admin_cannot_switch_off_themselves(website, database_file):
    logged_in(website, "boss").post("/users/U1/active", data={"turn": "off"})
    assert ask(database_file, "SELECT is_active FROM users WHERE id = 'U1'")[0] == 1


def test_last_active_admin_cannot_be_switched_off(website, database_file):
    admin = logged_in(website, "boss")
    admin.post("/users/U3/active", data={"turn": "off"})          # boss2 off: fine, boss stays
    assert ask(database_file, "SELECT is_active FROM users WHERE id = 'U3'")[0] == 0
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE users SET is_active = 1 WHERE id = 'U3'")
    connection.execute("UPDATE users SET is_active = 0 WHERE id = 'U1'")
    connection.commit()
    connection.close()
    other = logged_in(website, "boss2")
    other.post("/users/U3/active", data={"turn": "off"})
    assert ask(database_file, "SELECT is_active FROM users WHERE id = 'U3'")[0] == 1


def test_unknown_user_gives_404(website):
    assert logged_in(website, "boss").get("/users/nobody/password").status_code == 404

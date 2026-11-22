# WHAT THIS FILE DOES: Handles login, logout, scrambled (hashed) passwords and the 5-wrong-passwords lock.
# WHO CAN USE IT: Both (every person must log in first). Only Admin can reach admin-only pages (see permissions.py).
#
# To give a sample account a password (passwords are NEVER saved in Git), run from the project folder:
#     python app/auth.py set-password sample_admin

import getpass
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, current_app, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

# The rule from the guide (F1): 5 wrong passwords lock the account for 15 minutes.
MAX_WRONG_PASSWORDS = 5
LOCK_MINUTES = 15
MIN_PASSWORD_LENGTH = 8
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"   # dates are stored as UTC text

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATABASE_FILE = os.path.join(PROJECT_FOLDER, "data", "tracker.db")

auth_blueprint = Blueprint("auth", __name__, template_folder="templates")

# A fake scrambled password. Checked when the username does not exist, so a wrong
# username and a wrong password take the same time and look the same to an attacker.
FAKE_PASSWORD_HASH = generate_password_hash("not-a-real-password")


# Returns the current time in UTC, without a time zone label (matches how we store it).
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


# Opens the database once per request and reuses it.
def get_db():
    if "db" not in g:
        database_file = current_app.config.get("DATABASE", DEFAULT_DATABASE_FILE)
        g.db = sqlite3.connect(database_file)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


# Closes the database at the end of each request.
@auth_blueprint.teardown_app_request
def close_db(error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


# Writes one line to the activity log (who did what, and when).
def write_activity_log(database, user_id, action, details=""):
    database.execute(
        "INSERT INTO activity_log (id, user_id, action, table_name, record_id, details, created_at) "
        "VALUES (?, ?, ?, 'users', ?, ?, ?)",
        ("L" + uuid.uuid4().hex[:12], user_id, action, user_id, details, utc_now().strftime(TIME_FORMAT)),
    )


# Finds a user by username. Returns None if there is no such user.
def find_user(database, username):
    return database.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


# Returns how many whole minutes are left on an account lock (0 if not locked).
def minutes_locked(user):
    if not user["locked_until"]:
        return 0
    locked_until = datetime.strptime(user["locked_until"], TIME_FORMAT)
    seconds_left = (locked_until - utc_now()).total_seconds()
    if seconds_left <= 0:
        return 0
    return int(seconds_left // 60) + 1


# Counts one more wrong password, and locks the account when the limit is reached.
def record_wrong_password(database, user):
    new_count = user["failed_login_count"] + 1
    if new_count >= MAX_WRONG_PASSWORDS:
        locked_until = (utc_now() + timedelta(minutes=LOCK_MINUTES)).strftime(TIME_FORMAT)
        database.execute("UPDATE users SET failed_login_count = 0, locked_until = ? WHERE id = ?",
                         (locked_until, user["id"]))
        write_activity_log(database, user["id"], "ACCOUNT_LOCKED", "Too many wrong passwords")
    else:
        database.execute("UPDATE users SET failed_login_count = ? WHERE id = ?", (new_count, user["id"]))
        write_activity_log(database, user["id"], "LOGIN_FAILED", "Wrong password")
    database.commit()


# Clears the wrong-password counter and any old lock after a good login.
def record_good_login(database, user):
    database.execute("UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (user["id"],))
    write_activity_log(database, user["id"], "LOGIN", "Logged in")
    database.commit()


# Checks a username and password. Returns (user, message). The user is None when login fails.
def check_login(database, username, password):
    wrong_message = "Wrong username or password. Please try again."
    user = find_user(database, username)

    if user is None or not user["password_hash"]:
        check_password_hash(FAKE_PASSWORD_HASH, password)
        return None, wrong_message
    if not user["is_active"]:
        return None, "This account is switched off. Please ask your Admin."

    minutes_left = minutes_locked(user)
    if minutes_left > 0:
        return None, f"Too many wrong passwords. This account is locked. Please try again in {minutes_left} minute(s)."

    if not check_password_hash(user["password_hash"], password):
        record_wrong_password(database, user)
        user = find_user(database, username)
        if minutes_locked(user) > 0:
            return None, f"Too many wrong passwords. This account is locked for {LOCK_MINUTES} minutes."
        return None, wrong_message

    record_good_login(database, user)
    return user, ""


# Returns the logged-in user (a database row), or None if nobody is logged in
# or the account was switched off since they logged in.
def get_current_user():
    if "current_user" in g:
        return g.current_user
    user = None
    user_id = session.get("user_id")
    if user_id:
        user = get_db().execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
        if user is None:
            session.clear()
    g.current_user = user
    return user


# Saves a new scrambled password for a user. Returns True if saved, False if the username is unknown.
def set_password(database, username, new_password):
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    user = find_user(database, username)
    if user is None:
        return False
    database.execute("UPDATE users SET password_hash = ?, failed_login_count = 0, locked_until = NULL WHERE id = ?",
                     (generate_password_hash(new_password), user["id"]))
    write_activity_log(database, user["id"], "PASSWORD_CHANGED", "Password was set or reset")
    database.commit()
    return True


# Shows the login page and handles the login form.
@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", message="", username="")

    username = request.form.get("username", "").strip()[:100]
    password = request.form.get("password", "")[:200]
    user, message = check_login(get_db(), username, password)
    if user is None:
        return render_template("login.html", message=message, username=username), 401

    session.clear()                      # start a fresh session so an old one cannot be reused
    session["user_id"] = user["id"]
    return redirect("/")


# Logs the user out. POST only, so another website cannot log people out with a link.
@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    user = get_current_user()
    if user is not None:
        write_activity_log(get_db(), user["id"], "LOGOUT", "Logged out")
        get_db().commit()
    session.clear()
    return redirect(url_for("auth.login"))


# Makes "current_user" available inside every HTML page.
@auth_blueprint.app_context_processor
def add_user_to_pages():
    return {"current_user": get_current_user()}


# Command line helper: python app/auth.py set-password <username>
def run_command_line():
    if len(sys.argv) != 3 or sys.argv[1] != "set-password":
        print("Usage: python app/auth.py set-password <username>")
        return
    username = sys.argv[2]
    password = getpass.getpass(f"New password for {username} (at least {MIN_PASSWORD_LENGTH} characters): ")
    if password != getpass.getpass("Type it again: "):
        print("The two passwords do not match. Nothing was changed.")
        return
    database = sqlite3.connect(DEFAULT_DATABASE_FILE)
    database.row_factory = sqlite3.Row
    try:
        saved = set_password(database, username, password)
    except ValueError as problem:
        print(problem)
        return
    print("Password saved." if saved else f"No user called {username}.")


if __name__ == "__main__":
    run_command_line()

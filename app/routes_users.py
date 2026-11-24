# WHAT THIS FILE DOES: The Users screens: list accounts, add a user, change a role, reset a password, and
#   switch an account off or on (guide F8). Accounts are never deleted; they are switched off instead (Rule C9).
# WHO CAN USE IT: Admin only. Every page is guarded on the server by admin_required (Rule C7).

import re
import sqlite3
import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import (MIN_PASSWORD_LENGTH, TIME_FORMAT, find_user, get_current_user, get_db, set_password,
                      utc_now)
from app.permissions import ADMIN_ROLE, EMPLOYEE_ROLE, admin_required

users_blueprint = Blueprint("users", __name__, url_prefix="/users", template_folder="templates")

ROLES = (ADMIN_ROLE, EMPLOYEE_ROLE)
MAX_USERNAME_LENGTH = 50
MAX_PASSWORD_LENGTH = 200
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


# Writes one line to the activity log: which Admin did what to which account.
def write_user_log(database, admin_id, action, target_id, details):
    database.execute(
        "INSERT INTO activity_log (id, user_id, action, table_name, record_id, details, created_at) "
        "VALUES (?, ?, ?, 'users', ?, ?, ?)",
        ("L" + uuid.uuid4().hex[:12], admin_id, action, target_id, details, utc_now().strftime(TIME_FORMAT)))


# Returns the user with this id, or stops with a "not found" page.
def get_user_or_404(user_id):
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)
    return user


# Returns how many active Admin accounts there are.
def count_active_admins(database):
    return database.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_active = 1").fetchone()[0]


# Returns a plain-language problem if this username is not allowed, otherwise "".
def check_username(database, username):
    if not USERNAME_PATTERN.match(username):
        return "Please type a username of 3 to 50 letters, numbers, dots, dashes or underscores, with no spaces."
    if find_user(database, username) is not None:
        return "That username is already used. Please choose another one."
    return ""


# Returns a plain-language problem if this password is not allowed, otherwise "".
def check_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Please type a password of at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return "That password is too long. Please use fewer than 200 characters."
    return ""


# Shows every account with its role, whether it is on, and the buttons to manage it.
@users_blueprint.route("/")
@admin_required
def list_users():
    users = get_db().execute("SELECT * FROM users ORDER BY is_active DESC, username").fetchall()
    return render_template("users_list.html", users=users, roles=ROLES, me=get_current_user())


# Shows the "Add user" form (GET) and creates the account (POST).
@users_blueprint.route("/add", methods=["GET", "POST"])
@admin_required
def add_user():
    form = {"username": "", "role": EMPLOYEE_ROLE}
    problems = []
    if request.method == "POST":
        database = get_db()
        form = {"username": request.form.get("username", "").strip(), "role": request.form.get("role", "")}
        password = request.form.get("password", "")
        problems = [p for p in (check_username(database, form["username"]), check_password(password)) if p]
        if form["role"] not in ROLES:
            problems.append("Please choose a role: Admin or Employee.")
        if not problems:
            return create_user(database, form, password)
    return render_template("users_form.html", form=form, problems=problems, roles=ROLES, min_length=MIN_PASSWORD_LENGTH)


# Saves a new account and its scrambled password, writes the log line, and returns to the list.
def create_user(database, form, password):
    user_id = "U" + uuid.uuid4().hex[:12]
    try:
        database.execute("INSERT INTO users (id, username, role) VALUES (?, ?, ?)",
                         (user_id, form["username"], form["role"]))
    except sqlite3.IntegrityError:
        database.rollback()
        return render_template("users_form.html", form=form, roles=ROLES, min_length=MIN_PASSWORD_LENGTH,
                               problems=["That username is already used. Please choose another one."]), 400
    set_password(database, form["username"], password)
    write_user_log(database, get_current_user()["id"], "USER_ADDED", user_id,
                   f"Added {form['username']} as {form['role']}")
    database.commit()
    flash(f"Added {form['username']}.")
    return redirect(url_for("users.list_users"))


# Changes the role of one account. An Admin cannot lower their own role, and the last Admin stays Admin.
@users_blueprint.route("/<user_id>/role", methods=["POST"])
@admin_required
def change_role(user_id):
    database, admin, user = get_db(), get_current_user(), get_user_or_404(user_id)
    new_role = request.form.get("role", "")
    if new_role not in ROLES:
        flash("Please choose a role: Admin or Employee.")
    elif new_role != user["role"] and user["role"] == ADMIN_ROLE and user["id"] == admin["id"]:
        flash("You cannot make yourself an Employee. Ask another Admin to do it.")
    elif new_role != user["role"]:
        database.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user["id"]))
        write_user_log(database, admin["id"], "ROLE_CHANGED", user["id"],
                       f"Changed role of {user['username']} from {user['role']} to {new_role}")
        database.commit()
        flash(f"{user['username']} is now {new_role.title()}.")
    return redirect(url_for("users.list_users"))


# Shows the "Reset password" form (GET) and saves the new password (POST).
@users_blueprint.route("/<user_id>/password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id):
    user = get_user_or_404(user_id)
    problem = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        problem = check_password(password)
        if not problem:
            set_password(get_db(), user["username"], password)
            write_user_log(get_db(), get_current_user()["id"], "PASSWORD_RESET", user["id"],
                           f"Reset password of {user['username']}")
            get_db().commit()
            flash(f"New password saved for {user['username']}. They can log in with it now.")
            return redirect(url_for("users.list_users"))
    return render_template("users_password.html", user=user, problem=problem, min_length=MIN_PASSWORD_LENGTH)


# Switches an account off or on. An Admin cannot switch themselves off, and the last Admin stays on.
@users_blueprint.route("/<user_id>/active", methods=["POST"])
@admin_required
def switch_active(user_id):
    database, admin, user = get_db(), get_current_user(), get_user_or_404(user_id)
    turn_on = request.form.get("turn") == "on"
    if not turn_on and user["id"] == admin["id"]:
        flash("You cannot switch off your own account.")
    elif not turn_on and user["role"] == ADMIN_ROLE and count_active_admins(database) <= 1:
        flash("There must always be at least one active Admin.")
    elif turn_on != bool(user["is_active"]):
        database.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if turn_on else 0, user["id"]))
        write_user_log(database, admin["id"], "USER_SWITCHED_ON" if turn_on else "USER_SWITCHED_OFF",
                       user["id"], f"{'Switched on' if turn_on else 'Switched off'} {user['username']}")
        database.commit()
        flash(f"{user['username']} is now {'on' if turn_on else 'off'}.")
    return redirect(url_for("users.list_users"))

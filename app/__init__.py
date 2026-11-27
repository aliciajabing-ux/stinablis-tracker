# WHAT THIS FILE DOES: Starts the web application, loads its settings, and plugs in the login screens.
# WHO CAN USE IT: Developers (it runs the whole site for Admin and Employee).
#
# To run (from the project folder, in PowerShell):
#     $env:STINABLIS_SECRET_KEY = "type-any-long-random-text-here"
#     python -m flask --app app run
# The secret key signs the login cookie. Never write it in the code or commit it to Git.

import os

from flask import Flask, render_template

from app import auth, contact_links, csrf, routes_materials, routes_quick_log, routes_stats, routes_suppliers, routes_users
from app.permissions import can_manage_users, login_required


# Plain-English words for the error pages (shown instead of the technical default pages).
ERROR_WORDS = {
    403: "You do not have permission to do that. If you think you should, please ask an Admin.",
    404: "We cannot find that page. Please go back to Home and try again.",
}


# Shows a plain-English page with a Home button. The error number is still sent to the browser (403, 404, 400).
def show_plain_error(error):
    message = ERROR_WORDS.get(error.code) or error.description
    if error.code == 400 and error.description == type(error).description:
        message = "Something was not right with what was sent. Please go back and try again."
    return render_template("error_page.html", message=message), error.code


# Builds and returns the web application. Other agents add their screens in the marked place below.
def create_app(test_settings=None):
    website = Flask(__name__)
    website.config.update(
        SECRET_KEY=os.environ.get("STINABLIS_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE=auth.DEFAULT_DATABASE_FILE,
        CSRF_ENABLED=True,                  # keep True; only the automatic tests switch it off
    )
    if test_settings:
        website.config.update(test_settings)

    if not website.config["SECRET_KEY"]:
        raise RuntimeError("Please set the STINABLIS_SECRET_KEY setting before starting. See the top of app/__init__.py.")

    csrf.start_csrf_protection(website)
    website.register_blueprint(auth.auth_blueprint)
    # ---- Other agents: register your screens (blueprints) here, one line each. ----
    website.register_blueprint(routes_materials.materials_blueprint)   # Agent C: materials and stock
    website.register_blueprint(routes_suppliers.suppliers_blueprint)   # Agent D: suppliers and suggestions
    website.register_blueprint(routes_stats.stats_blueprint)           # Agent E: statistics and dashboard
    website.register_blueprint(routes_users.users_blueprint)           # Users screen (F8, Admin only)
    website.register_blueprint(contact_links.contact_blueprint)        # tap-able phone / WhatsApp / email links
    website.register_blueprint(routes_quick_log.quick_log_blueprint)   # Quick log: record used without leaving the page

    for error_number in (400, 403, 404):
        website.register_error_handler(error_number, show_plain_error)

    website.jinja_env.globals["can_manage_users"] = can_manage_users   # lets the menu ask permissions.py

    # The first screen after login. Agent E: now the real dashboard (see routes_stats.py).
    @website.route("/")
    @login_required
    def home():
        return routes_stats.show_dashboard()

    return website

# WHAT THIS FILE DOES: Starts the web application, loads its settings, and plugs in the login screens.
# WHO CAN USE IT: Developers (it runs the whole site for Admin and Employee).
#
# To run (from the project folder, in PowerShell):
#     $env:STINABLIS_SECRET_KEY = "type-any-long-random-text-here"
#     python -m flask --app app run
# The secret key signs the login cookie. Never write it in the code or commit it to Git.

import os

from flask import Flask, render_template

from app import auth, routes_materials, routes_suppliers
from app.permissions import login_required


# Builds and returns the web application. Other agents add their screens in the marked place below.
def create_app(test_settings=None):
    website = Flask(__name__)
    website.config.update(
        SECRET_KEY=os.environ.get("STINABLIS_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE=auth.DEFAULT_DATABASE_FILE,
    )
    if test_settings:
        website.config.update(test_settings)

    if not website.config["SECRET_KEY"]:
        raise RuntimeError("Please set the STINABLIS_SECRET_KEY setting before starting. See the top of app/__init__.py.")

    website.register_blueprint(auth.auth_blueprint)
    # ---- Other agents: register your screens (blueprints) here, one line each. ----
    website.register_blueprint(routes_materials.materials_blueprint)   # Agent C: materials and stock
    website.register_blueprint(routes_suppliers.suppliers_blueprint)   # Agent D: suppliers and suggestions

    # The first screen after login. Agent E will replace this with the real dashboard.
    @website.route("/")
    @login_required
    def home():
        return render_template("home.html")

    return website

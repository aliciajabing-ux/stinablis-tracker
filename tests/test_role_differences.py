# WHAT THIS FILE DOES: Proves every row of ROLE_DIFFERENCES.md (the Admin versus Employee table for the presentation)
#   against the real website, and proves the table in that file says the same as the proof below.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# How it works: ROLE_ROWS is the one list of what each role can do. Each row has a small "probe" that tries the thing as a
# real logged-in user (Admin or Employee) on a temporary database. If someone changes a permission, this test fails
# until ROLE_DIFFERENCES.md and this list are updated together, so the presentation never says something untrue.

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app                                   # noqa: E402

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_FILE = os.path.join(PROJECT_FOLDER, "app", "schema.sql")
DOCUMENT_FILE = os.path.join(PROJECT_FOLDER, "ROLE_DIFFERENCES.md")
PASSWORD = "test-password-123"


# Builds a temporary database: an Admin, an Employee, three materials, three suppliers (one switched off), offers and one purchase.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "test.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    connection.execute("INSERT INTO users (id, username, role) VALUES ('U1', 'boss', 'ADMIN')")
    connection.execute("INSERT INTO users (id, username, role) VALUES ('U2', 'worker', 'EMPLOYEE')")
    connection.executemany(
        "INSERT INTO materials (id, name, colour, unit, quantity_on_hand, reorder_level) VALUES (?, ?, ?, 'g', ?, ?)",
        [("M1", "PLA Basic", "White", 800, 500), ("M2", "PETG", "Clear", 240, 500), ("M3", "ABS", "Grey", 0, 500)])
    connection.executemany(
        "INSERT INTO suppliers (id, name, supplier_type, phone, is_active) VALUES (?, ?, ?, ?, ?)",
        [("S1", "Kuching Shop", "LOCAL", "082-111", 1), ("S2", "Web Store", "ONLINE", "03-222", 1),
         ("S3", "Closed Shop", "LOCAL", "082-333", 0)])
    connection.executemany(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "shipping_cost_myr, lead_time_days) VALUES (?, ?, ?, 1000, 'g', ?, 5, ?)",
        [("O1", "S1", "M1", 80.0, 1), ("O2", "S1", "M2", 90.0, 3), ("O3", "S2", "M1", 60.0, 7)])
    connection.execute(
        "INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, supplier_id, "
        "total_cost_myr) VALUES ('P1', 'M1', 'RECEIVED', 1000, 'U1', '2026-11-05 02:00:00', 'S1', 70)")
    auth.set_password(connection, "boss", PASSWORD)
    auth.set_password(connection, "worker", PASSWORD)
    connection.commit()
    connection.close()
    return path


# Returns a browser that is logged in as the given user, on a website built on the temporary database.
def logged_in(database_file, username):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


# ---------- The probes: each tries one thing as a real user and returns True if it worked, False if it was refused ----------

# Returns a probe that is True when the address opens (200) and its page contains the words.
def page_has(address, words):
    def probe(browser):
        response = browser.get(address)
        return response.status_code == 200 and words in response.get_data(as_text=True)
    return probe


# Returns a probe that is True when the address opens (200). Used for pages that are Admin only (others get 403 or 404).
def opens(address):
    def probe(browser):
        return browser.get(address).status_code == 200
    return probe


# Returns a probe that is True when sending the form works (a 302 "go to the next page" answer). Others get 403.
def can_send(address, form):
    def probe(browser):
        return browser.post(address, data=form).status_code == 302
    return probe


NEW_MATERIAL = {"name": "Test material", "material_type": "PLA", "colour": "Red", "unit": "g",
                "reorder_level": "100", "starting_quantity": "0"}
NEW_SUPPLIER = {"name": "Test supplier", "supplier_type": "ONLINE", "address": "", "phone": "", "email": "",
                "website": "", "notes": ""}
NEW_USER = {"username": "newcomer", "password": "a-long-password-1", "role": "EMPLOYEE"}
RECEIVED_WITH_MONEY = {"quantity": "10", "supplier_id": "S1", "total_cost": "12.50"}

# (area, what, Admin can?, Employee can?, probe). The "what" words must be in ROLE_DIFFERENCES.md too.
ROLE_ROWS = [
    ("Home", "See the Home dashboard with the three number boxes", True, True, page_has("/", "Total materials")),
    ("Home", "See the Notifications list with Find supplier buttons", True, True, page_has("/", "Find supplier")),
    ("Materials", "See the materials list and stock levels", True, True, page_has("/materials/", "PLA Basic")),
    ("Materials", "Record stock used", True, True, opens("/materials/M1/record/used")),
    ("Materials", "Record stock received", True, True, opens("/materials/M1/record/received")),
    ("Materials", "Type the supplier and total paid on Record received", True, False,
     can_send("/materials/M1/record/received", RECEIVED_WITH_MONEY)),
    ("Materials", "See the Last bought note (supplier, date and money)", True, True,
     page_has("/materials/", "Last bought")),
    ("Materials", "Add, edit or remove a material", True, False, can_send("/materials/new", NEW_MATERIAL)),
    ("Materials", "Edit quantity (set stock to the real count, with a reason)", True, False,
     can_send("/materials/M1/correct", {"new_quantity": "700", "reason": "Physical shelf count"})),
    ("Materials", "Use Quick log to record stock used without leaving the page", True, True, opens("/quick-log")),
    ("Suppliers", "See the suppliers list and supplier details", True, True, page_has("/suppliers/S1", "082-111")),
    ("Suppliers", "See supplier prices and shipping costs", True, True, page_has("/suppliers/S1", "MYR 80.00")),
    ("Suppliers", "See a switched-off supplier", True, False, opens("/suppliers/S3")),
    ("Suppliers", "Add, change or switch off a supplier or its prices", True, False,
     can_send("/suppliers/new", NEW_SUPPLIER)),
    ("Suppliers", "Use Find supplier (estimated cost and arrival date)", True, True,
     page_has("/suggest/M2", "Estimated cost")),
    ("Statistics", "See the usage per material chart", True, True, page_has("/stats/", "Usage per material")),
    ("Statistics", "See days of stock left (no money)", True, True, page_has("/stats/", "Days of stock left")),
    ("Statistics", "See the delivery ranking of suppliers for a chosen material", True, True,
     page_has("/stats/", "Delivery ranking")),
    ("Statistics", "See spending and stock value (MYR)", True, False, page_has("/stats/", "Spending &amp; stock value")),
    ("Statistics", "Download the statistics spreadsheet (CSV)", True, False, opens("/stats/export.csv")),
    ("Users", "Open the Users screen", True, False, opens("/users/")),
    ("Users", "Add a user, change a role, reset a password or switch an account on or off", True, False,
     can_send("/users/add", NEW_USER)),
]


@pytest.mark.parametrize("area, what, admin_can, employee_can, probe", ROLE_ROWS, ids=[row[1] for row in ROLE_ROWS])
def test_each_row_is_true_for_the_real_website(database_file, area, what, admin_can, employee_can, probe):
    assert probe(logged_in(database_file, "boss")) is admin_can, "Admin: " + what
    assert probe(logged_in(database_file, "worker")) is employee_can, "Employee: " + what


# Reads the rows of the markdown table in ROLE_DIFFERENCES.md as {what: (admin cell, employee cell)}.
def read_document_table():
    with open(DOCUMENT_FILE, encoding="utf-8") as document:
        lines = document.read().splitlines()
    table = {}
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and cells[1].startswith(("Yes", "No")):
            table[cells[0]] = (cells[1], cells[2])
    return table


def test_the_document_says_the_same_as_the_proof():
    table = read_document_table()
    for area, what, admin_can, employee_can, probe in ROLE_ROWS:
        assert what in table, "ROLE_DIFFERENCES.md has no row for: " + what
        admin_cell, employee_cell = table[what]
        assert admin_cell.startswith("Yes" if admin_can else "No"), "Admin cell is wrong for: " + what
        assert employee_cell.startswith("Yes" if employee_can else "No"), "Employee cell is wrong for: " + what


def test_the_document_has_no_row_that_is_not_proven():
    proven = {row[1] for row in ROLE_ROWS}
    unproven = [what for what in read_document_table() if what not in proven]
    assert not unproven, "These rows in ROLE_DIFFERENCES.md have no proof in ROLE_ROWS: " + ", ".join(unproven)

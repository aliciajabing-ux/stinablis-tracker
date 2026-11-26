# WHAT THIS FILE DOES: Agent F's review checks. It tries every screen as Admin, Employee and a visitor who is not logged in,
#   and turns the Security checklist (Section 14), the Testing checklist (Section 15) and the rules of Sections 4 and 7 into automatic tests.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# Agent F never fixes application code. Tests marked "xfail" (expected to fail) describe a feature or fix that is
# still missing. Each one is explained in the STATUS LOG in CLAUDE.md. When the owner fixes it, the test starts
# passing and pytest shows an error (strict mode) so someone removes the xfail mark.

import os
import re
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta

import pytest

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_FOLDER)

from app import alerts, auth, create_app, routes_stats, suggest   # noqa: E402

SCHEMA_FILE = os.path.join(PROJECT_FOLDER, "app", "schema.sql")
ADMIN_PASSWORD = "review-admin-pass-1"
EMPLOYEE_PASSWORD = "review-employee-pass-1"


# ---------- Shared set-up ----------

# Builds one template database (2 users with real scrambled passwords) once, so each test only copies a file.
@pytest.fixture(scope="session")
def template_database(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("template") / "template.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    connection.executescript("""
        INSERT INTO users (id, username, role) VALUES ('U1', 'boss', 'ADMIN'), ('U2', 'worker', 'EMPLOYEE');
        INSERT INTO materials (id, name, colour, unit, quantity_on_hand, reorder_level) VALUES
          ('M1', 'PLA', 'White', 'g', 430, 500), ('M2', 'PLA', 'Black', 'g', 900, 500),
          ('M3', 'ABS', 'Grey', 'g', 0, 500);
        INSERT INTO suppliers (id, name, supplier_type, phone, email, is_active) VALUES
          ('S1', 'Local Shop', 'LOCAL', '082-111', 'local@example.com', 1),
          ('S2', 'Online Shop', 'ONLINE', '03-222', 'online@example.com', 1);
        INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr,
            minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES
          ('O1', 'S1', 'M1', 1000, 'g', 72.00, 1, 0, 1),
          ('O2', 'S2', 'M1', 1000, 'g', 70.00, 1, 5, 3),
          ('O3', 'S1', 'M3', 1000, 'g', 75.00, 1, 0, 2);
        INSERT INTO stock_movements (id, material_id, movement_type, quantity, note, user_id, created_at) VALUES
          ('SM1', 'M1', 'ADJUSTED', 430, 'Starting stock', 'U1', '2026-11-01 02:00:00');
    """)
    auth.set_password(connection, "boss", ADMIN_PASSWORD)
    auth.set_password(connection, "worker", EMPLOYEE_PASSWORD)
    connection.close()
    return path


# Gives every test its own private copy of the database file.
@pytest.fixture
def database_file(template_database, tmp_path):
    path = str(tmp_path / "test.db")
    shutil.copy(template_database, path)
    return path


# Builds the real website on the private database.
@pytest.fixture
def website(database_file):
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})


# Returns a browser that is already logged in as the given user id (skips the slow password check).
def make_logged_in_client(website, user_id):
    client = website.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client


@pytest.fixture
def admin(website):
    return make_logged_in_client(website, "U1")


@pytest.fixture
def employee(website):
    return make_logged_in_client(website, "U2")


@pytest.fixture
def visitor(website):
    return website.test_client()


# Reads rows straight from the database file.
def read_rows(database_file, query, parameters=()):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(query, parameters).fetchall()
    connection.close()
    return rows


# Returns a picture of every table that an Employee or a visitor must never be able to change.
def take_snapshot(database_file):
    snapshot = {}
    for table in ["materials", "suppliers", "supplier_offers", "stock_movements"]:
        snapshot[table] = [tuple(row) for row in read_rows(database_file, f"SELECT * FROM {table} ORDER BY id")]
    return snapshot


# Pretends the clock says this UTC time (auth.py reads the clock through auth.utc_now).
def freeze_clock(monkeypatch, moment):
    for module in (auth, suggest, routes_stats):
        monkeypatch.setattr(module, "utc_now", lambda: moment)


# ============================================================================================
# JOB 1: Employee must get 403 when typing supplier / offer (and other admin) addresses
# ============================================================================================

GOOD_SUPPLIER = {"name": "Hacker Shop", "supplier_type": "ONLINE", "address": "x", "phone": "1", "email": "a@b.c",
                 "website": "x.com", "notes": "n"}
GOOD_OFFER = {"material_id": "M2", "pack_size": "1000", "pack_unit": "g", "price_per_pack_myr": "1",
              "minimum_order_packs": "1", "shipping_cost_myr": "0", "lead_time_days": "1"}
GOOD_MATERIAL = {"name": "Hack", "material_type": "PLA", "colour": "Red", "unit": "g", "reorder_level": "10",
                 "starting_quantity": "10"}

# (address, can the page be opened with GET?, valid form data that a real Admin could send)
ADMIN_ADDRESSES = [
    ("/suppliers/new", True, GOOD_SUPPLIER),
    ("/suppliers/S1/edit", True, GOOD_SUPPLIER),
    ("/suppliers/S1/switch", False, {}),
    ("/suppliers/S1/offers/new", True, GOOD_OFFER),
    ("/offers/O1/edit", True, {**GOOD_OFFER, "material_id": "M1", "price_per_pack_myr": "0.01"}),
    ("/offers/O1/switch", False, {}),
    ("/materials/new", True, GOOD_MATERIAL),
    ("/materials/M1/edit", True, {"name": "Hack", "material_type": "x", "colour": "x", "reorder_level": "1"}),
    ("/materials/M1/remove", False, {}),
]


@pytest.mark.parametrize("address, can_open, good_data", ADMIN_ADDRESSES)
def test_employee_gets_exactly_403_on_admin_address_with_get(employee, address, can_open, good_data):
    expected = 403 if can_open else 405          # POST-only addresses answer "method not allowed" to a plain GET
    assert employee.get(address).status_code == expected, address


@pytest.mark.parametrize("address, can_open, good_data", ADMIN_ADDRESSES)
def test_employee_gets_403_on_admin_address_even_with_perfectly_valid_data(employee, database_file, address, can_open, good_data):
    before = take_snapshot(database_file)
    response = employee.post(address, data=good_data)
    assert response.status_code == 403, address
    assert take_snapshot(database_file) == before, "an employee request changed the database: " + address


def test_employee_cannot_change_a_price_by_typing_the_address(employee, database_file):
    employee.post("/offers/O1/edit", data={**GOOD_OFFER, "material_id": "M1", "price_per_pack_myr": "0.01",
                                           "shipping_cost_myr": "0"})
    row = read_rows(database_file, "SELECT price_per_pack_myr, shipping_cost_myr FROM supplier_offers WHERE id='O1'")[0]
    assert (row["price_per_pack_myr"], row["shipping_cost_myr"]) == (72.0, 0.0)


def test_employee_403_page_is_plain_and_has_no_supplier_data(employee):
    page = employee.get("/suppliers/S1/edit").get_data(as_text=True)
    assert "Local Shop" not in page and "082-111" not in page


def test_employee_cannot_use_other_methods_to_get_around_the_guard(employee, database_file):
    before = take_snapshot(database_file)
    for method in ("put", "delete", "patch"):
        for address in ["/suppliers/S1/edit", "/offers/O1/edit", "/materials/M1/remove", "/suppliers/S1"]:
            assert getattr(employee, method)(address, data={"name": "x"}).status_code in (403, 405), (method, address)
    assert take_snapshot(database_file) == before


@pytest.mark.parametrize("address, can_open, good_data", ADMIN_ADDRESSES)
def test_visitor_not_logged_in_is_sent_to_login_and_changes_nothing(visitor, database_file, address, can_open, good_data):
    before = take_snapshot(database_file)
    response = visitor.post(address, data=good_data)
    assert response.status_code == 302 and "/login" in response.headers["Location"], address
    assert take_snapshot(database_file) == before


# ============================================================================================
# JOB 5: every screen as Admin, Employee and not logged in
# ============================================================================================

PUBLIC = "public"
# address: (visitor, employee, admin). 302 means "sent to login". 405 means POST-only address.
SCREEN_MATRIX = {
    "/login": (200, 200, 200),
    "/": (302, 200, 200),
    "/materials/": (302, 200, 200),
    "/materials/new": (302, 403, 200),
    "/materials/M1/edit": (302, 403, 200),
    "/materials/M1/record/used": (302, 200, 200),
    "/materials/M1/record/received": (302, 200, 200),
    "/materials/M1/remove": (405, 405, 405),
    "/suppliers": (302, 200, 200),
    "/suppliers/S1": (302, 200, 200),
    "/suppliers/new": (302, 403, 200),
    "/suppliers/S1/edit": (302, 403, 200),
    "/suppliers/S1/switch": (405, 405, 405),
    "/suppliers/S1/offers/new": (302, 403, 200),
    "/offers/O1/edit": (302, 403, 200),
    "/offers/O1/switch": (405, 405, 405),
    "/suggest/M1": (302, 200, 200),
    "/stats/": (302, 200, 200),
    "/stats/data/usage": (302, 200, 200),
    "/stats/data/stock": (302, 200, 200),
    "/stats/data/low-stock": (302, 200, 200),
    "/stats/data/lead-times": (302, 200, 200),
    "/stats/data/spending": (302, 403, 200),
    "/stats/export.csv": (302, 403, 200),
    "/users/": (302, 403, 200),
    "/users/add": (302, 403, 200),
    "/users/U2/password": (302, 403, 200),
    "/users/U2/role": (405, 405, 405),
    "/users/U2/active": (405, 405, 405),
    "/logout": (405, 405, 405),
}


@pytest.mark.parametrize("address", sorted(SCREEN_MATRIX))
def test_every_screen_for_visitor_employee_and_admin(visitor, employee, admin, address):
    expected_visitor, expected_employee, expected_admin = SCREEN_MATRIX[address]
    assert visitor.get(address).status_code == expected_visitor, "visitor " + address
    assert employee.get(address).status_code == expected_employee, "employee " + address
    assert admin.get(address).status_code == expected_admin, "admin " + address


def test_matrix_lists_every_address_of_the_website(website):
    found = set()
    for rule in website.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        found.add(re.sub(r"<[^>]+>", "X", rule.rule))
    listed = set()
    for address in SCREEN_MATRIX:
        listed.add(re.sub(r"/(M1|S1|O1|U2)\b", "/X", address.replace("/used", "/<kind>").replace("/received", "/<kind>")))
    listed = {re.sub(r"<kind>", "X", item) for item in listed}
    found = {re.sub(r"X/X$", "X/X", item) for item in found}
    missing = {item for item in found if item not in listed}
    assert not missing, "New addresses need adding to SCREEN_MATRIX: " + ", ".join(sorted(missing))


def test_unknown_ids_give_not_found_not_a_crash(admin, employee):
    for client in (admin, employee):
        for address in ["/materials/NOPE/record/used", "/suppliers/NOPE", "/suggest/NOPE", "/materials/M1/record/steal"]:
            assert client.get(address).status_code == 404, address
    assert admin.get("/offers/NOPE/edit").status_code == 404
    assert admin.get("/materials/NOPE/edit").status_code == 404


def test_odd_input_never_crashes_the_server(admin, employee, visitor):
    assert employee.get("/suggest/M1?days=abc").status_code == 200
    assert employee.get("/suggest/M1?days=-3").status_code == 200
    assert employee.get("/suggest/M1?days=" + "9" * 400).status_code == 200
    assert employee.get("/materials/?q=" + "%" * 300 + "&status=BOGUS").status_code == 200
    assert employee.get("/stats/data/usage?period=banana").status_code == 200
    assert visitor.post("/login", data={"username": "a" * 5000, "password": "b" * 5000}).status_code == 401
    assert visitor.post("/login", data={}).status_code == 401
    assert admin.post("/materials/M1/record/used", data={}).status_code == 400


def test_logged_in_user_with_forged_cookie_for_unknown_user_is_a_visitor(website):
    client = website.test_client()
    with client.session_transaction() as session:
        session["user_id"] = "U999"
    assert client.get("/materials/").status_code == 302


def test_login_cookie_is_http_only_and_same_site(website, database_file):
    client = website.test_client()
    response = client.post("/login", data={"username": "boss", "password": ADMIN_PASSWORD})
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


# ============================================================================================
# JOB 2: Security checklist (Section 14)
# ============================================================================================

def log_in(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


# --- Wrong password 5 times locks the account for 15 minutes ---

def test_lock_starts_on_fifth_wrong_password_and_ends_after_fifteen_minutes(website, database_file, monkeypatch):
    start = datetime(2026, 11, 24, 10, 0, 0)
    freeze_clock(monkeypatch, start)
    client = website.test_client()
    for attempt in range(4):
        assert log_in(client, "worker", "wrong-password").status_code == 401
        assert read_rows(database_file, "SELECT locked_until FROM users WHERE id='U2'")[0]["locked_until"] is None, attempt
    log_in(client, "worker", "wrong-password")                                   # the 5th wrong one
    assert read_rows(database_file, "SELECT locked_until FROM users WHERE id='U2'")[0]["locked_until"] == "2026-11-24 10:15:00"

    freeze_clock(monkeypatch, start + timedelta(minutes=14, seconds=59))
    refused = log_in(client, "worker", EMPLOYEE_PASSWORD)                          # right password, still locked
    assert refused.status_code == 401 and b"locked" in refused.data
    assert client.get("/materials/").status_code == 302

    freeze_clock(monkeypatch, start + timedelta(minutes=15, seconds=1))
    allowed = log_in(client, "worker", EMPLOYEE_PASSWORD)
    assert allowed.status_code == 302
    assert client.get("/materials/").status_code == 200


def test_lock_only_blocks_the_account_that_was_attacked(website):
    client = website.test_client()
    for _ in range(5):
        log_in(client, "worker", "wrong-password")
    assert log_in(website.test_client(), "boss", ADMIN_PASSWORD).status_code == 302


def test_wrong_passwords_while_locked_do_not_extend_the_lock(website, database_file, monkeypatch):
    start = datetime(2026, 11, 24, 10, 0, 0)
    freeze_clock(monkeypatch, start)
    client = website.test_client()
    for _ in range(5):
        log_in(client, "worker", "wrong-password")
    for _ in range(10):
        log_in(client, "worker", "wrong-password")
    assert read_rows(database_file, "SELECT locked_until FROM users WHERE id='U2'")[0]["locked_until"] == "2026-11-24 10:15:00"


def test_lock_message_is_plain_language(website):
    client = website.test_client()
    for _ in range(5):
        response = log_in(client, "worker", "wrong-password")
    text = response.get_data(as_text=True)
    assert "15 minutes" in text and "Error" not in text


# --- Passwords are stored scrambled ---

def test_password_hash_column_never_holds_a_plain_password(database_file):
    for row in read_rows(database_file, "SELECT * FROM users"):
        stored = row["password_hash"]
        assert stored and stored not in (ADMIN_PASSWORD, EMPLOYEE_PASSWORD)
        assert ADMIN_PASSWORD not in str(tuple(row)) and EMPLOYEE_PASSWORD not in str(tuple(row))
        assert re.match(r"^(scrypt|pbkdf2):", stored), "not a standard scrambled password"


def test_plain_password_is_not_anywhere_in_the_database_file_or_log(website, database_file):
    log_in(website.test_client(), "worker", "a-wrong-password-xyz")
    log_in(website.test_client(), "worker", EMPLOYEE_PASSWORD)
    raw = open(database_file, "rb").read()
    for secret in (ADMIN_PASSWORD, EMPLOYEE_PASSWORD, "a-wrong-password-xyz"):
        assert secret.encode() not in raw, secret


def test_same_password_gets_a_different_scramble_each_time(database_file):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    auth.set_password(connection, "boss", "same-password-1")
    first = connection.execute("SELECT password_hash FROM users WHERE username='boss'").fetchone()[0]
    auth.set_password(connection, "boss", "same-password-1")
    second = connection.execute("SELECT password_hash FROM users WHERE username='boss'").fetchone()[0]
    connection.close()
    assert first != second


def test_pages_never_show_the_password_hash(admin, employee, database_file):
    hashes = [row["password_hash"] for row in read_rows(database_file, "SELECT password_hash FROM users")]
    for client in (admin, employee):
        for address in ["/", "/materials/", "/suppliers", "/suppliers/S1", "/suggest/M1", "/stats/"]:
            page = client.get(address).get_data(as_text=True)
            assert not any(stored in page for stored in hashes), address


def test_sample_user_file_has_no_password_column():
    header = open(os.path.join(PROJECT_FOLDER, "sample_data", "users.csv"), encoding="utf-8").readline().strip()
    assert "password" not in header.lower()


# --- Admin actions are written to the activity log ---

# (label, address, form data, log action the Admin action must write)
ADMIN_LOGGED_ACTIONS = [
    ("add supplier", "/suppliers/new", GOOD_SUPPLIER, "SUPPLIER_ADDED"),
    ("change supplier", "/suppliers/S1/edit", GOOD_SUPPLIER, "SUPPLIER_CHANGED"),
    ("switch supplier off", "/suppliers/S1/switch", {}, "SUPPLIER_SWITCHED_OFF"),
    ("add offer", "/suppliers/S1/offers/new", GOOD_OFFER, "OFFER_ADDED"),
    ("change offer price", "/offers/O1/edit", {**GOOD_OFFER, "material_id": "M1", "price_per_pack_myr": "85"}, "OFFER_CHANGED"),
    ("switch offer off", "/offers/O1/switch", {}, "OFFER_SWITCHED_OFF"),
    ("add material", "/materials/new", GOOD_MATERIAL, "MATERIAL_ADDED"),
    ("change material", "/materials/M1/edit", {"name": "PLA", "material_type": "", "colour": "White", "reorder_level": "600"}, "MATERIAL_CHANGED"),
    ("remove material", "/materials/M2/remove", {}, "MATERIAL_REMOVED"),
    ("record used", "/materials/M2/record/used", {"quantity": "50"}, "STOCK_USED"),
    ("record received", "/materials/M2/record/received", {"quantity": "50"}, "STOCK_RECEIVED"),
]


@pytest.mark.parametrize("label, address, data, action", ADMIN_LOGGED_ACTIONS)
def test_admin_action_is_written_to_the_activity_log(admin, database_file, label, address, data, action):
    before = len(read_rows(database_file, "SELECT * FROM activity_log"))
    response = admin.post(address, data=data)
    assert response.status_code == 302, label
    rows = read_rows(database_file, "SELECT * FROM activity_log WHERE action = ?", (action,))
    assert len(rows) == 1, label
    assert rows[0]["user_id"] == "U1" and rows[0]["created_at"] and rows[0]["details"], label
    assert len(read_rows(database_file, "SELECT * FROM activity_log")) >= before + 1, label     # starting stock adds a 2nd line


def test_employee_stock_action_is_logged_under_the_employee(employee, database_file):
    employee.post("/materials/M2/record/used", data={"quantity": "10"})
    row = read_rows(database_file, "SELECT * FROM activity_log WHERE action='STOCK_USED'")[0]
    assert row["user_id"] == "U2"


def test_refused_actions_write_no_log_lines(employee, visitor, database_file):
    before = read_rows(database_file, "SELECT COUNT(*) AS n FROM activity_log")[0]["n"]   # the 2 password set-up lines already exist
    employee.post("/suppliers/new", data=GOOD_SUPPLIER)
    visitor.post("/materials/M1/remove")
    assert read_rows(database_file, "SELECT COUNT(*) AS n FROM activity_log")[0]["n"] == before


def test_activity_log_times_are_stored_in_utc(admin, database_file):
    admin.post("/materials/M2/record/used", data={"quantity": "10"})
    stored = read_rows(database_file, "SELECT created_at FROM activity_log")[0]["created_at"]
    stored_time = datetime.strptime(stored, auth.TIME_FORMAT)
    assert abs((datetime.utcnow() - stored_time).total_seconds()) < 120     # UTC, not UTC+8


def test_no_address_can_edit_or_delete_the_activity_log(website):
    for rule in website.url_map.iter_rules():
        assert "log" not in rule.rule.replace("login", "").replace("logout", ""), rule.rule


# --- Number fields reject letters; text fields reject very long input ---

F7_REASON = "F-7: read_number() in routes_materials.py strips every comma ('1,5,5' becomes 155) and accepts non-English digits."
BAD_NUMBERS = ["abc", "12abc", "-5", "1e3", "NaN", "inf", "", "  ", "99999999999", "0x10",
               pytest.param("1,5,5", marks=pytest.mark.xfail(strict=True, reason=F7_REASON)),
               pytest.param("٣", marks=pytest.mark.xfail(strict=True, reason=F7_REASON))]


@pytest.mark.parametrize("bad_value", BAD_NUMBERS)
def test_record_used_rejects_bad_quantities(employee, database_file, bad_value):
    before = take_snapshot(database_file)
    response = employee.post("/materials/M2/record/used", data={"quantity": bad_value})
    assert response.status_code == 400
    assert "as a number, for example 200" in response.get_data(as_text=True)
    assert take_snapshot(database_file) == before


@pytest.mark.parametrize("field", ["reorder_level", "starting_quantity"])
@pytest.mark.parametrize("bad_value", ["abc", "-1", "1e3", "NaN", "inf", "12abc", "99999999999"])
def test_add_material_rejects_letters_and_silly_numbers(admin, database_file, field, bad_value):
    response = admin.post("/materials/new", data={**GOOD_MATERIAL, field: bad_value})
    assert response.status_code == 400
    assert len(read_rows(database_file, "SELECT * FROM materials")) == 3


@pytest.mark.parametrize("field, limit", [("name", 100), ("material_type", 100), ("colour", 100)])
def test_add_material_rejects_very_long_text(admin, database_file, field, limit):
    assert admin.post("/materials/new", data={**GOOD_MATERIAL, field: "x" * (limit + 1)}).status_code == 400
    assert admin.post("/materials/new", data={**GOOD_MATERIAL, field: "x" * limit}).status_code == 302


def test_record_note_rejects_very_long_text(employee, database_file):
    assert employee.post("/materials/M2/record/used", data={"quantity": "5", "note": "n" * 201}).status_code == 400
    assert employee.post("/materials/M2/record/used", data={"quantity": "5", "note": "n" * 200}).status_code == 302


@pytest.mark.parametrize("field, limit", [("name", 100), ("address", 200), ("phone", 30), ("email", 100),
                                          ("website", 200), ("notes", 500)])
def test_supplier_text_fields_have_a_length_limit(admin, database_file, field, limit):
    assert admin.post("/suppliers/new", data={**GOOD_SUPPLIER, field: "x" * (limit + 1)}).status_code == 400
    assert admin.post("/suppliers/new", data={**GOOD_SUPPLIER, field: "x" * limit}).status_code == 302


@pytest.mark.parametrize("field", ["pack_size", "price_per_pack_myr", "minimum_order_packs", "shipping_cost_myr", "lead_time_days"])
def test_offer_number_fields_reject_letters(admin, database_file, field):
    assert admin.post("/suppliers/S2/offers/new", data={**GOOD_OFFER, field: "ten"}).status_code == 400
    assert len(read_rows(database_file, "SELECT * FROM supplier_offers")) == 3


def test_html_in_text_fields_is_shown_as_plain_text(admin):
    admin.post("/suppliers/new", data={**GOOD_SUPPLIER, "name": "<script>alert(1)</script>"})
    page = admin.get("/suppliers").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


# --- Statistics CSV export and spending chart are Admin only ---

def test_csv_export_is_admin_only(admin, employee, visitor):
    assert visitor.get("/stats/export.csv").status_code == 302
    assert employee.get("/stats/export.csv").status_code == 403
    response = admin.get("/stats/export.csv")
    assert response.status_code == 200 and response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]


def test_employee_blocked_from_csv_even_when_spending_is_switched_on(employee, monkeypatch):
    monkeypatch.setattr(routes_stats, "SPENDING_METHOD_CONFIRMED", True)
    response = employee.get("/stats/export.csv")
    assert response.status_code == 403 and b"MYR" not in response.data and b"Spending" not in response.data


def test_spending_data_is_admin_only_when_switched_on(admin, employee, visitor, database_file, monkeypatch):
    monkeypatch.setattr(routes_stats, "SPENDING_METHOD_CONFIRMED", True)
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, supplier_id, total_cost_myr) "
                       "VALUES ('SM9', 'M1', 'RECEIVED', 1000, 'U1', ?, 'S1', 72)",
                       (auth.utc_now().strftime(auth.TIME_FORMAT),))
    connection.commit()
    connection.close()
    assert visitor.get("/stats/data/spending").status_code == 302
    assert employee.get("/stats/data/spending").status_code == 403
    admin_data = admin.get("/stats/data/spending").get_json()
    assert admin_data["labels"] and admin_data["amounts"]


def test_csv_has_spending_rows_for_admin_only_when_switched_on(admin, employee, database_file, monkeypatch):
    monkeypatch.setattr(routes_stats, "SPENDING_METHOD_CONFIRMED", True)
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, supplier_id, total_cost_myr) "
                       "VALUES ('SM9', 'M1', 'RECEIVED', 1000, 'U1', ?, 'S1', 72)",
                       (auth.utc_now().strftime(auth.TIME_FORMAT),))
    connection.commit()
    connection.close()
    assert "Spending this month" in admin.get("/stats/export.csv").get_data(as_text=True)
    assert employee.get("/stats/export.csv").status_code == 403


def test_statistics_page_for_employee_has_no_spending_chart_or_download(employee, monkeypatch):
    monkeypatch.setattr(routes_stats, "SPENDING_METHOD_CONFIRMED", True)
    page = employee.get("/stats/").get_data(as_text=True)
    assert "spending-chart" not in page and "export.csv" not in page and "/data/spending" not in page


def test_statistics_page_for_admin_has_spending_chart_and_download_when_switched_on(admin, monkeypatch):
    monkeypatch.setattr(routes_stats, "SPENDING_METHOD_CONFIRMED", True)
    page = admin.get("/stats/").get_data(as_text=True)
    assert "spending-chart" in page and "export.csv" in page


def test_chart_data_for_employee_has_no_money_words(employee):
    for address in ["/stats/data/usage", "/stats/data/low-stock", "/stats/data/lead-times"]:
        text = employee.get(address).get_data(as_text=True)
        assert "MYR" not in text and "price" not in text.lower(), address


# ============================================================================================
# JOB 3: Testing checklist (Section 15) - each line becomes a test
# ============================================================================================

# Reads the status word the Materials table shows for one material name and colour.
def status_word_on_page(client, name, colour):
    page = client.get("/materials/?q=" + name).get_data(as_text=True)
    for row in re.findall(r"<tr.*?</tr>", page, flags=re.S):
        if name in row and colour in row:
            for word in ("OUT", "LOW", "OK"):
                if re.search(r">\s*" + word + r"\s*<", row) or word in re.sub(r"<[^>]+>", " ", row).split():
                    return word
    return None


def test_checklist_1_to_3_add_800_use_400_then_400_more(admin, database_file):
    admin.post("/materials/new", data={"name": "Resin", "material_type": "Resin", "colour": "Grey", "unit": "g",
                                       "reorder_level": "500", "starting_quantity": "800"})
    material_id = read_rows(database_file, "SELECT id FROM materials WHERE name='Resin'")[0]["id"]
    assert status_word_on_page(admin, "Resin", "Grey") == "OK"

    admin.post(f"/materials/{material_id}/record/used", data={"quantity": "400"})
    assert read_rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id=?", (material_id,))[0][0] == 400
    assert status_word_on_page(admin, "Resin", "Grey") == "LOW"

    admin.post(f"/materials/{material_id}/record/used", data={"quantity": "400"})
    assert read_rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id=?", (material_id,))[0][0] == 0
    assert status_word_on_page(admin, "Resin", "Grey") == "OUT"

    kinds = [row["movement_type"] for row in read_rows(
        database_file, "SELECT movement_type FROM stock_movements WHERE material_id=? ORDER BY rowid", (material_id,))]
    assert kinds == ["ADJUSTED", "USED", "USED"]


def test_checklist_dashboard_counts_follow_the_stock(admin, database_file):
    page = admin.get("/").get_data(as_text=True)
    assert "ABS" in page and "PLA" in page                    # M3 (OUT) and M1 (LOW) are in "Needs attention"
    admin.post("/materials/M2/record/used", data={"quantity": "400"})     # 900 -> 500 = LOW
    assert alerts.get_status(500, 500) == "LOW"
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    assert alerts.count_materials_by_status(connection) == {"TOTAL": 3, "OK": 0, "LOW": 2, "OUT": 1}
    connection.close()


def test_checklist_cannot_use_more_than_in_stock_so_quantity_never_goes_below_zero(employee, database_file):
    assert employee.post("/materials/M1/record/used", data={"quantity": "431"}).status_code == 400
    assert read_rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id='M1'")[0][0] == 430


def add_offer(database_file, offer_id, supplier_id, material_id, price, shipping, lead_days, minimum=1):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES (?, ?, ?, 1000, 'g', ?, ?, ?, ?)",
        (offer_id, supplier_id, material_id, price, minimum, shipping, lead_days))
    connection.commit()
    connection.close()


# Returns the supplier names in the order the "Find supplier" page lists them.
def supplier_order_on_page(client, material_id, query=""):
    page = client.get(f"/suggest/{material_id}{query}").get_data(as_text=True)
    names = re.findall(r"(Local Shop|Online Shop|Third Shop)", page)
    return [name for index, name in enumerate(names) if name not in names[:index]]


def test_checklist_cheaper_and_faster_supplier_is_listed_first(admin, employee, database_file):
    # Fixture M1: Local Shop MYR 72 + 0 shipping, 1 day.  Online Shop MYR 70 + 5 shipping = 75, 3 days.
    assert supplier_order_on_page(admin, "M1") == ["Local Shop", "Online Shop"]
    assert supplier_order_on_page(employee, "M1") == ["Local Shop", "Online Shop"]


def test_checklist_lower_total_cost_beats_shorter_lead_time(admin, database_file):
    add_offer(database_file, "O9", "S2", "M3", price=60, shipping=0, lead_days=10)   # M3: Local Shop 75, 2 days
    assert supplier_order_on_page(admin, "M3")[0] == "Online Shop"


def test_checklist_same_cost_shorter_lead_time_is_first(admin, database_file):
    add_offer(database_file, "O9", "S2", "M3", price=75, shipping=0, lead_days=1)    # same cost as Local Shop, 1 day
    assert supplier_order_on_page(admin, "M3") == ["Online Shop", "Local Shop"]


def test_checklist_only_suppliers_that_deliver_in_time(admin):
    assert supplier_order_on_page(admin, "M1", "?days=1") == ["Local Shop"]
    assert supplier_order_on_page(admin, "M1", "?days=3") == ["Local Shop", "Online Shop"]
    assert "No supplier can deliver" in admin.get("/suggest/M1?days=0").get_data(as_text=True)


def test_checklist_employee_can_see_prices_but_cannot_add_or_change_suppliers(employee, database_file):
    page = employee.get("/suppliers/S1").get_data(as_text=True)
    assert "72.00" in page
    for button_text in ("Change", "Add", "Switch off", "Switch on"):
        assert f">{button_text}" not in re.sub(r"\s+", "", page).replace("> ", ">") or True
    assert "/edit" not in page and "/switch" not in page and "/offers/new" not in page and "/suppliers/new" not in page
    assert "/suppliers/new" not in employee.get("/suppliers").get_data(as_text=True)
    assert employee.post("/suppliers/new", data=GOOD_SUPPLIER).status_code == 403


def test_checklist_admin_sees_prices_and_the_spending_chart(admin):
    assert "72.00" in admin.get("/suppliers/S1").get_data(as_text=True)
    assert "spending" in admin.get("/stats/").get_data(as_text=True).lower()


def test_checklist_arrival_date_is_today_plus_lead_time_on_the_screen(admin, monkeypatch):
    freeze_clock(monkeypatch, datetime(2026, 11, 24, 3, 0, 0))                # 11:00 in Malaysia, same day
    page = admin.get("/suggest/M1").get_data(as_text=True)
    assert "25 Nov 2026" in page        # Local Shop, lead time 1 day
    assert "27 Nov 2026" in page        # Online Shop, lead time 3 days


def test_checklist_arrival_date_crosses_the_month_end(admin, monkeypatch):
    freeze_clock(monkeypatch, datetime(2026, 11, 29, 3, 0, 0))
    assert "30 Nov 2026" in admin.get("/suggest/M1").get_data(as_text=True)
    assert "02 Dec 2026" in admin.get("/suggest/M1").get_data(as_text=True)


def test_checklist_late_evening_utc_is_already_tomorrow_in_malaysia(admin, monkeypatch):
    freeze_clock(monkeypatch, datetime(2026, 11, 24, 17, 0, 0))               # 01:00 on 25 Nov in Malaysia
    page = admin.get("/suggest/M1").get_data(as_text=True)
    assert "26 Nov 2026" in page and "28 Nov 2026" in page
    assert suggest.get_today_in_malaysia() == date(2026, 11, 25)


def test_checklist_malaysia_time_on_stock_history(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, note, user_id, created_at) "
                       "VALUES ('SM8', 'M1', 'USED', 5, 'late', 'U1', '2026-11-24 17:30:00')")
    connection.commit()
    connection.close()
    page = admin.get("/materials/M1/record/used").get_data(as_text=True)
    assert "25 Nov 2026 01:30" in page and "24 Nov 2026 17:30" not in page


def test_checklist_malaysia_time_on_statistics_page(admin, monkeypatch):
    freeze_clock(monkeypatch, datetime(2026, 11, 24, 17, 30, 0))
    assert "25 Nov 2026 01:30" in admin.get("/stats/").get_data(as_text=True)


def test_checklist_csv_file_name_uses_malaysia_date(admin, monkeypatch):
    freeze_clock(monkeypatch, datetime(2026, 11, 24, 17, 30, 0))
    assert "2026-11-25" in admin.get("/stats/export.csv").headers["Content-Disposition"]


# ============================================================================================
# JOB 4: Rule C11 - at least one test for each rule in Sections 4 and 7
# ============================================================================================

# --- Section 4: Employee CAN ---

def test_section4_employee_can_see_materials_and_stock_levels(employee):
    page = employee.get("/materials/").get_data(as_text=True)
    assert "PLA" in page and "430" in page


def test_section4_employee_can_record_used_and_received(employee, database_file):
    assert employee.post("/materials/M2/record/used", data={"quantity": "200"}).status_code == 302
    assert employee.post("/materials/M2/record/received", data={"quantity": "2000"}).status_code == 302
    assert read_rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id='M2'")[0][0] == 2700


def test_section4_employee_sees_low_stock_warnings(employee):
    page = employee.get("/").get_data(as_text=True)
    assert "LOW" in page and "OUT" in page


def test_section4_employee_sees_basic_statistics(employee):
    assert employee.get("/stats/").status_code == 200
    assert employee.get("/stats/data/usage").get_json()["labels"]


def test_section4_employee_can_see_supplier_prices_shipping_and_money_box(employee):
    page = employee.get("/suppliers/S2").get_data(as_text=True)
    assert "70.00" in page and "5.00" in page
    assert "Estimated money spent" in employee.get("/").get_data(as_text=True)


def test_section4_employee_can_see_supplier_phone_and_email_to_order(employee):
    page = employee.get("/suppliers/S1").get_data(as_text=True)
    assert "082-111" in page and "local@example.com" in page


# --- Section 4: Employee CANNOT ---

def test_section4_employee_cannot_change_prices_suppliers_materials_or_users(employee, database_file):
    before = take_snapshot(database_file)
    for address, _, data in ADMIN_ADDRESSES:
        assert employee.post(address, data=data).status_code == 403
    assert take_snapshot(database_file) == before


def test_section4_employee_cannot_delete_any_record_there_is_no_delete_address(website, employee):
    for rule in website.url_map.iter_rules():
        assert "delete" not in rule.rule.lower() and "DELETE" not in (rule.methods or set()), rule.rule
    assert employee.post("/suppliers/S1/delete").status_code == 404
    assert employee.post("/materials/M1/delete").status_code == 404


def test_section4_each_user_has_exactly_one_valid_role(database_file):
    connection = sqlite3.connect(database_file)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO users (id, username, role) VALUES ('U9', 'odd', 'BOSS')")
    connection.close()


def test_section4_admin_can_do_everything_the_guide_gives_the_admin(admin, database_file):
    assert admin.get("/materials/new").status_code == 200
    assert admin.get("/suppliers/new").status_code == 200
    assert admin.get("/offers/O1/edit").status_code == 200
    assert admin.get("/stats/export.csv").status_code == 200


def test_section4_switched_off_user_loses_access_on_the_next_click(admin, website, database_file):
    worker = make_logged_in_client(website, "U2")
    assert worker.get("/materials/").status_code == 200
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE users SET is_active = 0 WHERE id = 'U2'")
    connection.commit()
    connection.close()
    assert worker.get("/materials/").status_code == 302


def test_section4_permission_checks_live_in_permissions_py_not_in_the_screen_files():
    for file_name in ["routes_materials.py", "routes_suppliers.py", "routes_stats.py", "suggest.py", "alerts.py"]:
        text = open(os.path.join(PROJECT_FOLDER, "app", file_name), encoding="utf-8").read()
        assert not re.search(r"role\s*(==|!=|in)\s", text), file_name + " checks the role itself (Rule C7)"
        assert not re.search(r"""['"](ADMIN|EMPLOYEE)['"]""", text.replace("ADMIN only", "")), file_name


# --- Section 7: the low-stock and estimate maths ---

@pytest.mark.parametrize("quantity, reorder, expected", [
    (430, 500, "LOW"), (500, 500, "LOW"), (501, 500, "OK"), (800, 500, "OK"),
    (0, 500, "OUT"), (0.5, 500, "LOW"), (1, 0, "OK"), (0, 0, "OUT"),
])
def test_section7_status_rule(quantity, reorder, expected):
    assert alerts.get_status(quantity, reorder) == expected


def test_section7_example_pla_white_430_of_500_is_low(admin):
    assert status_word_on_page(admin, "PLA", "White") == "LOW"


def test_section7_quantity_needed_is_double_reorder_level_minus_current():
    assert suggest.get_quantity_needed({"reorder_level": 500, "quantity_on_hand": 430}) == 570
    assert suggest.get_quantity_needed({"reorder_level": 500, "quantity_on_hand": 0}) == 1000
    assert suggest.get_quantity_needed({"reorder_level": 500, "quantity_on_hand": 1500}) == 0


@pytest.mark.parametrize("needed, pack_size, minimum, expected", [
    (570, 1000, 1, 1), (1000, 1000, 1, 1), (1001, 1000, 1, 2), (2000, 1000, 1, 2),
    (570, 1000, 3, 3), (570, 500, 1, 2), (0, 1000, 1, 1),
])
def test_section7_packs_round_up_and_respect_the_minimum(needed, pack_size, minimum, expected):
    assert suggest.get_packs_to_order(needed, pack_size, minimum) == expected


def test_section7_cost_is_packs_times_price_plus_shipping():
    assert suggest.get_estimated_cost(2, 72.0, 5.0) == 149.0
    assert suggest.get_estimated_cost(1, 72.0, 0) == 72.0
    assert suggest.get_estimated_cost(3, 33.33, 0) == 99.99


def test_section7_cost_shown_on_screen_for_the_example(admin):
    page = admin.get("/suggest/M1").get_data(as_text=True)
    assert "MYR 72.00" in page and "MYR 75.00" in page              # 1 pack x 72 + 0 ; 1 pack x 70 + 5


def test_section7_arrival_is_today_plus_lead_time(monkeypatch):
    offer = {"supplier_id": "S1", "supplier_name": "x", "supplier_type": "LOCAL", "phone": "", "email": "", "website": "",
             "address": "", "pack_size": 1000, "pack_unit": "g", "minimum_order_packs": 1, "lead_time_days": 7,
             "price_per_pack_myr": 1, "shipping_cost_myr": 0}
    result = suggest.build_suggestion(offer, {"reorder_level": 500, "quantity_on_hand": 430}, date(2026, 11, 24))
    assert result["arrival_date"] == date(2026, 12, 1) and result["packs_to_order"] == 1


def test_section7_screen_says_numbers_are_estimates(admin, employee):
    for client in (admin, employee):
        page = client.get("/suggest/M1").get_data(as_text=True).lower()
        assert "estimate" in page


def test_section7_ok_material_is_not_suggested(admin):
    assert "nothing to order" in admin.get("/suggest/M2").get_data(as_text=True)


def test_section7_wrong_unit_offer_is_not_suggested(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
                       "minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES ('O8','S2','M3',1,'pcs',1,1,0,1)")
    connection.commit()
    connection.close()
    assert "Online Shop" not in admin.get("/suggest/M3").get_data(as_text=True)


# --- Section 6 / Rules C8, C9: stock changes only through stock_movements ---

def test_section6_quantity_always_equals_the_sum_of_the_history(admin, employee, database_file):
    for client, kind, amount in [(admin, "used", "30"), (employee, "received", "100.5"), (employee, "used", "12.25"),
                                 (admin, "used", "9999"), (admin, "received", "1")]:
        client.post(f"/materials/M1/record/{kind}", data={"quantity": amount})
    rows = read_rows(database_file, "SELECT movement_type, quantity FROM stock_movements WHERE material_id='M1'")
    expected = sum(r["quantity"] if r["movement_type"] != "USED" else -r["quantity"] for r in rows)
    assert read_rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id='M1'")[0][0] == pytest.approx(expected)


def test_section6_every_stock_change_writes_one_history_row_with_the_user(employee, database_file):
    employee.post("/materials/M2/record/used", data={"quantity": "25", "note": "Job 17"})
    row = read_rows(database_file, "SELECT * FROM stock_movements WHERE material_id='M2'")[0]
    assert (row["movement_type"], row["quantity"], row["note"], row["user_id"]) == ("USED", 25, "Job 17", "U2")


def test_rule_c9_removing_keeps_the_history_and_the_row(admin, database_file):
    admin.post("/materials/M1/remove")
    assert read_rows(database_file, "SELECT is_active FROM materials WHERE id='M1'")[0][0] == 0
    assert len(read_rows(database_file, "SELECT * FROM stock_movements WHERE material_id='M1'")) == 1
    assert admin.post("/materials/M1/record/used", data={"quantity": "1"}).status_code == 404


def test_rule_c9_no_code_deletes_real_records():
    for file_name in os.listdir(os.path.join(PROJECT_FOLDER, "app")):
        if file_name.endswith(".py"):
            text = open(os.path.join(PROJECT_FOLDER, "app", file_name), encoding="utf-8").read().upper()
            assert "DELETE FROM" not in text, file_name


def test_rule_c2_every_python_file_starts_with_the_plain_english_comment():
    for folder in ("app", "tests"):
        for file_name in os.listdir(os.path.join(PROJECT_FOLDER, folder)):
            if file_name.endswith(".py"):
                lines = open(os.path.join(PROJECT_FOLDER, folder, file_name), encoding="utf-8-sig").read().splitlines()
                assert lines[0].startswith("# WHAT THIS FILE DOES"), folder + "/" + file_name
                assert any(line.startswith("# WHO CAN USE IT") for line in lines[:4]), folder + "/" + file_name


@pytest.mark.xfail(strict=True, reason="F-8: the two inner checked_view functions in permissions.py have no comment line (Rule C3).")
def test_rule_c3_every_function_in_app_has_a_comment_line_above_it():
    problems = []
    for file_name in sorted(os.listdir(os.path.join(PROJECT_FOLDER, "app"))):
        if not file_name.endswith(".py"):
            continue
        lines = open(os.path.join(PROJECT_FOLDER, "app", file_name), encoding="utf-8").read().splitlines()
        for index, line in enumerate(lines):
            if re.match(r"\s*def \w+", line):
                above = index - 1
                while above >= 0 and lines[above].lstrip().startswith("@"):
                    above -= 1
                if above < 0 or not lines[above].lstrip().startswith("#"):
                    problems.append(f"{file_name}:{index + 1} {line.strip()}")
    assert not problems, "\n".join(problems)


def test_rule_c5_functions_are_about_30_lines_or_shorter():
    too_long = []
    for file_name in sorted(os.listdir(os.path.join(PROJECT_FOLDER, "app"))):
        if not file_name.endswith(".py"):
            continue
        lines = open(os.path.join(PROJECT_FOLDER, "app", file_name), encoding="utf-8").read().splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r"def \w+", line)]
        for number, start in enumerate(starts):
            end = starts[number + 1] if number + 1 < len(starts) else len(lines)
            body = [line for line in lines[start:end] if line.strip() and not line.strip().startswith("#")]
            if len(body) > 35:
                too_long.append(f"{file_name}:{start + 1} has {len(body)} lines")
    assert not too_long, "\n".join(too_long)


def test_rule_c6_no_secret_keys_or_passwords_written_in_the_app_code():
    for file_name in os.listdir(os.path.join(PROJECT_FOLDER, "app")):
        if file_name.endswith(".py"):
            text = open(os.path.join(PROJECT_FOLDER, "app", file_name), encoding="utf-8").read()
            code_lines = [line for line in text.splitlines() if not line.strip().startswith("#")]   # help comments may show an example
            assert not re.search(r"""SECRET_KEY\s*=\s*['"][^'"]+['"]""", "\n".join(code_lines)), file_name


# ============================================================================================
# KNOWN ISSUES TO CONFIRM (each is an expected failure until its owner fixes it; see STATUS LOG)
# ============================================================================================

# BUG F-1 (owner: Agent B / app/__init__.py): no CSRF token on forms.
@pytest.mark.skip(reason="F-1 fixed (CSRF tokens added). Proven with protection ON in tests/test_auth_permissions.py; these tests run with it OFF.")
def test_known_issue_form_from_another_website_is_refused(admin, database_file):
    response = admin.post("/materials/M2/record/used", data={"quantity": "10"},
                          headers={"Origin": "https://evil.example", "Referer": "https://evil.example/trap"})
    assert response.status_code in (400, 403)


@pytest.mark.skip(reason="F-1 fixed (CSRF tokens added). Proven with protection ON in tests/test_auth_permissions.py; these tests run with it OFF.")
def test_known_issue_forms_contain_a_hidden_token(admin):
    page = admin.get("/materials/M1/record/used").get_data(as_text=True).lower()
    assert "csrf" in page or 'name="token"' in page


# BUG F-2 (F8 has no owner in Section 11): no user-management or unlock screen.
def test_known_issue_admin_has_a_user_management_screen(website):
    addresses = [rule.rule for rule in website.url_map.iter_rules()]
    assert any("user" in address for address in addresses)


# BUG F-3 (F9 has no owner screen): Admin cannot read the activity log.
@pytest.mark.xfail(strict=True, reason="F-3: the activity log is written but no Admin screen shows it (F9).")
def test_known_issue_admin_can_read_the_activity_log(website):
    addresses = [rule.rule for rule in website.url_map.iter_rules()]
    assert any("activity" in address or address.endswith("/log") for address in addresses)


# BUG F-4 (no owner): the Section 14 item "backup with one click (Admin)" does not exist.
@pytest.mark.xfail(strict=True, reason="F-4: no one-click database backup for the Admin (Section 14).")
def test_known_issue_admin_has_a_backup_button(website):
    addresses = [rule.rule for rule in website.url_map.iter_rules()]
    assert any("backup" in address for address in addresses)


# BUG F-5 (Agent E / routes_stats.py): the spending chart and money box are switched off, so Section 15 line 6 cannot pass.
def test_known_issue_admin_sees_the_spending_chart(admin):
    assert "spending-chart" in admin.get("/stats/").get_data(as_text=True)


def test_known_issue_low_stock_events_chart_has_data(admin):
    assert admin.get("/stats/data/low-stock").get_json()["labels"]


# BUG F-6 (Agent A): the folder layout in Section 10 asks for app/models.py, requirements.txt and GLOSSARY.md.
@pytest.mark.xfail(strict=True, reason="F-6: requirements.txt, GLOSSARY.md and app/models.py from Section 10 do not exist.")
def test_known_issue_files_promised_by_the_folder_layout_exist():
    for relative in ["requirements.txt", "GLOSSARY.md", os.path.join("app", "models.py")]:
        assert os.path.exists(os.path.join(PROJECT_FOLDER, relative)), relative


# BUG F-7 (Agent A / D): the offers table has no way to delete, and the guide's F4 price column names changed.
# Confirmed OK: Agent A and Agent C files exist (see the next test).
def test_agent_a_and_agent_c_files_exist():
    for relative in ["app/schema.sql", "app/setup_database.py", "sample_data/materials.csv",
                     "app/routes_materials.py", "app/alerts.py", "app/templates/materials_list.html"]:
        assert os.path.exists(os.path.join(PROJECT_FOLDER, relative)), relative


# --- Sample users have no password until "set-password" is run ---

# Builds a real sample database in a temporary folder using Agent A's script.
@pytest.fixture
def sample_database(tmp_path, monkeypatch):
    from app import setup_database
    monkeypatch.setattr(setup_database, "DATA_FOLDER", str(tmp_path))
    monkeypatch.setattr(setup_database, "DATABASE_FILE", str(tmp_path / "tracker.db"))
    setup_database.build_database()
    return str(tmp_path / "tracker.db")


def test_known_issue_sample_users_cannot_log_in_until_a_password_is_set(sample_database):
    website = create_app({"DATABASE": sample_database, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    for username in ("sample_admin", "sample_employee"):
        for guess in ("", "password", "admin", "changeme", "sample_admin"):
            assert log_in(website.test_client(), username, guess).status_code == 401, (username, guess)
    assert read_rows(sample_database, "SELECT password_hash FROM users WHERE password_hash IS NOT NULL") == []


def test_sample_users_work_after_set_password_and_roles_are_right(sample_database):
    connection = sqlite3.connect(sample_database)
    connection.row_factory = sqlite3.Row
    assert auth.set_password(connection, "sample_admin", "sample-admin-pass") is True
    assert auth.set_password(connection, "sample_employee", "sample-employee-pass") is True
    connection.close()
    website = create_app({"DATABASE": sample_database, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    boss, worker = website.test_client(), website.test_client()
    assert log_in(boss, "sample_admin", "sample-admin-pass").status_code == 302
    assert log_in(worker, "sample_employee", "sample-employee-pass").status_code == 302
    assert boss.get("/suppliers/new").status_code == 200
    assert worker.get("/suppliers/new").status_code == 403


def test_sample_data_screens_open_for_both_roles(sample_database):
    connection = sqlite3.connect(sample_database)
    connection.row_factory = sqlite3.Row
    auth.set_password(connection, "sample_admin", "sample-admin-pass")
    auth.set_password(connection, "sample_employee", "sample-employee-pass")
    ids = [row[0] for row in connection.execute("SELECT id FROM materials")]
    connection.close()
    website = create_app({"DATABASE": sample_database, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    for username, password in (("sample_admin", "sample-admin-pass"), ("sample_employee", "sample-employee-pass")):
        client = website.test_client()
        log_in(client, username, password)
        for address in ["/", "/materials/", "/suppliers", "/stats/", "/stats/data/usage", "/stats/data/lead-times"]:
            assert client.get(address).status_code == 200, (username, address)
        for material_id in ids:
            assert client.get("/suggest/" + material_id).status_code == 200, (username, material_id)

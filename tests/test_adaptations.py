# WHAT THIS FILE DOES: Checks the three ShopGuard adaptations (2026-11-24): hardware pieces (pcs) in the sample data,
#   the "Last bought" memory (with the price rules), and the plain-English words and error pages.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, routes_materials, setup_database   # noqa: E402

PASSWORD = "test-password-123"
HARDWARE_NAMES = ["Screws", "Springs", "Magnets", "Fidget Clicker", "Keychain Rings"]


# Builds a temporary database from schema.sql and the real sample_data files, with passwords for the sample users.
@pytest.fixture
def sample_database_file(tmp_path):
    path = str(tmp_path / "sample.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    with open(setup_database.SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    for table_name in setup_database.TABLES_TO_LOAD:
        setup_database.load_table(connection, table_name)
    for user in connection.execute("SELECT username FROM users").fetchall():
        auth.set_password(connection, user["username"], PASSWORD)
    connection.close()
    return path


# Returns a test browser logged in as the first active user with this role (CSRF can be switched on or off).
def logged_in_as(database_file, role, csrf=False):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True,
                          "CSRF_ENABLED": csrf})
    connection = sqlite3.connect(database_file)
    username = connection.execute("SELECT username FROM users WHERE role = ? AND is_active = 1", (role,)).fetchone()[0]
    connection.close()
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


# Returns the id of a sample material by a part of its name.
def material_id(database_file, name_part):
    connection = sqlite3.connect(database_file)
    found = connection.execute("SELECT id FROM materials WHERE name LIKE ?", ("%" + name_part + "%",)).fetchone()[0]
    connection.close()
    return found


# ---- (a) hardware pieces in the sample data ----

def test_sample_data_has_g_ml_and_pcs_items_and_five_named_hardware_samples(sample_database_file):
    connection = sqlite3.connect(sample_database_file)
    units = {row[0] for row in connection.execute("SELECT DISTINCT unit FROM materials")}
    names = [row[0] for row in connection.execute("SELECT name FROM materials WHERE unit = 'pcs'")]
    connection.close()
    assert units == {"g", "ml", "pcs"}
    for word in HARDWARE_NAMES:
        assert any(word in name and name.startswith("SAMPLE") for name in names), word


def test_every_hardware_sample_has_a_supplier_offer_in_the_same_unit(sample_database_file):
    connection = sqlite3.connect(sample_database_file)
    missing = connection.execute(
        "SELECT m.name FROM materials m WHERE m.name LIKE 'SAMPLE%' AND NOT EXISTS "
        "(SELECT 1 FROM supplier_offers o WHERE o.material_id = m.id AND o.pack_unit = m.unit)").fetchall()
    connection.close()
    assert missing == []


def test_hardware_items_show_ok_low_and_out_words_and_the_word_pieces(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "SAMPLE Magnets" in page and "pieces" in page
    for word in ("OK", "LOW", "OUT"):
        assert f"tag-{word}" in page and f">{word}</span>" in page


# ---- (b) "Last bought" memory ----

def test_employee_sees_last_bought_supplier_and_price_on_list_and_record_pages(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    list_page = employee.get("/materials/").get_data(as_text=True)
    record_page = employee.get(f"/materials/{material_id(sample_database_file, 'M4 Socket')}/record/used").get_data(as_text=True)
    assert "Last bought: 200 pieces from" in list_page and "SAMPLE Hardware Hub E" in list_page
    assert "MYR 24.00" in list_page and "MYR 24.00" in record_page
    assert "Last bought:" in record_page and "<strong>SAMPLE Hardware Hub E</strong>" in record_page


def test_admin_sees_the_same_last_bought_line(sample_database_file):
    page = logged_in_as(sample_database_file, "ADMIN").get("/materials/").get_data(as_text=True)
    assert "Last bought: 1000 g from" in page and "MYR 76.00" in page


def test_material_never_bought_through_the_app_says_so(sample_database_file):
    record = logged_in_as(sample_database_file, "EMPLOYEE").get(
        f"/materials/{material_id(sample_database_file, 'Standard Resin')}/record/used").get_data(as_text=True)
    assert "Last bought:" not in record
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "Not bought through this app yet." in page


def test_money_is_hidden_when_can_see_prices_says_no_but_supplier_name_stays(sample_database_file, monkeypatch):
    monkeypatch.setattr(routes_materials, "can_see_prices", lambda user: False)
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "MYR" not in page
    assert "Last bought: 1000 g from" in page


def test_visitor_is_sent_to_login_and_employee_still_cannot_change_anything(sample_database_file):
    website = create_app({"DATABASE": sample_database_file, "SECRET_KEY": "test-only-key", "TESTING": True,
                          "CSRF_ENABLED": False})
    assert website.test_client().get("/materials/").status_code == 302
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    for address in ("/materials/new", "/suppliers/new", "/users/", "/stats/export.csv"):
        assert employee.get(address).status_code == 403, address
    assert employee.post("/materials/new", data={"name": "X", "unit": "g"}).status_code == 403


def test_admin_receive_with_supplier_and_money_updates_last_bought_and_employee_cannot_type_money(sample_database_file):
    target = material_id(sample_database_file, "Magnets")
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    refused = employee.post(f"/materials/{target}/record/received",
                            data={"quantity": "100", "supplier_id": "S005", "total_cost": "38"})
    assert refused.status_code == 403                      # purchase money is Admin only (can_record_purchase_cost)
    admin = logged_in_as(sample_database_file, "ADMIN")
    response = admin.post(f"/materials/{target}/record/received",
                          data={"quantity": "100", "supplier_id": "S005", "total_cost": "38"})
    assert response.status_code == 302
    for browser in (admin, employee):                      # both roles may SEE the result
        page = browser.get("/materials/").get_data(as_text=True)
        assert "Last bought: 100 pieces from" in page and "MYR 38.00" in page


# ---- (c) plain English words and error pages ----

def test_status_words_are_explained_in_one_plain_sentence(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "= enough in stock" in page and "= at or below the reorder level" in page and "= none left" in page


def test_record_page_explains_low_and_out_in_plain_words(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    low = employee.get(f"/materials/{material_id(sample_database_file, 'Springs')}/record/used").get_data(as_text=True)
    out = employee.get(f"/materials/{material_id(sample_database_file, 'Magnets')}/record/used").get_data(as_text=True)
    assert "This is LOW: at or below the reorder level of 50 pieces" in low
    assert "This is OUT: none left" in out


def test_no_permission_and_missing_page_use_plain_english_with_a_home_button(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    forbidden = employee.get("/materials/new")
    missing = employee.get("/materials/no-such-material/record/used")
    assert forbidden.status_code == 403 and missing.status_code == 404
    for response in (forbidden, missing):
        text = response.get_data(as_text=True)
        assert "Back to Home" in text and "Forbidden" not in text and "Not Found" not in text
    assert "do not have permission" in forbidden.get_data(as_text=True)


def test_expired_form_still_gets_400_with_a_plain_message(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE", csrf=True)
    response = employee.post(f"/materials/{material_id(sample_database_file, 'Springs')}/record/used", data={"quantity": "1"})
    assert response.status_code == 400
    assert "expired" in response.get_data(as_text=True) and "Back to Home" in response.get_data(as_text=True)


def test_buttons_are_big_enough_to_tap(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    assert "min-height: 44px" in employee.get("/materials/").get_data(as_text=True)
    page = employee.get(f"/materials/{material_id(sample_database_file, 'Springs')}/record/used").get_data(as_text=True)
    assert "min-height: 44px" in page

# WHAT THIS FILE DOES: Automatic checks for the Suppliers screens and the "best supplier" suggestion (guide Sections 4, 5 F4/F6, 7, 14, 15).
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db) and the real website on top of it.

import os
import sqlite3
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, suggest      # noqa: E402

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
ADMIN_PASSWORD = "test-admin-pass-1"
EMPLOYEE_PASSWORD = "test-employee-pass-1"


# Builds a temporary database: 2 users, 3 materials (LOW, OK, OUT) and 4 suppliers with offers.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "test.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    connection.executescript("""
        INSERT INTO users (id, username, role) VALUES ('U1', 'boss', 'ADMIN'), ('U2', 'worker', 'EMPLOYEE');
        INSERT INTO materials (id, name, colour, unit, quantity_on_hand, reorder_level) VALUES
          ('M1', 'PLA', 'White', 'g', 430, 500), ('M2', 'PLA', 'Black', 'g', 900, 500),
          ('M3', 'ABS', 'Grey', 'g', 0, 500);
        INSERT INTO suppliers (id, name, supplier_type, phone, is_active) VALUES
          ('S1', 'Local Shop', 'LOCAL', '082-111', 1), ('S2', 'Online Shop', 'ONLINE', '03-222', 1),
          ('S3', 'Cheap Slow Shop', 'ONLINE', '03-333', 1), ('S4', 'Closed Shop', 'LOCAL', '082-444', 0);
        INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr,
            minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES
          ('O1', 'S1', 'M1', 1000, 'g', 72.00, 1, 0, 1),
          ('O2', 'S2', 'M1', 1000, 'g', 70.00, 1, 5, 3),
          ('O3', 'S3', 'M1', 1000, 'g', 50.00, 2, 10, 14),
          ('O4', 'S4', 'M1', 1000, 'g', 10.00, 1, 0, 1),
          ('O5', 'S1', 'M3', 1000, 'g', 75.00, 1, 0, 2),
          ('O6', 'S1', 'M2', 1000, 'g', 72.00, 1, 0, 1);
    """)
    auth.set_password(connection, "boss", ADMIN_PASSWORD)
    auth.set_password(connection, "worker", EMPLOYEE_PASSWORD)
    connection.close()
    return path


# Builds the real website on the temporary database.
@pytest.fixture
def website(database_file):
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True})


# Returns a browser that is logged in as the Admin.
@pytest.fixture
def admin(website):
    client = website.test_client()
    client.post("/login", data={"username": "boss", "password": ADMIN_PASSWORD})
    return client


# Returns a browser that is logged in as an Employee.
@pytest.fixture
def employee(website):
    client = website.test_client()
    client.post("/login", data={"username": "worker", "password": EMPLOYEE_PASSWORD})
    return client


# Reads rows straight from the database file.
def read_rows(database_file, query):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(query).fetchall()
    connection.close()
    return rows


# Returns the ranked suggestions for a material, straight from suggest.py.
def suggestions_for(database_file, material_id, show_prices=True, days_allowed=None):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    material = connection.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    result = suggest.get_suggestions(connection, material, show_prices, days_allowed, today=date(2026, 11, 23))
    connection.close()
    return result


# ---------- The suggestion rules (guide Sections 5 F6, 7, 15) ----------

def test_quantity_needed_is_double_reorder_level_minus_stock():
    assert suggest.get_quantity_needed({"reorder_level": 500, "quantity_on_hand": 430}) == 570
    assert suggest.get_quantity_needed({"reorder_level": 500, "quantity_on_hand": 0}) == 1000


def test_packs_are_rounded_up_and_respect_the_minimum():
    assert suggest.get_packs_to_order(570, 1000, 1) == 1
    assert suggest.get_packs_to_order(1001, 1000, 1) == 2
    assert suggest.get_packs_to_order(570, 1000, 5) == 5


def test_cost_is_packs_times_price_plus_shipping():
    assert suggest.get_estimated_cost(2, 72.00, 0) == 144.00
    assert suggest.get_estimated_cost(5, 58.00, 18.00) == 308.00


def test_lower_cost_is_listed_first_then_closed_shops_and_switched_off_are_left_out(database_file):
    names = [s["supplier_name"] for s in suggestions_for(database_file, "M1")]
    assert names == ["Local Shop", "Online Shop", "Cheap Slow Shop"]      # 72, 75, 110 MYR; Closed Shop is left out


def test_same_cost_is_ordered_by_shortest_lead_time():
    ranked = suggest.sort_suggestions([
        {"estimated_cost_myr": 80, "lead_time_days": 7}, {"estimated_cost_myr": 80, "lead_time_days": 1}])
    assert [s["lead_time_days"] for s in ranked] == [1, 7]


def test_arrival_date_is_today_plus_lead_time(database_file):
    first, second, third = suggestions_for(database_file, "M1")
    assert first["arrival_date"] == date(2026, 11, 24)
    assert second["arrival_date"] == date(2026, 11, 26)
    assert third["arrival_date"] == date(2026, 12, 7)


def test_only_suppliers_that_deliver_in_time_are_listed(database_file):
    names = [s["supplier_name"] for s in suggestions_for(database_file, "M1", days_allowed=3)]
    assert names == ["Local Shop", "Online Shop"]
    assert suggestions_for(database_file, "M1", days_allowed=0) == []


def test_today_uses_malaysia_time(monkeypatch):
    monkeypatch.setattr(suggest, "utc_now", lambda: datetime(2026, 11, 23, 17, 0, 0))   # 01:00 next day in Malaysia
    assert suggest.get_today_in_malaysia() == date(2026, 11, 24)


def test_offer_in_a_different_unit_is_not_suggested(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE supplier_offers SET pack_unit = 'ml' WHERE id = 'O5'")
    connection.commit()
    connection.close()
    assert suggestions_for(database_file, "M3") == []


def test_employee_suggestions_have_no_money_at_all(database_file):
    for suggestion in suggestions_for(database_file, "M1", show_prices=False):
        assert not any("myr" in key or "price" in key or "cost" in key for key in suggestion)


# ---------- The screens ----------

def test_ok_material_gets_no_suggestion_screen_list(admin):
    page = admin.get("/suggest/M2").get_data(as_text=True)
    assert "nothing to order" in page and "Local Shop" not in page


def test_low_material_screen_shows_status_word_and_estimate(admin):
    page = admin.get("/suggest/M1").get_data(as_text=True)
    assert "LOW" in page and "estimate" in page and "Local Shop" in page
    assert "MYR 72.00" in page


def test_out_material_screen_works(admin):
    assert "OUT" in admin.get("/suggest/M3").get_data(as_text=True)


def test_employee_suggestion_page_shows_prices(employee):
    # Team decision 2026-11-24: employees may SEE prices (but not change them).
    page = employee.get("/suggest/M1").get_data(as_text=True)
    assert "Local Shop" in page and "082-111" in page
    assert "Estimated cost" in page and "MYR" in page


def test_employee_supplier_pages_show_prices_but_no_edit_buttons(employee):
    page = employee.get("/suppliers/S1").get_data(as_text=True)
    assert "MYR 72.00" in page and "Lead time" in page
    for edit_control in ["Change", "Switch off", "Switch on", "Add material this supplier sells", "/edit"]:
        assert edit_control not in page
    assert "Add supplier" not in employee.get("/suppliers").get_data(as_text=True)


def test_admin_supplier_page_shows_prices(admin):
    page = admin.get("/suppliers/S1").get_data(as_text=True)
    assert "MYR 72.00" in page and "Change supplier" in page


def test_employee_cannot_see_switched_off_supplier(employee, admin):
    assert employee.get("/suppliers/S4").status_code == 404
    assert "Closed Shop" not in employee.get("/suppliers").get_data(as_text=True)
    assert "Closed Shop" in admin.get("/suppliers").get_data(as_text=True)


def test_not_logged_in_is_sent_to_login(website):
    for address in ["/suppliers", "/suppliers/S1", "/suggest/M1", "/suppliers/new"]:
        response = website.test_client().get(address)
        assert response.status_code == 302 and "/login" in response.headers["Location"]


# ---------- Employee cannot change anything (guide Section 4, security checklist) ----------

ADMIN_ONLY_ADDRESSES = ["/suppliers/new", "/suppliers/S1/edit", "/suppliers/S1/switch",
                        "/suppliers/S1/offers/new", "/offers/O1/edit", "/offers/O1/switch"]


def test_employee_is_blocked_from_every_admin_address(employee):
    for address in ADMIN_ONLY_ADDRESSES:
        assert employee.get(address).status_code in (403, 405), address
        assert employee.post(address, data={"name": "Hacker"}).status_code == 403, address


def test_employee_attempts_change_nothing(employee, database_file):
    employee.post("/suppliers/new", data={"name": "Hacker", "supplier_type": "LOCAL"})
    employee.post("/suppliers/S1/switch")
    employee.post("/offers/O1/switch")
    assert len(read_rows(database_file, "SELECT * FROM suppliers")) == 4
    assert read_rows(database_file, "SELECT is_active FROM suppliers WHERE id='S1'")[0]["is_active"] == 1
    assert read_rows(database_file, "SELECT is_active FROM supplier_offers WHERE id='O1'")[0]["is_active"] == 1


VALID_SUPPLIER_FORM = {"name": "Renamed Shop", "supplier_type": "ONLINE", "address": "x", "phone": "1",
                       "email": "a@b.c", "website": "", "notes": ""}
VALID_OFFER_FORM = {"material_id": "M1", "pack_unit": "g", "pack_size": "1000", "price_per_pack_myr": "1",
                    "minimum_order_packs": "1", "shipping_cost_myr": "0", "lead_time_days": "1"}


# A fully valid form sent by an Employee must still be refused, so only the permission check can be what stops it.
@pytest.mark.parametrize("address, form", [
    ("/suppliers/new", VALID_SUPPLIER_FORM),
    ("/suppliers/S1/edit", VALID_SUPPLIER_FORM),
    ("/suppliers/S1/offers/new", VALID_OFFER_FORM),
    ("/offers/O1/edit", VALID_OFFER_FORM),
])
def test_employee_with_a_valid_form_gets_403_and_nothing_changes(employee, database_file, address, form):
    before = (read_rows(database_file, "SELECT * FROM suppliers"), read_rows(database_file, "SELECT * FROM supplier_offers"),
              read_rows(database_file, "SELECT * FROM activity_log"))
    assert employee.post(address, data=form).status_code == 403
    after = (read_rows(database_file, "SELECT * FROM suppliers"), read_rows(database_file, "SELECT * FROM supplier_offers"),
             read_rows(database_file, "SELECT * FROM activity_log"))
    assert [[tuple(r) for r in part] for part in before] == [[tuple(r) for r in part] for part in after]


def test_the_same_valid_forms_do_work_for_the_admin(admin, database_file):
    assert admin.post("/offers/O1/edit", data=VALID_OFFER_FORM).status_code == 302
    assert read_rows(database_file, "SELECT price_per_pack_myr FROM supplier_offers WHERE id='O1'")[0][0] == 1


def test_employee_price_stays_the_same_after_typing_the_price_address(employee, database_file):
    employee.post("/offers/O1/edit", data=VALID_OFFER_FORM)
    assert read_rows(database_file, "SELECT price_per_pack_myr FROM supplier_offers WHERE id='O1'")[0][0] == 72.0


# ---------- Admin changes (guide F4, C8, C9) ----------

GOOD_OFFER = {"material_id": "M2", "pack_size": "1000", "pack_unit": "g", "price_per_pack_myr": "60",
              "minimum_order_packs": "1", "shipping_cost_myr": "5", "lead_time_days": "4"}


def test_admin_can_add_a_supplier_and_it_is_logged(admin, database_file):
    response = admin.post("/suppliers/new", data={"name": "New Shop", "supplier_type": "ONLINE"})
    assert response.status_code == 302
    assert read_rows(database_file, "SELECT * FROM suppliers WHERE name='New Shop'")[0]["id"] == "S005"
    log = read_rows(database_file, "SELECT * FROM activity_log WHERE action='SUPPLIER_ADDED'")
    assert len(log) == 1 and log[0]["user_id"] == "U1"


def test_admin_can_add_an_offer_and_it_changes_the_suggestions(admin, database_file):
    assert admin.post("/suppliers/S2/offers/new", data=GOOD_OFFER).status_code == 302
    assert len(read_rows(database_file, "SELECT * FROM supplier_offers")) == 7
    assert read_rows(database_file, "SELECT * FROM activity_log WHERE action='OFFER_ADDED'")


def test_price_change_is_logged_with_old_and_new_price(admin, database_file):
    admin.post("/offers/O1/edit", data={**GOOD_OFFER, "material_id": "M1", "price_per_pack_myr": "85"})
    details = read_rows(database_file, "SELECT details FROM activity_log WHERE action='OFFER_CHANGED'")[0]["details"]
    assert "MYR 72.00 to MYR 85.00" in details


def test_switching_off_keeps_the_record(admin, database_file):
    admin.post("/suppliers/S1/switch")
    rows = read_rows(database_file, "SELECT is_active FROM suppliers WHERE id='S1'")
    assert len(rows) == 1 and rows[0]["is_active"] == 0
    names = [s["supplier_name"] for s in suggestions_for(database_file, "M1")]
    assert "Local Shop" not in names
    admin.post("/suppliers/S1/switch")
    assert read_rows(database_file, "SELECT is_active FROM suppliers WHERE id='S1'")[0]["is_active"] == 1


def test_no_delete_address_exists(admin):
    assert admin.post("/suppliers/S1/delete").status_code == 404


def test_letters_in_number_fields_are_refused_in_plain_language(admin, database_file):
    response = admin.post("/suppliers/S2/offers/new", data={**GOOD_OFFER, "price_per_pack_myr": "abc"})
    assert response.status_code == 400
    assert "as a number, for example" in response.get_data(as_text=True)
    assert len(read_rows(database_file, "SELECT * FROM supplier_offers")) == 6


def test_bad_numbers_are_refused(admin):
    for field, value in [("price_per_pack_myr", "-5"), ("pack_size", "0"), ("lead_time_days", "2.5"),
                         ("minimum_order_packs", "0"), ("price_per_pack_myr", "nan"), ("shipping_cost_myr", "inf")]:
        assert admin.post("/suppliers/S2/offers/new", data={**GOOD_OFFER, field: value}).status_code == 400, field


def test_very_long_text_is_refused(admin, database_file):
    response = admin.post("/suppliers/new", data={"name": "x" * 101, "supplier_type": "LOCAL"})
    assert response.status_code == 400
    assert len(read_rows(database_file, "SELECT * FROM suppliers")) == 4


def test_supplier_needs_a_name_and_a_valid_type(admin):
    assert admin.post("/suppliers/new", data={"name": "  ", "supplier_type": "LOCAL"}).status_code == 400
    assert admin.post("/suppliers/new", data={"name": "A", "supplier_type": "MOON"}).status_code == 400

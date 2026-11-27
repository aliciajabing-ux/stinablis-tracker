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
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})


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


# A lead time of 1 reads "1 day"; any other number reads "N days" (wording only).
def test_lead_time_words_use_day_for_one_and_days_for_other_numbers(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, "
                       "price_per_pack_myr, minimum_order_packs, shipping_cost_myr, lead_time_days) "
                       "VALUES ('O7', 'S3', 'M3', 1000, 'g', 60.00, 1, 5, 7)")
    connection.commit()
    connection.close()
    one_day_page = admin.get("/suggest/M1").get_data(as_text=True)
    seven_day_page = admin.get("/suggest/M3").get_data(as_text=True)
    assert '<td data-label="Lead time">1 day</td>' in one_day_page and "1 days" not in one_day_page
    assert '<td data-label="Lead time">7 days</td>' in seven_day_page
    assert "within 1 day." in admin.get("/suggest/M3?days=1").get_data(as_text=True)
    assert "within 1 days" not in admin.get("/suggest/M3?days=1").get_data(as_text=True)
    assert "within 0 days." in admin.get("/suggest/M3?days=0").get_data(as_text=True)


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
    assert "MYR 72.00" in page and "Edit supplier" in page


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


# ---------- Editing a supplier from the Suppliers list (team request 2026-11-26) ----------

FULL_SUPPLIER_FORM = {"name": "Renamed Shop", "supplier_type": "ONLINE", "address": "1 New Road, Kuching",
                      "phone": "082-999", "email": "new@shop.example", "website": "https://shop.example",
                      "notes": "Changed note", "is_active": "1"}


def test_admin_list_has_an_edit_button_on_every_row_that_opens_the_edit_form(admin):
    page = admin.get("/suppliers").get_data(as_text=True)
    for supplier_id in ["S1", "S2", "S3", "S4"]:                      # S4 is switched off: the Admin still sees and can edit it
        assert f'href="/suppliers/{supplier_id}/edit"' in page
    assert page.count('class="button"') >= 5 and "<th>Actions</th>" in page      # 4 Edit buttons + Add supplier
    assert "Edit<span" in page and "min-height: 44px" in page          # plain word "Edit", tap-friendly, name for screen readers


def test_employee_list_has_no_edit_button_and_no_actions_column(employee):
    page = employee.get("/suppliers").get_data(as_text=True)
    assert "/edit" not in page and "Edit" not in page and "<th>Actions</th>" not in page and "Add supplier" not in page


def test_edit_form_shows_every_field_with_the_current_values_and_status(admin):
    page = admin.get("/suppliers/S4/edit").get_data(as_text=True)
    assert "<h1>Edit supplier</h1>" in page and "<title>Edit supplier - Stinablis Tracker</title>" in page and "Change supplier" not in page
    assert "Edit supplier" in page and 'value="Closed Shop"' in page and "082-444" in page
    for field in ["name", "supplier_type", "address", "phone", "email", "website", "notes", "is_active"]:
        assert f'name="{field}"' in page
    assert '<option value="0" selected>' in page                       # S4 is switched off, and the form says so
    assert '<option value="1" selected>' in admin.get("/suppliers/S1/edit").get_data(as_text=True)


def test_add_supplier_form_has_no_status_box_and_keeps_its_title(admin):
    page = admin.get("/suppliers/new").get_data(as_text=True)
    assert "Add supplier" in page and 'name="is_active"' not in page


def test_admin_can_change_every_field_and_the_change_is_saved_and_logged(admin, database_file):
    response = admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "0"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/suppliers/S1")
    row = read_rows(database_file, "SELECT * FROM suppliers WHERE id='S1'")[0]
    assert (row["name"], row["supplier_type"], row["address"], row["phone"], row["email"], row["website"], row["notes"],
            row["is_active"]) == ("Renamed Shop", "ONLINE", "1 New Road, Kuching", "082-999", "new@shop.example",
                                  "https://shop.example", "Changed note", 0)
    actions = [r["action"] for r in read_rows(database_file, "SELECT action FROM activity_log")]
    assert "SUPPLIER_CHANGED" in actions and "SUPPLIER_SWITCHED_OFF" in actions
    assert len(read_rows(database_file, "SELECT * FROM suppliers")) == 4          # nothing added, nothing deleted


def test_admin_can_switch_a_supplier_back_on_from_the_edit_form_and_employees_then_see_it(admin, employee, database_file):
    admin.post("/suppliers/S4/edit", data={**FULL_SUPPLIER_FORM, "name": "Closed Shop", "is_active": "1"})
    assert read_rows(database_file, "SELECT is_active FROM suppliers WHERE id='S4'")[0]["is_active"] == 1
    assert "SUPPLIER_SWITCHED_ON" in [r["action"] for r in read_rows(database_file, "SELECT action FROM activity_log")]
    assert "Closed Shop" in employee.get("/suppliers").get_data(as_text=True)


def test_saving_without_a_status_box_keeps_the_status_and_writes_no_switch_line(admin, database_file):
    data = {key: value for key, value in FULL_SUPPLIER_FORM.items() if key != "is_active"}
    admin.post("/suppliers/S4/edit", data=data)
    assert read_rows(database_file, "SELECT is_active FROM suppliers WHERE id='S4'")[0]["is_active"] == 0
    assert not [r for r in read_rows(database_file, "SELECT action FROM activity_log") if "SWITCHED" in r["action"]]


def test_a_bad_status_or_empty_name_is_refused_in_plain_words_and_changes_nothing(admin, database_file):
    before = [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")]
    bad_status = admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "maybe"})
    assert bad_status.status_code == 400 and "Active or Switched off" in bad_status.get_data(as_text=True)
    assert "Edit supplier" in bad_status.get_data(as_text=True)      # still the Edit form, not "Add supplier"
    empty_name = admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "name": "  "})
    assert empty_name.status_code == 400
    assert [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")] == before
    assert read_rows(database_file, "SELECT * FROM activity_log WHERE action LIKE 'SUPPLIER_%'") == []


def test_employee_still_gets_403_on_the_edit_form_even_with_a_status_value(employee, database_file):
    before = [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")]
    assert employee.get("/suppliers/S1/edit").status_code == 403
    assert employee.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "0"}).status_code == 403
    assert [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")] == before


def test_editing_a_supplier_that_does_not_exist_says_not_found(admin):
    assert admin.get("/suppliers/S999/edit").status_code == 404
    assert admin.post("/suppliers/S999/edit", data=FULL_SUPPLIER_FORM).status_code == 404


def test_supplier_detail_page_still_has_edit_supplier_and_switch_buttons_for_admin(admin):
    page = admin.get("/suppliers/S1").get_data(as_text=True)
    assert "Edit supplier" in page and "Switch off" in page and "/suppliers/S1?edit=1" in page


# ---------- Edit a supplier from its own page (2026-11-27) ----------

def test_detail_page_has_an_edit_supplier_button_that_opens_the_form_inside_the_card(admin):
    list_page = admin.get("/suppliers").get_data(as_text=True)
    assert 'href="/suppliers/S1/edit"' in list_page                                 # the list button is unchanged
    page = admin.get("/suppliers/S1").get_data(as_text=True)
    assert 'href="/suppliers/S1?edit=1"' in page and "Edit supplier" in page and "min-height: 44px" in page
    assert "supplier-edit-form" not in page and "Change supplier" not in page        # closed until the button is pressed
    page = admin.get("/suppliers/S1?edit=1").get_data(as_text=True)
    card = page[page.index('id="supplier-card"'):page.index("Materials this supplier sells")]
    for field in ["name", "supplier_type", "address", "phone", "email", "website", "notes"]:
        assert f'name="{field}"' in card
    assert 'value="Local Shop"' in card and "Save" in card and "Cancel" in card
    assert 'action="/suppliers/S1/edit"' in card and 'name="csrf_token"' in card
    assert "Materials this supplier sells" in page and "Add material this supplier sells" in page     # the offers table stays


def test_inline_form_and_standalone_form_use_the_same_fields_and_validation(admin):
    standalone = admin.get("/suppliers/S1/edit").get_data(as_text=True)
    inline = admin.get("/suppliers/S1?edit=1").get_data(as_text=True)
    for field in ["name", "supplier_type", "address", "phone", "email", "website", "notes"]:
        assert f'name="{field}"' in standalone and f'name="{field}"' in inline
    bad = {**FULL_SUPPLIER_FORM, "name": "  ", "from_detail": "1"}
    response = admin.post("/suppliers/S1/edit", data=bad)
    page = response.get_data(as_text=True)
    assert response.status_code == 400 and "supplier-edit-form" in page and "Please fill in the" in page    # error shown inside the card
    assert "Materials this supplier sells" in page and "Changed note" in page                        # typed values are kept
    assert "Local Shop" in admin.get("/suppliers/S1").get_data(as_text=True)                         # nothing was saved


def test_saving_from_the_detail_page_shows_fresh_details_a_saved_message_and_updates_the_list(admin):
    response = admin.post("/suppliers/S1/edit", data=FULL_SUPPLIER_FORM)
    assert response.status_code == 302 and response.headers["Location"].endswith("/suppliers/S1")
    detail = admin.get("/suppliers/S1").get_data(as_text=True)
    assert "Saved Renamed Shop." in detail and "<h1>Renamed Shop</h1>" in detail
    assert "082-999" in detail and "new@shop.example" in detail and "Changed note" in detail and "ONLINE" in detail
    assert "Saved Renamed Shop." not in admin.get("/suppliers/S1").get_data(as_text=True)       # the message shows once only
    listing = admin.get("/suppliers").get_data(as_text=True)
    assert "Renamed Shop" in listing and "082-999" in listing and "new@shop.example" in listing


def test_the_status_box_on_the_same_form_switches_a_supplier_off_and_on_in_both_places(admin):
    admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "0"})
    assert "(Switched off)" in admin.get("/suppliers/S1").get_data(as_text=True)
    assert "Switched off" in admin.get("/suppliers").get_data(as_text=True)
    admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "1"})
    assert "(Switched off)" not in admin.get("/suppliers/S1").get_data(as_text=True)


def test_a_bad_edit_from_the_detail_page_keeps_the_form_and_the_data(admin):
    response = admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "name": "  "})
    assert response.status_code == 400 and "Edit supplier" in response.get_data(as_text=True)
    assert "Local Shop" in admin.get("/suppliers/S1").get_data(as_text=True)


def test_cancel_on_the_edit_form_goes_back_to_that_supplier_page(admin):
    page = admin.get("/suppliers/S1/edit").get_data(as_text=True)
    assert 'href="/suppliers/S1">Cancel' in page
    assert 'href="/suppliers">Cancel' in admin.get("/suppliers/new").get_data(as_text=True)


def test_editing_a_supplier_never_touches_its_offers(admin, database_file):
    offers_before = [tuple(r) for r in read_rows(database_file, "SELECT * FROM supplier_offers ORDER BY id")]
    admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "is_active": "0"})
    assert [tuple(r) for r in read_rows(database_file, "SELECT * FROM supplier_offers ORDER BY id")] == offers_before


def test_employee_still_gets_no_edit_option_on_the_detail_page_and_403_on_the_address(employee, database_file):
    page = employee.get("/suppliers/S1").get_data(as_text=True)
    assert "Edit supplier" not in page and "/edit" not in page and "Switch off" not in page
    before = [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")]
    assert employee.get("/suppliers/S1/edit").status_code == 403
    assert employee.post("/suppliers/S1/edit", data=FULL_SUPPLIER_FORM).status_code == 403
    assert [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")] == before


def test_inline_save_keeps_you_on_the_supplier_page_and_leaves_status_alone(admin):
    admin.post("/suppliers/S4/edit", data={k: v for k, v in FULL_SUPPLIER_FORM.items() if k != "is_active"} | {"from_detail": "1"})
    detail = admin.get("/suppliers/S4").get_data(as_text=True)
    assert "Saved Renamed Shop." in detail and "(Switched off)" in detail           # S4 stays switched off: no status box in the card
    response = admin.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "from_detail": "1"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/suppliers/S1")


def test_employee_never_gets_the_inline_form_even_with_edit_in_the_address(employee, database_file):
    page = employee.get("/suppliers/S1?edit=1").get_data(as_text=True)
    assert "supplier-edit-form" not in page and 'name="phone"' not in page and "Edit supplier" not in page
    assert "Switch off" not in page and "Materials this supplier sells" in page
    before = [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")]
    assert employee.post("/suppliers/S1/edit", data={**FULL_SUPPLIER_FORM, "from_detail": "1"}).status_code == 403
    assert employee.post("/suppliers/S1/switch").status_code == 403
    assert [tuple(r) for r in read_rows(database_file, "SELECT * FROM suppliers ORDER BY id")] == before


def test_offer_controls_below_the_card_still_work_while_the_card_is_in_edit_mode(admin):
    page = admin.get("/suppliers/S1?edit=1").get_data(as_text=True)
    assert "/offers/O1/edit" in page and "/offers/O1/switch" in page and "/suppliers/S1/switch" in page

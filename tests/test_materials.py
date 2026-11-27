# WHAT THIS FILE DOES: Automatic checks for the Materials screens, stock recording and the OK / LOW / OUT rule.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db).

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app                       # noqa: E402
from app.alerts import (count_materials_by_status, get_materials_needing_attention,   # noqa: E402
                        get_status)

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
PASSWORD = "test-password-123"


# Builds a temporary database with an admin, an employee, three materials and one supplier price.
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
        "INSERT INTO materials (id, name, material_type, colour, unit, quantity_on_hand, reorder_level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("M1", "PLA Basic", "PLA", "White", "g", 800, 500), ("M2", "PETG", "PETG", "Clear", "g", 240, 500),
         ("M3", "ABS", "ABS", "Grey", "g", 0, 500)])
    connection.execute("INSERT INTO suppliers (id, name, supplier_type) VALUES ('S1', 'Shop', 'LOCAL')")
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, "
                       "price_per_pack_myr, lead_time_days) VALUES ('O1', 'S1', 'M1', 1000, 'g', 72.55, 1)")
    auth.set_password(connection, "boss", PASSWORD)
    auth.set_password(connection, "worker", PASSWORD)
    connection.close()
    return path


# Builds the real website (create_app) pointed at the temporary database.
@pytest.fixture
def website(database_file):
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})


# Returns a test browser that is already logged in as the given user.
def logged_in(website, username):
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


@pytest.fixture
def admin(website):
    return logged_in(website, "boss")


@pytest.fixture
def employee(website):
    return logged_in(website, "worker")


# Reads one value from the temporary database.
def ask_database(database_file, sql, parameters=()):
    connection = sqlite3.connect(database_file)
    row = connection.execute(sql, parameters).fetchone()
    connection.close()
    return row[0] if row else None


# ---------- The OK / LOW / OUT rule (guide Sections 5 F5 and 7) ----------

def test_status_rule_boundaries():
    assert get_status(800, 500) == "OK"
    assert get_status(501, 500) == "OK"
    assert get_status(500, 500) == "LOW"       # "at or below" the reorder level is LOW
    assert get_status(430, 500) == "LOW"       # the guide's example
    assert get_status(0, 500) == "OUT"
    assert get_status(0, 0) == "OUT"


def test_needing_attention_and_counts(database_file):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    names = [m["name"] for m in get_materials_needing_attention(connection)]
    assert names == ["ABS", "PETG"]            # OUT first, then LOW
    assert count_materials_by_status(connection) == {"TOTAL": 3, "OK": 1, "LOW": 1, "OUT": 1}
    connection.close()


# ---------- Testing checklist, Section 15 ----------

def test_checklist_add_then_use_until_low_then_out(admin, database_file):
    reply = admin.post("/materials/new", data={"name": "Resin", "material_type": "Resin", "colour": "Grey",
                                               "unit": "g", "starting_quantity": "800", "reorder_level": "500"})
    assert reply.status_code == 302
    material_id = ask_database(database_file, "SELECT id FROM materials WHERE name = 'Resin'")
    assert "OK" in admin.get("/materials/?q=Resin").get_data(as_text=True)

    admin.post(f"/materials/{material_id}/record/used", data={"quantity": "400"})
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = ?", (material_id,)) == 400
    assert "LOW" in admin.get("/materials/?q=Resin").get_data(as_text=True)

    admin.post(f"/materials/{material_id}/record/used", data={"quantity": "400"})
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = ?", (material_id,)) == 0
    assert "OUT" in admin.get("/materials/?q=Resin").get_data(as_text=True)


def test_starting_stock_is_written_to_history(admin, database_file):
    admin.post("/materials/new", data={"name": "Resin", "unit": "ml", "starting_quantity": "800", "reorder_level": "500"})
    assert ask_database(database_file, "SELECT movement_type FROM stock_movements WHERE quantity = 800") == "ADJUSTED"


# ---------- Recording stock (guide rules C8, Section 6) ----------

def test_used_and_received_change_quantity_and_write_history(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "200", "note": "Job 12"})
    employee.post("/materials/M1/record/received", data={"quantity": "1000"})
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 1600
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements WHERE material_id = 'M1'") == 2
    assert ask_database(database_file, "SELECT note FROM stock_movements WHERE movement_type = 'USED'") == "Job 12"
    assert ask_database(database_file, "SELECT user_id FROM stock_movements WHERE movement_type = 'USED'") == "U2"
    assert ask_database(database_file, "SELECT COUNT(*) FROM activity_log WHERE action LIKE 'STOCK_%'") == 2


def test_cannot_use_more_than_is_in_stock(employee, database_file):
    reply = employee.post("/materials/M2/record/used", data={"quantity": "241"})
    assert reply.status_code == 400
    assert "only 240" in reply.get_data(as_text=True)
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'") == 240
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements") == 0


@pytest.mark.parametrize("bad_quantity", ["abc", "", "-5", "0", "1e5", "nan", "inf", "12.345", "99999999", "1_0"])
def test_bad_quantities_are_refused_in_plain_words(employee, database_file, bad_quantity):
    reply = employee.post("/materials/M1/record/received", data={"quantity": bad_quantity})
    assert reply.status_code == 400
    assert "as a number, for example 200" in reply.get_data(as_text=True)
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 800


def test_note_that_is_too_long_is_refused(employee, database_file):
    reply = employee.post("/materials/M1/record/used", data={"quantity": "10", "note": "x" * 201})
    assert reply.status_code == 400
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 800


def test_decimal_quantities_do_not_drift(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "0.1"})
    employee.post("/materials/M1/record/used", data={"quantity": "0.2"})
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 799.7


def test_history_shows_malaysia_time(employee, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at) "
                       "VALUES ('S9', 'M1', 'USED', 5, 'U2', '2026-11-23 16:00:00')")
    connection.commit()
    connection.close()
    page = employee.get("/materials/M1/record/used").get_data(as_text=True)
    assert "24 Nov 2026 00:00" in page         # UTC 16:00 is midnight in Malaysia (UTC+8)


# ---------- Roles (guide Section 4) ----------

def test_not_logged_in_is_sent_to_login(website):
    browser = website.test_client()
    for address in ["/materials/", "/materials/new", "/materials/M1/edit", "/materials/M1/record/used"]:
        reply = browser.get(address)
        assert reply.status_code == 302 and "/login" in reply.headers["Location"]
    assert browser.post("/materials/M1/remove").status_code == 302


def test_employee_cannot_add_edit_or_remove(employee, database_file):
    assert employee.get("/materials/new").status_code == 403
    assert employee.post("/materials/new", data={"name": "Hack", "unit": "g", "reorder_level": "1"}).status_code == 403
    assert employee.get("/materials/M1/edit").status_code == 403
    assert employee.post("/materials/M1/edit", data={"name": "Renamed", "reorder_level": "1"}).status_code == 403
    assert employee.post("/materials/M1/remove").status_code == 403
    assert ask_database(database_file, "SELECT COUNT(*) FROM materials") == 3
    assert ask_database(database_file, "SELECT name FROM materials WHERE id = 'M1'") == "PLA Basic"
    assert ask_database(database_file, "SELECT is_active FROM materials WHERE id = 'M1'") == 1


def test_employee_page_has_no_admin_buttons_and_no_prices(employee):
    page = employee.get("/materials/").get_data(as_text=True)
    assert "Record used" in page and "Record received" in page
    assert "Add material" not in page and ">Edit<" not in page and ">Remove<" not in page
    for secret in ["72.55", "price", "MYR", "shipping"]:
        assert secret.lower() not in page.lower()


def test_admin_sees_admin_buttons(admin):
    page = admin.get("/materials/").get_data(as_text=True)
    assert "Add material" in page and ">Edit<" in page and ">Remove<" in page


# ---------- Admin: add, edit, remove ----------

def test_add_material_with_bad_input_is_refused(admin, database_file):
    bad_forms = [{"name": "", "unit": "g", "reorder_level": "5"},
                 {"name": "A", "unit": "kg", "reorder_level": "5"},
                 {"name": "A", "unit": "g", "reorder_level": "five"},
                 {"name": "A", "unit": "g", "reorder_level": "5", "starting_quantity": "-1"},
                 {"name": "x" * 101, "unit": "g", "reorder_level": "5"}]
    for form in bad_forms:
        assert admin.post("/materials/new", data=form).status_code == 400
    assert ask_database(database_file, "SELECT COUNT(*) FROM materials") == 3


def test_edit_changes_details_logs_it_and_ignores_quantity(admin, database_file):
    admin.post("/materials/M1/edit", data={"name": "PLA Plus", "material_type": "PLA", "colour": "White",
                                           "reorder_level": "600", "quantity_on_hand": "99999", "unit": "ml"})
    assert ask_database(database_file, "SELECT name FROM materials WHERE id = 'M1'") == "PLA Plus"
    assert ask_database(database_file, "SELECT reorder_level FROM materials WHERE id = 'M1'") == 600
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 800
    assert ask_database(database_file, "SELECT unit FROM materials WHERE id = 'M1'") == "g"
    details = ask_database(database_file, "SELECT details FROM activity_log WHERE action = 'MATERIAL_CHANGED'")
    assert "reorder_level from 500.0 to 600.0" in details


def test_remove_keeps_the_row_and_history(admin, database_file):
    admin.post("/materials/M1/record/used", data={"quantity": "10"})
    admin.post("/materials/M1/remove")
    assert ask_database(database_file, "SELECT is_active FROM materials WHERE id = 'M1'") == 0
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements WHERE material_id = 'M1'") == 1
    assert "<td>PLA Basic</td>" not in admin.get("/materials/").get_data(as_text=True)
    assert admin.post("/materials/M1/record/used", data={"quantity": "10"}).status_code == 404
    assert ask_database(database_file, "SELECT COUNT(*) FROM activity_log WHERE action = 'MATERIAL_REMOVED'") == 1


# ---------- Search and filter (F3) ----------

# The Materials list has two sections (Filament & Resin = grams and resin bottles, then Other materials = alcohol, hardware ...). Inside EACH
# section it shows OK first, then LOW, then OUT (Ryan's test, 2026-11-26), and keeps names in A-Z order inside each group.
def test_materials_list_is_sorted_by_urgency(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.executemany(
        "INSERT INTO materials (id, name, material_type, colour, unit, quantity_on_hand, reorder_level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("M4", "AAA Nuts", "Hardware", "Steel", "pcs", 900, 100),     # Other materials, OK
         ("M5", "ZZZ Resin", "Resin", "Grey", "ml", 0, 100)])           # Filament & Resin section, OUT (a resin bottle)
    connection.commit()
    connection.close()
    page = admin.get("/materials/").get_data(as_text=True)
    hardware_start = page.index("<h2>Other materials")
    sections = {"Filament": page[page.index("<h2>Filament"):hardware_start], "Hardware": page[hardware_start:]}   # second section = Other materials
    expected_order = {"Filament": ["PLA Basic", "PETG", "ABS", "ZZZ Resin"],   # OK, LOW, OUT, OUT (A-Z); resin sits with the filament
                      "Hardware": ["AAA Nuts"]}
    for section, names in expected_order.items():
        positions = [sections[section].index('data-label="Name"><span class="m-name">' + name) for name in names]
        assert positions == sorted(positions), section
    assert 'data-label="Name"><span class="m-name">AAA Nuts' not in sections["Filament"]       # pieces never appear in the filament section
    assert 'data-label="Name"><span class="m-name">ZZZ Resin' not in sections["Hardware"]       # resin never sits with the hardware


def test_search_and_status_filter(employee):
    page = employee.get("/materials/?q=petg").get_data(as_text=True)
    assert "PETG" in page and "PLA Basic" not in page
    page = employee.get("/materials/?status=LOW").get_data(as_text=True)
    assert "PETG" in page and "PLA Basic" not in page and "ABS" not in page
    page = employee.get("/materials/?status=OUT").get_data(as_text=True)
    assert "ABS" in page and "PETG" not in page


def test_search_treats_percent_as_plain_letter(employee):
    assert "No materials found" in employee.get("/materials/?q=%25").get_data(as_text=True)


# ---------- Record received: supplier and total paid (Admin only; feeds the "money spent" numbers) ----------

def test_admin_received_saves_supplier_and_total_paid(admin, database_file):
    reply = admin.post("/materials/M1/record/received",
                       data={"quantity": "1000", "supplier_id": "S1", "total_cost": "75.50"})
    assert reply.status_code == 302
    row = ask_database(database_file, "SELECT supplier_id || '|' || total_cost_myr FROM stock_movements "
                                      "WHERE movement_type = 'RECEIVED'")
    assert row == "S1|75.5"
    log = ask_database(database_file, "SELECT details FROM activity_log WHERE action = 'STOCK_RECEIVED'")
    assert "Paid MYR 75.50 to Shop" in log


def test_received_without_supplier_or_cost_still_works_for_both_roles(admin, employee, database_file):
    assert admin.post("/materials/M1/record/received", data={"quantity": "10"}).status_code == 302
    assert employee.post("/materials/M1/record/received", data={"quantity": "10"}).status_code == 302
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements WHERE total_cost_myr IS NOT NULL") == 0
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 820


@pytest.mark.parametrize("form", [
    {"quantity": "100", "supplier_id": "S1", "total_cost": "50"},
    {"quantity": "100", "total_cost": "50"},
    {"quantity": "100", "supplier_id": "S1"},
])
def test_employee_typing_money_is_refused_and_nothing_changes(employee, database_file, form):
    assert employee.post("/materials/M1/record/received", data=form).status_code == 403
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 800
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements") == 0


@pytest.mark.parametrize("form", [
    {"quantity": "100", "total_cost": "50"},                                    # money but no supplier
    {"quantity": "100", "supplier_id": "S1", "total_cost": "abc"},              # letters
    {"quantity": "100", "supplier_id": "S1", "total_cost": "-5"},               # negative
    {"quantity": "100", "supplier_id": "NOPE", "total_cost": "5"},              # unknown supplier
])
def test_admin_bad_money_input_is_rejected_and_changes_nothing(admin, database_file, form):
    assert admin.post("/materials/M1/record/received", data=form).status_code == 400
    assert ask_database(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'") == 800
    assert ask_database(database_file, "SELECT COUNT(*) FROM stock_movements") == 0


def test_money_boxes_show_for_admin_received_only(admin, employee, database_file):
    admin.post("/materials/M1/record/used", data={"quantity": "100", "supplier_id": "S1", "total_cost": "9"})
    assert ask_database(database_file, "SELECT total_cost_myr FROM stock_movements") is None
    assert 'name="total_cost"' in admin.get("/materials/M1/record/received").get_data(as_text=True)
    assert 'name="total_cost"' not in admin.get("/materials/M1/record/used").get_data(as_text=True)
    assert 'name="total_cost"' not in employee.get("/materials/M1/record/received").get_data(as_text=True)


# ---------- Low-stock events (feeds the Statistics line chart) ----------

def count_events(database_file):
    return ask_database(database_file, "SELECT COUNT(*) FROM low_stock_events")


def test_used_that_drops_ok_to_low_saves_one_event(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "400"})      # 800 -> 400 (LOW, level 500)
    assert count_events(database_file) == 1
    row = ask_database(database_file, "SELECT material_id || '|' || status || '|' || quantity_at_event || '|' || "
                                      "reorder_level_at_event FROM low_stock_events")
    assert row == "M1|LOW|400.0|500.0"
    linked = ask_database(database_file, "SELECT m.movement_type FROM low_stock_events e "
                                         "JOIN stock_movements m ON m.id = e.movement_id")
    assert linked == "USED"                       # the event points to the Record used line that caused it
    assert ask_database(database_file, "SELECT COUNT(*) FROM activity_log WHERE action = 'LOW_STOCK_EVENT'") == 1


def test_further_drops_while_low_do_not_save_more_events(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "400"})      # OK -> LOW (event)
    employee.post("/materials/M1/record/used", data={"quantity": "100"})      # LOW -> LOW
    employee.post("/materials/M1/record/used", data={"quantity": "300"})      # LOW -> OUT (not counted)
    assert count_events(database_file) == 1


def test_used_that_stays_ok_and_received_stock_save_no_event(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "100"})      # 700, still OK
    employee.post("/materials/M2/record/received", data={"quantity": "1000"})
    assert count_events(database_file) == 0


def test_dropping_again_after_restocking_saves_a_second_event(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "400"})
    employee.post("/materials/M1/record/received", data={"quantity": "1000"})  # back to 1400 (OK)
    employee.post("/materials/M1/record/used", data={"quantity": "1000"})      # OK -> LOW again
    assert count_events(database_file) == 2


def test_refused_used_saves_no_event(employee, database_file):
    employee.post("/materials/M1/record/used", data={"quantity": "5000"})      # more than in stock
    assert count_events(database_file) == 0


# ---------- Add material with its supplier (Admin only, all optional) ----------

MATERIAL_BOXES = {"name": "Nylon", "material_type": "Nylon", "colour": "Black", "unit": "g",
                  "starting_quantity": "0", "reorder_level": "500"}
OFFER_BOXES = {"pack_size": "1000", "price_per_pack_myr": "88.50", "minimum_order_packs": "2",
               "shipping_cost_myr": "12", "lead_time_days": "3"}
NEW_SUPPLIER_BOXES = {"supplier_choice": "new", "new_name": "Borneo Filament", "new_supplier_type": "ONLINE",
                      "new_phone": "082-123456", "new_email": "sales@example.com"}


# Counts the rows of one table in the temporary database.
def count_rows(database_file, table_name):
    return ask_database(database_file, f"SELECT COUNT(*) FROM {table_name}")


def test_add_material_with_a_new_supplier_saves_everything(admin, database_file):
    reply = admin.post("/materials/new", data={**MATERIAL_BOXES, **NEW_SUPPLIER_BOXES, **OFFER_BOXES})
    assert reply.status_code == 302
    assert ask_database(database_file, "SELECT supplier_type FROM suppliers WHERE name = 'Borneo Filament'") == "ONLINE"
    assert ask_database(database_file, "SELECT phone FROM suppliers WHERE name = 'Borneo Filament'") == "082-123456"
    offer = sqlite3.connect(database_file).execute(
        "SELECT o.pack_unit, o.pack_size, o.price_per_pack_myr, o.minimum_order_packs, o.shipping_cost_myr, "
        "o.lead_time_days FROM supplier_offers o JOIN materials m ON m.id = o.material_id "
        "JOIN suppliers s ON s.id = o.supplier_id WHERE m.name = 'Nylon' AND s.name = 'Borneo Filament'").fetchone()
    assert offer == ("g", 1000.0, 88.5, 2, 12.0, 3)          # the offer takes the material's unit
    for action in ("MATERIAL_ADDED", "SUPPLIER_ADDED", "OFFER_ADDED"):
        assert ask_database(database_file, "SELECT COUNT(*) FROM activity_log WHERE action = ?", (action,)) == 1


def test_new_material_and_supplier_appear_in_find_supplier(admin, database_file):
    admin.post("/materials/new", data={**MATERIAL_BOXES, **NEW_SUPPLIER_BOXES, **OFFER_BOXES})
    material_id = ask_database(database_file, "SELECT id FROM materials WHERE name = 'Nylon'")
    page = admin.get(f"/suggest/{material_id}").get_data(as_text=True)
    assert "Borneo Filament" in page


def test_add_material_with_an_existing_supplier_adds_only_an_offer(admin, database_file):
    suppliers_before = count_rows(database_file, "suppliers")
    admin.post("/materials/new", data={**MATERIAL_BOXES, "supplier_choice": "S1", **OFFER_BOXES})
    assert count_rows(database_file, "suppliers") == suppliers_before
    assert ask_database(database_file, "SELECT COUNT(*) FROM supplier_offers o JOIN materials m ON m.id = o.material_id "
                                       "WHERE m.name = 'Nylon' AND o.supplier_id = 'S1'") == 1


def test_no_supplier_chosen_ignores_the_supplier_boxes(admin, database_file):
    admin.post("/materials/new", data={**MATERIAL_BOXES, "supplier_choice": "", "new_name": "Ignored", **OFFER_BOXES})
    assert ask_database(database_file, "SELECT COUNT(*) FROM materials WHERE name = 'Nylon'") == 1
    assert ask_database(database_file, "SELECT COUNT(*) FROM suppliers WHERE name = 'Ignored'") == 0
    assert count_rows(database_file, "supplier_offers") == 1             # only the one from the fixture


@pytest.mark.parametrize("changes,words", [
    ({"price_per_pack_myr": "abc"}, "price as a number"),
    ({"price_per_pack_myr": "-5"}, "price must be a number"),
    ({"lead_time_days": ""}, "lead time in days as a number"),
    ({"minimum_order_packs": "0"}, "minimum order must be a number"),
    ({"new_name": ""}, "fill in the supplier name"),
    ({"new_name": "Shop" * 40}, "too long"),
    ({"new_supplier_type": "SPACE"}, "ONLINE or LOCAL"),
    ({"new_name": "shop"}, "already exists"),        # the fixture already has a supplier called "Shop"
])
def test_bad_supplier_boxes_save_nothing_and_explain_in_plain_words(admin, database_file, changes, words):
    materials_before = count_rows(database_file, "materials")
    suppliers_before = count_rows(database_file, "suppliers")
    reply = admin.post("/materials/new", data={**MATERIAL_BOXES, **NEW_SUPPLIER_BOXES, **OFFER_BOXES, **changes})
    assert reply.status_code == 400 and words in reply.get_data(as_text=True)
    assert count_rows(database_file, "materials") == materials_before
    assert count_rows(database_file, "suppliers") == suppliers_before


def test_problem_re_shows_the_typed_supplier_details(admin):
    page = admin.post("/materials/new", data={**MATERIAL_BOXES, **NEW_SUPPLIER_BOXES, **OFFER_BOXES,
                                              "price_per_pack_myr": "abc"}).get_data(as_text=True)
    assert "Borneo Filament" in page and "082-123456" in page and "abc" in page


def test_unknown_or_switched_off_supplier_is_refused(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO suppliers (id, name, supplier_type, is_active) VALUES ('S9', 'Closed', 'LOCAL', 0)")
    connection.commit()
    connection.close()
    for supplier_id in ("S9", "nobody"):
        reply = admin.post("/materials/new", data={**MATERIAL_BOXES, "supplier_choice": supplier_id, **OFFER_BOXES})
        assert reply.status_code == 400 and "choose a supplier from the list" in reply.get_data(as_text=True)
    assert ask_database(database_file, "SELECT COUNT(*) FROM materials WHERE name = 'Nylon'") == 0


def test_form_lists_active_suppliers_only(admin, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO suppliers (id, name, supplier_type, is_active) VALUES ('S9', 'Closed Shop', 'LOCAL', 0)")
    connection.commit()
    connection.close()
    page = admin.get("/materials/new").get_data(as_text=True)
    assert "Who sells it?" in page and "Shop (LOCAL)" in page and "Closed Shop" not in page


def test_employee_cannot_add_a_material_or_supplier_this_way(employee, database_file):
    suppliers_before = count_rows(database_file, "suppliers")
    assert employee.get("/materials/new").status_code == 403
    reply = employee.post("/materials/new", data={**MATERIAL_BOXES, **NEW_SUPPLIER_BOXES, **OFFER_BOXES})
    assert reply.status_code == 403
    assert count_rows(database_file, "suppliers") == suppliers_before
    assert ask_database(database_file, "SELECT COUNT(*) FROM materials WHERE name = 'Nylon'") == 0


# Layout guard (bug fix 2026-11-27): the Actions buttons on the Materials rows, including the ones under "More"
# (Edit, Correct stock, Remove), must be ONE vertical column of equal width, so "Correct stock" is never cut off.
def test_materials_row_buttons_are_one_stretched_column_in_the_css():
    import re
    css_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "theme.css")
    with open(css_file, encoding="utf-8") as css_text:
        css = css_text.read()
    for selector in (".row-actions", ".row-more", ".row-more-menu"):
        rule = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", css, re.MULTILINE)
        assert rule is not None, selector
        assert "flex-direction: column" in rule.group(1) and "align-items: stretch" in rule.group(1), selector
    page_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "templates", "materials_list.html")
    with open(page_file, encoding="utf-8") as page_text:
        page = page_text.read()
    assert "align-items: flex-start" not in page.split(".row-actions", 1)[1].split("}", 1)[0]    # the page rule must not undo the stretch

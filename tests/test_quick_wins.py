# WHAT THIS FILE DOES: Checks the five "quick wins" of 2026-11-27: contact links, Find supplier for every material,
#   "New sealed spool / bottle" on Record received, Admin-only Edit quantity (stock correction), and the kept search plus Quick log.
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import os
import re
import sqlite3
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, contact_links, create_app, routes_stats   # noqa: E402

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
PASSWORD = "test-password-123"
LONG_AGO = "2026-01-01"


# Builds a temporary database: Admin + Employee, a filament spool (opened long ago), a resin bottle, hardware, an OK
# material, suppliers with real-looking phone numbers and emails, offers, one USED and one RECEIVED line.
@pytest.fixture
def database_file(tmp_path):
    path = str(tmp_path / "test.db")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    with open(SCHEMA_FILE, encoding="utf-8") as schema:
        connection.executescript(schema.read())
    connection.executescript(f"""
        INSERT INTO users (id, username, role) VALUES ('U1', 'boss', 'ADMIN'), ('U2', 'worker', 'EMPLOYEE');
        INSERT INTO materials (id, name, material_type, colour, unit, quantity_on_hand, reorder_level, opened_date, last_dried_date) VALUES
          ('M1', 'PLA Basic', 'PLA', 'White', 'g', 430, 500, '{LONG_AGO}', '{LONG_AGO}'),
          ('M2', 'PETG', 'PETG', 'Clear', 'g', 900, 500, NULL, NULL),
          ('M3', 'Standard Resin', 'Resin', 'Grey', 'ml', 800, 200, '{LONG_AGO}', NULL),
          ('M4', 'M4 Screws', 'Hardware', '', 'pcs', 300, 100, NULL, NULL);
        INSERT INTO suppliers (id, name, supplier_type, phone, email, is_active) VALUES
          ('S1', 'Local Shop', 'LOCAL', '082-111 222', 'sales@localshop.example', 1),
          ('S2', 'Online Shop', 'ONLINE', '+60 3-7890 1120', 'not an email', 1),
          ('S3', 'Short Phone Shop', 'LOCAL', '082-111', '', 1);
        INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr,
            minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES
          ('O1', 'S1', 'M1', 1000, 'g', 72.00, 1, 0, 1), ('O2', 'S2', 'M1', 1000, 'g', 70.00, 1, 5, 3),
          ('O3', 'S1', 'M2', 1000, 'g', 72.00, 1, 0, 1), ('O4', 'S3', 'M2', 1000, 'g', 60.00, 1, 0, 2);
    """)
    now_text = datetime.utcnow().strftime(auth.TIME_FORMAT)
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at) "
                       "VALUES ('SU1', 'M2', 'USED', 300, 'U1', ?)", (now_text,))
    connection.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, "
                       "supplier_id, total_cost_myr) VALUES ('SR1', 'M2', 'RECEIVED', 1000, 'U1', ?, 'S1', 72)", (now_text,))
    auth.set_password(connection, "boss", PASSWORD)
    auth.set_password(connection, "worker", PASSWORD)
    connection.commit()
    connection.close()
    return path


# Returns a browser logged in as the given user (CSRF switched off, like the other test files).
def browser_for(database_file, username):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    client = website.test_client()
    client.post("/login", data={"username": username, "password": PASSWORD})
    return client


# Returns a browser with CSRF switched ON, already logged in as the user id, holding the known token "abc123".
def browser_with_csrf(database_file, user_id):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "k", "TESTING": True, "CSRF_ENABLED": True})
    client = website.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["csrf_token"] = "abc123"
    return client


@pytest.fixture
def admin(database_file):
    return browser_for(database_file, "boss")


@pytest.fixture
def employee(database_file):
    return browser_for(database_file, "worker")


# Returns rows of a query as dictionaries.
def rows(database_file, sql, args=()):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    result = [dict(row) for row in connection.execute(sql, args).fetchall()]
    connection.close()
    return result


# Returns the page text of an address.
def page(client, address):
    return client.get(address).get_data(as_text=True)


# =====================================================================================================
# 1. Tap-able contact links
# =====================================================================================================

def test_phone_digits_and_whatsapp_address_rules():
    assert contact_links.get_whatsapp_address("082-111 222") == "https://wa.me/6082111222"      # local 0 becomes 60
    assert contact_links.get_whatsapp_address("+60 3-7890 1120") == "https://wa.me/60378901120"  # + and spaces stripped
    assert contact_links.get_whatsapp_address("0060 12 345 6789") == "https://wa.me/60123456789"
    assert contact_links.get_tel_address("+60 3-7890 1120") == "tel:+60378901120"
    assert contact_links.get_tel_address("082-111 222") == "tel:082111222"
    assert contact_links.get_whatsapp_address("082-111") == "" and contact_links.get_tel_address("call us") == ""
    assert contact_links.get_whatsapp_address(None) == "" and contact_links.get_mailto_address("not an email") == ""
    assert contact_links.get_mailto_address(" a@b.example ") == "mailto:a@b.example"


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_suppliers_list_has_tel_whatsapp_and_mailto_links(who, request):
    text = page(request.getfixturevalue(who), "/suppliers")
    assert 'href="tel:082111222"' in text and 'href="https://wa.me/6082111222"' in text
    assert 'href="tel:+60378901120"' in text and 'href="https://wa.me/60378901120"' in text
    assert 'href="mailto:sales@localshop.example"' in text
    assert "WhatsApp" in text


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_supplier_page_and_find_supplier_have_the_links(who, request):
    client = request.getfixturevalue(who)
    for address in ("/suppliers/S1", "/suggest/M1"):
        text = page(client, address)
        assert 'href="tel:082111222"' in text and 'href="https://wa.me/6082111222"' in text, address
        assert 'href="mailto:sales@localshop.example"' in text, address


def test_values_that_are_not_phones_or_emails_stay_plain_text(admin):
    text = page(admin, "/suppliers")
    assert "not an email" in text and "mailto:not" not in text
    assert "082-111</td>" in text and "wa.me/82111" not in text and "tel:082111<" not in text     # too short: plain text
    assert "wa.me/" not in page(admin, "/suppliers/S3")


# =====================================================================================================
# 2. Find supplier for every material
# =====================================================================================================

@pytest.mark.parametrize("who", ["admin", "employee"])
def test_every_material_row_has_a_find_supplier_button(who, request):
    text = page(request.getfixturevalue(who), "/materials/")
    for material_id in ("M1", "M2", "M3", "M4"):                          # LOW (M1) and OK (M2, M3, M4) alike
        assert f'href="/suggest/{material_id}"' in text


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_find_supplier_for_an_ok_material_compares_suppliers(who, request):
    text = page(request.getfixturevalue(who), "/suggest/M2")
    assert "nothing to order" in text and "Local Shop" in text and "Short Phone Shop" in text
    assert text.index("Short Phone Shop") > 0


def test_find_supplier_for_ok_material_ranks_cheapest_first_and_employee_prices_follow_the_old_rule(admin, employee):
    admin_text = page(admin, "/suggest/M2")
    assert admin_text.index("Short Phone Shop") < admin_text.index("Local Shop")      # MYR 60 beats MYR 72
    assert "MYR 60.00" in admin_text


def test_find_supplier_for_material_without_offers_says_so(admin, database_file):
    assert "No supplier can deliver" in page(admin, "/suggest/M4")


# =====================================================================================================
# 3. "New sealed spool / bottle" on Record received
# =====================================================================================================

def test_checkbox_only_for_filament_and_resin_received(admin):
    for material_id in ("M1", "M3"):
        assert 'name="new_sealed"' in page(admin, f"/materials/{material_id}/record/received")
    assert "New sealed spool (reset opened &amp; dried dates)" in page(admin, "/materials/M1/record/received")
    assert "New sealed bottle (reset opened &amp; dried dates)" in page(admin, "/materials/M3/record/received")
    assert 'name="new_sealed"' not in page(admin, "/materials/M4/record/received")         # hardware
    assert 'name="new_sealed"' not in page(admin, "/materials/M1/record/used")             # used form


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_ticking_it_clears_both_dates_and_the_chip_says_sealed(who, request, database_file):
    client = request.getfixturevalue(who)
    assert "put in dryer" in page(client, "/materials/").lower()                              # warning before
    client.post("/materials/M1/record/received", data={"quantity": "1000", "new_sealed": "yes"})
    row = rows(database_file, "SELECT * FROM materials WHERE id = 'M1'")[0]
    assert row["opened_date"] is None and row["last_dried_date"] is None and row["quantity_on_hand"] == 1430
    assert "Sealed" in page(client, "/materials/")
    assert "put in dryer" not in page(client, "/materials/").lower()
    log = rows(database_file, "SELECT * FROM activity_log WHERE action = 'SPOOL_RESET'")
    assert len(log) == 1 and "M1" == log[0]["record_id"]


def test_not_ticking_keeps_the_old_dates(admin, database_file):
    admin.post("/materials/M1/record/received", data={"quantity": "1000"})
    row = rows(database_file, "SELECT * FROM materials WHERE id = 'M1'")[0]
    assert row["opened_date"] == LONG_AGO and row["last_dried_date"] == LONG_AGO
    assert rows(database_file, "SELECT * FROM activity_log WHERE action = 'SPOOL_RESET'") == []


def test_resin_bottle_reset_and_hardware_ignores_the_box(admin, database_file):
    admin.post("/materials/M3/record/received", data={"quantity": "500", "new_sealed": "yes"})
    assert rows(database_file, "SELECT opened_date FROM materials WHERE id = 'M3'")[0]["opened_date"] is None
    admin.post("/materials/M4/record/received", data={"quantity": "50", "new_sealed": "yes"})
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M4'")[0]["quantity_on_hand"] == 350
    assert len(rows(database_file, "SELECT * FROM activity_log WHERE action = 'SPOOL_RESET'")) == 1


def test_a_refused_receive_does_not_reset_the_dates(admin, database_file):
    response = admin.post("/materials/M1/record/received", data={"quantity": "abc", "new_sealed": "yes"})
    assert response.status_code == 400
    assert rows(database_file, "SELECT opened_date FROM materials WHERE id = 'M1'")[0]["opened_date"] == LONG_AGO


def test_used_never_resets_the_dates(admin, database_file):
    admin.post("/materials/M1/record/used", data={"quantity": "10", "new_sealed": "yes"})
    assert rows(database_file, "SELECT opened_date FROM materials WHERE id = 'M1'")[0]["opened_date"] == LONG_AGO


# =====================================================================================================
# 4. Admin-only stock correction
# =====================================================================================================

def correct(client, material_id, new_quantity, reason="Physical shelf count"):
    return client.post(f"/materials/{material_id}/correct", data={"new_quantity": new_quantity, "reason": reason})


def test_admin_can_open_the_edit_quantity_page_and_it_has_a_help_sentence(admin):
    text = page(admin, "/materials/M1/correct")
    assert "Edit quantity" in text and "Correct stock" not in text and "Save quantity" in text
    assert "Set stock to" in text and "Reason (required)" in text and "nothing is deleted" in text


def test_correcting_down_sets_the_quantity_and_writes_one_adjusted_line(admin, database_file):
    response = correct(admin, "M2", "850", "Damaged spool")
    assert response.status_code == 302
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 850
    line = rows(database_file, "SELECT * FROM stock_movements WHERE movement_type = 'ADJUSTED'")[0]
    assert line["quantity"] == 50 and line["material_id"] == "M2" and line["user_id"] == "U1"
    assert "900 -> 850" in line["note"] and "-50" in line["note"] and "Damaged spool" in line["note"]
    assert line["supplier_id"] is None and line["total_cost_myr"] is None
    log = rows(database_file, "SELECT * FROM activity_log WHERE action = 'STOCK_CORRECTED'")
    assert len(log) == 1 and "Damaged spool" in log[0]["details"] and log[0]["user_id"] == "U1"


def test_correcting_up_and_to_zero(admin, database_file):
    correct(admin, "M1", "600")
    correct(admin, "M1", "0", "Lost")
    lines = rows(database_file, "SELECT quantity, note FROM stock_movements WHERE movement_type = 'ADJUSTED' ORDER BY rowid")
    assert [line["quantity"] for line in lines] == [170, 600] and "+170" in lines[0]["note"] and "-600" in lines[1]["note"]
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M1'")[0]["quantity_on_hand"] == 0
    assert "OUT" in page(admin, "/materials/")


def test_history_shows_a_stock_correction_with_its_direction(admin):
    correct(admin, "M2", "850")
    text = page(admin, "/materials/M2/record/used")
    assert "Stock correction" in text and "-50 g" in text and "Starting stock" not in text


@pytest.mark.parametrize("quantity, reason", [("", "x"), ("abc", "x"), ("-5", "x"), ("900", "same number"),
                                              ("850", ""), ("850", "   "), ("850", "r" * 201), ("99999999", "big")])
def test_bad_corrections_are_refused_with_plain_words_and_change_nothing(admin, database_file, quantity, reason):
    before = rows(database_file, "SELECT * FROM stock_movements")
    response = correct(admin, "M2", quantity, reason)
    assert response.status_code == 400
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 900
    assert rows(database_file, "SELECT * FROM stock_movements") == before
    assert "problems" in response.get_data(as_text=True)


def test_employee_gets_403_on_the_correct_stock_page_and_save(employee, database_file):
    before = (rows(database_file, "SELECT * FROM materials"), rows(database_file, "SELECT * FROM stock_movements"),
              rows(database_file, "SELECT * FROM activity_log"))
    assert employee.get("/materials/M2/correct").status_code == 403
    assert correct(employee, "M2", "850").status_code == 403
    assert (rows(database_file, "SELECT * FROM materials"), rows(database_file, "SELECT * FROM stock_movements"),
            rows(database_file, "SELECT * FROM activity_log")) == before


def test_visitor_is_sent_to_login_and_nothing_changes(database_file):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "k", "TESTING": True, "CSRF_ENABLED": False})
    visitor = website.test_client()
    assert visitor.get("/materials/M2/correct").status_code == 302
    assert correct(visitor, "M2", "850").status_code == 302
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 900


def test_edit_quantity_button_is_only_drawn_for_the_admin(admin, employee):
    assert "/materials/M1/correct" in page(admin, "/materials/") and "Edit quantity" in page(admin, "/materials/")
    assert "Correct stock" not in page(admin, "/materials/")
    assert "/correct" not in page(employee, "/materials/") and "Edit quantity" not in page(employee, "/materials/")


def test_correct_stock_for_a_missing_material_is_404(admin):
    assert admin.get("/materials/NOPE/correct").status_code == 404


def stats_snapshot(database_file):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    snapshot = {"days_left": routes_stats.get_days_of_stock_left(connection),
                "spending": routes_stats.get_spending_and_stock_value(connection)["spent_total"],
                "by_supplier": routes_stats.get_spending_by_supplier(connection, routes_stats.period_start(routes_stats.malaysia_now(), "month")),
                "usage": routes_stats.get_usage_by_period(connection, "month"),
                "received": routes_stats.get_quantity_by_period(connection, "RECEIVED", "month")}
    connection.close()
    return snapshot


def test_adjusted_lines_do_not_change_usage_averages_or_spending(admin, database_file):
    before = stats_snapshot(database_file)
    assert before["days_left"] and before["spending"] == 72                        # the fixture has USED 300 and RECEIVED MYR 72
    correct(admin, "M2", "100", "Physical shelf count")                              # big correction DOWN
    correct(admin, "M2", "5000", "Found a box")                                      # big correction UP
    after = stats_snapshot(database_file)
    assert after["usage"] == before["usage"] and after["received"] == before["received"]
    assert after["spending"] == before["spending"] and after["by_supplier"] == before["by_supplier"]
    old, new = before["days_left"][0], after["days_left"][0]
    assert new["average_daily"] == old["average_daily"] == 300 / 30                  # the average still reads USED lines only
    assert new["stock"] == 5000 and new["days_left"] == 5000 / (300 / 30)            # only the stock number moved


def test_adjusted_lines_stay_out_of_the_csv_usage_and_purchase_rows(admin):
    before = admin.get("/stats/export.csv").get_data(as_text=True)
    correct(admin, "M2", "100")
    after = admin.get("/stats/export.csv").get_data(as_text=True)
    assert [line for line in after.splitlines() if "ADJUSTED" in line or "correction" in line.lower()] == []
    assert [l for l in before.splitlines() if "Spending" in l or "Usage" in l or "Purchases" in l] == \
           [l for l in after.splitlines() if "Spending" in l or "Usage" in l or "Purchases" in l]


def test_a_correction_never_writes_a_low_stock_event(admin, database_file):
    correct(admin, "M2", "100")                                                       # OK -> LOW by correction
    assert rows(database_file, "SELECT * FROM low_stock_events") == []


def test_correction_with_csrf_on_needs_the_token(database_file):
    client = browser_with_csrf(database_file, "U1")
    assert client.post("/materials/M2/correct", data={"new_quantity": "850", "reason": "x"}).status_code == 400
    assert client.post("/materials/M2/correct", data={"new_quantity": "850", "reason": "x", "csrf_token": "abc123"}).status_code == 302
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 850
    assert 'name="csrf_token"' in client.get("/materials/M2/correct").get_data(as_text=True)


# =====================================================================================================
# 5. Search kept after Record used, and Quick log
# =====================================================================================================

def test_record_used_returns_to_the_same_search(admin, database_file):
    response = admin.post("/materials/M2/record/used?q=PETG&status=OK", data={"quantity": "10"})
    assert response.status_code == 302
    assert "q=PETG" in response.headers["Location"] and "status=OK" in response.headers["Location"]
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 890


def test_record_received_returns_to_the_same_search_too(employee):
    response = employee.post("/materials/M2/record/received?q=PETG", data={"quantity": "10"})
    assert "q=PETG" in response.headers["Location"]


def test_without_a_search_the_old_redirect_is_unchanged(admin):
    response = admin.post("/materials/M2/record/used", data={"quantity": "10"})
    assert response.headers["Location"].rstrip("?").endswith("/materials/")


def test_a_wrong_status_in_the_address_is_ignored_and_long_search_is_cut(admin):
    response = admin.post("/materials/M2/record/used?status=EVIL&q=" + "a" * 500, data={"quantity": "10"})
    location = response.headers["Location"]
    assert "EVIL" not in location and "a" * 101 not in location


def test_materials_list_passes_the_search_to_the_record_links_and_cancel_goes_back(admin):
    text = page(admin, "/materials/?q=PETG")
    assert "/materials/M2/record/used?q=PETG" in text and "/materials/M2/record/received?q=PETG" in text
    assert 'href="/materials/?q=PETG"' in page(admin, "/materials/M2/record/used?q=PETG")      # Cancel keeps the search


def test_a_failed_record_used_keeps_you_on_the_form_with_the_search_still_in_the_address(admin):
    response = admin.post("/materials/M2/record/used?q=PETG", data={"quantity": "99999"})
    assert response.status_code == 400 and 'href="/materials/?q=PETG"' in response.get_data(as_text=True)


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_quick_log_page_lists_materials_and_filters_by_search(who, request):
    client = request.getfixturevalue(who)
    text = page(client, "/quick-log")
    assert "Record used" in text and "PLA Basic" in text and "M4 Screws" in text
    narrowed = page(client, "/quick-log?q=PETG")
    assert "PETG" in narrowed and "PLA Basic" not in narrowed
    assert "MYR" not in text and "price" not in text.lower()


@pytest.mark.parametrize("who", ["admin", "employee"])
def test_quick_log_records_used_and_answers_json_without_leaving_the_page(who, request, database_file):
    client = request.getfixturevalue(who)
    response = client.post("/quick-log/M2", data={"quantity": "100"}, headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True and data["left"] == "800 g" and data["status"] == "OK"
    line = rows(database_file, "SELECT * FROM stock_movements WHERE note = 'Quick log'")[0]
    assert line["movement_type"] == "USED" and line["quantity"] == 100 and line["material_id"] == "M2"
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 800
    assert len(rows(database_file, "SELECT * FROM activity_log WHERE action = 'STOCK_USED'")) == 1


def test_quick_log_status_changes_and_low_stock_event_is_written(admin, database_file):
    data = admin.post("/quick-log/M2", data={"quantity": "450"}, headers={"Accept": "application/json"}).get_json()
    assert data["status"] == "LOW" and data["left"] == "450 g"
    assert len(rows(database_file, "SELECT * FROM low_stock_events")) == 1


def test_quick_log_refuses_more_than_in_stock_and_bad_numbers(admin, database_file):
    for bad in ("5000", "abc", "-1", "0", ""):
        response = admin.post("/quick-log/M2", data={"quantity": bad}, headers={"Accept": "application/json"})
        assert response.status_code == 400 and response.get_json()["ok"] is False and response.get_json()["problems"]
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 900
    assert rows(database_file, "SELECT * FROM stock_movements WHERE note = 'Quick log'") == []


def test_quick_log_without_javascript_redirects_back_with_the_search(admin, database_file):
    response = admin.post("/quick-log/M2", data={"quantity": "10", "q": "PETG"})
    assert response.status_code == 302 and "/quick-log" in response.headers["Location"] and "q=PETG" in response.headers["Location"]
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 890


def test_quick_log_needs_login_and_is_post_only(database_file, admin):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "k", "TESTING": True, "CSRF_ENABLED": False})
    visitor = website.test_client()
    assert visitor.get("/quick-log").status_code == 302
    assert visitor.post("/quick-log/M2", data={"quantity": "10"}).status_code == 302
    assert rows(database_file, "SELECT quantity_on_hand FROM materials WHERE id = 'M2'")[0]["quantity_on_hand"] == 900
    assert admin.get("/quick-log/M2").status_code == 405
    assert admin.post("/quick-log/NOPE", data={"quantity": "1"}).status_code == 404


def test_quick_log_checks_the_csrf_token_and_accepts_the_header(database_file):
    client = browser_with_csrf(database_file, "U2")                                  # an Employee
    assert client.post("/quick-log/M2", data={"quantity": "10"}).status_code == 400            # no token: refused
    assert rows(database_file, "SELECT * FROM stock_movements WHERE note = 'Quick log'") == []
    ok = client.post("/quick-log/M2", data={"quantity": "10"}, headers={"X-CSRF-Token": "abc123", "Accept": "application/json"})
    assert ok.status_code == 200 and ok.get_json()["left"] == "890 g"
    assert 'name="csrf_token"' in client.get("/quick-log").get_data(as_text=True)


def test_materials_page_links_to_quick_log_with_the_search(admin):
    assert 'href="/quick-log?q=PETG"' in page(admin, "/materials/?q=PETG")
    assert 'href="/quick-log"' in page(admin, "/materials/")

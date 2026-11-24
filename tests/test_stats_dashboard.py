# WHAT THIS FILE DOES: Automatic checks for the Home dashboard boxes, the Statistics screen, the CSV download
#   and the rule that Employees never see money (guide Sections 4, 5 F2 and F7, 14).
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db).

import os
import sqlite3
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, routes_stats                     # noqa: E402

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "schema.sql")
PASSWORD = "test-password-123"
NOW = datetime(2026, 11, 23, 10, 0)    # a fixed "today" in Malaysia time (a Monday)


# Builds a temporary database: OK, LOW and OUT materials, two suppliers, offers and some history.
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
        "INSERT INTO suppliers (id, name, supplier_type) VALUES (?, ?, ?)",
        [("S1", "Kuching Shop", "LOCAL"), ("S2", "Web Store", "ONLINE")])
    connection.executemany(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "lead_time_days) VALUES (?, ?, ?, 1000, 'g', ?, ?)",
        [("O1", "S1", "M1", 80.0, 1), ("O2", "S1", "M2", 90.0, 3), ("O3", "S2", "M1", 60.0, 7)])
    auth.set_password(connection, "boss", PASSWORD)
    auth.set_password(connection, "worker", PASSWORD)
    connection.commit()
    connection.close()
    return path


# Adds one stock movement row to the temporary database (time is UTC text).
def add_movement(database_file, movement_id, material_id, kind, quantity, utc_text):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at) "
        "VALUES (?, ?, ?, ?, 'U1', ?)", (movement_id, material_id, kind, quantity, utc_text))
    connection.commit()
    connection.close()


# Opens the temporary database for the calculation functions.
def open_database(database_file):
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    return connection


# Builds the real website pointed at the temporary database.
@pytest.fixture
def website(database_file):
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True})


# Returns a test browser that is logged in as the given user.
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


# ---------- Home boxes (F2) ----------

def test_home_boxes_show_counts_with_words(admin):
    page = admin.get("/").get_data(as_text=True)
    assert "Total materials" in page and ">3<" in page
    assert "LOW</span> on stock" in page and "OUT</span> of stock" in page
    assert page.count('class="number">1<') == 2


def test_home_needs_attention_lists_low_and_out_with_find_supplier(employee):
    page = employee.get("/").get_data(as_text=True)
    assert "PETG Clear" in page and "ABS Grey" in page and "PLA Basic" not in page
    assert 'href="/suggest/M2"' in page and 'href="/suggest/M3"' in page
    assert page.index("ABS Grey") < page.index("PETG Clear")     # OUT is listed before LOW


def test_home_admin_sees_money_box(admin):
    page = admin.get("/").get_data(as_text=True)
    assert "Estimated money spent" in page


def test_home_employee_sees_money_box(employee):
    # Team decision 2026-11-24: employees may SEE prices and money totals (only Admin can change them).
    page = employee.get("/").get_data(as_text=True)
    assert "Estimated money spent" in page


def test_home_needs_login(website):
    assert website.test_client().get("/").status_code == 302


# ---------- Employee blocked pages (Section 4, 14) ----------

@pytest.mark.parametrize("address", ["/stats/export.csv", "/stats/data/spending"])
def test_employee_gets_403_on_money_addresses(employee, address):
    assert employee.get(address).status_code == 403


@pytest.mark.parametrize("address", ["/stats/export.csv", "/stats/data/spending", "/stats/", "/stats/data/usage"])
def test_not_logged_in_is_sent_to_login(website, address):
    assert website.test_client().get(address).status_code == 302


def test_admin_can_download_csv(admin):
    answer = admin.get("/stats/export.csv")
    assert answer.status_code == 200 and answer.mimetype == "text/csv"
    assert "Report,Name,Period,Value,Unit" in answer.get_data(as_text=True)


def test_employee_statistics_page_has_no_money_or_download(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert "MYR" not in page and "Spending" not in page and "export.csv" not in page
    assert "Usage per material" in page and "Average delivery time" in page


def test_admin_statistics_page_has_spending_and_download(admin):
    page = admin.get("/stats/").get_data(as_text=True)
    assert "Spending per supplier" in page and "/stats/export.csv" in page


@pytest.mark.parametrize("address", ["/stats/data/usage", "/stats/data/lead-times", "/stats/data/low-stock"])
def test_employee_chart_data_has_no_prices(employee, database_file, address):
    add_movement(database_file, "X1", "M1", "USED", 100, "2026-11-20 01:00:00")
    text = employee.get(address).get_data(as_text=True).lower()
    for word in ("price", "myr", "cost", "shipping", "80.0", "90.0"):
        assert word not in text


# ---------- Usage chart (F7) ----------

def test_usage_by_month_adds_used_rows_only(database_file):
    add_movement(database_file, "A", "M1", "USED", 200, "2026-11-10 02:00:00")
    add_movement(database_file, "B", "M1", "USED", 50, "2026-11-12 02:00:00")
    add_movement(database_file, "C", "M1", "RECEIVED", 999, "2026-11-12 02:00:00")
    chart = routes_stats.get_usage_by_period(open_database(database_file), "month", NOW)
    assert chart["labels"][-1] == "Nov 2026" and len(chart["labels"]) == 6
    assert chart["datasets"] == [{"label": "PLA Basic White (g)", "data": [0, 0, 0, 0, 0, 250]}]


def test_usage_by_week_starts_on_monday(database_file):
    add_movement(database_file, "A", "M1", "USED", 30, "2026-11-16 20:00:00")   # Mon 17 Nov 04:00 Malaysia
    add_movement(database_file, "B", "M1", "USED", 70, "2026-11-23 01:00:00")   # Mon 23 Nov 09:00 Malaysia
    chart = routes_stats.get_usage_by_period(open_database(database_file), "week", NOW)
    assert chart["labels"][-2:] == ["Week of 16 Nov", "Week of 23 Nov"]
    assert chart["datasets"][0]["data"][-2:] == [30, 70]


def test_usage_uses_malaysia_time_for_the_month(database_file):
    add_movement(database_file, "A", "M1", "USED", 40, "2026-10-31 17:00:00")   # 1 Nov 01:00 in Malaysia
    chart = routes_stats.get_usage_by_period(open_database(database_file), "month", NOW)
    assert chart["datasets"][0]["data"][-2:] == [0, 40]


def test_usage_chart_json_is_served(admin, database_file):
    add_movement(database_file, "A", "M1", "USED", 40, "2026-11-20 02:00:00")
    answer = admin.get("/stats/data/usage?period=month").get_json()
    assert answer["datasets"][0]["label"] == "PLA Basic White (g)"


# ---------- Average lead time (F7) ----------

def test_average_lead_time_per_supplier(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, "
                       "price_per_pack_myr, lead_time_days) VALUES ('O9', 'S1', 'M3', 1000, 'g', 50, 2)")
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, "
                       "price_per_pack_myr, lead_time_days, is_active) VALUES ('O8', 'S1', 'M3', 1000, 'g', 50, 30, 0)")
    connection.commit()
    connection.close()
    chart = routes_stats.get_average_lead_times(open_database(database_file))
    assert dict(zip(chart["labels"], chart["days"])) == {"Kuching Shop (local)": 2.0, "Web Store (online)": 7.0}


# ---------- Proposed methods (switched off until the team answers) ----------

# Adds a RECEIVED line with a supplier and a total paid (UTC time text).
def add_purchase(database_file, movement_id, supplier_id, total_cost, utc_text, kind="RECEIVED"):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, supplier_id, "
        "total_cost_myr) VALUES (?, 'M1', ?, 1000, 'U1', ?, ?, ?)", (movement_id, kind, utc_text, supplier_id, total_cost))
    connection.commit()
    connection.close()


def test_spending_adds_up_real_totals_per_supplier_for_this_month_only(database_file):
    add_purchase(database_file, "A", "S2", 120.5, "2026-11-05 02:00:00")
    add_purchase(database_file, "B", "S2", 30, "2026-11-20 02:00:00")
    add_purchase(database_file, "C", "S1", 80, "2026-11-21 02:00:00")
    add_purchase(database_file, "D", "S1", 999, "2026-10-05 02:00:00")                 # other month
    add_purchase(database_file, "E", "S1", 500, "2026-11-06 02:00:00", kind="USED")    # used is not spending
    add_movement(database_file, "F", "M1", "RECEIVED", 1000, "2026-11-07 02:00:00")    # no total typed: skipped
    spending = routes_stats.get_spending_by_supplier(open_database(database_file), date(2026, 11, 1))
    assert spending == {"Web Store": 150.5, "Kuching Shop": 80.0}


def test_spending_month_uses_malaysia_time(database_file):
    add_purchase(database_file, "A", "S1", 40, "2026-10-31 17:00:00")    # 1 Nov 01:00 in Malaysia
    spending = routes_stats.get_spending_by_supplier(open_database(database_file), date(2026, 11, 1))
    assert spending == {"Kuching Shop": 40.0}


def test_spending_chart_and_home_box_show_real_money(admin, employee, database_file, monkeypatch):
    monkeypatch.setattr(routes_stats, "malaysia_now", lambda: NOW)
    add_purchase(database_file, "A", "S2", 120.5, "2026-11-05 02:00:00")
    assert admin.get("/stats/data/spending").get_json() == {"labels": ["Web Store"], "amounts": [120.5]}
    assert "MYR 120.50" in admin.get("/").get_data(as_text=True)
    assert "MYR 120.50" in employee.get("/").get_data(as_text=True)
    assert employee.get("/stats/data/spending").status_code == 403


# Adds one saved low-stock event (time is UTC text).
def add_low_event(database_file, event_id, material_id, utc_text):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO low_stock_events (id, material_id, status_after, quantity_after, reorder_level, created_at) "
        "VALUES (?, ?, 'LOW', 400, 500, ?)", (event_id, material_id, utc_text))
    connection.commit()
    connection.close()


def test_low_events_are_counted_per_malaysia_month(database_file):
    add_low_event(database_file, "A", "M1", "2026-11-02 01:00:00")
    add_low_event(database_file, "B", "M2", "2026-11-20 01:00:00")
    add_low_event(database_file, "C", "M1", "2026-10-31 17:00:00")    # 1 Nov 01:00 in Malaysia
    add_low_event(database_file, "D", "M1", "2026-12-02 01:00:00")
    events = routes_stats.count_low_stock_events(open_database(database_file))
    assert events == {date(2026, 11, 1): 3, date(2026, 12, 1): 1}


def test_low_stock_chart_reads_saved_events_for_both_roles(admin, employee, database_file, monkeypatch):
    monkeypatch.setattr(routes_stats, "malaysia_now", lambda: NOW)
    add_low_event(database_file, "A", "M1", "2026-11-02 01:00:00")
    for browser in (admin, employee):
        chart = browser.get("/stats/data/low-stock").get_json()
        assert chart["labels"][-1] == "Nov 2026" and chart["counts"][-1] == 1
        assert "Not set up yet" not in browser.get("/stats/").get_data(as_text=True)


def test_money_text_format():
    assert routes_stats.format_money(72) == "MYR 72.00"
    assert routes_stats.format_money(1234.5) == "MYR 1,234.50"


def test_csv_cells_cannot_run_as_formulas():
    assert routes_stats.make_cell_safe("=1+1") == "'=1+1"
    assert routes_stats.make_cell_safe("PLA") == "PLA"

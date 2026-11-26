# WHAT THIS FILE DOES: Automatic checks for the Home dashboard boxes, the Statistics screen, the CSV download
#   and the rule that Employees never see money (guide Sections 4, 5 F2 and F7, 14).
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db).

import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

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
    return create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})


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


def test_home_list_is_called_notifications(admin):
    page = admin.get("/").get_data(as_text=True)
    assert "<h2>Notifications</h2>" in page and "Needs attention" not in page


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

@pytest.mark.parametrize("address", ["/stats/export.csv", "/stats/data/price-comparison"])
def test_employee_gets_403_on_money_addresses(employee, address):
    assert employee.get(address).status_code == 403


@pytest.mark.parametrize("address", ["/stats/export.csv", "/stats/data/price-comparison", "/stats/", "/stats/data/usage"])
def test_not_logged_in_is_sent_to_login(website, address):
    assert website.test_client().get(address).status_code == 302


def test_admin_can_download_csv(admin):
    answer = admin.get("/stats/export.csv")
    assert answer.status_code == 200 and answer.mimetype == "text/csv"
    assert "Report,Name,Period,Value,Unit" in answer.get_data(as_text=True)


def test_employee_statistics_page_has_no_money_or_download(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert "MYR" not in page and "Spending" not in page and "export.csv" not in page
    assert "Usage per material" in page and "Delivery ranking" in page


def test_admin_statistics_page_has_price_comparison_and_download(admin):
    page = admin.get("/stats/").get_data(as_text=True)
    assert "Supplier price comparison" in page and "/stats/export.csv" in page


@pytest.mark.parametrize("address", ["/stats/data/usage", "/stats/data/delivery-ranking", "/stats/data/delivery-ranking?material=M1"])
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
    assert chart["datasets"] == [{"label": "PLA Basic White (g)", "name": "PLA Basic White", "unit": "g",
                                  "data": [0, 0, 0, 0, 0, 250]}]


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


def test_home_money_box_shows_real_money_to_both_roles(admin, employee, database_file, monkeypatch):
    monkeypatch.setattr(routes_stats, "malaysia_now", lambda: NOW)
    add_purchase(database_file, "A", "S2", 120.5, "2026-11-05 02:00:00")
    assert "MYR 120.50" in admin.get("/").get_data(as_text=True)
    assert "MYR 120.50" in employee.get("/").get_data(as_text=True)


# The three charts the team removed on 2026-11-26 are gone for everybody: no page text, no chart, no data address.
@pytest.mark.parametrize("address", ["/stats/data/low-stock", "/stats/data/spending", "/stats/data/spending-by-material"])
def test_removed_chart_addresses_are_gone(admin, employee, address):
    assert admin.get(address).status_code == 404
    assert employee.get(address).status_code == 404


def test_removed_charts_are_not_on_the_statistics_page(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        for gone in ("Low-stock events per month", "low-chart", "Spending per supplier", "spending-chart",
                     "Spending per material", "material-spending-chart"):
            assert gone not in page, gone


# The same five dates as sample_data/stock_movements.csv (18 to 22 November 2026, UTC) must land in November.
def test_sample_style_usage_lands_in_november_by_month_and_by_week(database_file):
    add_movement(database_file, "A", "M1", "USED", 170, "2026-11-18 06:30:00")
    add_movement(database_file, "B", "M3", "USED", 500, "2026-11-20 08:15:00")
    add_movement(database_file, "C", "M2", "USED", 260, "2026-11-21 04:45:00")
    add_movement(database_file, "D", "M1", "USED", 500, "2026-11-22 09:00:00")
    database = open_database(database_file)
    month = routes_stats.get_usage_by_period(database, "month", now=NOW)
    assert month["labels"] == ["Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov 2026"]
    assert all(dataset["data"][:5] == [0, 0, 0, 0, 0] for dataset in month["datasets"])     # nothing in Jun to Oct
    assert sorted(dataset["data"][5] for dataset in month["datasets"]) == [260, 500, 670]   # all in Nov 2026
    week = routes_stats.get_usage_by_period(database, "week", now=NOW)
    assert week["labels"][-2:] == ["Week of 16 Nov", "Week of 23 Nov"]
    assert sum(dataset["data"][-2] for dataset in week["datasets"]) == 1430                 # all in "Week of 16 Nov"
    assert sum(dataset["data"][-1] for dataset in week["datasets"]) == 0


def test_usage_month_edges_use_malaysia_time_not_utc(database_file):
    add_movement(database_file, "A", "M1", "USED", 10, "2026-10-31 15:59:59")    # 31 Oct 23:59 in Malaysia: October
    add_movement(database_file, "B", "M1", "USED", 20, "2026-10-31 16:00:00")    # 1 Nov 00:00 in Malaysia: November
    month = routes_stats.get_usage_by_period(open_database(database_file), "month", now=NOW)
    data = month["datasets"][0]["data"]
    assert data[-2] == 10 and data[-1] == 20


def test_money_text_format():
    assert routes_stats.format_money(72) == "MYR 72.00"
    assert routes_stats.format_money(1234.5) == "MYR 1,234.50"


def test_csv_cells_cannot_run_as_formulas():
    assert routes_stats.make_cell_safe("=1+1") == "'=1+1"
    assert routes_stats.make_cell_safe("PLA") == "PLA"


# ---------- Procurement statistics (guide F7, decision 2026-11-26) ----------

# Adds one "Record received" line for any material, with an optional supplier and total paid (time is UTC text).
def add_received_line(database_file, line_id, material_id, quantity, utc_text, supplier_id=None, total_cost=None):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO stock_movements (id, material_id, movement_type, quantity, user_id, created_at, supplier_id, "
        "total_cost_myr) VALUES (?, ?, 'RECEIVED', ?, 'U1', ?, ?, ?)",
        (line_id, material_id, quantity, utc_text, supplier_id, total_cost))
    connection.commit()
    connection.close()


def test_purchases_per_material_add_received_lines_per_month_with_units(database_file):
    add_received_line(database_file, "A", "M1", 1000, "2026-11-05 02:00:00", "S1", 70)
    add_received_line(database_file, "B", "M1", 500, "2026-11-20 02:00:00")
    add_received_line(database_file, "C", "M2", 300, "2026-10-10 02:00:00")
    add_movement(database_file, "D", "M1", "USED", 400, "2026-11-06 02:00:00")          # used is not a purchase
    chart = routes_stats.get_purchases_by_material(open_database(database_file), NOW)
    assert chart["labels"][-2:] == ["Oct 2026", "Nov 2026"] and len(chart["labels"]) == 6
    by_label = {dataset["label"]: dataset for dataset in chart["datasets"]}
    assert by_label["PLA Basic White (g)"]["data"] == [0, 0, 0, 0, 0, 1500]
    assert by_label["PLA Basic White (g)"]["unit"] == "g" and by_label["PLA Basic White (g)"]["name"] == "PLA Basic White"
    assert by_label["PETG Clear (g)"]["data"] == [0, 0, 0, 0, 300, 0]
    assert "70" not in str(chart) and "cost" not in str(chart).lower()                   # no money inside


def test_spending_per_material_adds_totals_of_the_last_six_months(database_file):
    add_received_line(database_file, "A", "M1", 1000, "2026-11-05 02:00:00", "S1", 100)
    add_received_line(database_file, "B", "M1", 1000, "2026-11-20 02:00:00", "S2", 50)
    add_received_line(database_file, "C", "M2", 1000, "2026-10-10 02:00:00", "S1", 90)
    add_received_line(database_file, "D", "M1", 1000, "2026-05-01 02:00:00", "S1", 999)    # older than 6 months
    add_received_line(database_file, "E", "M2", 1000, "2026-11-07 02:00:00")               # no total typed: skipped
    chart = routes_stats.get_spending_by_material(open_database(database_file), NOW)
    assert chart["labels"] == ["PLA Basic White (g)", "PETG Clear (g)"]
    assert chart["amounts"] == [150.0, 90.0] and chart["purchases"] == [2, 1]


def test_price_comparison_chart_uses_the_newest_purchase_for_the_price_last_paid(database_file):
    add_received_line(database_file, "A", "M1", 1000, "2026-11-01 02:00:00", "S1", 90)      # older line: ignored
    add_received_line(database_file, "B", "M1", 2000, "2026-11-05 02:00:00", "S1", 150)     # newest: MYR 75 per kg
    add_received_line(database_file, "C", "M2", 1000, "2026-11-06 02:00:00", "S1", 72)      # MYR 72 against offer 90
    group = routes_stats.get_price_comparison_chart(open_database(database_file))["per_kg_litre"]
    white, petg = group["labels"].index("PLA Basic White (per kg)"), group["labels"].index("PETG Clear (per kg)")
    assert group["offer"][white] == 60.0 and group["paid"][white] == 75.0
    assert group["offer"][petg] == 90.0 and group["paid"][petg] == 72.0


def test_procurement_data_addresses_follow_the_roles(admin, employee):
    assert admin.get("/stats/data/purchases").status_code == 200
    assert employee.get("/stats/data/purchases").status_code == 200                           # no money in it
    assert admin.get("/stats/data/price-comparison").status_code == 200
    assert employee.get("/stats/data/price-comparison").status_code == 403                    # money: Admin only


def test_employee_purchases_data_has_no_money_keys(employee, database_file):
    add_received_line(database_file, "A", "M1", 1000, "2026-11-05 02:00:00", "S1", 70)
    text = employee.get("/stats/data/purchases").get_data(as_text=True).lower()
    assert "cost" not in text and "myr" not in text and "amount" not in text


def test_employee_statistics_page_has_purchases_but_no_money_panels(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert "Purchases per material" in page and "Quantity received (g, ml or pcs)" in page
    for money_word in ("MYR", "Spending", "Supplier price comparison", "per kg"):
        assert money_word not in page, money_word


def test_admin_statistics_page_has_every_procurement_panel(admin, database_file):
    add_received_line(database_file, "A", "M1", 1000, "2026-11-05 02:00:00", "S1", 70)
    page = admin.get("/stats/").get_data(as_text=True)
    for words in ("Purchases per material", "Supplier price comparison",
                  "Cheapest supplier offer", "per kg", "These are estimates"):
        assert words in page, words


def test_every_chart_names_its_unit_in_the_axis_title(employee, admin):
    employee_page = employee.get("/stats/").get_data(as_text=True)
    for words in ("Quantity used (g, ml or pcs)", "Quantity received (g, ml or pcs)", "Rank suppliers for"):
        assert words in employee_page, words
    admin_page = admin.get("/stats/").get_data(as_text=True)
    for words in ("MYR per kg or per litre", "MYR per piece"):
        assert words in admin_page, words


def test_csv_lists_purchases_and_spending_per_material(admin, database_file):
    yesterday = (routes_stats.utc_now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")   # always inside the last 6 months
    add_received_line(database_file, "A", "M1", 1000, yesterday, "S1", 70)
    text = admin.get("/stats/export.csv").get_data(as_text=True)
    assert "Purchased (received)" in text and "Spending per material (last 6 months)" in text


def test_price_comparison_chart_numbers_per_kg_and_per_piece(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO materials (id, name, colour, unit, quantity_on_hand, reorder_level) "
                       "VALUES ('M4', 'Screws', 'Steel', 'pcs', 100, 20)")
    connection.execute("INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
                       "lead_time_days) VALUES ('O4', 'S1', 'M4', 100, 'pcs', 9.0, 2)")           # MYR 0.09 per piece
    connection.commit()
    connection.close()
    add_received_line(database_file, "A", "M1", 2000, "2026-11-05 02:00:00", "S1", 150)        # MYR 75 per kg
    add_received_line(database_file, "B", "M4", 100, "2026-11-06 02:00:00", "S2", 12)          # MYR 0.12 per piece
    chart = routes_stats.get_price_comparison_chart(open_database(database_file))
    weight, piece = chart["per_kg_litre"], chart["per_piece"]
    assert "PLA Basic White (per kg)" in weight["labels"]
    i = weight["labels"].index("PLA Basic White (per kg)")
    assert weight["offer"][i] == 60.0 and weight["offer_supplier"][i] == "Web Store"
    assert weight["paid"][i] == 75.0 and weight["paid_supplier"][i] == "Kuching Shop" and weight["paid_date"][i] == "05 Nov 2026"
    assert "ABS Grey (per kg)" not in weight["labels"]                                           # no offer and never bought
    assert piece["labels"] == ["Screws Steel (per piece)"]
    assert piece["offer"] == [0.09] and piece["paid"] == [0.12] and piece["words"] == ["per piece"]


def test_price_comparison_chart_keeps_an_offer_with_no_purchase_yet(database_file):
    chart = routes_stats.get_price_comparison_chart(open_database(database_file))
    weight = chart["per_kg_litre"]
    i = weight["labels"].index("PETG Clear (per kg)")
    assert weight["offer"][i] == 90.0 and weight["paid"][i] is None and weight["paid_supplier"][i] == ""


def test_price_comparison_chart_is_admin_only_and_not_on_the_employee_page(admin, employee):
    assert admin.get("/stats/data/price-comparison").status_code == 200
    assert employee.get("/stats/data/price-comparison").status_code == 403
    admin_page = admin.get("/stats/").get_data(as_text=True)
    assert 'id="price-chart-weight"' in admin_page and 'id="price-chart-piece"' in admin_page
    employee_page = employee.get("/stats/").get_data(as_text=True)
    assert "price-chart" not in employee_page and "price-comparison" not in employee_page


# ---------- Delivery ranking (guide F7, decision 2026-11-26) ----------

# Adds one supplier offer for a material (lead time in days), switched on unless told otherwise.
def add_offer(database_file, offer_id, supplier_id, material_id, lead_days, is_active=1):
    connection = sqlite3.connect(database_file)
    connection.execute(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, lead_time_days, "
        "is_active) VALUES (?, ?, ?, 1000, 'g', 50, ?, ?)", (offer_id, supplier_id, material_id, lead_days, is_active))
    connection.commit()
    connection.close()


def test_delivery_ranking_for_one_material_is_fastest_first_with_an_arrival_date(database_file):
    ranking = routes_stats.get_delivery_ranking(open_database(database_file), "M1", today=date(2026, 11, 23))
    assert ranking["is_average"] is False
    assert [(r["rank"], r["supplier"], r["days_text"], r["arrival"]) for r in ranking["rows"]] == [
        (1, "Kuching Shop", "1 day", "24 Nov"), (2, "Web Store", "7 days", "30 Nov")]
    assert ranking["rows"][0]["type"] == "local" and ranking["rows"][1]["type"] == "online"


def test_delivery_ranking_ties_share_a_rank_and_are_ordered_a_to_z(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO suppliers (id, name, supplier_type) VALUES ('S9', 'Slow Shop', 'ONLINE')")
    connection.commit()
    connection.close()
    add_offer(database_file, "O8", "S2", "M2", 3)                  # Web Store also 3 days for PETG, like Kuching Shop
    add_offer(database_file, "O9", "S9", "M2", 5)
    rows = routes_stats.get_delivery_ranking(open_database(database_file), "M2", today=date(2026, 11, 23))["rows"]
    assert [(r["rank"], r["supplier"]) for r in rows] == [(1, "Kuching Shop"), (1, "Web Store"), (3, "Slow Shop")]


def test_delivery_ranking_ignores_switched_off_offers_and_suppliers_and_uses_the_fastest_offer(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO suppliers (id, name, supplier_type, is_active) VALUES ('S8', 'Closed Shop', 'LOCAL', 0)")
    connection.commit()
    connection.close()
    add_offer(database_file, "O7", "S8", "M1", 1)                  # closed supplier: left out
    add_offer(database_file, "O6", "S2", "M1", 2, is_active=0)     # switched-off offer: left out
    add_offer(database_file, "O5", "S2", "M1", 4)                  # Web Store has two offers: its fastest (4) counts
    rows = routes_stats.get_delivery_ranking(open_database(database_file), "M1", today=date(2026, 11, 23))["rows"]
    assert [(r["supplier"], r["days_text"]) for r in rows] == [("Kuching Shop", "1 day"), ("Web Store", "4 days")]


def test_delivery_ranking_for_all_materials_is_the_average_and_an_unknown_material_is_empty(database_file):
    ranking = routes_stats.get_delivery_ranking(open_database(database_file), "", today=date(2026, 11, 23))
    assert ranking["is_average"] is True
    assert [(r["supplier"], r["days_text"]) for r in ranking["rows"]] == [
        ("Kuching Shop", "2 days on average"), ("Web Store", "7 days on average")]
    assert routes_stats.get_delivery_ranking(open_database(database_file), "NOPE")["rows"] == []


def test_delivery_days_are_written_in_the_singular_for_one_day(database_file):
    add_offer(database_file, "O4", "S1", "M3", 1)                      # Kuching Shop: M1 1 day, M2 3 days, M3 1 day
    average = routes_stats.get_delivery_ranking(open_database(database_file), "")["rows"]
    assert average[0]["days_text"] == "1.7 days on average"
    only_one_day = routes_stats.get_delivery_ranking(open_database(database_file), "M3")["rows"]
    assert only_one_day[0]["days_text"] == "1 day"
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE supplier_offers SET lead_time_days = 1 WHERE id = 'O2'")
    connection.commit()
    connection.close()
    assert routes_stats.get_delivery_ranking(open_database(database_file), "")["rows"][0]["days_text"] == "1 day on average"


def test_the_material_list_has_only_materials_a_supplier_sells(database_file):
    labels = [m["label"] for m in routes_stats.get_ranking_materials(open_database(database_file))]
    assert labels == ["PETG Clear (g)", "PLA Basic White (g)"]           # ABS Grey has no offer


def test_ranking_address_works_for_both_roles_and_has_no_money(admin, employee):
    for browser in (admin, employee):
        data = browser.get("/stats/data/delivery-ranking?material=M1").get_json()
        assert data["rows"][0]["supplier"] == "Kuching Shop"
    text = employee.get("/stats/data/delivery-ranking?material=M1").get_data(as_text=True).lower()
    assert "myr" not in text and "price" not in text and "cost" not in text


def test_the_page_offers_the_material_choice_and_the_old_delivery_chart_is_gone(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        assert 'id="ranking-material"' in page and "All materials (average)" in page
        assert "PLA Basic White (g)" in page and "ABS Grey" not in page.split('id="ranking-material"')[1].split("</select>")[0]
        assert "lead-chart" not in page and "Average delivery time per supplier" not in page
        assert browser.get("/stats/data/lead-times").status_code == 404

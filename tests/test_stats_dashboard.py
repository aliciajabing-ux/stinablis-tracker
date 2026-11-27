# WHAT THIS FILE DOES: Automatic checks for the Home dashboard boxes, the Statistics screen, the CSV download
#   and the rule that Employees never see money (guide Sections 4, 5 F2 and F7, 14).
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests
#
# These checks build a temporary database (never data/tracker.db).

import os
import re
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


# 2026-11-26: the status is a coloured box (same as Materials), just left of the Find supplier button.
def test_home_notifications_show_status_box_left_of_find_supplier(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/").get_data(as_text=True)
        out_box = page.index('class="tag tag-OUT"')
        low_box = page.index('class="tag tag-LOW"')
        assert out_box < page.index('href="/suggest/M3"')          # ABS Grey (OUT): box, then button
        assert low_box < page.index('href="/suggest/M2"')          # PETG Clear (LOW): box, then button
        assert out_box < low_box                                   # OUT still first
        assert "MYR" not in page


# The "money spent this month" box was removed on 2026-11-26 (team decision): three boxes, no money on Home.
def test_home_has_three_boxes_and_no_money_box_for_either_role(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/").get_data(as_text=True)
        assert len(re.findall(r'class="tile[ "]', page)) == 3                      # the boxes, not the box holder
        assert "Estimated money spent" not in page and "MYR" not in page


def test_home_needs_login(website):
    assert website.test_client().get("/").status_code == 302


# ---------- Employee blocked pages (Section 4, 14) ----------

@pytest.mark.parametrize("address", ["/stats/export.csv"])
def test_employee_gets_403_on_money_addresses(employee, address):
    assert employee.get(address).status_code == 403


@pytest.mark.parametrize("address", ["/stats/export.csv", "/stats/", "/stats/data/usage"])
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


def test_admin_statistics_page_has_spending_and_stock_value_and_download(admin):
    page = admin.get("/stats/").get_data(as_text=True)
    assert "Spending &amp; stock value" in page and "/stats/export.csv" in page


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


def test_removed_procurement_addresses_are_gone_for_everybody(admin, employee):
    for address in ("/stats/data/purchases", "/stats/data/price-comparison"):
        assert admin.get(address).status_code == 404
        assert employee.get(address).status_code == 404


def test_removed_procurement_panels_are_not_on_the_page(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        for gone in ("Purchases per material", "purchases-chart", "Supplier price comparison", "price-chart", "Cheapest supplier offer"):
            assert gone not in page, gone


def test_employee_statistics_page_has_no_money_panels(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    for money_word in ("MYR", "Spending", "Stock value", "stock value", "export.csv"):
        assert money_word not in page, money_word


def test_every_chart_names_its_unit_in_the_axis_title(employee, admin):
    page = employee.get("/stats/").get_data(as_text=True)
    assert '"Quantity used (" + unit + ")"' in page and "Rank suppliers" in page or "Delivery ranking" in page


def test_csv_lists_purchases_and_spending_per_material(admin, database_file):
    yesterday = (routes_stats.utc_now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")   # always inside the last 6 months
    add_received_line(database_file, "A", "M1", 1000, yesterday, "S1", 70)
    text = admin.get("/stats/export.csv").get_data(as_text=True)
    assert "Purchased (received)" in text and "Spending per material (last 6 months)" in text


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


def test_ranking_address_works_for_both_roles_and_has_no_money(admin, employee):
    for browser in (admin, employee):
        data = browser.get("/stats/data/delivery-ranking?material=M1").get_json()
        assert data["rows"][0]["supplier"] == "Kuching Shop"
    text = employee.get("/stats/data/delivery-ranking?material=M1").get_data(as_text=True).lower()
    assert "myr" not in text and "price" not in text and "cost" not in text


# Returns the words of the ranking list (the <ol>) of a Statistics page, and the empty-message tag.
def ranking_part(page):
    after_list = page.split('id="ranking-list"')[1]
    return after_list.split("</ol>")[0], after_list.split("</ol>")[1].split("</p>")[0]


RANKING_SUBTITLE = ("Which supplier delivers fastest. Choose a material to rank the suppliers that sell it. The days are what "
                    "each supplier says; the arrival date is today plus those days (an estimate).")


# Decision 2026-11-27: the "Rank suppliers for:" drop-down is ALWAYS there, with every active material A to Z.
def test_the_dropdown_lists_every_active_material_a_to_z_without_units(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO materials (id, name, colour, unit, quantity_on_hand, reorder_level, is_active) "
                       "VALUES ('M9', 'AAA Retired', 'Red', 'g', 1, 1, 0)")
    connection.commit()
    connection.close()
    labels = [m["label"] for m in routes_stats.get_ranking_materials(open_database(database_file))]
    assert labels == ["ABS Grey", "PETG Clear", "PLA Basic White"]            # switched-off material left out, no "(g)"


def test_the_page_has_the_subtitle_then_the_dropdown_then_the_list_for_both_roles(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        panel = page.split('id="panel-ranking"')[1]
        assert RANKING_SUBTITLE in panel
        assert panel.index(RANKING_SUBTITLE) < panel.index("Rank suppliers for:") < panel.index('id="ranking-list"')
        chooser = page.split('id="ranking-material"')[1].split("</select>")[0]
        options = re.findall(r"<option value=\"([^\"]*)\"[^>]*>([^<]*)</option>", chooser)
        assert options == [("", "All materials (average)"), ("M3", "ABS Grey"), ("M2", "PETG Clear"), ("M1", "PLA Basic White")]
        assert "lead-chart" not in page and "Average delivery time per supplier" not in page
        assert browser.get("/stats/data/lead-times").status_code == 404


def test_the_dropdown_is_there_even_when_no_material_has_two_suppliers(admin, employee, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("DELETE FROM supplier_offers WHERE id = 'O3'")             # PLA now has one supplier too
    connection.commit()
    connection.close()
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        assert 'id="ranking-material"' in page and "Rank suppliers for:" in page and "PETG Clear" in page


def test_all_materials_ranks_every_supplier_by_average_days_for_both_roles(admin, employee):
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        items, empty = ranking_part(page)
        assert 'value="" selected' not in page and "<option value=\"\">All materials (average)</option>" in page
        assert items.index("Kuching Shop") < items.index("Web Store")
        assert "2 days on average, arrives about" in items and "7 days on average, arrives about" in items
        assert "hidden" in empty                                                  # the "nobody sells this" line is hidden


def test_one_material_shows_only_the_suppliers_that_sell_it_without_on_average(admin, employee):
    for browser in (admin, employee):
        pla = ranking_part(browser.get("/stats/?material=M1").get_data(as_text=True))[0]
        assert pla.index("Kuching Shop") < pla.index("Web Store")                # fastest first
        assert "1 day, arrives about" in pla and "7 days, arrives about" in pla and "on average" not in pla
        petg_page = browser.get("/stats/?material=M2").get_data(as_text=True)
        petg = ranking_part(petg_page)[0]
        assert "Kuching Shop" in petg and "Web Store" not in petg                # Web Store sells no PETG
        assert "3 days, arrives about" in petg and "on average" not in petg
        assert '<option value="M2" selected>PETG Clear</option>' in petg_page    # the choice is kept in the dropdown


def test_one_material_nobody_sells_says_so_and_an_unknown_material_means_all(admin, employee):
    for browser in (admin, employee):
        items, empty = ranking_part(browser.get("/stats/?material=M3").get_data(as_text=True))
        assert "<li" not in items and "No supplier sells this yet." in empty and "hidden" not in empty
        fallback = browser.get("/stats/?material=NOPE").get_data(as_text=True)
        assert "on average" in ranking_part(fallback)[0]


def test_ties_share_rank_one_both_get_fastest_and_the_next_is_number_three(admin, employee, database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO suppliers (id, name, supplier_type) VALUES ('S9', 'Slow Shop', 'ONLINE')")
    connection.commit()
    connection.close()
    add_offer(database_file, "O8", "S2", "M2", 3)                  # Web Store ties with Kuching Shop (3 days) for PETG
    add_offer(database_file, "O9", "S9", "M2", 5)
    for browser in (admin, employee):
        items = ranking_part(browser.get("/stats/?material=M2").get_data(as_text=True))[0]
        numbers = re.findall(r'class="rank-number">(\d+)<', items)
        assert numbers == ["1", "1", "3"] and items.count("Fastest") == 2
        data = browser.get("/stats/data/delivery-ranking?material=M2").get_json()
        assert [(r["rank"], r["supplier"]) for r in data["rows"]] == [(1, "Kuching Shop"), (1, "Web Store"), (3, "Slow Shop")]


def test_the_data_address_matches_the_page_for_all_and_for_one_material(admin, employee):
    for browser in (admin, employee):
        everything = browser.get("/stats/data/delivery-ranking").get_json()
        assert everything["is_average"] is True and everything["rows"][0]["days_text"] == "2 days on average"
        one = browser.get("/stats/data/delivery-ranking?material=M1").get_json()
        assert one["is_average"] is False and [r["days_text"] for r in one["rows"]] == ["1 day", "7 days"]
        assert all(re.match(r"\d{2} \w{3}$", row["arrival"]) for row in one["rows"])


def test_changing_the_dropdown_works_without_a_reload_and_has_a_plain_address_fallback(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert '<form method="get" action="/stats/#ranking" id="ranking-form">' in page
    assert 'name="material"' in page and "<noscript><button" in page             # without script the button sends ?material=
    assert 'addEventListener("change", loadRanking)' in page and "replaceState" in page


def test_two_offers_of_one_supplier_still_show_one_line_for_that_supplier(database_file):
    add_offer(database_file, "O5", "S1", "M2", 9)                                 # same supplier again for PETG
    rows = routes_stats.get_delivery_ranking(open_database(database_file), "M2")["rows"]
    assert [r["supplier"] for r in rows] == ["Kuching Shop"]                      # one line, its fastest offer (3 days)


# ---------- The Statistics sidebar (guide F7, decision 2026-11-26) ----------

# Returns the links inside the sidebar of a page as (address, words) pairs, in order.
def sidebar_links(page):
    import re
    nav = re.search(r'<nav class="stats-nav".*?</nav>', page, re.S).group(0)
    import html
    return [(href, html.unescape(re.sub(r"\s+", " ", words).strip())) for href, words in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', nav, re.S)]


def test_employee_sidebar_lists_only_the_statistics_an_employee_may_open(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert sidebar_links(page) == [("#usage", "Usage per material"), ("#days", "Days of stock left"),
                                   ("#ranking", "Delivery ranking")]
    for gone in ("#spending", "nav-spending", "panel-spending", "export.csv", "MYR"):
        assert gone not in page, gone


def test_admin_sidebar_also_lists_spending_and_stock_value_and_the_download(admin):
    links = sidebar_links(admin.get("/stats/").get_data(as_text=True))
    assert [words for _, words in links] == ["Usage per material", "Days of stock left", "Delivery ranking",
                                             "Spending & stock value", "Download spreadsheet (CSV)"]
    assert links[3][0] == "#spending" and links[4][0] == "/stats/export.csv"


def test_only_the_first_statistic_is_shown_when_the_page_opens(admin, employee):
    admin_page = admin.get("/stats/").get_data(as_text=True)
    assert 'id="panel-usage">' in admin_page                                   # shown
    for hidden_one in ("panel-days", "panel-ranking", "panel-spending"):
        assert 'id="%s" hidden>' % hidden_one in admin_page, hidden_one
    employee_page = employee.get("/stats/").get_data(as_text=True)
    assert 'id="panel-usage">' in employee_page
    assert 'id="panel-days" hidden>' in employee_page and 'id="panel-ranking" hidden>' in employee_page


def test_the_sidebar_marks_the_first_statistic_and_a_script_switches_between_them(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert 'id="nav-usage" href="#usage" class="active" aria-current="true"' in page
    assert "function showStatistic(" in page and 'addEventListener("hashchange"' in page
    assert 'STATISTIC_NAMES = ["usage", "days", "ranking"]' in page              # an Employee's script knows no "spending"


# ---------- Usage per unit (guide F7, decision 2026-11-27) ----------

# Adds one extra material counted in the given unit (stock 100, reorder level 20).
def add_material(database_file, material_id, name, unit):
    connection = sqlite3.connect(database_file)
    connection.execute("INSERT INTO materials (id, name, unit, quantity_on_hand, reorder_level) VALUES (?, ?, ?, 100, 20)",
                       (material_id, name, unit))
    connection.commit()
    connection.close()


def test_usage_chart_defaults_to_grams_and_filters_by_unit(admin, employee, database_file):
    add_material(database_file, "M6", "Standard Resin", "ml")
    add_material(database_file, "M7", "Screws", "pcs")
    add_movement(database_file, "A", "M1", "USED", 200, "2026-11-20 02:00:00")
    add_movement(database_file, "B", "M6", "USED", 300, "2026-11-20 02:00:00")
    add_movement(database_file, "C", "M7", "USED", 40, "2026-11-20 02:00:00")
    for browser in (admin, employee):
        default = browser.get("/stats/data/usage?period=month").get_json()
        assert {d["unit"] for d in default["datasets"]} == {"g"}                       # one unit, one scale
        for unit, name in (("g", "PLA Basic White"), ("ml", "Standard Resin"), ("pcs", "Screws")):
            data = browser.get("/stats/data/usage?period=month&unit=" + unit).get_json()
            assert [(d["name"], d["unit"]) for d in data["datasets"]] == [(name, unit)]
        wrong = browser.get("/stats/data/usage?unit=banana").get_json()                  # unknown unit: back to grams
        assert {d["unit"] for d in wrong["datasets"]} == {"g"}


def test_usage_function_without_a_unit_still_includes_every_unit_for_the_csv(database_file):
    add_material(database_file, "M7", "Screws", "pcs")
    add_movement(database_file, "A", "M1", "USED", 200, "2026-11-20 02:00:00")
    add_movement(database_file, "C", "M7", "USED", 40, "2026-11-20 02:00:00")
    chart = routes_stats.get_usage_by_period(open_database(database_file), "month", NOW)
    assert {d["unit"] for d in chart["datasets"]} == {"g", "pcs"}


def test_usage_panel_has_the_unit_choice_with_filament_first(employee):
    page = employee.get("/stats/").get_data(as_text=True)
    assert 'id="usage-unit"' in page
    assert page.index("Filament (g)") < page.index("Resin (ml)") < page.index("Hardware (pcs)")
    assert page.split('id="usage-unit"')[1].split("<option")[1].startswith(' value="g"')   # grams is the default


# ---------- Days of stock left (guide F7, decision 2026-11-27) ----------

def test_days_left_is_stock_divided_by_average_daily_use_over_30_days(database_file):
    add_movement(database_file, "A", "M1", "USED", 150, "2026-11-10 02:00:00")      # inside the 30 days
    add_movement(database_file, "B", "M1", "USED", 150, "2026-11-20 02:00:00")
    add_movement(database_file, "C", "M1", "USED", 9999, "2026-09-01 02:00:00")     # older than 30 days: ignored
    add_movement(database_file, "D", "M1", "RECEIVED", 500, "2026-11-15 02:00:00")  # received is not use
    rows = routes_stats.get_days_of_stock_left(open_database(database_file), NOW)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "PLA Basic White" and row["unit"] == "g" and row["stock"] == 800
    assert row["average_daily"] == 10.0 and row["days_left"] == 80.0                # 300 g / 30 days = 10 g a day; 800 / 10
    assert row["lead_time_days"] == 1                                               # fastest active offer (Kuching Shop)


def test_days_left_window_uses_malaysia_time(database_file):
    # NOW is 23 Nov 10:00 Malaysia; 30 days back is 24 Oct 10:00 Malaysia = 24 Oct 02:00 UTC.
    add_movement(database_file, "A", "M1", "USED", 30, "2026-10-24 01:59:00")       # just outside
    assert routes_stats.get_days_of_stock_left(open_database(database_file), NOW) == []
    add_movement(database_file, "B", "M1", "USED", 30, "2026-10-24 02:01:00")       # just inside
    assert len(routes_stats.get_days_of_stock_left(open_database(database_file), NOW)) == 1


def test_days_left_sorts_fewest_days_first_and_skips_unused_and_switched_off_materials(database_file):
    add_movement(database_file, "A", "M1", "USED", 300, "2026-11-20 02:00:00")      # 800 g at 10 g/day = 80 days
    add_movement(database_file, "B", "M2", "USED", 300, "2026-11-20 02:00:00")      # 240 g at 10 g/day = 24 days
    add_movement(database_file, "C", "M3", "USED", 300, "2026-11-20 02:00:00")      # 0 g left = 0 days
    rows = routes_stats.get_days_of_stock_left(open_database(database_file), NOW)
    assert [r["name"] for r in rows] == ["ABS Grey", "PETG Clear", "PLA Basic White"]
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET is_active = 0 WHERE id = 'M2'")
    connection.commit()
    connection.close()
    rows = routes_stats.get_days_of_stock_left(open_database(database_file), NOW)
    assert [r["name"] for r in rows] == ["ABS Grey", "PLA Basic White"]


def test_days_left_badges_order_now_low_and_ok():
    assert routes_stats.days_left_badge(2, 3) == "Order now"
    assert routes_stats.days_left_badge(3, 3) == "Order now"                        # equal to the lead time counts
    assert routes_stats.days_left_badge(3.1, 3) == "Low"
    assert routes_stats.days_left_badge(10, 3) == "Low"                             # lead time + 7 days margin
    assert routes_stats.days_left_badge(10.1, 3) == ""
    assert routes_stats.days_left_badge(0, None) == "Order now"                     # no supplier, nothing left
    assert routes_stats.days_left_badge(5, None) == "Low"


def test_days_left_with_no_supplier_says_so_and_ignores_switched_off_offers(database_file):
    add_movement(database_file, "C", "M3", "USED", 30, "2026-11-20 02:00:00")       # ABS Grey has no offer at all
    rows = routes_stats.get_days_of_stock_left(open_database(database_file), NOW)
    assert rows[0]["lead_time_days"] is None
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE supplier_offers SET is_active = 0 WHERE id = 'O1'")  # Kuching Shop offer off: Web Store (7) remains
    connection.commit()
    connection.close()
    add_movement(database_file, "D", "M1", "USED", 30, "2026-11-20 02:00:00")
    by_name = {r["name"]: r for r in routes_stats.get_days_of_stock_left(open_database(database_file), NOW)}
    assert by_name["PLA Basic White"]["lead_time_days"] == 7


def test_days_left_page_shows_table_badges_and_no_money_for_both_roles(admin, employee, database_file):
    recent = (routes_stats.utc_now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    add_movement(database_file, "A", "M3", "USED", 300, recent)                     # ABS Grey is at 0 g: Order now
    add_movement(database_file, "B", "M1", "USED", 300, recent)
    for browser in (admin, employee):
        page = browser.get("/stats/").get_data(as_text=True)
        panel = page.split('id="panel-days"')[1].split('id="panel-ranking"')[0]
        for header in ("Material", "In stock", "Days left", "Lead time", "Status"):
            assert "<th>%s</th>" % header in panel or ">%s</th>" % header in panel, header
        assert "Est. days left" not in panel and "Supplier lead time" not in panel and "Stock on hand" not in panel
        assert "Order now" in panel and "ABS Grey" in panel and "PLA Basic White" in panel
        assert panel.index("ABS Grey") < panel.index("PLA Basic White")             # fewest days first
        assert "No supplier" in panel and "MYR" not in panel and "price" not in panel.lower()


def test_days_left_page_has_a_clear_empty_state(employee):
    panel = employee.get("/stats/").get_data(as_text=True).split('id="panel-days"')[1].split('id="panel-ranking"')[0]
    assert "No usage has been recorded in the last 30 days yet" in panel and "<table" not in panel


# ---------- Spending & stock value (guide F7, decision 2026-11-27, Admin only) ----------

def test_stock_value_is_stock_times_the_cheapest_active_price_per_unit(database_file):
    value = routes_stats.get_stock_value(open_database(database_file))
    # M1 800 g at the cheaper offer MYR 60 per 1000 g = 48.00; M2 240 g at MYR 90 per 1000 g = 21.60; M3 has no stock.
    assert round(value["total"], 2) == 69.60 and value["priced"] == 2 and value["unpriced"] == 0


def test_stock_value_leaves_out_materials_with_no_supplier_price_and_counts_them(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE materials SET quantity_on_hand = 100 WHERE id = 'M3'")      # ABS Grey: stock but no offer
    connection.execute("UPDATE supplier_offers SET is_active = 0 WHERE id = 'O3'")         # the cheaper PLA offer is off
    connection.commit()
    connection.close()
    value = routes_stats.get_stock_value(open_database(database_file))
    assert round(value["total"], 2) == round(0.8 * 80 + 0.24 * 90, 2) and value["priced"] == 2 and value["unpriced"] == 1


def test_stock_value_ignores_offers_in_another_unit_and_switched_off_materials(database_file):
    connection = sqlite3.connect(database_file)
    connection.execute("UPDATE supplier_offers SET pack_unit = 'ml' WHERE id = 'O2'")      # PETG offer no longer in grams
    connection.execute("UPDATE materials SET is_active = 0 WHERE id = 'M1'")
    connection.commit()
    connection.close()
    value = routes_stats.get_stock_value(open_database(database_file))
    assert value["total"] == 0 and value["priced"] == 0 and value["unpriced"] == 1


def test_spending_panel_shows_this_months_total_with_a_breakdown_by_supplier(admin, database_file):
    this_month = routes_stats.utc_now().strftime("%Y-%m-15 02:00:00")
    add_purchase(database_file, "A", "S2", 120.5, this_month)
    add_purchase(database_file, "B", "S1", 80, this_month)
    add_purchase(database_file, "C", "S1", 999, "2020-01-05 02:00:00")                     # another month
    panel = admin.get("/stats/").get_data(as_text=True).split('id="panel-spending"')[1]
    assert "MYR 200.50" in panel and "Web Store" in panel and "MYR 120.50" in panel
    assert panel.index("Web Store") < panel.index("Kuching Shop")                          # biggest first
    assert "999" not in panel and "Estimated stock value on hand" in panel and "MYR 69.60" in panel


def test_spending_panel_has_a_clear_empty_state(admin):
    panel = admin.get("/stats/").get_data(as_text=True).split('id="panel-spending"')[1]
    assert "MYR 0.00" in panel and "No purchases with a total paid have been recorded this month" in panel


def test_employee_page_never_contains_the_spending_numbers(employee, database_file):
    this_month = routes_stats.utc_now().strftime("%Y-%m-15 02:00:00")
    add_purchase(database_file, "A", "S2", 123.45, this_month)
    page = employee.get("/stats/").get_data(as_text=True)
    assert "123.45" not in page and "69.60" not in page and "panel-spending" not in page


def test_days_left_shows_whole_days_and_one_consistent_status_pill_per_row(admin, employee, database_file):
    recent = (routes_stats.utc_now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    add_movement(database_file, "A", "M1", "USED", 30, recent)       # 800 g at 1 g/day = 800 days, lead time 1: no badge
    add_movement(database_file, "B", "M2", "USED", 900, recent)      # 240 g at 30 g/day = 8 days, lead time 3: Low
    add_movement(database_file, "C", "M3", "USED", 300, recent)      # 0 g left, no supplier: Order now
    for browser in (admin, employee):
        panel = browser.get("/stats/").get_data(as_text=True).split('id="panel-days"')[1].split('id="panel-ranking"')[0]
        assert "800 days" in panel and "8 days" in panel and "0 days" in panel
        assert ".0 day" not in panel and ".1 day" not in panel and ".5 day" not in panel
        assert panel.count("status-pill") >= 3
        assert 'tag tag-OUT status-pill">Order now' in panel and 'tag tag-LOW status-pill">Low' in panel
        assert 'status-pill status-ok">OK' in panel


def test_days_left_intro_is_short(employee):
    panel = employee.get("/stats/").get_data(as_text=True).split('id="panel-days"')[1].split('id="panel-ranking"')[0]
    intro = panel.split("<p>")[1].split("</p>")[0]
    assert len(intro) < 220 and "Estimated from the last 30 days" in intro


def test_spending_panel_has_two_kpi_cards_and_a_supplier_table_that_fits_a_phone(admin, database_file):
    this_month = routes_stats.utc_now().strftime("%Y-%m-15 02:00:00")
    add_purchase(database_file, "A", "S2", 120.5, this_month)
    page = admin.get("/stats/").get_data(as_text=True)
    panel = page.split('id="panel-spending"')[1]
    # two cards in a grid (one column on a phone), each with its heading and a big MYR figure
    assert panel.count('class="kpi-card"') == 2 and 'class="kpi-grid"' in panel
    assert "grid-template-columns:repeat(2, minmax(0, 1fr))" in page and "gap:16px" in page
    assert "@media (max-width: 640px) { .kpi-grid { grid-template-columns:minmax(0, 1fr); } }" in page
    assert ".kpi-card { background:var(--eerie-light); border:1px solid var(--line); border-radius:14px;" in page
    first, second = panel.split('class="kpi-card"')[1:3]
    assert "Spent in " in first and "big-number" in first and "MYR 120.50" in first
    assert "Estimated stock value on hand" in second and "big-number" in second and 'class="note"' in second
    # a subheading above the supplier table; the table overrides the theme's 880 px minimum and keeps the MYR column on one line
    assert panel.index("kpi-grid") < panel.index("Spending by supplier") < panel.index('class="money-table"')
    assert "body .money-table { width:100%; min-width:0; max-width:100%; border-collapse:collapse; table-layout:auto; }" in page
    assert "padding:12px 14px; border:0; border-bottom:1px solid var(--line)" in page
    assert "text-align:right; white-space:nowrap;" in page
    assert '<th>Supplier</th><th class="num">Spent (MYR)</th>' in panel


def test_spending_panel_intro_is_short(admin):
    panel = admin.get("/stats/").get_data(as_text=True).split('id="panel-spending"')[1]
    intro = panel.split("<p>")[1].split("</p>")[0]
    assert len(intro) < 160 and "Estimates in MYR" in intro


def test_days_table_layout_rules_fit_a_half_width_window(employee):
    # The menu stacks above the panel at 960 px, the panel and the table may shrink (min-width 0), and the table
    # overrides the theme's table minimum width so the Status column is never clipped.
    page = employee.get("/stats/").get_data(as_text=True)
    assert "@media (max-width: 960px)" in page and ".stats-layout { display:block; }" in page
    assert ".stats-main { min-width:0; width:100%; }" in page and ".stats-layout > * { min-width:0; }" in page
    assert "body .days-table { width:100%; min-width:0; max-width:100%; table-layout:auto; border-collapse:collapse; }" in page
    assert ".days-table td:first-child { overflow-wrap:anywhere; }" in page
    assert ".days-table td.num, .days-table th.num { text-align:right; white-space:nowrap; }" in page
    assert "white-space:nowrap; }" in page.split(".days-table td.status-cell")[1].split("\n")[0]


def test_home_notification_rows_keep_their_buttons_on_the_right_above_640px(admin, employee):
    # Above 640 px a row never wraps (a long name wraps in the left column), so no row's buttons jump below the others.
    for browser in (admin, employee):
        page = browser.get("/").get_data(as_text=True)
        assert "flex-wrap:nowrap; align-items:center; justify-content:space-between; gap:16px;" in page
        assert ".attention li > span:first-child { flex:1; min-width:0;" in page
        assert ".attention li > .row-end, .attention li > form { flex-shrink:0; white-space:nowrap; }" in page
        assert ".attention li { flex-direction:column; align-items:flex-start; }" in page.split("@media (max-width: 640px)")[1]


# ---------- Delivery ranking follows an edited delivery time (Admin edits the offer) ----------

# The lead time is stored on each supplier offer ("supplier X sells material Y with this lead time"). The Admin edits it on the
# offer form (the "Edit" link in "Materials this supplier sells"). The ranking reads the same column, so it must follow at once.
OFFER_EDIT_FORM = {"material_id": "M1", "pack_unit": "g", "pack_size": "1000", "price_per_pack_myr": "60",
                   "minimum_order_packs": "1", "shipping_cost_myr": "0", "lead_time_days": "1"}


def ranking_pairs(browser, material=""):
    rows = browser.get("/stats/data/delivery-ranking?material=" + material).get_json()["rows"]
    return [(row["rank"], row["supplier"], row["days_text"]) for row in rows]


def test_editing_an_offers_delivery_time_changes_the_delivery_ranking_at_once(admin, employee):
    # Before: Kuching Shop 1 day, Web Store 7 days for PLA (M1).
    assert ranking_pairs(admin, "M1") == [(1, "Kuching Shop", "1 day"), (2, "Web Store", "7 days")]
    # The Admin makes Web Store (offer O3) slower: 9 days. The order stays, the days change.
    assert admin.post("/offers/O3/edit", data={**OFFER_EDIT_FORM, "lead_time_days": "9"}).status_code == 302
    assert ranking_pairs(admin, "M1") == [(1, "Kuching Shop", "1 day"), (2, "Web Store", "9 days")]
    # The Admin makes Web Store faster than Kuching Shop: the ranking order flips, for both roles.
    assert admin.post("/offers/O3/edit", data={**OFFER_EDIT_FORM, "lead_time_days": "0"}).status_code == 302
    for browser in (admin, employee):
        assert ranking_pairs(browser, "M1") == [(1, "Web Store", "0 days"), (2, "Kuching Shop", "1 day")]
    # The "All materials (average)" ranking follows too: Kuching Shop averages (1 + 3) / 2 = 2 days, Web Store 0 days.
    assert ranking_pairs(admin) == [(1, "Web Store", "0 days on average"), (2, "Kuching Shop", "2 days on average")]


def test_the_statistics_page_ranking_is_read_fresh_each_time_and_is_not_cached(admin):
    answer = admin.get("/stats/data/delivery-ranking?material=M1")
    assert "max-age" not in (answer.headers.get("Cache-Control") or "") and "Expires" not in answer.headers
    admin.post("/offers/O1/edit", data={**OFFER_EDIT_FORM, "lead_time_days": "5"})            # Kuching Shop: 5 days now
    assert ranking_pairs(admin, "M1") == [(1, "Kuching Shop", "5 days"), (2, "Web Store", "7 days")]


def test_the_supplier_edit_form_has_no_delivery_time_box_so_it_cannot_change_the_ranking(admin):
    # A supplier has no single delivery time: each of its offers has one. The supplier form only changes contact details and status.
    page = admin.get("/suppliers/S1/edit").get_data(as_text=True)
    assert 'name="lead_time_days"' not in page
    assert admin.get("/offers/O1/edit").get_data(as_text=True).count('name="lead_time_days"') == 1

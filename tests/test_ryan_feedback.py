# WHAT THIS FILE DOES: Checks the fixes from Ryan's real user test (2026-11-26): search box first, "Stock" menu word,
#   Current stock on Home, OK / LOW / OUT order, soft OUT badge, "Noti", and the new Stock page (unit choice, speed ranking).
# WHO CAN USE IT: Developers. Run from the project folder with: python -m pytest tests

import os
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, create_app, setup_database   # noqa: E402

PASSWORD = "test-password-123"
STATUS_RANK = {"OK": 0, "LOW": 1, "OUT": 2}


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


# Returns a test browser logged in as the first active user with this role.
def logged_in_as(database_file, role):
    website = create_app({"DATABASE": database_file, "SECRET_KEY": "test-only-key", "TESTING": True, "CSRF_ENABLED": False})
    connection = sqlite3.connect(database_file)
    username = connection.execute("SELECT username FROM users WHERE role = ? AND is_active = 1", (role,)).fetchone()[0]
    connection.close()
    browser = website.test_client()
    browser.post("/login", data={"username": username, "password": PASSWORD})
    return browser


# Returns the OK / LOW / OUT words of the status badges in the order they appear in some page text.
def badge_order(page_text):
    return re.findall(r'class="tag tag-(OK|LOW|OUT)"', page_text)


# ---- 1. fast search box at the top of Materials ----

def test_materials_search_box_comes_first_and_is_ready_to_type(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert page.index('id="search-box"') < page.index("Show all") < page.index("<table")
    assert "Search by item name" in page and "autofocus" in page and 'name="q"' in page


def test_materials_search_by_name_still_works_on_the_server(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/?q=magnets").get_data(as_text=True)
    assert "SAMPLE Magnets" in page and "SAMPLE Fidget" not in page


def test_materials_rows_carry_the_name_for_live_filtering(sample_database_file):
    page = logged_in_as(sample_database_file, "ADMIN").get("/materials/").get_data(as_text=True)
    assert 'data-name="sample magnets' in page and "filterRows" in page


# ---- 2. "Stock" menu word and less clutter ----

@pytest.mark.parametrize("role", ["ADMIN", "EMPLOYEE"])
def test_menu_says_stock_not_statistics(sample_database_file, role):
    page = logged_in_as(sample_database_file, role).get("/").get_data(as_text=True)
    assert ">Stock<" in page and ">Statistics<" not in page


def test_show_only_ok_button_is_gone_but_the_other_filters_stay(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "Show only OK" not in page
    assert "Show all" in page and "Show only LOW" in page and "Show only OUT" in page


def test_home_shows_current_stock_next_to_record_shortcuts(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/").get_data(as_text=True)
    stock = page[page.index("Current stock"):page.index('id="noti"')]
    assert "SAMPLE Magnets" in stock and "PLA Basic" in stock
    assert 'href="/materials/M001/record/used"' in stock and 'href="/materials/M001/record/received"' in stock
    assert "pieces" in stock and " pcs" not in stock          # plain word for pcs


# ---- 3. status clarity: order, soft OUT badge, "Noti" ----

@pytest.mark.parametrize("address", ["/materials/", "/"])
def test_lists_show_ok_first_then_low_then_out(sample_database_file, address):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get(address).get_data(as_text=True)
    if address == "/":
        page = page[page.index("Current stock"):page.index('id="noti"')]
    ranks = [STATUS_RANK[word] for word in badge_order(page)]
    assert ranks == sorted(ranks) and set(ranks) == {0, 1, 2}


def test_home_uses_the_word_noti_not_needs_attention(sample_database_file):
    page = logged_in_as(sample_database_file, "ADMIN").get("/").get_data(as_text=True)
    assert "<h2>Noti</h2>" in page and "Needs attention" not in page
    assert "Find supplier" in page


def test_out_badge_is_calm_not_alarm_coloured():
    css = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "static", "theme.css"),
               encoding="utf-8").read()
    for rule_start in ("body .tag-OUT", "body .tile.out .word"):
        rule = css[css.index(rule_start):].split("}")[0]
        assert "hot-orange" not in rule and "dashed" in rule, rule_start


def test_status_words_are_still_written_next_to_the_soft_badge(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert ">OUT</span>" in page and "none left" in page


# ---- 4. the new Stock page ----

def test_stock_page_has_unit_choice_and_speed_ranking_and_no_old_charts(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/stats/").get_data(as_text=True)
    assert "<h1>Stock</h1>" in page and "Current stock" in page
    for code in ('value="g"', 'value="ml"', 'value="pcs"'):
        assert code in page
    assert "Supplier speed ranking" in page and "(fastest)" in page
    for gone in ("lead-chart", "low-chart", "Average delivery time per supplier", "Low-stock events per month"):
        assert gone not in page, gone


def test_speed_ranking_lists_suppliers_from_fastest_to_slowest(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/stats/").get_data(as_text=True)
    ranking = page[page.index('class="ranking"'):page.index("</ol>")]
    days = [float(number) for number in re.findall(r"about ([0-9.]+) day", ranking)]
    assert len(days) >= 3 and days == sorted(days)


def test_stock_page_has_no_money_for_employee_but_admin_keeps_spending_and_csv(sample_database_file):
    employee_page = logged_in_as(sample_database_file, "EMPLOYEE").get("/stats/").get_data(as_text=True)
    assert "MYR" not in employee_page and "Spending" not in employee_page and "export.csv" not in employee_page
    admin_page = logged_in_as(sample_database_file, "ADMIN").get("/stats/").get_data(as_text=True)
    assert "Spending per supplier" in admin_page and "/stats/export.csv" in admin_page


@pytest.mark.parametrize("unit, expected_name", [("g", "PLA Basic"), ("ml", "Standard Resin"), ("pcs", "SAMPLE Magnets")])
def test_stock_data_for_each_unit_only_lists_items_in_that_unit(sample_database_file, unit, expected_name):
    data = logged_in_as(sample_database_file, "EMPLOYEE").get("/stats/data/stock?unit=" + unit).get_json()
    assert data["unit"] == unit and any(expected_name in label for label in data["labels"])
    assert len(data["labels"]) == len(data["quantities"]) == len(data["reorder_levels"]) == len(data["statuses"])
    others = {"g": "Standard Resin", "ml": "PLA Basic", "pcs": "PLA Basic"}[unit]
    assert not any(others in label for label in data["labels"])


def test_stock_data_unknown_unit_falls_back_to_grams_and_has_no_money(sample_database_file):
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    data = employee.get("/stats/data/stock?unit=drop-table").get_json()
    assert data["unit"] == "g"
    text = employee.get("/stats/data/stock?unit=pcs").get_data(as_text=True).lower()
    assert "myr" not in text and "price" not in text and "cost" not in text


def test_stock_data_needs_login_and_permissions_are_unchanged(sample_database_file):
    website = create_app({"DATABASE": sample_database_file, "SECRET_KEY": "test-only-key", "TESTING": True})
    assert website.test_client().get("/stats/data/stock").status_code == 302
    employee = logged_in_as(sample_database_file, "EMPLOYEE")
    for address in ("/stats/export.csv", "/stats/data/spending", "/materials/new", "/suppliers/new", "/users/"):
        assert employee.get(address).status_code == 403, address

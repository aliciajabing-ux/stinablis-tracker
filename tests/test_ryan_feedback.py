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

def test_show_only_ok_button_is_gone_but_the_other_filters_stay(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert "Show only OK" not in page
    assert "Show all" in page and "Show only LOW" in page and "Show only OUT" in page


# ---- 3. status clarity: order, soft OUT badge, "Noti" ----

def test_lists_show_ok_first_then_low_then_out_inside_each_section(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    hardware_start = page.index("<h2>Hardware")
    for section_text in (page[page.index("<h2>Filament"):hardware_start], page[hardware_start:]):
        ranks = [STATUS_RANK[word] for word in badge_order(section_text)]
        assert ranks == sorted(ranks) and set(ranks) == {0, 1, 2}


def test_status_words_are_still_written_next_to_the_soft_badge(sample_database_file):
    page = logged_in_as(sample_database_file, "EMPLOYEE").get("/materials/").get_data(as_text=True)
    assert ">OUT</span>" in page and "none left" in page


# ---- 4. the new Stock page ----


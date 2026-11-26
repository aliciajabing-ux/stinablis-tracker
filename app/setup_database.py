# WHAT THIS FILE DOES: Creates the database file from schema.sql and fills it with the sample data.
# WHO CAN USE IT: Developers only. Run it from the project folder with: python app/setup_database.py
#
# Safety rule: if data/tracker.db already exists, a plain run stops and does not touch it.
# To bring an existing database up to date WITHOUT losing data, run:
#     python app/setup_database.py upgrade
# (safe to repeat; it only adds what is missing and deletes nothing).
# To make an existing database use the sample suppliers (one supplier per material) from sample_data, run:
#     python app/setup_database.py sync-suppliers
# (safe to repeat; it switches old offers off instead of deleting them).

import csv
import os
import sqlite3
import sys

# Work out folder paths from where this file lives, so the script runs from any folder.
APP_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(APP_FOLDER)
SCHEMA_FILE = os.path.join(APP_FOLDER, "schema.sql")
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")
DATABASE_FILE = os.path.join(DATA_FOLDER, "tracker.db")
SAMPLE_FOLDER = os.path.join(PROJECT_FOLDER, "sample_data")

# Load parents before children, so links (such as an offer pointing to a material) always exist.
TABLES_TO_LOAD = ["users", "materials", "suppliers", "supplier_offers", "stock_movements"]


# Reads one sample CSV file and returns a list of rows, where each row is a dictionary.
def read_sample_rows(table_name):
    file_path = os.path.join(SAMPLE_FOLDER, table_name + ".csv")
    rows = []
    with open(file_path, newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            rows.append(clean_row(row))
    return rows


# Turns "yes" into 1 and "no" into 0, and empty text into None (the database's "nothing" value).
def clean_row(row):
    cleaned = {}
    for column, value in row.items():
        if value == "":
            cleaned[column] = None
        elif value == "yes":
            cleaned[column] = 1
        elif value == "no":
            cleaned[column] = 0
        else:
            cleaned[column] = value
    return cleaned


# Adds every row of one sample table into the database.
def load_table(connection, table_name):
    rows = read_sample_rows(table_name)
    for row in rows:
        columns = list(row.keys())
        placeholders = ", ".join("?" for _ in columns)
        column_text = ", ".join(columns)
        sql = f"INSERT INTO {table_name} ({column_text}) VALUES ({placeholders})"
        connection.execute(sql, [row[column] for column in columns])
    return len(rows)


# Returns True if the table already has a column with this name.
def column_exists(connection, table_name, column_name):
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(column[1] == column_name for column in columns)


# Returns True if a table with this name exists in the database.
def table_exists(connection, table_name):
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone()
    return row is not None


# Adds one column to a table only if it is missing, and says what it did.
def add_column_if_missing(connection, table_name, column_name, column_definition):
    if column_exists(connection, table_name, column_name):
        print(f"Already there: {table_name}.{column_name} (nothing changed)")
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
    print(f"Added column {table_name}.{column_name}")


# Upgrades an existing database to the newest layout. Safe to run again and again. Deletes nothing.
def upgrade_database(database_file=DATABASE_FILE):
    if not os.path.exists(database_file):
        print("STOP: there is no database to upgrade. Run this script without 'upgrade' to build one.")
        return
    connection = sqlite3.connect(database_file)
    connection.execute("PRAGMA foreign_keys = ON")

    add_column_if_missing(connection, "stock_movements", "supplier_id", "TEXT REFERENCES suppliers(id)")
    add_column_if_missing(
        connection, "stock_movements", "total_cost_myr",
        "REAL CHECK (total_cost_myr IS NULL OR total_cost_myr >= 0)",
    )

    had_events_table = table_exists(connection, "low_stock_events")
    with open(SCHEMA_FILE, encoding="utf-8") as schema_file:
        connection.executescript(schema_file.read())   # every table uses IF NOT EXISTS, so old ones are untouched
    if had_events_table:
        print("Already there: table low_stock_events (nothing changed)")
    else:
        print("Created table low_stock_events")

    connection.commit()
    connection.close()
    print("Upgrade finished. No rows were changed or deleted.")


# Makes an existing database match sample_data/suppliers.csv and supplier_offers.csv: the sample suppliers are
# added or renamed, and each sample material gets exactly ONE active offer. Other offers on those materials are
# switched off (never deleted, Rule C9). Suppliers and materials that are not in the sample files are not touched.
def sync_sample_suppliers(database_file=DATABASE_FILE):
    if not os.path.exists(database_file):
        print("STOP: there is no database to sync. Run this script without arguments to build one.")
        return
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    for supplier in read_sample_rows("suppliers"):
        sync_one_supplier(connection, supplier)
    offers = read_sample_rows("supplier_offers")
    sample_material_ids = [row["id"] for row in read_sample_rows("materials")]
    marks = ", ".join("?" for _ in sample_material_ids)
    connection.execute(f"UPDATE supplier_offers SET is_active = 0 WHERE material_id IN ({marks})", sample_material_ids)
    for offer in offers:
        sync_one_offer(connection, offer)
    connection.commit()
    connection.close()
    print(f"Synced {len(offers)} offers: each sample material now has exactly one active supplier offer.")


# Adds one sample supplier, or updates the name, type and contact details of the one with the same id.
def sync_one_supplier(connection, supplier):
    known = connection.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier["id"],)).fetchone()
    if known is None:
        columns = list(supplier.keys())
        marks = ", ".join("?" for _ in columns)
        connection.execute(f"INSERT INTO suppliers ({', '.join(columns)}) VALUES ({marks})", [supplier[c] for c in columns])
        print(f"Added supplier {supplier['id']} {supplier['name']}")
        return
    connection.execute(
        "UPDATE suppliers SET name = ?, supplier_type = ?, address = ?, phone = ?, email = ?, website = ?, notes = ?, "
        "is_active = 1 WHERE id = ?",
        (supplier["name"], supplier["supplier_type"], supplier["address"], supplier["phone"], supplier["email"],
         supplier["website"], supplier["notes"], supplier["id"]))
    print(f"Updated supplier {supplier['id']} {supplier['name']}")


# Switches on the offer of this supplier and material (reusing an old row if there is one), or adds it.
def sync_one_offer(connection, offer):
    old = connection.execute("SELECT id FROM supplier_offers WHERE supplier_id = ? AND material_id = ? ORDER BY id",
                             (offer["supplier_id"], offer["material_id"])).fetchone()
    values = (offer["pack_size"], offer["pack_unit"], offer["price_per_pack_myr"], offer["minimum_order_packs"],
              offer["shipping_cost_myr"], offer["lead_time_days"])
    if old is not None:
        connection.execute(
            "UPDATE supplier_offers SET pack_size = ?, pack_unit = ?, price_per_pack_myr = ?, minimum_order_packs = ?, "
            "shipping_cost_myr = ?, lead_time_days = ?, is_active = 1 WHERE id = ?", values + (old["id"],))
        return
    offer_id = offer["id"]
    while connection.execute("SELECT 1 FROM supplier_offers WHERE id = ?", (offer_id,)).fetchone():
        offer_id = "O" + str(int(offer_id[1:]) + 1000)     # the sample id is taken by another row: use a free one
    connection.execute(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "minimum_order_packs, shipping_cost_myr, lead_time_days, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (offer_id, offer["supplier_id"], offer["material_id"]) + values)


# Builds all the tables from schema.sql, then loads the sample data.
def build_database():
    if os.path.exists(DATABASE_FILE):
        print("STOP: data/tracker.db already exists. Delete it by hand if you want a fresh start,")
        print("or run: python app/setup_database.py upgrade   (keeps all your data)")
        return

    os.makedirs(DATA_FOLDER, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE)
    connection.execute("PRAGMA foreign_keys = ON")   # make the database check that links are valid

    with open(SCHEMA_FILE, encoding="utf-8") as schema_file:
        connection.executescript(schema_file.read())

    for table_name in TABLES_TO_LOAD:
        count = load_table(connection, table_name)
        print(f"Loaded {count} rows into {table_name}")

    connection.commit()
    connection.close()
    print("Done. Database saved at data/tracker.db")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "upgrade":
        upgrade_database()
    elif len(sys.argv) > 1 and sys.argv[1] == "sync-suppliers":
        sync_sample_suppliers()
    else:
        build_database()

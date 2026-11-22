# WHAT THIS FILE DOES: Creates the database file from schema.sql and fills it with the sample data.
# WHO CAN USE IT: Developers only. Run it from the project folder with: python app/setup_database.py
#
# Safety rule: if data/tracker.db already exists, this script stops and does not touch it.
# Delete that file by hand only when you really want to start again.

import csv
import os
import sqlite3

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


# Builds all the tables from schema.sql, then loads the sample data.
def build_database():
    if os.path.exists(DATABASE_FILE):
        print("STOP: data/tracker.db already exists. Delete it by hand if you want a fresh start.")
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
    build_database()

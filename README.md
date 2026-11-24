# Stinablis Material & Supplier Tracker

A website for Stinablis (a 3D printing company in Kuching, Sarawak) that keeps one list of
materials and stock, one list of suppliers, warns when a material is running low, and suggests
the best supplier to order from. Only staff who log in can use it. Team: 3BitWonder.

**Read first:** [`CLAUDE.md`](CLAUDE.md) is the project guide (the PRD and the rulebook). Inside
that file it still calls itself `PROJECT_GUIDE.txt`; that is the same file. The status log at the
bottom of it says what each agent has done.

Other files for the team:

| File | What it is |
|---|---|
| [`GLOSSARY.md`](GLOSSARY.md) | Plain meaning of every technical word in the code |
| [`PRESENTATION_NOTES.md`](PRESENTATION_NOTES.md) | What each member says in the presentation |
| [`TESTS.md`](TESTS.md) | What the automatic and manual tests prove |

---

## How to run it (Windows, PowerShell)

Do these steps once, in order. Run every command from the project folder
(the folder that contains this file).

### 1. Check that Python is installed

```powershell
python --version
```

You should see Python 3 (we tested with 3.14). If not, install Python from python.org first.

### 2. Make a private Python space and install the libraries

```powershell
python -m venv .venv
```

Switch it on. Look inside the `.venv` folder: if it has a `Scripts` folder use the first command,
if it has a `bin` folder (this happens with some Python installs) use the second.

```powershell
.venv\Scripts\Activate.ps1
```

```powershell
.venv\bin\Activate.ps1
```

If PowerShell refuses with a message about "running scripts is disabled", run this once, then
try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Install the libraries the project needs (the list is in `requirements.txt`):

```powershell
pip install -r requirements.txt
```

We tested with Flask 3.1.3 and pytest 9.2.0.

### 3. Create the database with the sample data

```powershell
python app/setup_database.py
```

This makes `data/tracker.db` and fills it with **invented sample data** (supplier names start
with "SAMPLE"). It is not real Stinablis data. If the file already exists the script stops and
touches nothing. To start again, delete `data/tracker.db` by hand first. The `data/` folder is
ignored by Git on purpose; never commit it.

### 4. Choose a password for each sample account

```powershell
python app/auth.py set-password sample_admin
```

```powershell
python app/auth.py set-password sample_employee
```

You are asked to type the password twice (at least 8 characters; the letters are hidden while you
type). Passwords are saved scrambled in your own `data/tracker.db`. Never write a password in a
file, a chat message or Git.

### 5. Set the secret key

The secret key signs the login cookie. The app refuses to start without it. Make up a long random
one for yourself:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the text it prints, then set it **in the same PowerShell window you will start the app from**:

```powershell
$env:STINABLIS_SECRET_KEY = "paste-the-long-text-here"
```

This lasts only until you close the window, so repeat this step each time you open a new window.
Never put the real key in a file or in Git.

### 6. Start the app

```powershell
python -m flask --app app run
```

Open <http://127.0.0.1:5000> in your browser and log in. To stop the app, press Ctrl+C in the
PowerShell window.

---

## The two roles and how to log in

| Username | Role | Can do |
|---|---|---|
| `sample_admin` | **Admin** | Everything: add / change / remove materials, suppliers and prices; record stock; see all statistics; download the statistics CSV; manage user accounts on the **Users** screen |
| `sample_employee` | **Employee** | See materials, suppliers, prices and the "Find supplier" suggestions; record stock used and received; see low-stock warnings and the usage statistics. **Cannot** change anything else (including the Users screen), and is shown a "Forbidden" (403) page if they type an admin address |

The password for each account is the one you chose in step 4. Employees may *see* prices and money
(team decision 2026-11-24) but only the Admin can *change* them.

After 5 wrong passwords an account is locked for 15 minutes.

### A quick tour (about 2 minutes)

1. Log in as `sample_admin`. The **Home** page shows how many materials are LOW and OUT.
2. Press **Materials**, then **Record used** on a material and type a quantity (for example `200`).
3. Press **Find supplier** on a LOW material to see the ranked supplier list, cost and arrival date.
4. Log out, log in as `sample_employee`, and notice there are no Add / Change / Remove buttons.
   Type `/suppliers/new` after the web address: you get a "Forbidden" page.

The **Statistics** page draws its charts with Chart.js loaded from the internet, so the computer
needs a connection to see the charts.

---

## Run the tests

```powershell
python -m pytest tests
```

This takes about a minute. After the final merge on 2026-11-25 it reported **146 passed**. The tests
use a temporary database and never touch `data/tracker.db`. [`TESTS.md`](TESTS.md) lists what each test
proves. (Re-run it before the demo; the number changes whenever someone adds a test.)

---

## Known problems (as of the final merge, 2026-11-25; see the status log in `CLAUDE.md`)

* "Estimated money spent" on Home and the spending / low-stock charts still say "Not set up yet".
  The database has the new columns, but the "Record received" form does not yet ask for the supplier
  and cost, and low-stock events are not yet saved when they happen (Agents C and E).
* A database built before 2026-11-24 may contain old-format dates in its sample history, and the
  Record used page can fail on it. Build the database again (step 3) to fix it.
* The statistics charts load Chart.js from the internet. With no connection at the printers the charts
  stay empty.
* There is no activity-log screen (F9) and no one-click database backup yet. Every change is still
  written to the activity log table.
* There is no screen to correct a wrong stock count.

## What is not built (do not demo these)

Email alerts, automatic ordering, barcode scanning, printer connections, customer orders and a
phone app are out of scope for version 1 (guide Section 17).

## Why this fits Stinablis

* **One simple system for different kinds of stock.** Filament-only trackers such as Spoolman, and
  large print-farm ERPs such as FilaOps, are built around spools or whole factories. Ours keeps
  filaments (`g`), resins and liquids (`ml`) and small pieces (`pcs`) in one list. Because it supports
  pieces, it can also track small workshop hardware such as screws, springs, magnets, fidget clickers
  and keychain rings (subject to confirmation with the founder; which materials Stinablis really uses
  is still an open question, guide Section 16).
* **Built for buying in Kuching.** For each LOW or OUT material the Find supplier page compares every
  supplier of that material on estimated total cost (packs x price + shipping), minimum order and
  delivery time. The sample data shows the kind of choice: a local shop with delivery in 1 day, against
  an online shop with a lower price per pack but a larger minimum order and 7 days of shipping. Every
  number is labelled as an estimate. The real suppliers and lead times still come from the founder.
* **Made for the shop floor.** Plain-English labels, the status words OK / LOW / OUT shown with their
  colours, big buttons, a layout that works on a phone at the printer, and every permission checked on
  the server.

## Where things are

```
CLAUDE.md          the project guide and status log (read first)
requirements.txt   the libraries to install
app/               the application (Python / Flask)
  __init__.py        starts the app, needs STINABLIS_SECRET_KEY
  auth.py            login, logout, passwords, 5-wrong-passwords lock
  permissions.py     the rules of who can do what (the only place roles are checked)
  routes_materials.py  materials screens and Record used / received
  routes_suppliers.py  suppliers screens and the "Find supplier" page
  routes_stats.py      Home boxes, statistics, CSV download
  routes_users.py      the Users screen (Admin only)
  csrf.py              the hidden token that protects every form
  alerts.py          OK / LOW / OUT rule
  suggest.py         best-supplier ranking, cost and arrival date
  schema.sql         the database tables
  setup_database.py  builds data/tracker.db from sample_data/
  templates/         the HTML pages
sample_data/       invented sample data (fake; see SAMPLE_DATA_README.txt)
tests/             automatic tests
data/              your local database (ignored by Git)
```

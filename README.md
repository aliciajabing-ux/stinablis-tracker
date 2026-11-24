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

Install the two libraries the project needs (there is no `requirements.txt` yet; see the status log):

```powershell
pip install flask pytest
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
| `sample_admin` | **Admin** | Everything: add / change / remove materials, suppliers and prices; record stock; see all statistics; download the statistics CSV |
| `sample_employee` | **Employee** | See materials, suppliers, prices and the "Find supplier" suggestions; record stock used and received; see low-stock warnings and the usage statistics. **Cannot** change anything else, and is shown a "Forbidden" (403) page if they type an admin address |

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

This takes under a minute. On 2026-11-24 it reported **108 passed**. The tests use a temporary
database and never touch `data/tracker.db`. [`TESTS.md`](TESTS.md) lists what each test proves.

---

## Known problems (as of 2026-11-24; see the status log in `CLAUDE.md`)

* **After step 3, "Record used" / "Record received" and the usage chart show an error page
  (500).** The sample file `sample_data/stock_movements.csv` writes dates like
  `2026-11-10T02:00:00Z`, but the app expects `2026-11-10 02:00:00`. Until Agent A fixes the
  sample file, repair your own local database once with this command (it only changes your
  ignored `data/tracker.db`):

  ```powershell
  python -c "import sqlite3; d = sqlite3.connect('data/tracker.db'); d.execute('UPDATE stock_movements SET created_at = substr(created_at,1,10) || char(32) || substr(created_at,12,8) WHERE length(created_at) = 20'); d.commit(); print('Dates repaired')"
  ```

  Then reload the page. (Starting over with step 3 after the fix also works.)
* "Estimated money spent" on Home and the spending / low-stock charts say "Not set up yet": the
  team still has to build how those numbers are stored.
* Forms have no CSRF protection yet (see the glossary).
* There is no Admin screen yet for user accounts, the activity log, or a one-click database backup
  (features F8 and F9 in the guide, and a Section 14 checklist item).

## What is not built (do not demo these)

Email alerts, automatic ordering, barcode scanning, printer connections, customer orders and a
phone app are out of scope for version 1 (guide Section 17).

## Where things are

```
CLAUDE.md          the project guide and status log (read first)
app/               the application (Python / Flask)
  __init__.py        starts the app, needs STINABLIS_SECRET_KEY
  auth.py            login, logout, passwords, 5-wrong-passwords lock
  permissions.py     the rules of who can do what (the only place roles are checked)
  routes_materials.py  materials screens and Record used / received
  routes_suppliers.py  suppliers screens and the "Find supplier" page
  routes_stats.py      Home boxes, statistics, CSV download
  alerts.py          OK / LOW / OUT rule
  suggest.py         best-supplier ranking, cost and arrival date
  schema.sql         the database tables
  setup_database.py  builds data/tracker.db from sample_data/
  templates/         the HTML pages
sample_data/       invented sample data (fake; see SAMPLE_DATA_README.txt)
tests/             automatic tests
data/              your local database (ignored by Git)
```

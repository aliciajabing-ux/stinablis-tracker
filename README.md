# Stinablis Material & Supplier Tracker

A website for Stinablis (3D printing, Kuching) that staff log into. It keeps one list of materials and
suppliers, warns when stock is LOW or OUT, suggests which supplier to order from, and shows simple statistics.

Team: 3BitWonder. The full plan and rules are in **`CLAUDE.md`** (the project guide). Read it before changing
anything. If this README and the guide disagree, the guide wins.

---

## How to run it (Windows PowerShell)

Run every command from the project folder (the one that contains `app` and `tests`).

**1. Make a private Python environment (once)**
```
python -m venv .venv
```

**2. Install the libraries (once)**
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
If the `.venv\Scripts` folder does not exist, use `.venv\bin` in this and every command below.
Do not use another Python (for example the one in `C:\msys64`): it will not have Flask.

**3. Build the database with the sample data (once)**
```
.venv\Scripts\python.exe app\setup_database.py
```
This makes the file `data\tracker.db`. If the file already exists, the script stops and touches nothing.
To start again, close the app, delete `data\tracker.db` by hand, and run the command again.
This erases everything stored in the old file.

**4. Give the sample users a password (once)**
```
.venv\Scripts\python.exe app\auth.py set-password sample_admin
.venv\Scripts\python.exe app\auth.py set-password sample_employee
```
You type the password twice (at least 8 characters). Passwords are never saved in Git and never shown on screen.

**5. Start the website (every time)**
```
$env:STINABLIS_SECRET_KEY = "type-any-long-random-text-here"
.venv\Scripts\python.exe -m flask --app app run
```
The secret key signs the login cookie. Never write it in a file or commit it. Leave this window open while
you use the site. Press Ctrl+C to stop it.

**6. Open it:** http://localhost:5000/ and log in.

---

## Who can do what

| | Admin | Employee |
|---|---|---|
| See materials, stock, LOW / OUT warnings | Yes | Yes |
| Record stock used or received | Yes | Yes |
| See supplier details, prices, shipping and the supplier suggestion | Yes | Yes (view only) |
| Add, change or remove materials | Yes | No |
| Add, change or switch off suppliers and prices | Yes | No |
| See usage statistics | Yes | Yes |
| Spending chart and CSV download | Yes | No |
| Users screen (add user, change role, reset password, switch off) | Yes | No |

Sample accounts: `sample_admin` (Admin) and `sample_employee` (Employee).
Every permission is checked on the server, so typing an address by hand does not get around it.

Other rules you will notice:
- 5 wrong passwords lock the account for 15 minutes.
- Nothing is ever deleted. Materials, suppliers and users are switched off instead, and their history stays.
- Every stock change is written to the history, and every change to users, materials and suppliers is written
  to the activity log.
- Times are stored in UTC and shown in Malaysia time (UTC+8). Money is in MYR.
- All numbers on the suggestion screen are estimates.

---

## Run the automatic tests

```
.venv\Scripts\python.exe -m pytest tests
```
The tests use a temporary database, never `data\tracker.db`. All of them should pass. The results and the
manual browser checks are listed in `TESTS.md`.

---

## What is in the folder

| Path | What it is |
|---|---|
| `CLAUDE.md` | The project guide, rules and STATUS LOG |
| `TESTS.md` | Test results for each part |
| `app/` | The website code. `permissions.py` decides who can do what |
| `app/templates/` | The HTML pages |
| `sample_data/` | Fake data for testing (see `SAMPLE_DATA_README.txt`). Not real Stinablis data |
| `tests/` | Automatic checks |
| `data/` | The database file. Never committed to Git |

---

## Known problems and things not built yet

- The forms have no CSRF protection yet (a second layer against forged form posts). The team still has to
  decide on it. Today only the SameSite cookie setting protects them.
- The "money spent this month" box and the low-stock events chart say "Not set up yet". The team chose to store
  the real cost when stock is received, and to store each low-stock event as it happens. That needs a database
  change and a change to the "Record received" form first.
- There is no screen yet to correct a wrong stock count.
- There is no activity log screen, no one-click database backup, and no email alerts.
- The charts load Chart.js from the internet. Without internet at the printers the charts stay empty.
- The sample data is invented. Replace it when the founder answers the questions in Section 16 of the guide.
- A database made before 2026-11-24 has old dates in the sample history and the Record used page can fail on
  it. Build the database again (step 3) to fix it.

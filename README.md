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

This makes `data/tracker.db` and fills it with **invented sample data** (made-up suppliers,
prices and stock). It is not real Stinablis data. If the file already exists the script stops and
touches nothing. To start again, delete `data/tracker.db` by hand first. The `data/` folder is
ignored by Git on purpose; never commit it.

### 4. The sample passwords (demo only)

A **fresh** database already has fixed demo passwords, so there is nothing to type:

| Username | Password |
|---|---|
| `sample_admin` | `sampleadmin` |
| `sample_employee` | `sampleemployee` |

These are public demo passwords (team decision 2026-11-27). Use them only on demo or test databases,
never with real company data. To choose your own password for any account, run
`python app/auth.py set-password sample_admin` (at least 8 characters; the letters are hidden while you
type). The `upgrade` and `sync-suppliers` commands never change a password.

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

The demo passwords are in step 4 (or the one you chose with `set-password`). Employees may *see* prices and money
(team decision 2026-11-24) but only the Admin can *change* them.

After 5 wrong passwords an account is locked for 15 minutes.

### A quick tour (about 2 minutes)

1. Log in as `sample_admin`. The **Home** page shows how many materials are LOW and OUT.
2. Press **Materials**, then **Record used** on a material and type a quantity (for example `200`).
3. Press **Find supplier** on a LOW material to see the ranked supplier list, cost and arrival date.
   On the Materials page, look for the **Last bought** line under a material (see below).
4. Log out, log in as `sample_employee`, and notice there are no Add / Change / Remove buttons.
   Type `/suppliers/new` after the web address: you get a "Forbidden" page.

The **Statistics** page draws its charts with Chart.js loaded from the internet, so the computer
needs a connection to see the charts.

---

## Run the tests

```powershell
python -m pytest tests
```

This takes about a minute. After the group's final merge (2026-11-26) it reported
**458 passed, 2 skipped, 6 expected failures** (an "expected failure" is a test that describes a
known bug; see the status log). The tests use a temporary database and never touch
`data/tracker.db`. [`TESTS.md`](TESTS.md) lists what each test proves. (Re-run it before the demo;
the numbers change whenever someone adds a test.)

---

## What you will notice on the screens

* **"Last bought" memory.** On the Materials list and on the Record used / Record received pages, each
  material can show who it was last bought from, how much, the date and (if someone typed it) the
  total paid in MYR. It is read from the newest "received" line that names a supplier or a cost. Admin
  and Employee both see the money (view only, team decision 2026-11-24, `can_see_prices`); the server
  still answers 403 to anyone who tries to change prices. A material with no such line shows nothing.
* **Sample materials, including hardware in pieces (`pcs`).** The sample data has 39 materials. The first
  13 include SAMPLE-named hardware (M4 socket screws, compression springs, magnets, a fidget clicker kit,
  keychain rings) sold by a SAMPLE hardware supplier. A teammate then added 26 more (M014 to M039: PLA+,
  PLA, PETG and PLA Silk filament, screws, nuts, inserts, bearings, magnets, clicker switches, keychain
  parts and more) so that Test 2 can be run. These are **not** named "SAMPLE" and have **no supplier
  offers yet**. All of it is demo data: the founder has not confirmed what Stinablis really tracks (guide
  Section 2 and Section 16 Q1). The Materials list shows two sections, "Filament & other materials" and
  "Hardware", and inside each section it runs OK, then LOW, then OUT.
* **OK / LOW / OUT in plain English.** The Materials page explains the words once: **OK** = enough in
  stock, **LOW** = at or below the reorder level (time to order), **OUT** = none left. The word is always
  shown together with the colour.
* **Easy to tap.** Buttons and links on the new and changed screens are at least about 44 px tall, so a
  thumb can hit them on a phone. A shared dark theme (`app/static/theme.css`, Agent H) now styles every
  screen; Agent H checked login, Home, Materials and Statistics in a browser, not every page.
  **Still to check in a browser:** the top menu links get their size from `theme.css` (padding plus a small
  minimum height), so confirm on a phone that they are also about 44 px tall, as the screen controls are.
* **Plain-English error pages.** If you have no permission (403), a page is missing (404) or a form has
  expired (400), you see a short sentence in plain words and a **Back to Home** button, instead of a
  technical page. The browser still gets the real error number.
* **Prices paid and low-stock events now work.** On "Record received" **only an Admin** sees and can fill
  the two optional boxes "Bought from" and "Total paid (MYR)" (rule `can_record_purchase_cost`). An
  Employee can still record received stock, without the money; if an Employee types money anyway the
  server answers 403 and saves nothing. The Admin-only supplier price comparison on the Statistics page
  uses the prices paid. (Home no longer has a "money spent" box: the group removed it on 2026-11-26, so
  Home shows three boxes: total, LOW and OUT.) A low-stock
  event is saved each time a "Record used" drops a material from OK to LOW or OUT (the Statistics page
  no longer draws a chart of them).

## Known problems (as of 2026-11-26; see the status log in `CLAUDE.md`)

* Received lines saved without a total (always the case when an Employee records them) count as MYR 0
  in the money numbers (price comparison and CSV). Low-stock events
  are counted from the day the feature was switched on, so older drops have no event.
* A database built before 2026-11-24 may be missing the new columns and the new table (and may have
  old-format dates). Build the database again (step 3): close the app, delete `data\tracker.db`, and run
  step 3 once more. This erases everything in the old file.
* The statistics charts load Chart.js from the internet. With no connection at the printers the charts
  stay empty.
* There is no activity-log screen (F9) and no one-click database backup yet. Every change is still
  written to the activity log table.
* There is no screen to correct a wrong stock count.
* **Open phone-test findings (from the status log, not re-tested in a browser by me):**
  **F-11** the Materials, Suppliers and Supplier pages need sideways scrolling on a phone to see the right
  columns; **F-12** supplier phone numbers and emails are plain text, not tappable `tel:` / `mailto:` links
  (I also found no such links in the templates); **F-13** (the "Average delivery time per supplier" chart cut off
  on phones) was about a chart that has since been replaced by the "Delivery ranking" on the Statistics
  page; I have not re-checked that page on a phone. Text size and buttons were fine in that test. F-11 and
  F-12 have no fix logged yet.
* Six automatic tests are marked "expected failure" because they describe known bugs found by
  Agent F (see the status log).

## Real user test with Ryan (2026-11-26)

Ryan from Stinablis tested the app (Jacob was not available). He was timed.

* **Before the test (pre-test interview, confirmed by Ryan):** Stinablis spends about **2 to 3 hours per
  week** finding out where materials were bought. That means checking the **Shopee purchase history**,
  **local shop memory**, a **collaborator list** and **past receipts**.
* **Test 1 tasks (total time 7:16):**
  1. Find where we bought standard resin.
  2. Find which supplier is cheapest for nuts.
  3. Add a new purchase.
* **Where he got stuck: Tasks 1 and 2** (finding standard resin's supplier, and comparing supplier prices
  for nuts). Reason: the Materials list had **no search bar**, and moving between stock information and
  supplier information was **not direct**.
* **His words, exactly:** "Will use but need improvements. (Don't want confusing) As long can key in one data, its good."
* **What it means for us:** he will use it, but it must not be confusing, and the one thing that matters is
  typing in one piece of data quickly.

**What changed on `main` after the test (the group's final decisions, 2026-11-26):**

1. **A search box first on Materials** ("Search by item name", the list narrows as you type).
2. **The list runs OK, then LOW, then OUT**, and the "Show only OK" button is hidden to reduce clutter.
3. **Two sections on Materials:** "Filament & other materials" and "Hardware" (items counted in pieces).
   The OK, LOW, OUT order applies inside each section. The group added 26 more sample materials (M014 to
   M039) so Test 2 can be run: they include PLA+ Orange and PETG Grey.
4. **The Statistics page** (the menu word stays "Statistics") has a delivery ranking per chosen material
   (fastest to slowest, no prices). The Home page stays simple, with a **Notifications** list, and OUT
   stays red. (An earlier idea to rename the page "Stock" and add a Current stock list on Home was **not**
   kept.)

**Honest open gaps:**
* **Task 2 is still not a one-step job.** The "Find supplier" page only shows a ranked supplier list for
  items that are **LOW or OUT**, so for an item that is OK (such as nuts) there is no direct comparison.
  The 26 new sample materials also have **no supplier offers yet**. The team still has to decide (guide
  rule R4) whether the comparison should work for every item.
* **Test 2 has not been timed or completed.** It uses **PLA Orange, PETG Gray and adding a new purchase**.
  Until it is done we do **not** claim any faster time than the 7:16 baseline. Write the Test 2 time next
  to 7:16. (The new sample data contains "PLA+ 1.75mm" in Orange and "PETG 1.75mm" in Grey for this.)

## What is not built (do not demo these)

Email alerts, automatic ordering, barcode scanning, printer connections, customer orders and a
phone app are out of scope for version 1 (guide Section 17).

## Why this fits Stinablis

* **One simple system for different kinds of stock.** Filament-only trackers such as Spoolman, and
  large print-farm ERPs such as FilaOps, are built around spools or whole factories. Ours keeps
  filaments (`g`), resins and liquids (`ml`) and small pieces (`pcs`) in one list. Because it supports
  pieces, it can also track small workshop hardware such as screws, springs, magnets, fidget clickers
  and keychain rings. The hardware in our demo is sample data only; which materials Stinablis really
  uses still has to be confirmed with the founder (guide Section 16).
* **Built for buying in Kuching.** For each LOW or OUT material the Find supplier page compares every
  supplier of that material on estimated total cost (packs x price + shipping), minimum order and
  delivery time. The sample data shows the kind of choice: a local shop with delivery in 1 day, against
  an online shop with a lower price per pack but a larger minimum order and 7 days of shipping. Every
  number is labelled as an estimate. The real suppliers and lead times still come from the founder.
* **Made for the shop floor.** Plain-English labels, the status words OK / LOW / OUT shown with their
  colours, big tap-friendly buttons (at least about 44 px tall), a "Last bought" reminder next to each
  material, plain-English error pages with a Back to Home button, a layout that works on a phone at
  the printer, and every permission checked on the server.

## Where things are

```
CLAUDE.md          the project guide and status log (read first)
requirements.txt   the libraries to install
app/               the application (Python / Flask)
  __init__.py        starts the app, needs STINABLIS_SECRET_KEY
  auth.py            login, logout, passwords, 5-wrong-passwords lock
  permissions.py     the rules of who can do what (the only place roles are checked)
  routes_materials.py  materials screens, Record used / received, "Last bought" line
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

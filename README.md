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
| `sample_admin` | **Admin** | Everything: add / change / remove materials, suppliers and prices; record stock; see everything on the **Stock** page; download the CSV; manage user accounts on the **Users** screen |
| `sample_employee` | **Employee** | See materials, suppliers, prices and the "Find supplier" suggestions; record stock used and received; see low-stock warnings (the **Noti** list) and the **Stock** page (current stock and usage). **Cannot** change anything else (including the Users screen), and is shown a "Forbidden" (403) page if they type an admin address |

The password for each account is the one you chose in step 4. Employees may *see* prices and money
(team decision 2026-11-24) but only the Admin can *change* them.

After 5 wrong passwords an account is locked for 15 minutes.

### A quick tour (about 2 minutes)

1. Log in as `sample_admin`. The **Home** page shows how many materials are LOW and OUT.
2. Press **Materials**, then **Record used** on a material and type a quantity (for example `200`).
3. Press **Find supplier** on a LOW material to see the ranked supplier list, cost and arrival date.
   On the Materials page, look for the **Last bought** line under a material (see below).
4. Log out, log in as `sample_employee`, and notice there are no Add / Change / Remove buttons.
   Type `/suppliers/new` after the web address: you get a "Forbidden" page.

The **Stock** page (it was called Statistics until 2026-11-26) draws its charts with Chart.js loaded from the internet, so the computer
needs a connection to see the charts.

---

## Run the tests

```powershell
python -m pytest tests
```

This takes about a minute. After Ryan's user-test fixes (2026-11-26) it reports
**405 passed, 2 skipped, 6 expected failures** (an "expected failure" is a test that describes a
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
* **Sample hardware items in pieces (`pcs`).** The sample data now has small hardware next to the
  `g` and `ml` items: SAMPLE M4 socket screws, compression springs, magnets, a fidget clicker kit and
  keychain rings, sold by a SAMPLE hardware supplier. They are **demo items only**: the founder has
  not confirmed what hardware Stinablis really tracks (guide Section 2 and Section 16 Q1).
* **OK / LOW / OUT in plain English.** The Materials page explains the words once: **OK** = enough in
  stock, **LOW** = at or below the reorder level (time to order), **OUT** = none left. The word is always
  shown together with the colour.
* **Easy to tap.** Buttons and links on the new and changed screens are at least about 44 px tall, so a
  thumb can hit them on a phone. A shared dark theme (`app/static/theme.css`, Agent H) now styles every
  screen; Agent H checked login, Home, Materials and Stock in a browser, not every page.
  **Still to check in a browser:** the top menu links get their size from `theme.css` (padding plus a small
  minimum height), so confirm on a phone that they are also about 44 px tall, as the screen controls are.
* **Plain-English error pages.** If you have no permission (403), a page is missing (404) or a form has
  expired (400), you see a short sentence in plain words and a **Back to Home** button, instead of a
  technical page. The browser still gets the real error number.
* **Money spent and low-stock events now work.** On "Record received" **only an Admin** sees and can fill
  the two optional boxes "Bought from" and "Total paid (MYR)" (rule `can_record_purchase_cost`). An
  Employee can still record received stock, without the money; if an Employee types money anyway the
  server answers 403 and saves nothing. Home's money box adds up the real totals for the current month,
  and the spending chart (Admin only) shows them per supplier. A low-stock event is saved each time a
  "Record used" drops a material from OK to LOW or OUT. (Since 2026-11-26 no page draws a chart of these events; they are still saved.)

## Known problems (as of 2026-11-25; see the status log in `CLAUDE.md`)

* Received lines saved without a total (always the case when an Employee records them) count as MYR 0
  in the money numbers. Low-stock events
  are counted from the day the feature was switched on, so older drops have no event.
* A database built before 2026-11-24 may be missing the new columns and the new table (and may have
  old-format dates). Build the database again (step 3): close the app, delete `data\tracker.db`, and run
  step 3 once more. This erases everything in the old file.
* The Stock page charts load Chart.js from the internet. With no connection at the printers the charts
  stay empty.
* There is no activity-log screen (F9) and no one-click database backup yet. Every change is still
  written to the activity log table.
* There is no screen to correct a wrong stock count.
* **Open phone-test findings (from the status log, not re-tested in a browser by me):**
  **F-11** the Suppliers and Supplier pages still need sideways scrolling on a phone (the **Materials** list
  was fixed on 2026-11-26: each material is now a small card with its status word and buttons visible);
  **F-12** supplier phone numbers and emails are plain text, not tappable `tel:` / `mailto:` links
  (I also found no such links in the templates), still open; **F-13** is **closed**: the delivery-time chart
  that was cut off on phones was replaced by the "Supplier speed ranking" list on 2026-11-26.
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
  supplier information was **not direct**. This is why we added the instant search bar on Materials and put
  Current stock and the quick actions together on Home.
* **His words, exactly:** "Will use but need improvements. (Don't want confusing) As long can key in one data, its good."
* **What it means for us:** he will use it, but it must not be confusing, and the one thing that matters is
  typing in one piece of data quickly.

**The four highest-impact fixes made on 2026-11-26 (all permission rules unchanged, no table changed):**

1. **Fast search at the top of Materials.** A big "Search by item name" box is the first thing on the
   page, ready to type in, and the list narrows as you type. On a phone each material is now a small card,
   so its status word and the Record buttons are visible without sideways scrolling.
2. **Simpler navigation and Home.** The menu word "Statistics" is now **Stock**. Home shows **Current
   stock** next to the quick shortcuts (**Record used** and **Record received** on every row). The "Show
   only OK" button was removed as clutter.
3. **Clearer status.** Lists show OK first, then LOW, then OUT. The OUT badge is now a calm dashed outline,
   not an alarm colour (the word OUT is still written). "Needs attention" is now **Noti**.
4. **Clearer charts.** The low-stock events chart and the average delivery time chart are gone (this also
   closes F-13). The Stock page now has a **Current stock** chart where you choose the unit (grams,
   millilitres or pieces), and a **Supplier speed ranking** list from fastest to slowest. No money appears
   in either, so Admin and Employee both see them.

**Honest open gap (Task 2):** the search bar now finds "nuts" instantly, but the "Find supplier" page only
shows a ranked supplier list for items that are **LOW or OUT**. In the sample data the nuts are OK, so
comparing their suppliers is still not a one-step job, and the Materials list has no "Find supplier" button.
The team should decide (guide rule R4) whether that comparison should work for every item. It is not fixed yet.

**Not yet re-tested:** **Test 2** (PLA Orange, PETG Gray, add a new purchase) has **not been timed or
completed yet**. Until it is, we do **not** claim any faster time than the 7:16 baseline. Note: the sample
data has no "PLA Orange" or "PETG Gray" (it has PLA Basic White and Black, and PETG Clear), so add those
items first, or run Test 2 on the real data. Write the Test 2 time next to the 7:16 baseline.

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
  routes_stats.py      Home boxes, Current stock, Stock page and its data, CSV download
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

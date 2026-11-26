# Presentation notes (for every team member)

Goal (guide Section 13): **every member can explain these six things in plain words.** Read the
"Say it like this" box for each topic, learn the facts under it, and practise the demo. Unknown
words are in [`GLOSSARY.md`](GLOSSARY.md).

Facts below were checked against the code and by running the app on 2026-11-24. The sample numbers
are **invented sample data** (supplier names start with "SAMPLE"); never present them as real
Stinablis facts or real prices (rule R7).

Last re-checked against code: 2026-11-26, after the fixes from Ryan's user test (405 automatic tests
passed, 2 skipped, 6 "expected failures" that describe known bugs). That includes all feature, test and
design branches. Re-check these notes if anything else is merged (see the status log in `CLAUDE.md`).

**Ryan's user test (2026-11-26) in one breath:** Ryan from Stinablis (Jacob was not available) was timed:
7:16 baseline, stuck on steps 1 and 2. In his words: "Will use but need improvements. (Don't want confusing) As long can key in one data, its good."
We made four fixes: fast search first on Materials; "Statistics" renamed **Stock** and Home shows Current
stock with Record shortcuts; OK, LOW, OUT order with a softer OUT badge and "Noti" instead of "Needs
attention"; and two confusing charts replaced by a Current stock chart (pick g, ml or pieces) and a
Supplier speed ranking list. We have **not** re-timed the flow yet; do not claim it is faster.

> **Reminder before the final demo:** test counts, pending fixes and open-source log notes can go
> stale. Re-check them against `TESTS.md` and the STATUS LOG in `CLAUDE.md` right before the demo.

---

## 1. The problem

> **Say it like this:** "Stinablis is a 3D printing company in Kuching. Staff have to remember how
> much material is left, which supplier sells what at what price, and then notice in time when
> something is running low. That is slow and easy to get wrong, so printing jobs sometimes stop
> because the material ran out. We built one website that keeps all of this in one place and warns
> people early."

Facts:
- Three jobs that waste time today: (a) tracking how much is left, (b) remembering supplier, price,
  contact and delivery time, (c) noticing "low" and finding someone to buy from, often too late.
- What the website does: one list of materials and stock; one list of suppliers; low-stock
  warnings; a suggested supplier with an estimated cost and arrival date; simple statistics;
  different rights for different users.
- **Why our app fits Stinablis better than filament-only tools (like Spoolman) or heavy print-farm
  ERPs (like FilaOps):**
  - *One system for several kinds of stock.* Stinablis does industrial engineering and rapid
    prototyping in Kuching. Because our system supports pieces (`pcs`) alongside grams (`g`) and
    millilitres (`ml`), it can track filaments, resins and liquids, and also small hardware items such as
    screws, springs, magnets, fidget clickers and keychain rings, in one simple web app. The hardware in
    our demo is **sample data only** (names start with "SAMPLE"). Whether Stinablis really tracks such
    items is **to be confirmed with the founder** (guide Section 2 and Section 16 Q1, Rule R4).
  - *Buying in Kuching.* The Find supplier page compares a fast local shop (for example delivery in
    1 day) with an online shop that may have a cheaper pack price but a larger minimum order and
    several days of shipping, using estimated total cost and arrival date. Every number is marked as
    an estimate. The suppliers in our demo are invented sample data; the founder still has to give us
    the real ones.
  - *Made for the shop floor.* Plain-English labels, the words OK / LOW / OUT shown with their
    colours and explained once in a sentence on the Materials page, big buttons (at least about 44 px
    tall, so a thumb can tap them), a "Last bought" reminder next to each material, plain-English error
    pages with a **Back to Home** button, a phone-friendly layout, and every permission checked on the
    server. Be honest about phones: the team's phone test found buttons and text fine, but wide tables
    scroll sideways on the Suppliers pages (F-11; the Materials list was fixed on 2026-11-26 and is now a stack
    of small cards), and phone numbers are not yet tappable (F-12). The cut-off delivery-time chart (F-13)
    is gone: it was replaced by the Supplier speed ranking list. F-11 (Suppliers pages) and F-12 are still
    open findings from the status log.
    *To check before the demo:* the top menu links get their size from `theme.css`; confirm in a browser
    that they are about 44 px tall, like the other controls.
  - *SupplyTrail pitch (team goal, not a measured result).* The aim is to cut the time spent searching
    for suppliers, local Kuching shops against online ones, from about 2 hours a week towards about
    30 minutes a week. These two numbers come from the team's pitch. I could not find them in
    `CLAUDE.md` or the founder questions, so treat them as an **estimate to confirm with the founder**
    (Section 16), not as a proven saving.
- Only logged-in staff can use it. It works on a phone browser at the printer.
- It is **not** built yet: email alerts, automatic ordering, barcode scanning, connecting to
  printers, customer orders, a phone app (guide Section 17: version 2 ideas).

## 2. The two roles

> **Say it like this:** "There are two kinds of user. The Admin is the owner or manager and can do
> everything. The Employee, for example a printer operator, can look at everything and record stock
> used or received, but cannot change materials, suppliers or prices, and cannot manage users."

| | Admin | Employee |
|---|---|---|
| See materials, stock, LOW / OUT warnings | Yes | Yes |
| Record stock **used** / **received** | Yes | Yes |
| Type "Bought from" and "Total paid (MYR)" when recording **received** | Yes | **No** (403 if tried) |
| See supplier contacts, **prices, shipping, cost estimates** | Yes | Yes (team decision 2026-11-24) |
| See "Last bought" (who, how much, date, total paid in MYR) | Yes | Yes (view only) |
| Add / change / remove materials | Yes | **No** (403) |
| Add / change / switch off suppliers and offers, change prices | Yes | **No** (403) |
| Stock page: current stock (choose g, ml or pieces), usage, supplier speed ranking | Yes | Yes |
| Stock page: spending chart, CSV download | Yes | **No** (403) |
| Manage user accounts (Users screen: add user, change role, reset password, switch off) | Yes | **No** (403) |

Facts:
- Each user has exactly one role. Login is a username and password; 5 wrong passwords lock the
  account for 15 minutes.
- **Safety rule:** permissions are checked on the **server**. Hiding a button is not enough: an
  Employee who types an admin address is stopped with a "Forbidden" (403) page.
- If in doubt, deny (guide Section 4).
- Still open for the founder: should Employees see supplier phone numbers and emails? Today they
  can (our proposal); the founder has not confirmed.
- Settled (guide Section 5, F7): the Stock page's spending chart and CSV export are Admin only.
- Built: the Admin Users screen (F8). Not built yet: the activity-log screen (F9). Every change is
  still written to the activity log table.

## 3. One feature from start to finish: "Record used"

> **Say it like this:** "Say a printer operator used 200 grams of white PLA. They open Materials, press
> Record used, type 200 and press Save. The server first checks they are logged in and allowed to
> record stock. Then it checks that 200 is a proper number and that we really have that much. If all
> is well it lowers the stock number, writes a line in the stock history, and writes a line in the
> activity log saying who did it. If the new number is at or below the reorder level, the material
> shows as LOW on the Home page."

Step by step (code in `app/routes_materials.py`, `app/alerts.py`):

1. **Screen:** Materials list, press **Record used** on a row. Page address `/materials/<id>/record/used`.
   The page shows the current stock, the status word, a one-line hint if it is LOW or OUT, a **Last
   bought** line (who it was bought from, how much, the date and the total paid in MYR if it was typed),
   and the last 10 history lines in Malaysia time.
2. **Send:** the person types a quantity (and an optional note) and presses Save. The browser sends
   a POST to the server.
3. **Server checks the form is genuine and the person is allowed:** the form carries a hidden
   secret token (CSRF protection); a missing or wrong token is refused. Then `login_required`, then
   `can_record_stock(user)` from `permissions.py` (Admin and Employee both pass). Anyone else gets 403
   or the login page.
4. **Server checks the input:** `read_number` accepts only a plain number (no letters, minus, zero,
   or more than two decimals). The note must be 200 letters or fewer. A bad input gives a message in
   plain words, for example "Please type the quantity as a number, for example 200".
5. **Server checks stock:** you cannot take out more than you have. The database update itself only
   works if enough is left, so two people cannot take the same grams at the same moment.
6. **Stock number goes down:** `quantity_on_hand` drops by 200, rounded to 2 decimals.
7. **History row written:** one new row in `stock_movements` (type USED, quantity, note, who, when
   in UTC). Rows are never edited.
8. **Activity log row written:** for example "Used 200 g of PLA Basic. Now 630 g." (rule C8).
9. **Save together:** both rows and the new number are committed at once; if anything fails
   everything is undone.
10. **Back to the list** with a short confirmation message.
11. **LOW or OUT:** the status is not stored; it is worked out each time a page is shown by
    `get_status` (zero or less = OUT; at or below the reorder level = LOW; otherwise OK). So the Home
    page "Noti" list and the orange LOW box update by themselves.

Verified on 2026-11-24 with the sample data: PLA Basic White 830 g (reorder level 1000 g, so
already LOW); an Employee recorded 200 g used; quantity became 630 g, one USED row and one
STOCK_USED activity row appeared.

**Demo tip:** use the Section 15 checklist. Add a material with reorder level 500 g and quantity
800 g (status OK), record 400 g used (400 g, LOW), record 400 g used again (0 g, OUT).

**Record received (new):** the form has two optional boxes, "Bought from" and "Total paid (MYR)". **Only
an Admin** sees and can fill them. This is enforced on the server by `can_record_purchase_cost` in
`permissions.py`: an Employee can still record received stock, but without money, and if an Employee
sends supplier or total anyway the server answers **403** and saves nothing. What the Admin types becomes
the new "Last bought" line and the real number behind Home's "money spent" box. Employees can still
**see** "Last bought" and its money, according to `can_see_prices()`, but cannot change it.

**Sample data check (2026-11-25):** the sample file's date format bug is fixed. An automatic test
builds the database from the sample files and opens the Record used page, the usage data and the CSV
without errors. If you built your database before 2026-11-24, build it again (README step 3).

## 4. How the best supplier is picked

> **Say it like this:** "When a material is LOW or OUT you press Find supplier. The system works out
> how much we need to buy, then for every supplier that sells it, how many packs that means, what
> the total would cost with shipping, and which day it would arrive. Then it lists the suppliers
> with the cheapest total first and, if the cost is the same, the fastest delivery first. Every
> money number and date is marked as an estimate."

The rules (code in `app/suggest.py`; guide Sections 5 F6 and 7):

1. **Quantity needed** = (reorder level x 2) minus what we have now (never below zero).
   *(The guide still marks this formula "[CONFIRM] with the founder".)*
2. **Packs to order** = quantity needed divided by the pack size, **rounded up** to whole packs,
   and never fewer than the supplier's minimum order.
3. **Estimated cost** = packs x price per pack + shipping cost.
4. **Estimated arrival** = today (Malaysia time) + the supplier's lead time in days.
5. **Which suppliers count:** only active suppliers and active offers, and only offers sold in the
   same unit as the material (grams, millilitres or pieces).
6. **Ordering:** sorted by cheapest estimated cost, then shortest lead time.
7. **"In time":** the guide says "only suppliers that can deliver in time" but does not define it.
   So the page has an optional box, "Needed within how many days?". If you fill it in, slower
   suppliers drop out; if you leave it empty every supplier counts. The founder has not confirmed
   this.

**Worked example with the invented sample data** (PLA Basic White, 830 g on hand, reorder level
1000 g, sold in 1000 g spools):

- Quantity needed = (1000 x 2) minus 830 = **1170 g**, which rounds up to **2 spools**.
- Local shop (SAMPLE Kuching Filament Shop A): 2 x MYR 72.00 + MYR 0.00 shipping = **MYR 144.00**,
  lead time 1 day, arrives tomorrow.
- Online shop (SAMPLE OnlineFil Store C): the minimum order is **5** spools, so 5 x MYR 58.00 +
  MYR 18.00 shipping = **MYR 308.00**, lead time 7 days.
- Result: the local shop is **Best** at the top. The online price per spool is lower, but the
  minimum order makes the total higher and it is slower.
- Second example, ABS Grey (OUT, 0 g): needed = 1000 g = 1 spool; only one supplier sells it, so it
  is the only line: MYR 93.00, arrives in 7 days.

*(Note: `sample_data/SAMPLE_DATA_README.txt` says the online total is MYR 134. That older note
ignored the minimum order. The app's MYR 308 is the correct result of the rules.)*

The mix of local and online suppliers above comes from invented sample data. Which real suppliers
are local or online, and their real lead times, is still a founder question (guide Section 16, Q3).

Both Admin and Employee see the same list, costs and contacts (team decision 2026-11-24).

## 5. How Employees can SEE prices but not CHANGE them (`permissions.py`)

> **Say it like this:** "On 24 November the team decided that Employees may see prices, shipping
> costs and money totals, to make ordering easier, but may not change anything. All our rules about
> who can do what live in one small file, permissions.py, as plain yes/no questions. One question,
> can_see_prices, says yes to both Admin and Employee. A different question, can_manage_suppliers,
> says yes only to Admin. The pages that change data are guarded by the Admin-only check, so even if
> an Employee types the address of an edit page by hand, the server answers 403 Forbidden."

Facts (`app/permissions.py`):

- `can_see_prices(user)` = active Admin **or** active Employee. Used for the money columns, the
  suggestion costs and the Home money box.
- `can_manage_materials`, `can_manage_suppliers`, `can_manage_users`, `can_view_activity_log` =
  active Admin only.
- `can_record_stock` = Admin or Employee.
- `admin_required` is the guard placed on every page that changes things. If the person is not
  an Admin it stops with **403**; if not logged in it sends them to the login page.
- **Seeing is not changing:** two different functions, on purpose. When the team changed its mind,
  only `can_see_prices` had to change, and the "change" buttons and pages stayed Admin-only.
- Switched-off accounts, not-logged-in visitors and unknown roles get nothing (deny by default).
- Rule C7: screen files must never write `if role == "admin"`; they only ask `permissions.py`.
- The page also hides the Add / Change / Switch-off buttons from Employees, but that is only for
  convenience. The real protection is the server check.

**Bug we found and fixed on the same day:** when prices became visible, some supplier pages used
`can_see_prices` to mean "is Admin", so Employees briefly saw edit buttons and switched-off
suppliers. It was fixed by using `can_manage_suppliers` for those (status log, 2026-11-24). This is
a good story for "why one question per decision".

**Verified on 2026-11-24:** logged in as the sample Employee, GET and POST to `/suppliers/new`,
`/suppliers/S001/edit`, an offer edit address and `/materials/new` all answered **403**, and
`/stats/export.csv` answered **403**. Employees can still open the supplier pages and the Find
supplier page with MYR prices. Since the merge on 2026-11-25 there are also automatic tests that send
complete, valid forms as an Employee to the supplier and offer add / edit addresses: all give 403 and
nothing changes.

**"Last bought" follows the same rule.** The money in the "Last bought" line is shown only if
`can_see_prices()` says yes (Admin and Employee; a visitor who is not logged in or a switched-off account
gets nothing). Seeing it changes nothing: typing the purchase cost is behind its own rule,
`can_record_purchase_cost` (Admin only), and editing prices stays behind `can_manage_*` and
`admin_required`, so an Employee who types an edit address still gets 403, now with a plain-English page
and a **Back to Home** button.

What is **Admin only**: under `CLAUDE.md` Section 5 (F7), the spending chart and the CSV export on
the Stock page are Admin only. This is settled, not an open question. (The 2026-11-24 decision
covered seeing prices, not these.) The question still open for the founder is whether Employees
should see supplier phone numbers and emails.

## 6. Open-source projects we looked at, and credits

> **Say it like this:** "Before writing code we looked for free, open-source projects so we did not
> reinvent the wheel. We studied several, borrowed their ideas, such as how to split permissions by
> role and how to do low-stock alerts, and wrote our own small application. We copied no code from
> them. If we ever copy code, we first check its license, keep the copyright notice and credit the
> project."

| Project | What it is | Idea we borrowed | License checked on GitHub, 2026-11-24 |
|---|---|---|---|
| [Spoolman](https://github.com/Donkie/Spoolman) (Donkie) | Tracks 3D printer filament spools | A clear list of spools with material and remaining weight | MIT |
| [InvenTree](https://github.com/inventree/InvenTree) | General inventory system (Python Django + React) | How a mature system tracks stock and has an API. Too big to copy; we studied the ideas | MIT |
| [FilaOps](https://github.com/BLB3DPrinting/filaops) (found by search; the guide's link `printertechn/filaops` does not exist) | ERP for 3D print farms: inventory, low-stock alerts, bill of materials | Closest match to our low-stock alerts and reordering | Custom licence ("NOASSERTION"). **Read it before using any code; we use none** |
| [OSSMS](https://github.com/iitzm1lly/ossms) (iitzm1lly) | Office supplies stock system (Next.js, Tauri, SQLite) | A simple, clear split of permissions by role (Admin / Staff / Viewer) | MIT |
| [Stockify](https://github.com/Princelad/stockify) (Princelad) | Stock and billing system (React and Express) | General small-business stock screens | MIT |
| [filament-tracker](https://github.com/Xeferis/filament-tracker) (Xeferis) | A simple filament tracker | Basic screens of a simple tracker | **No license found: all rights reserved, never copy code from it** |
| abduznik/filament-tracker (from the guide) | A simple filament tracker | Basic screens | The GitHub link returned "Not Found" on 2026-11-24; ask the team who found it |

Facts:
- **Why we built our own instead of using them:** Spoolman tracks filament spools only, and
  FilaOps is a heavy ERP for print farms. Because our system supports pieces (`pcs`) alongside `g`
  and `ml`, it can also track small hardware items such as screws, springs, magnets, fidget clickers
  and keychain rings, next to filaments, resins and other supplies, in one simple web app with
  supplier cost and delivery-time comparisons (subject to confirmation with the founder).
- **Result of our code search (2026-11-24):** no file in `app/`, `tests/` or `sample_data/` mentions
  any of these projects or contains a pasted-code credit. That means no code was copied. Everyone
  must still confirm this honestly before presenting.
- The libraries we install (Flask, Werkzeug, Jinja, pytest) and load (Chart.js) are listed with
  their licenses at the bottom of [`GLOSSARY.md`](GLOSSARY.md). They are used, not copied.
- Rule C10 (if you copy code): check the license, add a source-link comment, explain it in the
  glossary.
- **Team to do (guide Section 3):** each member opens two of the projects and writes **3 sentences
  in the status log** about what they found. Nobody has done this yet. Do it in your own words;
  the judges will ask.

---

## Version 1 (built) versus Version 2 (ideas only)

**Built in Version 1 (you may demo these):**
- Materials in `g`, `ml` and `pcs`, with OK / LOW / OUT status and a plain-English explanation.
- Record used and Record received, with a history row and an activity-log row for each change.
- "Last bought" memory (who, how much, date, total paid; money only for people allowed to see prices).
- Find supplier: ranked by estimated total cost, then lead time, with estimated arrival dates.
- Home boxes with Current stock and Record shortcuts, a Stock page (current stock chart with a unit choice,
  usage chart, supplier speed ranking), money spent; Admin-only spending chart and CSV download.
- Roles (Admin and Employee), server-side permission checks, login lock, CSRF protection, the Admin
  Users screen, plain-English error pages, tap-friendly buttons.

**Version 2 ideas (NOT built, NOT promised; guide Section 17 says write them down and do not build them):**
- Printable labels for racks and shelves.
- Humidity and dry-box alerts for moisture-sensitive filaments in Sarawak's damp climate.
- Linking material stock to job quoting, so a quote uses real material cost.
- Also version 2 already: barcode or NFC scanning, customer orders and invoices, email alerts,
  automatic ordering, connecting to printers.

Only the list above under "Built" may be shown as working. Everything under "Version 2" is a talking
point for questions.

## Two-minute demo script

1. Log in as the Admin. "Home shows four boxes: total materials, LOW, OUT, and money spent this
   month. Money spent adds up the real totals an Admin typed on Record received; on the sample data it
   may show a small number or MYR 0.00." (Do not claim a real figure.)
2. (Optional, 15 seconds) Press **Users** to show the Admin-only screen for accounts.
3. Point to **Noti**. Press **Find supplier** on PLA Basic White. Read the ranked list,
   "Best" at the top, and the word "estimate".
4. Go to Materials. Point to the OK / LOW / OUT sentence and a **Last bought** line. Press **Record
   used**, type a quantity, save. Show the status change. (On a phone: the buttons are big enough to tap.)
5. Log out. Log in as the Employee. Show: prices are visible, no Add / Change / Remove buttons and
   no Users link.
6. Type `/suppliers/new` in the address bar: a plain-English "no permission" page with a **Back to Home**
   button. "The server blocks it, not just the button."

## Questions you may be asked (honest answers)

- **"Is this real company data?"** No. It is invented sample data. The founder's answers (Section 16)
  are still needed to replace it.
- **"Why not just a spreadsheet?"** One place, warnings that appear by themselves, a supplier
  suggestion, a history of who changed what, and different rights for different people.
- **"What happens if someone types a forbidden address?"** 403 Forbidden, checked on the server.
- **"How are passwords stored?"** Scrambled (hashed); nobody can read them back, not even us.
- **"What if the internet is down?"** The app itself runs on our own computer. Only the Stock page
  charts need the internet, because the chart library is loaded from the web.
- **"What can it not do yet?"** Email alerts, a manual stock correction screen (ADJUSTED), an
  activity-log screen, a one-click backup button, and the shared look across every screen (Agent H's
  job). Money spent and low-stock events now work. Received lines saved without a total count as MYR 0,
  and low-stock events are counted from the day the feature was switched on. All are in the status log.
- **"What would you build next (version 2)?"** See "Version 1 versus Version 2" above: those are ideas
  only, not built and not promised.
- **"Are the hardware items (screws, springs, magnets...) real?"** They are sample data to show that the
  system can count pieces next to grams and millilitres. What hardware Stinablis really tracks is a
  founder question.
- **"Is the 2 hours to 30 minutes a week saving proven?"** No. It is the team's goal and estimate. We
  have not measured it and the founder has not confirmed the 2-hour starting point.
- **"How do you know it works?"** 405 automatic tests passed (2 skipped, 6 expected failures
  that describe known bugs; commit `6024c83`, 2026-11-25), a manual checklist (`TESTS.md`), and a phone check.
- **"How are forms protected from forged requests?"** Every form that changes data carries a hidden
  secret token (CSRF protection), on top of the safe cookie settings.

## Open questions we must NOT answer for the founder (guide Section 16)

Which materials, units and reorder levels; which suppliers are online or local and their lead
times; whether prices include shipping and tax; who is Admin; whether Employees see supplier phone
and email; whether email alerts are wanted; whether to track which printer used which material;
whether there are spreadsheets to import. If asked on the day, say: "These are still waiting for
the founder's answer."

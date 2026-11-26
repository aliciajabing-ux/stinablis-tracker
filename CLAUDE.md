=====================================================================
PROJECT GUIDE AND PRD (Product Requirements Document)
Project: Stinablis Material & Supplier Tracker
Team: 3BitWonder
=====================================================================

HOW TO USE THIS FILE
---------------------
- Every AI agent (and every team member) must read this whole file
  BEFORE doing any work on the project.
- If you are an AI agent, this file is your rulebook. If something in
  another instruction conflicts with this file, stop and ask the team.
- When the team changes a decision, update this file FIRST, then the code.
- Keep the "STATUS LOG" at the bottom up to date after each work session.
- Tip: if your tool looks for a special file name (for example
  CLAUDE.md or AGENTS.md), copy or rename this file to that name.

Words in [brackets] are things the team still needs to confirm.


---------------------------------------------------------------------
1. THE PROBLEM IN PLAIN WORDS
---------------------------------------------------------------------
Stinablis is a 3D printing company in Kuching, Sarawak. It buys printing
materials (for example filament, resin, and similar supplies) from many
suppliers. Some are online and some are local shops.

Right now, the company has to:
  a) Keep track of how much material is left. This takes time and is
     easy to get wrong.
  b) Remember which supplier sells each material, how much it costs,
     how to contact them, and how long delivery takes.
  c) Notice when material is running low and then find someone to buy
     from. This often happens too late, so printing jobs stop.

WHAT WE ARE BUILDING
Web application (a website that only staff can log into) that:
  1. Keeps one list of all materials and their stock levels.
  2. Keeps one list of all suppliers with contact details and prices.
  3. Warns people when a material is running low.
  4. Suggests the best supplier to order from, and shows how long it
     will take to arrive.
  5. Shows simple statistics (charts and a ranking) so the boss can see
     what is used, what is bought, which supplier delivers fastest, and
     how supplier prices compare.
  6. Limits what each type of user can see and change.


---------------------------------------------------------------------
2. ABOUT THE COMPANY (what we know so far)
---------------------------------------------------------------------
- Company: Stinablis (https://stinablis.com/)
- Location: Kuching, Sarawak, Malaysia
- The website describes the business as industrial engineering and
  digital manufacturing: 3D printing, custom automotive parts, rapid
  prototyping, composite manufacturing, reverse engineering, and
  engineering software.
- The website does NOT list which materials they use or their suppliers.
  That information comes from our interview with the founder.
- [CONFIRM WITH FOUNDER] List of materials they currently use.
- [CONFIRM WITH FOUNDER] Which suppliers are online and which are local.
- [CONFIRM WITH FOUNDER] Whether staff also need to track small hardware
  pieces counted in pcs (for example screws, springs, magnets, fidget
  clickers, keychain rings). Until the founder answers, such items appear
  ONLY in the sample/demo data, clearly named as samples (Rule R4).
  Update 2026-11-26: a teammate added 26 more sample materials (M014 to M039:
  PLA+, PLA, PETG and PLA Silk filament, screws, nuts, inserts, bearings,
  magnets, clicker switches, keychain parts and more) so that Test 2 can
  be run (PLA+ Orange, PETG Grey). They are NOT named "SAMPLE" and have no
  supplier offers yet. [CONFIRM WITH FOUNDER] whether they match real stock.


---------------------------------------------------------------------
3. OPEN-SOURCE RESEARCH (done BEFORE writing code)
---------------------------------------------------------------------
We searched for existing free, open-source projects first, so we do not
reinvent the wheel. Findings:

  a) Spoolman (github.com/Donkie/Spoolman)
     - Tracks 3D printer filament spools. License: MIT.
     - Useful idea: a clear list of spools, their material and remaining
       weight.

  b) InvenTree (github.com/inventree/InvenTree)
     - General open-source inventory system. License: MIT.
     - Built with Python (Django) on the server and React on the screen.
     - Useful idea: a mature example of stock tracking and an API.
     - Note: it is large. We should study its ideas, not copy it whole.

  c) FilaOps (github.com/printertechn/filaops; also listed as
     "filaops" in the awesome-list index)
     - Open-source ERP (business management system) for 3D print farms.
     - Its feature list includes inventory, low stock alerts, and a
       bill of materials (BOM: the list of parts/materials needed to
       make one product).
     - Useful idea: closest match to our low-stock alerts and reordering.
     - Built with Python (FastAPI) and React.

  d) OSSMS (github.com/iitzm1lly/ossms)
     - Office supplies stock system. Lists three user roles: Admin,
       Staff, and Viewer.
     - Useful idea: a simple, clear way to split permissions by role.
     - Built with Next.js, Tauri, and SQLite.

  e) Stockify (github.com/princelad/stockify)
     - Stock and billing system for small businesses.
     - Built with React and Express.

  f) Smaller filament-tracker projects (abduznik/filament-tracker,
     xeferis/filament-tracker) - simple examples of the basic screens.

DECISION FROM THE RESEARCH
- We will build our own small application, but use these projects as
  reference for ideas (role permissions, low-stock alerts, layout).
- RULE: Before copying ANY code from these projects, check its license
  file. Only use code whose license allows it (MIT is allowed, but we
  must keep the copyright notice). Always credit the source in a
  comment and in the presentation.
- [TEAM TO DO] Each team member opens two of the projects above on
  GitHub and writes 3 sentences in the STATUS LOG about what they found.
  Do not skip this step; it is needed for the presentation.


---------------------------------------------------------------------
4. WHO USES THE SYSTEM (USER ROLES AND PERMISSIONS)
---------------------------------------------------------------------
There are two roles. Each user has exactly one role.

ROLE 1: ADMIN (the owner, manager, or trusted person)
  Can do everything:
  - See and change all materials, stock levels, suppliers, and prices.
  - See all statistics and reports.
  - Create, change, and remove user accounts and their roles.
  - Turn low-stock alert settings on and off.
  - Export data (download to a spreadsheet file).

ROLE 2: EMPLOYEE (general staff, for example operators at the printers)
  Can:
  - See the material list and current stock levels.
  - Record stock used (for example "used 200 g of PLA").
  - Record stock received (for example "received 2 spools today").
  - See low-stock warnings.
  - See the basic statistics for their daily work.
  - SEE supplier prices, shipping costs and the total paid on the "Last
    bought" note (team decision 2026-11-24; the Home "money spent" box
    was removed on 2026-11-26). Seeing is not changing.
  Cannot:
  - Change supplier prices (costs).
  - Add, change, or delete suppliers.
  - Add, change, or delete materials.
  - Manage user accounts.
  - Delete any records.
  [CONFIRM WITH FOUNDER] Whether employees may see supplier contact
  phone numbers and emails. Our proposal: yes, to make ordering easy,
  but they cannot edit them.

PERMISSION RULE (very important)
- Every permission is checked on the SERVER (the computer that runs the
  application), not only on the screen. Hiding a button is not enough.
  A user who types the wrong web address must still be blocked.
- If in doubt, DENY access. It is easier to allow later than to undo a
  data leak.

SENSITIVE DATA (must never reach an employee account)
- (Supplier prices, shipping costs and the "Last bought" total paid:
  employees may now SEE these, since 2026-11-24. They must still never be
  able to CHANGE them. The price comparison charts and the CSV download
  stay Admin only.)
- User passwords (stored in scrambled form only; never shown).
- Admin account details.


---------------------------------------------------------------------
5. FEATURES (WHAT THE SCREENS DO)
---------------------------------------------------------------------
Keep screens simple. Each main screen should be reachable within
two clicks from the Home screen.

F1. LOGIN SCREEN
    - Username and password. Log out button.
    - After 5 wrong passwords, lock the account for 15 minutes.

F2. HOME / DASHBOARD (the first screen after login)
    - Three big boxes at the top:
        * Total number of materials
        * Number of materials LOW on stock (shown in red)
        * Number of materials OUT of stock (shown in dark red)
      (The fourth box, "estimated money spent this month", was REMOVED on
      2026-11-26: the team said it is not relevant any more.)
    - A "Notifications" list (called "Needs attention" until 2026-11-26): the
      low and out-of-stock materials, with a button to see the suggested supplier.
      Each line shows its status (LOW or OUT) in the same coloured box as the
      Materials screen, placed just to the left of the "Find supplier" button
      (decision 2026-11-26, for readability).

F3. MATERIALS SCREEN
    - A table of all materials: name, type (for example PLA, PETG, resin),
      colour, quantity left, unit (grams, millilitres, pieces), and
      status (OK / LOW / OUT).
    - A big search box at the very top of the list ("Search by item name"),
      filtering as you type (decision 2026-11-26). Filter buttons: Show all,
      Show only LOW, Show only OUT. The "Show only OK" button was removed as
      clutter. The list has two sections (decision 2026-11-26, from the
      ShopGuard materials): "Filament & other materials" (g and ml items) and
      "Hardware" (items counted in pieces). Inside each section the order is
      OK first, then LOW, then OUT.
    - Add / edit / delete a material: ADMIN only.
    - "Add material" has an optional "Who sells it?" part (2026-11-26): no
      supplier, an existing supplier, or a new supplier, plus what they charge
      (pack size, price per pack in MYR, smallest order, shipping, delivery
      days). Material, supplier and offer are saved together or not at all.
      Admin only (Employees get 403 on the whole form); the form does not
      appear on "Edit material".
    - "Record used" and "Record received" buttons: everyone.
    - "Last bought" memory (decision 2026-11-24): each material row and the
      Record screens show who it was last bought from, how much, the date
      and (if typed) the total paid in MYR. It is read from the newest
      RECEIVED line that names a supplier or a cost. The money part follows
      can_see_prices() (Admin and Employee, view only). Changing prices
      stays Admin only and the server still answers 403 to anyone else.

F4. SUPPLIERS SCREEN (ADMIN can change; EMPLOYEE can only view)
    - One row per supplier: name, type (ONLINE or LOCAL), address,
      phone, email, website, and notes.
    - Each supplier has a list of materials they sell, with:
        * Price per unit (Admin and Employee can see; only Admin can change)
        * Minimum order quantity
        * Lead time in days (how long from ordering to arriving)
        * Shipping cost (Admin and Employee can see; only Admin can change)

F5. LOW-STOCK ALERTS
    - Each material has a "reorder level": the quantity at which we
      should order more. Example: reorder at 500 g.
    - When quantity drops to or below the reorder level, the material
      becomes LOW and shows on the Home screen.
    - When quantity reaches zero, it becomes OUT.
    - Alerts are shown on screen. [TEAM DECISION] Optional later:
      send an email to the Admin.

F6. SUPPLIER SUGGESTION (the main time-saver)
    - For a LOW or OUT material, the system lists every supplier that
      sells it, sorted by the best choice.
    - Simple rule for "best":
        1. Only suppliers that can deliver in time (see lead time).
        2. Then the lowest total cost (price x quantity needed + shipping).
        3. Then the shortest lead time.
    - For each suggestion, show:
        * Supplier name and type (ONLINE or LOCAL)
        * Estimated cost
        * Estimated arrival date = today + lead time days
        * Contact details
    - Admin and Employee both see cost, supplier name, lead time, arrival
      date, and contact details (team decision 2026-11-24).

F7. STATISTICS SCREEN (ADMIN sees everything; EMPLOYEE sees usage only)
    - Usage per material per week or per month (bar chart).
    - Delivery ranking (decision 2026-11-26; it replaces the "average lead
      time per supplier" bar chart): the suppliers ranked from the fastest
      to the slowest delivery for a material the user chooses, or the
      average over all materials. It shows the rank, the supplier, ONLINE or
      LOCAL, the days, and the estimated arrival date (today + the days).
      Suppliers with the same days share a rank. No money in it: Admin and
      Employee both see it.
    - REMOVED on 2026-11-26 (team decision): the "low-stock events per month"
      line chart, the "spending per supplier this month" chart and the
      "spending per material" chart are no longer on the Statistics screen.
      (The Home box "money spent this month" stays. Low-stock events are still
      saved in the database, they are just not charted.)
    - Procurement statistics (decision 2026-11-26), all built from the
      "Record received" lines:
        * Purchases per material per month, with the unit (g, ml, pcs) -
          Admin and Employee (no money in it).
        * Supplier price comparison per material: cheapest supplier offer
          next to the price last paid, per kg, per litre or per piece -
          ADMIN only. Shown as two bar charts (per kg or litre, and per
          piece, because their prices are on very different scales). The
          table with the same numbers was removed on 2026-11-26 (team
          decision: it repeated the charts). Estimates: the offer price is
          before shipping.
    - Statistics sidebar (decision 2026-11-26): a menu on the left lists the
      statistics (usage, purchases, delivery ranking, and for the Admin the
      supplier price comparison). Clicking one shows only that statistic, so
      nobody has to scroll down the page. The chosen one is marked, and the
      address keeps it (for example /stats/#purchases) so a refresh or a
      bookmark opens the same one. The Admin also finds the CSV download in
      the sidebar. On a phone the menu is a row of buttons across the top.
    - Every chart shows its unit (g, ml, pcs, days) or MYR in the axis title
      and in the pop-up text, never just a bare number.
    - Export to spreadsheet (CSV) - ADMIN only (it also lists purchases and
      spending per material, and the average delivery time per supplier).

F8. USER MANAGEMENT (ADMIN only)
    - Add user, change role, reset password, disable account.
    - Never delete a user who has records; disable them instead.

F9. ACTIVITY LOG (ADMIN only)
    - Every change is written down: who, what, when. Example:
      "Ali changed price of PLA from MYR 80 to MYR 85, 19 Nov 2026 20:40".
    - Nobody can edit or delete this log.

Currency: Malaysian Ringgit (MYR). Use "MYR" in every label and number
(for example "MYR 72.00"). The founder may confirm this later.


---------------------------------------------------------------------
6. DATA WE STORE (plain-language database plan)
---------------------------------------------------------------------
Think of the database as a set of spreadsheets that are linked together.

TABLE: users
  id, username, password_hash (scrambled password), role (ADMIN or
  EMPLOYEE), is_active (yes or no), failed_login_count, locked_until

TABLE: materials
  id, name, material_type, colour, unit (g, ml, pcs), quantity_on_hand,
  reorder_level, created_at, updated_at

TABLE: suppliers
  id, name, supplier_type (ONLINE or LOCAL), address, phone, email,
  website, notes, created_at, updated_at

TABLE: supplier_offers  (links a supplier to a material)
  id, supplier_id, material_id, price_per_unit (Admin only data),
  minimum_order_qty, shipping_cost (Admin only data),
  lead_time_days, is_active

TABLE: stock_movements  (every change to stock, never edited)
  id, material_id, movement_type (USED, RECEIVED, ADJUSTED),
  quantity, note, user_id, created_at

TABLE: activity_log  (who changed what)
  id, user_id, action, table_name, record_id, details, created_at

RULES FOR THE DATABASE
- Never delete a supplier or material that has history. Mark it
  inactive instead.
- Stock quantity changes ONLY through stock_movements. Example: when
  someone records 200 g used, add a USED row, then reduce quantity_on_hand.
- Use the same database format for development and for the real system
  (SQLite for our project; it is a single file and easy to back up).
- Store dates as UTC and show them in Malaysia time (UTC+8).


---------------------------------------------------------------------
7. HOW THE LOW-STOCK MATH WORKS (in plain words)
---------------------------------------------------------------------
Example for one material, PLA white, 1 kg spools (1000 g):
  - Reorder level = 500 g. (The company sets this.)
  - Current quantity = 430 g.
  - 430 is less than or equal to 500, so status = LOW.

Estimated arrival:
  - Order date = today.
  - Arrival date = today + lead_time_days (for the chosen supplier).
  - Example: Local shop lead time 1 day -> arrives tomorrow.
            Online shop lead time 7 days -> arrives in 7 days.

Estimated cost:
  - Quantity needed = (reorder level x 2) minus current quantity,
    rounded up to whole spools. [CONFIRM the formula with the founder.]
  - Cost = number of spools x price per spool + shipping cost.

All of these numbers are ESTIMATES. The screen must say so.


---------------------------------------------------------------------
8. SCREEN DESIGN RULES (easy for everyone)
---------------------------------------------------------------------
- Big, clear buttons with plain words: "Record used", "Find supplier",
  "Add material". Never use technical words on screen.
- Use colours with words too: green = OK, orange = LOW, red = OUT.
  (Do not rely on colour alone; always write the word.)
- Maximum 3 clicks to any common task.
- Buttons and links are at least about 44 px tall so a thumb can tap them.
- Status words are explained once in plain English on the Materials screen:
  OK = enough, LOW = at or below the reorder level, OUT = none left.
- Error pages (no permission, page not found, expired form) use plain words
  and a button back to Home.
- Mobile-friendly: it should work on a phone or tablet at the printer.
- Every form shows a short help sentence under the title.
- Error messages in plain language. Bad: "Error 422 invalid payload".
  Good: "Please type the quantity as a number, for example 200".


---------------------------------------------------------------------
9. TECHNOLOGY CHOICES (simple version)
---------------------------------------------------------------------
Recommended stack for a team with no programming background:
  - Language: Python 3 (easy to read)
  - Web framework: Flask (small and simple to learn)
  - Database: SQLite (one file, no server to install)
  - Screens: HTML, CSS, and a small amount of JavaScript
    (or Bootstrap for ready-made style)
  - Charts: Chart.js (simple chart library)
  - Passwords: a standard library that scrambles them (bcrypt or
    werkzeug.security). Never store plain passwords.
  - Version control: Git and GitHub (one shared project folder).
  - Testing: pytest (Python's test tool).

Why this stack: it is widely taught, has lots of beginner examples, and
the code is short enough to explain in a presentation.

[TEAM DECISION] Confirm before coding starts.


---------------------------------------------------------------------
10. FOLDER LAYOUT (where files go)
---------------------------------------------------------------------
stinablis-tracker/
  PROJECT_GUIDE.txt      <- this file (read first, always)
  README.md              <- short "how to run it" for humans
  GLOSSARY.md            <- plain-language meaning of every technical word
  app/
    __init__.py          <- starts the application
    models.py            <- describes the tables (the spreadsheets)
    auth.py              <- login, logout, passwords, roles
    permissions.py       <- the rules of who can do what
    routes_materials.py  <- screens and actions for materials
    routes_suppliers.py  <- screens and actions for suppliers
    routes_stats.py      <- statistics screen and numbers
    alerts.py            <- low-stock and out-of-stock logic
    suggest.py           <- picks the best supplier
    templates/           <- the HTML pages
    static/              <- style (CSS) and small scripts (JS)
  tests/                 <- automatic checks
  data/                  <- database file (never commit real data to Git)
  requirements.txt       <- list of libraries to install
  .gitignore             <- tells Git which files to skip (secrets, data)

Each Python file must start with a short comment in plain English that
says what the file is for (see Rule C2 below).


---------------------------------------------------------------------
11. AGENT TEAM (who builds what)
---------------------------------------------------------------------
We will use separate AI agents for separate parts. Each agent works ONLY
inside its own files, reads this guide first, and writes to the STATUS
LOG when finished.

AGENT A - DATABASE AGENT
  Files: app/models.py, data seed scripts, database setup.
  Job: create all tables in Section 6, with sample data for testing.

AGENT B - LOGIN AND PERMISSIONS AGENT
  Files: app/auth.py, app/permissions.py, login screen.
  Job: login, logout, password scrambling, account lock, role checks.
  Must have tests proving employees cannot reach admin-only pages.

AGENT C - MATERIALS AND STOCK AGENT
  Files: app/routes_materials.py, app/alerts.py, material screens.
  Job: material list, add/edit, record used/received, LOW/OUT logic.

AGENT D - SUPPLIERS AND SUGGESTION AGENT
  Files: app/routes_suppliers.py, app/suggest.py, supplier screens.
  Job: supplier list, supplier offers, the best-supplier suggestion.

AGENT E - STATISTICS AND DASHBOARD AGENT
  Files: app/routes_stats.py, home dashboard, charts.
  Job: home boxes, charts, CSV export (Admin only for money).

AGENT F - TESTING AND REVIEW AGENT
  Files: tests/ only (it may read everything).
  Job: write tests, try each role on each screen, and report bugs.
  It must NOT fix code itself; it writes the bug to the STATUS LOG.

AGENT G - DOCUMENTATION AND PRESENTATION AGENT
  Files: README.md, GLOSSARY.md, presentation notes.
  Job: explain the code in plain words for the competition.

AGENT H - INTERFACE AND DESIGN AGENT
  Files: app/static/ (CSS and small JS), app/templates/base.html.
  Job: one shared look for all screens, following Section 8: plain words,
  OK/LOW/OUT shown with a colour AND a word, big tap-friendly buttons,
  works on a phone, help sentence under each form title, plain-language errors.
  Must NOT change what a page does, only how it looks. No permission logic
  (Rule C7). Page-specific changes go to the owning agent as a request (R3).

ORDER OF WORK
  1. Database (A)  ->  2. Login and roles (B)  ->  3. Materials (C) and
  Suppliers (D) in parallel  ->  4. Statistics (E)  ->  5. Interface and
  design (H)  ->  6. Testing (F)  ->  7. Documentation (G).
  Nothing from later steps starts until the earlier step passes testing.


---------------------------------------------------------------------
12. CODING RULES (so the team can explain every line)
---------------------------------------------------------------------
C1. Keep it simple. If there are two ways to write something, choose
    the one a first-year student can read.
C2. Every file starts with a comment block in plain English:
      # WHAT THIS FILE DOES: (one or two sentences)
      # WHO CAN USE IT: (Admin / Employee / Both)
C3. Every function has a one-line comment above it saying what it does
    in plain words. Example:
      # Returns True if the user is an admin, otherwise False.
C4. Names must describe the thing. Use "supplier_price" not "sp" or "x".
C5. No clever tricks, no one-line code that does many things at once.
    Maximum about 30 lines per function. If longer, split it.
C6. Never put passwords, secret keys, or real company data in the code.
    Use a settings file that Git ignores.
C7. Every permission check happens on the server, using the function in
    permissions.py. Never write "if role == 'admin'" inside a screen file.
C8. Every change that touches stock or prices writes a row to
    activity_log or stock_movements.
C9. No deleting of real records from the code. Use "is_active = no".
C10. Do not copy code from the internet or the open-source projects
    without (a) checking the license, (b) adding a comment with the
    source link, and (c) explaining it in GLOSSARY.md.
C11. Write at least one automatic test for each rule in Sections 4 and 7.
C12. Use Git: small commits with clear messages, for example
    "Add low-stock alert for materials". Never commit the data folder.


---------------------------------------------------------------------
13. EXPLAINING THE CODE IN THE PRESENTATION (for every team member)
---------------------------------------------------------------------
Every member must be able to explain, in plain words:
  1. The problem (Section 1) and why it wastes time.
  2. The two user roles (Admin and Employee) and what each can do. The table is
     ROLE_DIFFERENCES.md; the test tests/test_role_differences.py proves it.
  3. One feature end-to-end: for example, "what happens when someone
     clicks Record used?" (Screen -> Server checks permission -> Stock
     number goes down -> Row is written to the history -> If low, the
     Home screen shows the warning.)
  4. How the best supplier is picked (Section 7 example).
  5. How we let employees SEE prices but not change them (permissions.py).
  6. What open-source projects we looked at and what we borrowed.

GLOSSARY.md must explain every technical word we use, for example:
  - Database: a set of linked spreadsheets stored in one file.
  - Server: the computer that runs the application and checks rules.
  - Login / password hash: the password is stored scrambled, so even the
    database owner cannot read it.
  - API: a set of addresses the screens use to ask the server for data.
  - Git: a history book of every change to the code.


---------------------------------------------------------------------
14. SECURITY CHECKLIST (must pass before the demo)
---------------------------------------------------------------------
[ ] Employee cannot open the Suppliers edit page by typing its address.
[ ] Employee sees prices but has no edit buttons, and cannot change a
    price by typing an address (changed 2026-11-24).
[ ] Wrong password 5 times locks the account for 15 minutes.
[ ] Passwords are stored scrambled (check the database file).
[ ] Admin actions are written to the activity log.
[ ] No secret keys are in the Git history.
[ ] Backup of the database file can be made with one click (Admin).
[ ] Forms reject letters in number fields, and very long text.


---------------------------------------------------------------------
15. TESTING CHECKLIST (before each demo)
---------------------------------------------------------------------
[ ] Add a material with reorder level 500 g and quantity 800 g -> OK.
[ ] Record 400 g used -> quantity becomes 400 g -> status LOW.
[ ] Record 400 g used again -> quantity 0 -> status OUT.
[ ] Two suppliers for one material: the one with the shorter lead time
    and lower total cost is listed first.
[ ] Employee account: can see prices, cannot add or change a supplier.
[ ] Admin account: sees prices and the supplier price comparison charts.
[ ] Estimated arrival date is correct for the lead time (today + days).
[ ] Malaysia time (UTC+8) shows correctly on every date.


---------------------------------------------------------------------
16. OPEN QUESTIONS FOR THE FOUNDER (ask in the next meeting)
---------------------------------------------------------------------
1. Which materials are used most, and what units do they buy them in?
2. What is the usual reorder level for each material?
3. Which suppliers are online and which are local? Lead times for each?
4. Are prices in RM before or after shipping? Is tax included?
5. Who should be Admin? Who are the employees?
6. Should employees see supplier phone numbers and emails?
7. Should the system send emails for low stock, or is an on-screen
   alert enough for now?
8. Does the company need to record which printer used which material
   (future feature, not in the first version)?
9. Is there any data already in spreadsheets we should import?


---------------------------------------------------------------------
17. OUT OF SCOPE FOR VERSION 1 (do NOT build these yet)
---------------------------------------------------------------------
- Automatic ordering from supplier websites.
- Barcode or NFC scanning.
- Connecting to 3D printers.
- Customer orders and invoices.
- Mobile app (the website must just work on a phone browser).
- Multiple company branches.
If a team member wants to add one of these, write it in the STATUS LOG
as an idea for version 2. Do not build it.


---------------------------------------------------------------------
18. RULES FOR EVERY AI AGENT
---------------------------------------------------------------------
R1. Read this whole file before you start.
R2. Work only in the files listed for your agent role (Section 11).
R3. If you need a change in another agent's file, write a request in
    the STATUS LOG. Do not edit it yourself.
R4. If a decision is not in this file, do not guess. Write a question
    in the STATUS LOG and stop that part.
R5. Never delete data, files, or history without the team's approval.
R6. Explain your work in plain words in the STATUS LOG: what you did,
    what is left, and any problem.
R7. Never show a real password, key, or supplier price in a public place.


---------------------------------------------------------------------
19. STATUS LOG (update after each work session)
---------------------------------------------------------------------
Format: DATE | AGENT | WHAT WAS DONE | WHAT IS NEXT | PROBLEMS

2026-11-19 | Team (planning) | Open-source research done (Section 3).
  Draft PRD and this guide written. | Confirm open questions (Section 16),
  confirm tech stack (Section 9), then start Agent A. | None yet.

2026-11-23 | Agent B (login & roles) | Wrote app/auth.py (login, logout, scrambled
  passwords, 5-wrong = 15-minute lock, activity-log lines for login/lock/logout),
  app/permissions.py (is_admin, can_see_prices, login_required, admin_required...),
  app/templates/login.html, and tests/test_auth_permissions.py (20 checks, all pass).
  | Agent F: please re-run and extend the tests. Agent C/D/E: use only the
  functions in permissions.py, never "if role == ..." (Rule C7). | REQUESTS
  (Rule R3, files I do not own): (1) app/__init__.py does not exist yet. It must
  set SECRET_KEY from an environment variable (never in code), set
  SESSION_COOKIE_HTTPONLY/SAMESITE="Lax", and register auth.auth_blueprint.
  (2) Sample users have NO password yet: run "python app/auth.py set-password
  sample_admin" (and sample_employee) once. (3) Home page "/" must exist as a
  @login_required page; login sends people there. (4) Need a base template with a
  Log out button: a form with method="post" to url_for('auth.logout'). (5) Needs
  decision: add a CSRF token to forms? Not built; SameSite=Lax cookie is the only
  protection for now. (6) Admin user-management screen (F8) has no owner in
  Section 11; it can use auth.set_password.

2026-11-23 | Agent B (login & roles) | Wrote app/__init__.py (create_app: secret key
  from STINABLIS_SECRET_KEY, safe cookie settings, "/" home page), app/templates/
  base.html (Log out button) and home.html (placeholder). 22 automatic tests pass.
  Founder-side manual test passed: admin login, employee login, 5 wrong passwords
  lock the account, correct password refused while locked. Sample passwords set
  (not stored in Git). | Agent F: review and extend tests. Then Agents C and D can
  start; register your screens at the marked line in app/__init__.py, and use only
  permissions.py for role checks. Agent E replaces home.html. | Still open: CSRF
  tokens on forms (not built); no Admin screen yet to unlock/reset accounts (F8);
  add .venv/ to .gitignore (no .gitignore exists yet).

2026-11-23 | Agent C (materials & stock) | Wrote app/alerts.py (OK/LOW/OUT rule,
  needs-attention list, counts), app/routes_materials.py (list with search and
  filter, add/edit/remove for Admin, Record used/received for everyone, every stock
  change writes stock_movements + activity_log, Malaysia-time history) and 3
  templates (materials_list/form/record.html). Registered the blueprint at the
  marked line in app/__init__.py. 28 new tests, whole suite 50 pass (TESTS.md).
  Employee page checked for prices: none. Remove only switches a material off (C9).
  | Agent E: use alerts.count_materials_by_status(db) and
  alerts.get_materials_needing_attention(db) for the Home boxes and list; link
  "Find supplier" to Agent D's page. Agent F: review and do the manual tests.
  | NOTES/REQUESTS: (1) No CSRF tokens on forms (same open item as Agent B).
  (2) Stock can only change by Used/Received; the starting quantity of a new
  material is saved as an ADJUSTED row. There is no screen yet to correct a wrong
  count (ADJUSTED stores no +/- direction); needs a decision (R4). (3) Unit cannot
  be changed after a material is created (it would make old history wrong).
  (4) Reorder level is entered per material; the Section 7 "quantity needed"
  formula is Agent D's. (5) Founder question still open: units/reorder levels.

2026-11-23 | Agent D (suppliers & suggestion) | Wrote app/suggest.py (quantity needed,
  packs rounded up with minimum order, cost, arrival date in Malaysia time, ranking,
  money removed for Employees), app/routes_suppliers.py (supplier list and details for
  everyone; add/change/switch-off supplier and offer for Admin; "Find supplier" page at
  /suggest/<material id>) and 6 templates (suppliers, supplier_detail, supplier_form,
  offer_form, suggest, supplier_style). Registered the blueprint at the marked line in
  app/__init__.py. 29 new tests, whole suite 79 pass (TESTS.md). Employee pages checked
  for prices in the page source: none. Nothing is ever deleted, only switched off (C9);
  every change writes the activity log (C8). | Agent E: link each Needs-attention row
  to url_for('suppliers.suggest_supplier', material_id=...) and the Home menu to
  url_for('suppliers.supplier_list'). Agent F: review and do the manual tests.
  | QUESTIONS (R4, I did not guess beyond what is below): (1) F6 rule 1 "deliver in
  time" has no deadline defined. I built an optional "needed within N days" box; empty
  means every supplier counts. Founder to confirm. (2) Quantity formula (reorder x 2
  minus stock) is as written in Section 7 and still [CONFIRM]. (3) An offer is only
  suggested if its pack unit matches the material's unit (g, ml, pcs). (4) Employees see
  supplier phone, email and website (proposal in Section 4, still to confirm).
  (5) Offers use price per PACK (schema), so Section 6's "price_per_unit" is per pack.
  (6) No CSRF tokens on forms (same open item as B and C). (7) .venv/ and __pycache__
  still not in .gitignore.

2026-11-23 | Agent D (suppliers & suggestion) | REQUEST TO AGENT B (Rule R3, file
  app/templates/base.html): please add a small menu bar to the top bar, shown only when
  logged in, with three plain links: "Home" -> url_for('home'), "Materials" ->
  url_for('materials.<materials list function>') (Agent C: please state the name of
  your list function), "Suppliers" -> url_for('suppliers.supplier_list'). Big enough
  to tap on a phone; the top bar already wraps (flex-wrap). No role checks needed:
  every link opens a page that checks permissions itself. Reason: the Home page has
  no links yet, so testers must type addresses by hand. | Nothing else needed from B.
  | None.

2026-11-23 | Agent B (login & roles) | DONE: request from Agent D ticked off. Added a menu bar
  to app/templates/base.html, shown only when logged in: Home, Materials, Suppliers (links
  built with url_for; no role checks, each page checks its own permissions). Tap-friendly
  (padding 10px 14px, font 1rem) and wraps on narrow screens. Added 1 test in
  tests/test_auth_permissions.py (menu appears when logged in, not on the login page).
  | Agent E: when you replace home.html, keep "extends base.html" so the menu stays.
  Add a link here if you add a Statistics page. | None.

2026-11-23 | Agent B (login & roles) | Committed my remaining files (base.html with menu bar,
  home.html, tests/test_auth_permissions.py) and updated .gitignore (.venv/ and
  __pycache__/ added; data/ kept). All 80 tests passed before the commit. Not pushed.
  | CLAUDE.md.txt is still untracked (not mine to add; the team should decide whether to
  keep it, since it duplicates README.md). | None.

2026-11-23 | Agent E (statistics & dashboard) | Wrote app/routes_stats.py, home.html (four boxes,
  Needs attention list with Find supplier buttons, See statistics button) and stats.html
  (usage bar chart by week/month, low-stock line chart, average delivery time per supplier,
  Admin-only spending chart and CSV download; Chart.js 4.4.1 loaded from a CDN). In
  app/__init__.py I registered the blueprint and replaced the placeholder "/" (it now calls
  routes_stats.show_dashboard; the endpoint name "home" is kept). Employee gets 403 on the CSV
  and spending address; Employee pages and chart data contain no money (tests prove it). Found
  and fixed one leak while testing: the spending chart script was sent to Employees. 27 new
  tests; see TESTS.md. | Agent F: review and do the manual test, including a phone-sized window.
  | QUESTIONS (R4, built but switched off, screens say "Not set up yet"; flags
  SPENDING_METHOD_CONFIRMED and LOW_EVENTS_METHOD_CONFIRMED in routes_stats.py): (1) Where does
  "money spent" come from? stock_movements has no price. PROPOSAL: each RECEIVED movement is
  priced as quantity x the price per unit of the cheapest active offer for that material, and is
  credited to that supplier. Weakness: we do not know who the stock was really bought from, and
  prices change. Better option: add a supplier and a price to the "Record received" form (needs
  Agent A and C). Team to choose. (2) How is a "low-stock event" counted? There is no stored
  event. PROPOSAL: replay stock_movements (starting stock and received add, used subtracts); one
  event = one USED row that moves a material from OK to LOW or OUT; counted by Malaysia-time
  month, using today's reorder level. Weakness: ADJUSTED rows have no +/- direction. (3) "Usage per
  material" mixes g, ml and pcs on one chart (units shown in each label); shows the 8 most used
  materials and the last 6 weeks or months. OK? (4) "Estimated money spent" is shown for the
  current Malaysia-time month.
  | REQUEST TO AGENT B (R3, app/templates/base.html): please add a "Statistics" link to the menu:
  url_for('stats.statistics_page'). Until then Home has a "See statistics" button.
  | NOTE: the charts need internet for Chart.js; if the shop has none at the printers, we should
  save the file into app/static/ (team decision). No CSRF issue here (no forms).

2026-11-24 | Agent B (login & roles) | DONE: request from Agent E ticked off. Added a "Statistics"
  link to the menu in app/templates/base.html (Home, Materials, Suppliers, Statistics; links to
  stats.statistics_page; no role check, the page checks its own permissions). Menu test in
  tests/test_auth_permissions.py now also checks the Statistics link. Full suite: 107 pass.
  | Agent E may remove the temporary "See statistics" button from Home if wanted. Change is
  not committed yet. | None.

2026-11-24 | Agent E (statistics & dashboard) | Team answered my questions: (1) money spent:
  Option B, store the real cost when stock is received. (2) low-stock events: Option B, store
  the event when it happens. (3) usage chart mixing g/ml/pcs, 8 most used, last 6 periods: Yes.
  (4) money box shows the current Malaysia-time month: Yes. Manual tests on a real phone: all 3
  pass (TESTS.md). | Spending and low-stock events stay "Not set up yet" until A and C finish
  below; then I will read the real data and switch both flags on. | REQUESTS (R3):
  TO AGENT A (schema.sql, setup_database.py): (a) in stock_movements add nullable columns
  supplier_id (TEXT, refers to suppliers) and total_cost_myr (REAL, >= 0), filled only for
  RECEIVED rows. (b) new table low_stock_events: id, material_id, status (LOW or OUT),
  quantity_at_event, reorder_level_at_event, movement_id (the USED row that caused it),
  created_at (UTC). Rows are added, never edited or deleted. Existing databases need a
  safe upgrade (add columns, create table) without losing data.
  TO AGENT C (routes_materials.py, materials_record.html): on "Record received" ask for the
  supplier (list of active suppliers) and total price paid in MYR, and save them on the
  RECEIVED row. These two boxes must only appear for Admin; Employees must still be able to
  record received stock (Section 4: Employees cannot see prices), so for an Employee the cost
  stays empty. TEAM TO DECIDE (R4): should an Admin fill the cost in later for rows an
  Employee recorded? Also on every "Record used" that moves a material from OK to LOW or OUT,
  write one low_stock_events row (use alerts.get_status before and after) and one
  activity_log line.
  | Nothing built by me for this yet. Money from RECEIVED rows with no cost will be left
  out of the totals, and the screen will say so.

2026-11-24 | Agent E (statistics & dashboard) | TEAM DECISION CHANGE: Employees may SEE prices,
  shipping costs and money totals, but still cannot change suppliers, offers or materials.
  Guide updated first (Section 4 roles and sensitive data, F2, F4, F6, Section 14 checklist).
  My side: Home money box already follows can_see_prices(), so it will show for Employees as soon
  as that function changes. I split the Statistics page: spending chart and CSV download now use
  is_admin() (F7 still says Admin only; team to confirm, see question below). | REQUESTS (R3):
  TO AGENT B (app/permissions.py): make can_see_prices return True for an active Admin OR an
  active Employee (keep can_manage_* Admin only). TO AGENTS B, C, D, F: old tests that say
  "Employee sees no price / no MYR" must be rewritten to "Employee sees prices but gets 403 when
  changing them"; Agent D's supplier templates and suggest page may test role directly and need
  checking (Rule C7). My tests in tests/test_stats_dashboard.py with "Employee ... no money" will
  fail after Agent B's change and I will update them then. | QUESTION (R4): should Employees also
  see the spending chart and the CSV download (F7 says Admin only)? Until answered they stay Admin
  only.

2026-11-24 | Agent B (login & roles) | DONE: request from Agent E (Employees may SEE prices).
  app/permissions.py: can_see_prices now returns True for an active Admin or active Employee;
  switched-off, not logged in and unknown roles still False. can_manage_materials,
  can_manage_suppliers, can_manage_users, can_view_activity_log and admin_required are
  unchanged (Admin only). My tests updated (24 pass): prices visible to Admin and Employee,
  Employee still cannot manage anything. Full suite: 104 pass, 4 fail (all in other agents'
  files, not edited): tests/test_stats_dashboard.py::test_home_employee_has_no_money_box_or_money,
  tests/test_suppliers_suggest.py::test_employee_suggestion_page_has_no_prices_anywhere_in_the_source,
  ::test_employee_supplier_pages_have_no_prices (all three expect "no price": expected, Agents
  D/E should update them), and ::test_employee_cannot_see_switched_off_supplier (NOT just an
  old expectation: see next). | REQUEST TO AGENT D (Rule R3): app/routes_suppliers.py uses
  can_see_prices() as a stand-in for "is Admin" (lines ~100, 125, 136-139: switched-off
  suppliers/offers hidden, and show_prices in supplier_detail.html also controls the Add /
  Change buttons at lines ~17, 33, 44). Now that Employees can see prices, Employees can open
  switched-off suppliers and are shown the Add / Change links (the server still answers 403
  when they click, but the buttons must not show, and switched-off records must stay hidden,
  Rule C9). Please use a separate check from permissions.py (can_manage_suppliers) for those,
  and use can_see_prices only for the money columns. Same check for Agent E's files. | Until
  D fixes this the supplier pages show Employees buttons they cannot use. Not committed yet.
  (Merged here on 2026-11-24 from the loose file CLAUDE.md.txt; the text above is unchanged.)

2026-11-24 | Team decision + fix (done at the team's request, across Agent B/D/E
  files) | Team decided employees may SEE prices and money totals but not
  change them. Updated Sections 4, 5 (F2, F4, F6), 13, 14 and 15 of this guide
  first. Then fixed a bug this caused: routes_suppliers.py and
  supplier_detail.html used can_see_prices to mean "is Admin", so employees
  could open switched-off suppliers and saw Change / Switch off / Add buttons.
  They now use can_manage_suppliers. Rewrote 3 old tests that expected
  "no prices for employees" (now: employees see prices but no edit buttons).
  All 108 tests pass. | Agent F: add a test that an employee gets 403 when
  typing the supplier/offer edit addresses directly. Team: commit and push (the
  GitHub copy is behind). Remember to run set-password for the sample users.
  | Edit buttons were hidden from employees by the page only before; the
  routes use admin_required, but the new tests do not prove it yet. Statistics
  CSV export and the spending chart are still Admin only (decision covered
  seeing prices, not exports). Agents A, C, D, E have no log entries yet.

2026-11-24 | Agent E (with the team's request to also edit A and C files) | DONE: "money spent" now works.
  Decision: money spent = the real "Total paid" typed on "Record received", counted per supplier per
  Malaysia-time month (not a guess from offers). Changes: app/schema.sql (stock_movements gets supplier_id
  and total_cost_myr, both empty for USED/ADJUSTED), app/routes_materials.py + materials_record.html (Record
  received has optional "Bought from" list and "Total paid (MYR)"; money needs a supplier; bad input is
  refused; the activity log line says who was paid), app/routes_stats.py (SPENDING_METHOD_CONFIRMED = True;
  spending adds up the real totals), sample_data/stock_movements.csv (new columns), tests (117 pass).
  Home money box: Admin and Employee. Spending chart and CSV: still Admin only. | Low-stock events chart is
  still off (needs the table from Agents A/C). Team: an existing data/tracker.db needs two lines run once:
  ALTER TABLE stock_movements ADD COLUMN supplier_id TEXT REFERENCES suppliers(id);
  ALTER TABLE stock_movements ADD COLUMN total_cost_myr REAL CHECK (total_cost_myr IS NULL OR total_cost_myr >= 0);
  (or delete it and run setup_database.py again for sample data). | Old received lines have no total, so they
  count as MYR 0 until someone types one. Committed and pushed.

2026-11-24 | Agent E (with the team's request to also edit A and C files) | DONE: low-stock events chart works.
  Team decision: a low-stock event = one "Record used" that drops a material from OK to LOW or OUT; further
  drops while it stays LOW or OUT do not count again. Changes: app/schema.sql (new table low_stock_events: id,
  material_id, status_after, quantity_after, reorder_level at that moment, created_at), app/routes_materials.py
  (Record used writes the event row in the same save as the stock change), app/routes_stats.py
  (LOW_EVENTS_METHOD_CONFIRMED = True; the chart counts rows per Malaysia-time month; the old "replay history"
  guess is removed), tests (122 pass). Both roles can see the chart (no money in it). | Team: an existing
  data/tracker.db needs this once (the table is new): run the CREATE TABLE low_stock_events block from
  app/schema.sql, or delete the file and run setup_database.py again. | Drops that happened before today have
  no event rows, so the chart starts counting from now. Committed and pushed.

2026-11-24 | Team decision (recorded by Agent E) | Spending chart and CSV download stay ADMIN ONLY.
  Employees still SEE prices and the Home money box (view only). Section 5 F7 already says this, so no screen
  or code change. Existing tests prove it (Employee gets 403 on /stats/export.csv and /stats/data/spending;
  the Statistics page has no chart or download for Employees). | Next: Agent F test that Employees get 403
  when typing the supplier and offer edit addresses. | None.

2026-11-24 | Agent F work (done by Agent E at the team's request) | DONE: Employee 403 proof for supplier and
  offer edit addresses. tests/test_suppliers_suggest.py: the old test sent a half-empty form, so a form check
  could have stopped it too. New tests send COMPLETE valid forms as an Employee to /suppliers/new,
  /suppliers/S1/edit, /suppliers/S1/offers/new and /offers/O1/edit: all give 403 and the suppliers, offers and
  activity log stay exactly the same. The same forms work for the Admin (proves the test is real), and an
  Employee cannot change a price (MYR 72 stays 72). Full suite: 128 pass. | Security checklist items 1 and 2
  in Section 14 can be ticked. Agent F: the rest of the list is yours. | None.

2026-11-24 | Agent E | DONE: chart colours for the dark theme (only app/templates/stats.html; no change to how
  any page works). Chart.js text (axis labels, legend, titles) is now #ECE9DF and grid lines #3a3933. Bars and
  the line use only the palette: usage bars cycle #EB4604, #F77E0D, #99A57D, #ECE9DF, #6f7a5a; delivery time =
  moss; low-stock line = orange wheel (with round points); spending = hot orange. Legends, axis words and
  tooltips are unchanged, so colour is never the only clue. Checked in a browser (Admin, Employee, phone width
  390): text readable, no sideways scroll, charts draw. Full suite on this branch: 128 pass. | Nothing needed
  from Agent H (theme.css and base.html untouched). | (1) The usage chart can show up to 8 materials but the
  palette has 5 colours, so colours repeat after the fifth; the legend and the pop-up name when you point at a
  bar tell them apart. If the team wants 8 clear colours, Agent H must add more palette colours (Rule R3).
  (2) The dark theme (app/static/theme.css) is NOT on this branch (main-0rpyg5); it is on main-iyvssn. The 146
  tests also belong to that branch. This branch and main-iyvssn both changed the money-spent columns,
  low_stock_events, routes_materials.py, routes_stats.py, schema.sql and tests, so merging them will conflict
  and needs the team to pick one version. (3) On a phone, the long supplier names on the delivery-time chart
  are cut off on the left (existing behaviour, not caused by this change).


2026-11-24 | Agent G (documentation & presentation) | DONE: README.md (short "how to run it":
  venv, pip install, setup_database, set-password, STINABLIS_SECRET_KEY, start, roles and log-in,
  tests, known problems), GLOSSARY.md (about 100 entries, grouped, incl. 403/CSRF/session/cookie/
  blueprint, and a table of libraries we use with licenses) and PRESENTATION_NOTES.md (the six
  Section 13 topics, a 2-minute demo script, honest answers to likely questions). Followed my own
  steps on a clean copy (new venv, pip install flask pytest, setup_database, set-password, run the
  app as Admin and Employee, run the tests): works; 108 tests pass. The old README.md was a copy of
  this guide; I replaced it with the short how-to. Its status-log entries (Agents B-E) were NOT in
  this file, so I copied them in above, unchanged, to keep them (they also remain in Git history).
  The guide is CLAUDE.md in the repo, so README says so (this file still calls itself
  PROJECT_GUIDE.txt in its header and in Section 10; team please change that text).
  | LEFT TO DO: (a) re-check all three files after Agent F's review and after the requests below
  land; (b) each member's 3 sentences about two open-source projects (Section 3 TEAM TO DO), I did
  not write them for you; (c) the Section 16 founder questions are untouched and still open (R4).
  | PROBLEM FOUND (real, please fix): sample_data/stock_movements.csv writes dates like
  2026-11-10T02:00:00Z but the app reads 2026-11-10 02:00:00. On a database made by
  app/setup_database.py these pages crash with 500: /materials/<id>/record/used (and received) for
  any material that has history, /stats/data/usage, and /stats/export.csv. The 108 tests pass
  because they build their own data. README has a temporary one-line repair for local databases.
  | REQUESTS (R3, files I do not own): (1) AGENT A: change the 5 dates in
  sample_data/stock_movements.csv to "YYYY-MM-DD HH:MM:SS" (or make setup_database.py convert
  them); update schema.sql comments that say price columns are "Admin only on screen" and
  sample_data/SAMPLE_DATA_README.txt (says Employees cannot see prices; says the online PLA total is
  MYR 134, but the 5-spool minimum order makes it MYR 308 in the app). Section 6 of this guide still
  says price_per_unit; the table has price_per_pack_myr. (2) NO OWNER: a requirements.txt does not
  exist. Suggest Agent A or B add one with flask and pytest (we tested Flask 3.1.3, pytest 9.2.0);
  then I will change README step 2 to "pip install -r requirements.txt". (3) AGENT F: add a test
  that builds the database with setup_database.py and opens the record page, the usage data and
  the CSV; and the pending test that an Employee gets 403 on the supplier/offer edit addresses
  (I checked by hand: 403 on GET and POST for /suppliers/new, /suppliers/S001/edit, an offer edit
  and /materials/new). (4) TEAM: CLAUDE.md.txt is still an untracked duplicate of old log lines;
  decide whether to delete it (I did not). The FilaOps link in Section 3 is wrong: the project is
  github.com/BLB3DPrinting/filaops and its license is custom, not MIT (read it before using any
  code; we use none). github.com/abduznik/filament-tracker returns "Not Found". Xeferis/
  filament-tracker has no license (never copy from it). Spoolman, InvenTree, OSSMS and Stockify
  show MIT. No code from any of them is in our files (searched).
  | NOTE: Home "money spent", the spending chart and low-stock events still say "Not set up yet",
  so the notes do not present them as working. Not built and not described as built: user
  management (F8), activity log screen (F9), backup button, CSRF tokens, email alerts.

2026-11-24 | Users screen (F8, no owner in Section 11; built at the team's request) | Wrote
  app/routes_users.py, templates users_list.html, users_form.html, users_password.html and
  tests/test_users.py (30 checks). Admin can add a user (with first password), change a role,
  reset a password (also unlocks the account) and switch an account off or on. Nothing is deleted.
  Safety rules: an Admin cannot switch off or demote themselves, and the last active Admin cannot be
  switched off. Every action is written to the activity log. Employees get 403 on every address.
  Registered the blueprint in app/__init__.py and added an Admin-only "Users" menu link in base.html,
  using can_manage_users from permissions.py (Rule C7). All 138 tests pass. | Agent F: re-run and try the
  screens in a browser on a phone. Team: forms still have no CSRF token (open since Agent B). Also decide
  who owns F8 in Section 11. | A user with no password cannot log in; "Add user" always sets one.

2026-11-25 | Agent A (database) | DONE: schema changes for "money spent" and "low-stock events"
  (team chose Option B). (1) app/schema.sql: stock_movements has two new empty-by-default columns,
  supplier_id (links to suppliers) and total_cost_myr (empty or at least 0); only for RECEIVED rows an
  Admin recorded. (2) New table low_stock_events (id, material_id, status LOW/OUT, quantity_at_event,
  reorder_level_at_event, movement_id -> the USED row that caused it, created_at). Rows are only added.
  (3) app/setup_database.py: new safe upgrade, run "python app/setup_database.py upgrade". It adds the
  two columns only if missing, creates the table only if missing, prints what it did, deletes nothing,
  and can be run many times. A plain run on an existing database still stops, and now points to
  "upgrade". (4) sample_data/stock_movements.csv: T001 now has supplier S003 and total 76.00
  (1 pack at MYR 58.00 + MYR 18.00 shipping, as in supplier_offers.csv O002; fake data). The other
  rows and low_stock_events stay empty. Note for fake data: O002 says minimum 5 packs but T001 is 1000 g.
  Proof: upgraded a copy of a database built from the OLD schema (git HEAD): all row counts equal
  before/after, second run changed nothing, foreign-key check clean, negative cost rejected. A fresh
  build loads the sample data. Full suite: 138 passed (the request said 141; I did not remove any test,
  the count in the request may have been from a different checkout). | AGENT C CAN START: (a) "Record
  received" form asks supplier and total price, Admin only; (b) each "Record used" that moves a material
  from OK to LOW or OUT writes one low_stock_events row and one activity-log line. Then Agent E can switch
  on SPENDING_METHOD_CONFIRMED and LOW_EVENTS_METHOD_CONFIRMED. | TEAM: the live data/tracker.db
  (if you have one) needs "python app/setup_database.py upgrade" once. I did not touch it.
2026-11-24 | Agent B (login & roles) | Added CSRF tokens (answers request 5 above). New file
  app/csrf.py: each session gets a secret code; every POST/PUT/DELETE must send it or the server
  answers 400 "page has expired". Added a hidden "csrf_token" box to all 9 POST forms (base, login,
  materials x3, suppliers x4 - small one-line edits in Agent C/D templates, done at the team's
  request). app/__init__.py calls csrf.start_csrf_protection and has a CSRF_ENABLED setting (keep True;
  existing tests set it False). 5 new tests; all 113 pass. | Any new form that uses method="post" MUST
  include <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">. JavaScript that sends
  data must add the header X-CSRF-Token. Browser-test one form per screen. | None.

--- Entries merged from CLAUDE.md.txt on 2026-11-24 (that file has been removed) ---

2026-11-23 | Agent B (login & roles) | Wrote app/__init__.py (create_app: secret key
  from STINABLIS_SECRET_KEY, safe cookie settings, "/" home page), app/templates/
  base.html (Log out button) and home.html (placeholder). 22 automatic tests pass.
  Founder-side manual test passed: admin login, employee login, 5 wrong passwords
  lock the account, correct password refused while locked. Sample passwords set
  (not stored in Git). | Agent F: review and extend tests. Then Agents C and D can
  start; register your screens at the marked line in app/__init__.py, and use only
  permissions.py for role checks. Agent E replaces home.html. | Still open: CSRF
  tokens on forms (not built); no Admin screen yet to unlock/reset accounts (F8);
  add .venv/ to .gitignore (no .gitignore exists yet).

2026-11-23 | Agent B (login & roles) | DONE: request from Agent D ticked off. Added a menu bar
  to app/templates/base.html, shown only when logged in: Home, Materials, Suppliers (links
  built with url_for; no role checks, each page checks its own permissions). Tap-friendly
  (padding 10px 14px, font 1rem) and wraps on narrow screens. Added 1 test in
  tests/test_auth_permissions.py (menu appears when logged in, not on the login page).
  | Agent E: when you replace home.html, keep "extends base.html" so the menu stays.
  Add a link here if you add a Statistics page. | None.

2026-11-23 | Agent B (login & roles) | Committed my remaining files (base.html with menu bar,
  home.html, tests/test_auth_permissions.py) and updated .gitignore (.venv/ and
  __pycache__/ added; data/ kept). All 80 tests passed before the commit. Not pushed.
  | CLAUDE.md.txt is still untracked (not mine to add; the team should decide whether to
  keep it, since it duplicates README.md). | None.

2026-11-24 | Agent B (login & roles) | DONE: request from Agent E ticked off. Added a "Statistics"
  link to the menu in app/templates/base.html (Home, Materials, Suppliers, Statistics; links to
  stats.statistics_page; no role check, the page checks its own permissions). Menu test in
  tests/test_auth_permissions.py now also checks the Statistics link. Full suite: 107 pass.
  | Agent E may remove the temporary "See statistics" button from Home if wanted. Change is
  not committed yet. | None.

2026-11-24 | Agent B (login & roles) | DONE: request from Agent E (Employees may SEE prices).
  app/permissions.py: can_see_prices now returns True for an active Admin or active Employee;
  switched-off, not logged in and unknown roles still False. can_manage_materials,
  can_manage_suppliers, can_manage_users, can_view_activity_log and admin_required are
  unchanged (Admin only). My tests updated (24 pass): prices visible to Admin and Employee,
  Employee still cannot manage anything. Full suite: 104 pass, 4 fail (all in other agents'
  files, not edited): tests/test_stats_dashboard.py::test_home_employee_has_no_money_box_or_money,
  tests/test_suppliers_suggest.py::test_employee_suggestion_page_has_no_prices_anywhere_in_the_source,
  ::test_employee_supplier_pages_have_no_prices (all three expect "no price": expected, Agents
  D/E should update them), and ::test_employee_cannot_see_switched_off_supplier (NOT just an
  old expectation: see next). | REQUEST TO AGENT D (Rule R3): app/routes_suppliers.py uses
  can_see_prices() as a stand-in for "is Admin" (lines ~100, 125, 136-139: switched-off
  suppliers/offers hidden, and show_prices in supplier_detail.html also controls the Add /
  Change buttons at lines ~17, 33, 44). Now that Employees can see prices, Employees can open
  switched-off suppliers and are shown the Add / Change links (the server still answers 403
  when they click, but the buttons must not show, and switched-off records must stay hidden,
  Rule C9). Please use a separate check from permissions.py (can_manage_suppliers) for those,
  and use can_see_prices only for the money columns. Same check for Agent E's files. | Until
  D fixes this the supplier pages show Employees buttons they cannot use. Not committed yet.

2026-11-24 | Agent B (login & roles) | HANDOFF: app/templates/base.html now belongs to Agent H
  (Section 11). I will NOT edit it from now on. Before handing over I checked it: it has the menu
  bar (Home, Materials, Suppliers, Statistics; no Users link because no Users page exists yet), the
  Log out form (method="post" to auth.logout) with the CSRF field, and no role checks (it only asks
  "is someone logged in", plus shows the username and role as plain text). Only change I made: fixed
  the indentation of the CSRF field. Merged branch main-nux7zb (it holds the Agent H entry in Section
  11) into main-igoj8o; it re-added CLAUDE.md.txt, which I removed again (entries were already merged
  into this log). All 113 tests pass. | AGENT H MUST KEEP: (1) the hidden field
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> inside the Log out form, and in
  every other POST form (without it the server answers 400); (2) the Log out button as a POST form,
  never a link; (3) every page after login must use {% extends "base.html" %} (login.html is the one
  page that stands alone and has its own style); (4) no "if role == ..." in templates (Rule C7);
  (5) the menu links use url_for, so keep the endpoint names. Add a Users link only when the page
  exists. | STYLING PROBLEMS NOTICED, NOT FIXED: app/static/ does not exist yet and all CSS is inline
  (base.html, login.html, home, materials x3, stats, supplier_style.html), so screens look slightly
  different; the current page is not highlighted in the menu; no visible keyboard-focus outline on
  buttons and links; the topbar button is not styled like the other buttons; Sections 8 needs a help
  sentence under each form title (not on every form yet); the login page does not use the menu look.
  | REQUESTS (Rule R3): Agent D: app/templates/suppliers.html line 9 uses
  current_user['role'] == 'ADMIN' in the template, which breaks Rule C7. Please use can_manage_suppliers
  (for example pass a "can_manage" value from the route, as the materials pages do). Not edited by me.
  | None.

2026-11-25 | Agent B (login & roles) | HANDOFF CONFIRMED (follow-up to the 2026-11-24 handoff entry).
  Merged origin/main-igoj8o (Agent H section, CSRF, first handoff) into main-iyvssn, which holds the
  Users screen and Agent A's work. Fixed the one clash in app/__init__.py (both csrf and routes_users
  are imported now). base.html is clean: menu (Home, Materials, Suppliers, Statistics, and Users shown
  through can_manage_users from permissions.py, so no role checks in the template), Log out POST form
  with the CSRF field. base.html is Agent H's; I will not edit it again. | AGENT H MUST KEEP: the
  csrf_token hidden field in every POST form, Log out as a POST form, "extends base.html" on every page
  after login, and the Users link (it now exists) with its can_manage_users check. | PROBLEMS (all in
  files I do not own, so not edited, Rule R2): full suite after merging everything = 120 pass, 26 FAIL: 24 in tests/test_users.py and 2 in tests/test_sample_data.py (line 41, same missing "CSRF_ENABLED": False).
  Cause: the Users screen was built before CSRF existed. REQUESTS (Rule R3): (1) Users screen owner:
  add <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> to the 4 forms in
  app/templates/users_form.html, users_password.html and users_list.html (2 forms); without it a real
  browser gets "page has expired". (2) Agent F / Users owner: tests/test_users.py line 38 must pass
  "CSRF_ENABLED": False in create_app (as the other test files do), plus one test that a POST without the
  token is refused. Styling problems: same list as the 2026-11-24 entry; nothing new.
2026-11-24 | Sample-data date bug (found by Agent G; fixed at the team's request, touching Agent A's
  sample_data and Agent F's tests) | Changed the 5 dates in sample_data/stock_movements.csv from
  "2026-11-10T02:00:00Z" to "2026-11-10 02:00:00", the format the app reads. Added
  tests/test_sample_data.py (3 checks): it builds a database from the real sample files and proves the
  dates have the right format and that the Record used/received pages, /stats/data/usage and
  /stats/export.csv open without a 500 error. The checks failed before the fix and pass now. All 141
  tests pass. | Agent A: databases already created with the old file still hold the old dates; delete
  data/tracker.db and run app/setup_database.py again, or use the repair in README.md. Also still to do
  from Agent G's request: schema.sql comments, SAMPLE_DATA_README.txt, requirements.txt. | None.

2026-11-24 | Schema comments, sample-data notes and requirements.txt (Agent G's requests; done at the
  team's request, touching Agent A's files) | app/schema.sql: the two price comments now say "Admin and
  Employee can see; only Admin can change" (comments only, no table change). sample_data/
  SAMPLE_DATA_README.txt: employees may see prices (team decision 2026-11-24), and the online PLA
  example is now MYR 308.00 (5-spool minimum order), so the local shop is cheaper and faster. New
  requirements.txt: Flask>=3.1,<4 and pytest>=8. All 141 tests pass. | Agent G: change the README
  install step to "pip install -r requirements.txt" (the README in this repo is still the old copy of
  the guide). Team: Section 6 of this guide still says price_per_unit and shipping_cost; the table has
  price_per_pack_myr, minimum_order_packs and shipping_cost_myr. | None.

2026-11-24 | README.md (Agent G's job; rebuilt at the team's request because Agent G's copy was not in
  the repo) | Replaced the old README.md, which was an out-of-date copy of this guide (721 lines; the
  only differences were older wording from before the 2026-11-24 decisions, and it stays in Git
  history), with a short how-to: virtual environment, pip install -r requirements.txt, setup_database,
  set-password, secret key, start, roles table, tests, folder map and known problems. I followed the
  steps on a clean clone (new venv, install, setup_database, set password, log in as Admin): Home,
  Materials, Statistics and Users all open. | Agent G: GLOSSARY.md and PRESENTATION_NOTES.md are still
  missing from the repo; compare this README with yours. | None.

2026-11-24 | GLOSSARY.md (Agent G's job; drafted at the team's request because Agent G's copy was not in
  the repo) | New GLOSSARY.md: about 100 words in six groups (business, how the system works, safety, code
  and testing, screens, libraries with licences). Checked against the code: the CSV safe-cell rule, the
  lock rule, the SameSite/HttpOnly cookie settings and the table names. States that no code was copied from
  the open-source projects (Rule C10). | Team: each member should read it before the presentation. Agent G:
  compare with your own version; PRESENTATION_NOTES.md is still missing. | The licence column is from
  general knowledge, not read from each project's licence file; please check before the presentation.

2026-11-25 | Agent B (login & roles) | DONE, at the team's request (edits in files I do not own, Rule R2 waived by the team): added the csrf_token hidden field to the 4 forms in users_form.html, users_password.html and users_list.html, and "CSRF_ENABLED": False to create_app in tests/test_users.py and tests/test_sample_data.py. This closes both requests in my entry above. Full suite: 146 pass. | Agent F: add a test that a POST without the token is refused on the Users screen. | None.

2026-11-25 | Agent H (interface and design) | DONE: new colour theme from the team's colour card (dark pages, hot-orange buttons, moss for OK). New file app/static/theme.css holds every colour in one :root list at the top (change a colour there, nowhere else). base.html no longer has inline CSS; it links theme.css. login.html got one extra line linking theme.css. The theme overrides the old inline colours of the other pages from the outside, so no other template or route was changed. Status words stay written (OK moss, LOW orange, OUT orange outline), buttons use dark text on orange for readability, keyboard focus is now visible. Checked in a browser: login, Home, Materials, Statistics. All 146 tests pass. | REQUESTS (Rule R3): Agent E: the Chart.js colours in app/templates/stats.html (blue/red bars, dark grey axis and legend text) are hard to read on the dark page; please use light text (#ECE9DF), grid lines #3a3933 and the palette (#EB4604, #F77E0D, #99A57D). Agents C/D/E and the Users owner: the old inline colours (#fff, #1a5fb4) can be deleted from your templates over time; theme.css wins either way. Not checked in a browser: Suppliers, suggestion, forms, Users pages. | None.

2026-11-24 | Agent E (merge done at the team's request; touches Agent A, B and C files) | DONE: merged
  main-iyvssn (dark theme, CSRF, Users screen, Agent A's schema) into main-0rpyg5. Team decisions: keep
  Agent A's database design, and ONLY THE ADMIN types supplier and total paid on "Record received". The 3
  text clashes (schema.sql, stock_movements.csv, this log) were settled by taking Agent A's schema and
  sample data and keeping both sets of log entries. Then changed my code to fit: (1) low_stock_events rows
  now use Agent A's columns (status, quantity_at_event, reorder_level_at_event, movement_id = the USED
  line that caused it) and each event also writes one activity-log line (LOW_STOCK_EVENT); (2) new rule
  can_record_purchase_cost in app/permissions.py (Admin only, Rule C7); the money boxes are drawn only for
  Admin, and an Employee who types supplier or total anyway gets 403 and nothing is saved; (3) tests
  updated (Employee money = 403, events link to their USED line). Employee "received" lines have no total,
  so they count as MYR 0 in money spent. Full suite: 169 pass. Also tried with CSRF switched on: Admin
  save works, Employee with money 403, Employee without money works, Record used writes the event.
  | Team: existing databases need "python app/setup_database.py upgrade" once (Agent A's command; it adds
  the two columns and the new table safely). The two ALTER lines in my 2026-11-24 entries are replaced by
  that command. | Old note: "Employees may type the total" in my earlier entries is no longer true.


2026-11-25 | Mark (Agent G) | Reviewed Spoolman and FilaOps on GitHub to borrow practical ideas without copying code: Spoolman shows how to display remaining material clearly, while FilaOps shows how low-stock alerts and reorder planning prevent print jobs from stopping. Where our app helps Stinablis more is tracking filaments, resins, composites, and everyday hardware pieces like screws, springs, magnets, fidget clickers, and keychain rings in one simple web app with supplier cost and delivery-time comparisons. | GLOSSARY.md, PRESENTATION_NOTES.md, and this open-source log are committed and pushed on branch main-o7f8p8. Ready to rebase and re-check the docs once Main Chat! merges the other branches. | sample_data/stock_movements.csv date format and requirements.txt still belong to other/unassigned files under Rule R3.

2026-11-25 | Agent G (documentation & presentation) | Post-merge sync of README.md, GLOSSARY.md and PRESENTATION_NOTES.md against origin/main-iyvssn. I merged that branch into main-o7f8p8 here (code merged cleanly; README, GLOSSARY and CLAUDE.md conflicted). I kept Agent G's README and GLOSSARY, took the integration branch's CLAUDE.md and re-added the 2026-11-25 Mark entry. Verified on the merged code: 146 pass (about 60 seconds); CSRF tokens on all 11 POST forms; Users screen (F8) built; requirements.txt exists; sample dates fixed and covered by tests/test_sample_data.py. Updated the three files (setup step uses requirements.txt, 146 tests, CSRF and Users described as built, date-bug warning removed, a "Why this fits Stinablis" section, and a version 2 answer for questions). VERSION 2 IDEAS (Section 17, not built, not promised): printable labels for racks and shelves; humidity and dry-box alerts for moisture-sensitive filaments in Sarawak's climate; linking material stock to job quoting. | Re-check the three files again after the branches below are merged: the "Not set up yet" money and low-stock-event statements, the Agent F review and the supplier-edit 403 test statements will change. | PROBLEMS: three remote branches were NOT in origin/main-iyvssn when I checked: main-0rpyg5 (money spent from Record received, low-stock events, Employee 403 tests on supplier and offer edit addresses, a decision that spending chart and CSV stay Admin only), main-tq6ebi (Agent D can_manage_suppliers fix) and claude/modest-albattani-0zgw7k (Agent F review tests and bugs F-1 to F-10). origin/main is still at bc665d4. Main Chat!: please confirm where the final merge lives. README now says the money box and low-stock chart are "Not set up yet" because that matches the merged code I tested. The hardware pieces list (screws, springs, magnets, fidget clickers, keychain rings) is still unconfirmed by the founder (Section 16 Q1); the docs say so. Guide text still stale (not mine, R3): Section 6 price_per_unit/shipping_cost "Admin only data"; Section 13 says "three roles"; header and Section 10 say PROJECT_GUIDE.txt; Section 3 FilaOps link.

2026-11-24 | Agent E (with the team's request to also edit A and C files) | DONE: "money spent" now works.
  Decision: money spent = the real "Total paid" typed on "Record received", counted per supplier per
  Malaysia-time month (not a guess from offers). Changes: app/schema.sql (stock_movements gets supplier_id
  and total_cost_myr, both empty for USED/ADJUSTED), app/routes_materials.py + materials_record.html (Record
  received has optional "Bought from" list and "Total paid (MYR)"; money needs a supplier; bad input is
  refused; the activity log line says who was paid), app/routes_stats.py (SPENDING_METHOD_CONFIRMED = True;
  spending adds up the real totals), sample_data/stock_movements.csv (new columns), tests (117 pass).
  Home money box: Admin and Employee. Spending chart and CSV: still Admin only. | Low-stock events chart is
  still off (needs the table from Agents A/C). Team: an existing data/tracker.db needs two lines run once:
  ALTER TABLE stock_movements ADD COLUMN supplier_id TEXT REFERENCES suppliers(id);
  ALTER TABLE stock_movements ADD COLUMN total_cost_myr REAL CHECK (total_cost_myr IS NULL OR total_cost_myr >= 0);
  (or delete it and run setup_database.py again for sample data). | Old received lines have no total, so they
  count as MYR 0 until someone types one. Committed and pushed.

2026-11-24 | Agent E (with the team's request to also edit A and C files) | DONE: low-stock events chart works.
  Team decision: a low-stock event = one "Record used" that drops a material from OK to LOW or OUT; further
  drops while it stays LOW or OUT do not count again. Changes: app/schema.sql (new table low_stock_events: id,
  material_id, status_after, quantity_after, reorder_level at that moment, created_at), app/routes_materials.py
  (Record used writes the event row in the same save as the stock change), app/routes_stats.py
  (LOW_EVENTS_METHOD_CONFIRMED = True; the chart counts rows per Malaysia-time month; the old "replay history"
  guess is removed), tests (122 pass). Both roles can see the chart (no money in it). | Team: an existing
  data/tracker.db needs this once (the table is new): run the CREATE TABLE low_stock_events block from
  app/schema.sql, or delete the file and run setup_database.py again. | Drops that happened before today have
  no event rows, so the chart starts counting from now. Committed and pushed.

2026-11-24 | Team decision (recorded by Agent E) | Spending chart and CSV download stay ADMIN ONLY.
  Employees still SEE prices and the Home money box (view only). Section 5 F7 already says this, so no screen
  or code change. Existing tests prove it (Employee gets 403 on /stats/export.csv and /stats/data/spending;
  the Statistics page has no chart or download for Employees). | Next: Agent F test that Employees get 403
  when typing the supplier and offer edit addresses. | None.

2026-11-24 | Agent F work (done by Agent E at the team's request) | DONE: Employee 403 proof for supplier and
  offer edit addresses. tests/test_suppliers_suggest.py: the old test sent a half-empty form, so a form check
  could have stopped it too. New tests send COMPLETE valid forms as an Employee to /suppliers/new,
  /suppliers/S1/edit, /suppliers/S1/offers/new and /offers/O1/edit: all give 403 and the suppliers, offers and
  activity log stay exactly the same. The same forms work for the Admin (proves the test is real), and an
  Employee cannot change a price (MYR 72 stays 72). Full suite: 128 pass. | Security checklist items 1 and 2
  in Section 14 can be ticked. Agent F: the rest of the list is yours. | None.

2026-11-24 | Agent F (testing & review) | Wrote tests/test_review_agent_f.py (about 200 checks). Whole suite:
  298 passed, 12 expected-failures (xfail = a test that describes a known bug; it turns into an
  error when the bug is fixed, so then remove the xfail mark). COVERED: employee gets exactly 403 on
  every supplier/offer add, edit, switch-off address (GET and POST, valid data, other methods) and
  changes nothing; visitor is sent to login; every address as Admin / Employee / visitor; account
  lock on the 5th wrong password and unlock after 15 minutes; password_hash is never a plain
  password; Admin and Employee actions write activity_log (and refused actions write none); number
  fields reject letters and silly values, text fields reject very long input; CSV export and
  spending data Admin only; every Section 15 item (800 g -> use 400 -> LOW -> use 400 -> OUT,
  cheaper+faster supplier first, arrival = today + lead time, Malaysia time UTC+8); every rule of
  Sections 4 and 7; Rules C2, C5, C6, C9. | NEXT: owners fix the bugs below, then remove the xfail marks.
  | PROBLEMS (not fixed by me, Rule R3):
  F-1 (CONFIRMED) No CSRF tokens on any form. Owner: Agent B (+ all form pages).
  F-2 (CONFIRMED) No Admin screen to add users, reset passwords, disable or unlock accounts (F8);
      the only way is "python app/auth.py set-password". Owner: team decision (F8 has no owner).
  F-3 No Admin screen shows the activity log (F9). Owner: team decision.
  F-4 No one-click database backup for Admin (Section 14). Owner: team decision.
  F-5 Spending chart and low-stock-events chart are switched off in routes_stats.py
      (SPENDING_METHOD_CONFIRMED, LOW_EVENTS_METHOD_CONFIRMED = False), waiting for the founder.
      Owner: Agent E. So the "Admin sees spending chart" check cannot be tested yet.
  F-6 requirements.txt, GLOSSARY.md and app/models.py (Section 10) do not exist. Owner: Agent G / A.
      Agent A's files DO exist (app/schema.sql, app/setup_database.py, sample_data/) and Agent C's
      files DO exist (routes_materials.py, alerts.py, templates), but neither agent wrote a log entry.
  F-7 BUG: in routes_materials.py read_number() deletes every comma, so typing "1,5,5" records 155 g,
      and it accepts non-English digits. Reject commas that are not thousands separators. Owner: Agent C.
  F-8 Rule C3: the two inner "checked_view" functions in permissions.py (lines ~60 and ~70) have no
      comment line. Owner: Agent B.
  F-9 BUG: sample_data/*.csv dates look like 2026-11-18T06:30:00Z, but the app reads
      "YYYY-MM-DD HH:MM:SS". With the sample data, /stats/data/usage crashes (server error).
      Owner: Agent A (change the sample dates or the import).
  F-10 (CONFIRMED) Sample users have no password until "python app/auth.py set-password sample_admin"
      and "... sample_employee" are run; until then nobody can log in (tested: safe, no guessable password).
  STILL UNTESTED: the real browser screens on a phone, CSV content with the spending chart (switched
  off, see F-5), email alerts (not built), and a real two-person race on the same stock record.

2026-11-24 | Agent E (merge done at the team's request) | DONE: PR #1 had a merge conflict again because
  main had moved on (other branches, including an older copy of mine, were merged into main). Merged
  origin/main into main-0rpyg5. 2 clashes: app/schema.sql (main still had my OLD column names
  status_after / quantity_after; kept Agent A's design: status, quantity_at_event, reorder_level_at_event,
  movement_id, matching the code and the setup_database.py upgrade) and this log (kept every entry from
  both sides). Everything else merged without edits. Full suite: 368 pass, 2 skipped, 6 expected failures
  (all in Agent F's review file, none about money or low-stock events). | Team: anyone who built a database
  from main's old schema needs a fresh one (delete data/tracker.db, run setup_database.py) because the
  low_stock_events column names changed; the upgrade command will NOT rename them. | Agent C / Agent F:
  F-7 (read_number turns "1,5,5" into 155) also affects the new "Total paid" box.


2026-11-24 | Main Chat (plan, done at the team's request across Agent A, C and B files) | DECISION: adapt
  three improvements from the ShopGuard idea list into Version 1. (a) Hardware pieces (unit pcs) next to
  g and ml items in the SAMPLE data only: screws, springs, magnets, fidget clickers and keychain rings,
  all named "SAMPLE ..." and listed under a hardware supplier; the real Stinablis item list is still
  [CONFIRM WITH FOUNDER] (Section 2, Section 16 Q1; Rule R4). (b) "Last bought" memory on the Materials
  list and the Record used / Record received screens (see Section 5 F3), using can_see_prices() for the
  money and leaving every edit check as it was (can_manage_*, admin_required, 403). (c) A plain-English
  pass: a one-line OK / LOW / OUT explanation, a LOW / OUT hint on the Record screens, tap-friendly
  buttons, and plain error pages with a Home button (Section 8). Sections 2, 5 and 8 updated FIRST. |
  Then: sample_data CSVs, app/routes_materials.py + materials_list.html + materials_record.html (Agent C),
  app/__init__.py + one new template error_page.html (Agent B), new tests. | CROSS-AGENT REQUESTS (R3,
  edits made at the team's request, please review): AGENT A: sample_data/materials.csv,
  supplier_offers.csv, stock_movements.csv and SAMPLE_DATA_README.txt got new sample rows (dates kept in
  "YYYY-MM-DD HH:MM:SS"). AGENT C: new helper in routes_materials.py for the last-bought line. AGENT B:
  error pages in app/__init__.py. AGENT H: base.html and app/static/ NOT touched; the shared look and the
  44 px tap size on every screen are still yours (the new tap-size lines are only inside the Agent C
  templates). AGENT F: please add Employee-sees-last-bought tests to your review list.
  | CLAUDE.md.txt was NOT recreated or committed.

2026-11-25 | Agent G (documentation & presentation) | FINAL DOC SYNC against origin/main-o7f8p8 at 10f78ab (branches main-0rpyg5, main-tq6ebi and Agent F's review are now merged). Full suite on that commit: 379 passed, 2 skipped, 6 xfailed (about 68 seconds). Updated README.md, GLOSSARY.md and PRESENTATION_NOTES.md: new test count; "Last bought" memory (money follows can_see_prices, edits still 403); sample hardware in pcs marked as SAMPLE and to confirm with the founder (R4); OK / LOW / OUT explained in plain English; 44 px tap size; plain-English 403/404/400 pages with "Back to Home"; money spent and low-stock events now described as working (they were "Not set up yet"); Version 1 built list kept apart from Version 2 ideas. | Re-check once more only if more branches are merged. Team: confirm the hardware list and the real suppliers with the founder (Section 16). | PROBLEMS: (1) The "SupplyTrail" pitch figures (supplier search from about 2 hours a week towards about 30 minutes a week) were not found anywhere in the repo, so PRESENTATION_NOTES.md labels them as the team's goal and an estimate, not measured and not confirmed by the founder (R4); Mark: please confirm the source. (2) Six tests are xfail (known bugs from Agent F's review); owners should fix them and remove the marks. (3) Still stale in the guide (R3, not mine): Section 6 price_per_unit / shipping_cost "Admin only data"; Section 13 says "three roles"; header and Section 10 say PROJECT_GUIDE.txt; Section 3 FilaOps link. (4) No activity-log screen (F9) or backup button yet.

2026-11-24 | Agent E | CHECKED: "Usage per material shows sample bars at Jun 2026" is NOT a bug. The chart always
  shows the last 6 months, oldest on the left: Jun, Jul, Aug, Sep, Oct, Nov 2026. "Jun 2026" is only the FIRST
  (leftmost) label and has no data. The sample usage (18 to 22 Nov 2026) is in the LAST slot, "Nov 2026", at
  the right edge. Proof: built a database from the real sample_data and read /stats/data/usage: month data is
  [0, 0, 0, 0, 0, 500/500/260/170] with labels Jun..Nov 2026; week view puts all of it in "Week of 16 Nov";
  low-stock events and spending also use Malaysia time and land in Nov 2026 (spending MYR 76.00, one bar).
  Took a browser screenshot: bars are at the right, under "Nov 2026". Checked for off-by-months, date format
  and UTC versus Malaysia time: none found (a movement at 31 Oct 16:00 UTC correctly counts as 1 Nov in
  Malaysia). Added 2 tests in tests/test_stats_dashboard.py (sample-style dates land in November by month and
  by week; month edges use Malaysia time). No code change. The chart recolour in stats.html was already
  committed (658fdd2) and merged with PR #1. Full suite passes. | If a screen still shows bars under
  Jun 2026, the database holds other (older) movements; check data/tracker.db. | None.

2026-11-24 | Agent E (restyle done at the team's request, touching Agent H's files app/static/theme.css and
  app/templates/base.html, plus login.html and my home.html and stats.html) | DONE: new look from the team's
  design reference (rounded outlined cards with a solid offset shadow, light and dark cards side by side,
  section titles in highlighted tags, mono-font buttons and links, one header row, hero with a small drawing
  on Home). THE COLOUR PALETTE IS UNCHANGED: only the 7 colours already in theme.css :root are used, no new ones.
  What changed: theme.css rewritten (same variables, new shapes, fonts Space Grotesk and Space Mono from Google
  Fonts with safe fallbacks if offline); base.html is now one header row (logo, menu, user and Log out) and the
  current page is marked in the menu (aria-current); home.html has a hero (welcome, two buttons, an inline
  drawing) and the four boxes as a light/dark checkerboard; login.html loads the fonts; stats.html charts use the
  same font. Row buttons inside tables are outlined and smaller; on a phone tables scroll sideways inside their own
  box (the page itself never does). Nothing a page DOES changed: same links (url_for), the Log out form is still
  a POST with the csrf_token, the Users link keeps its can_manage_users check, no role logic added. Checked in a
  browser (login, Home, Materials, Suppliers, Statistics, phone width 390): readable, no sideways page scroll.
  Full suite passes. | Agent H: please review the new theme.css and keep it as the base. Pages not
  checked in a browser: supplier detail, suggestion, material add/edit/record forms, Users screens; they use
  the same classes so should follow, but please look. | (1) The fonts come from fonts.googleapis.com and
  fonts.gstatic.com; if the team wants no outside requests, remove the 3 font lines in base.html and
  login.html (the page then uses Segoe UI or Arial). (2) The Home drawing is plain decoration (aria-hidden).

2026-11-26 | Agent E | DONE, at the team's request: the Home list "Needs attention" is now called "Notifications"
  (heading, and the empty text now says "No notifications. All materials are OK."). Only the words changed:
  the list still shows LOW and OUT materials (OUT first) with a Find supplier button. Files: app/templates/
  home.html, comments in app/routes_stats.py, TESTS.md, and 1 new test in tests/test_stats_dashboard.py.
  Full suite passes. | AGENT G (R3): GLOSSARY.md line "Needs attention" and PRESENTATION_NOTES.md (about lines
  117 and 259) still use the old name; please change them to "Notifications". Agent F: the comment in
  tests/test_review_agent_f.py line 586 still says "Needs attention" (comment only). | None.



2026-11-24 | Agent F (testing & review) | Founder-side phone test (iPhone-size screen, real site on the
  Mac over Wi-Fi) done by the team member; I added what they found. Only reads; no app code touched.
  | NEXT: owners fix below, then re-test on the phone. | PROBLEMS (Rule R3):
  F-11 Materials, Suppliers and Supplier pages need sideways scrolling on a phone to see the right
      columns (tables sit in an overflow-x box). Text size and buttons are fine. Idea: fewer columns
      or stacked rows on narrow screens. Owner: Agent C (materials_list.html), Agent D
      (suppliers.html, supplier_detail.html). Section 8 asks for mobile-friendly.
  F-12 Phone numbers (and emails) are plain text, not tappable. Use tel: and mailto: links in
      suggest.html, suppliers.html, supplier_detail.html. Owner: Agent D.
  F-13 Statistics: the "Average delivery time per supplier" chart is cut off on the left side on a
      phone (the usage chart is fine). Probably long supplier names squeezing the chart. Owner: Agent E
      (stats.html / its Chart.js settings, id lead-chart).
  F-9 UPDATE: confirmed on the phone. "Record used" gives an internal server error for materials
      that have sample history (M001, M003, M004), because the dates in sample_data/stock_movements.csv
      are like 2026-11-18T06:30:00Z. Local fix that worked for the tester: on macOS run
      sed -i '' -E 's/T([0-9:]{8})Z/ \1/' sample_data/stock_movements.csv, delete data/tracker.db,
      run setup_database.py again, then set-password for both sample users. Owner: Agent A (fix the
      sample file or the import). Agent C could also make the pages read both date styles.
  NOT A BUG: "Record used" shows the number keypad on a phone with no letters (it uses
      inputmode="decimal" on purpose). Good for typing quantities.
  Also noted: the dev server needed --host 0.0.0.0 and a port other than 5000 (macOS AirPlay) to open
      from a phone; macOS system Python 3.9 has no hashlib.scrypt, so auth.py crashes there
      (Agent B could pass method="pbkdf2:sha256"). Use Homebrew Python.

2026-11-25 | Agent G (documentation & presentation) | DOC SYNC after the final merge into main (commit 6024c83; I re-ran the suite: 384 passed, 2 skipped, 6 xfailed). Updated README.md, PRESENTATION_NOTES.md and one GLOSSARY.md entry: test count and commit; "Bought from" and "Total paid" on Record received are Admin only (can_record_purchase_cost; an Employee who sends them gets 403), while Employees still see "Last bought" under can_see_prices(); the shared dark theme (app/static/theme.css) is mentioned; the phone test findings F-11 and F-12 are stated honestly. | Before the demo: check in a browser that the top menu links (sized in theme.css by padding plus a small minimum height) are about 44 px tall like the other controls (Agent H). | PROBLEMS (R3, not mine): F-11 to F-13 from the phone test are still open (sideways-scrolling tables, phone numbers not tappable, delivery-time chart cut off); the merge repeated some older status-log entries in this file; the SupplyTrail figures still have no source (see the previous Agent G entry).

2026-11-26 | Agent E | CATCH-UP: things done since my last entries that were not written down yet. (1) The guide:
  Section 5 F2 now says "Notifications" (it still said "Needs attention"; the guide must change first, so
  that line is fixed now). (2) Pull request #1 (money spent, low-stock events, Employee 403 tests, chart
  colours, merge of the dark theme) was opened on 2026-11-24, had a second merge conflict when main moved
  (only app/schema.sql and this log; kept Agent A's low_stock_events columns and every log entry), and was
  MERGED into main. (3) Pull request #2 (the "Needs attention" to "Notifications" rename on Home) is open; main
  had moved again, so I merged origin/main into main-0rpyg5 first: one clash, only this log (kept both sides).
  Suite on the branch: 385 pass, 2 skipped, 6 expected failures (all Agent F review items). (4) Another
  session pushed one commit to main-0rpyg5 (branch main-0rpyg5-v2k49y): 4 lines in app/static/theme.css that
  style the "Last bought" notes (.memo) for the dark theme. Agent H's file; I only merged it in (fast-forward)
  and the tests still pass. (5) Restyle detail missing from my 2026-11-24 restyle entry: on phones (screen
  720 px or narrower) theme.css sets "table { min-width: 880px }", so tables keep a readable width and scroll
  sideways INSIDE their own box (the page itself never scrolls sideways). This is a main cause of F-11
  (Materials and Suppliers need sideways scrolling on a phone). The better fix is stacked rows on narrow
  screens; that is a page change for Agent C (materials_list.html) and Agent D (suppliers.html,
  supplier_detail.html), plus Agent H for the shared CSS (R3). | NEXT: F-13 is mine and still OPEN: the
  "Average delivery time per supplier" chart is cut off on the left on a phone because the long supplier
  names squeeze the chart; I plan to shorten or wrap the labels in stats.html (lead-chart) and check it at
  390 px. I will not start it until the team says go. Agent G: still to change "Needs attention" to
  "Notifications" in GLOSSARY.md and PRESENTATION_NOTES.md. | PROBLEMS: (a) the merges left repeated and
  out-of-date-order entries in this log (for example my "money spent" and "low-stock events" entries appear
  twice, once near the start of my entries and once after the Agent F review). I did not delete anything
  (Rule R5); the team or Agent G should decide how to tidy it. (b) Older entries of mine still say "Not
  committed yet" or describe the Admin-and-Employee money boxes; the 2026-11-24 merge entry (Admin only) is the
  one that is current.

2026-11-26 | Agent E | DONE: procurement statistics and units and prices on every chart (team decision 2026-11-26; the guide
  F7 text was updated first). NOTE ON HOW IT WAS BUILT: when I came back to the working folder it already held
  uncommitted work on my files from another session: the guide F7 text, the data functions and three data addresses
  in app/routes_stats.py (purchases, spending per material, price comparison rows), the CSV rows, and 3 small test
  edits. I did not overwrite it; I read it, kept it and finished the rest. WHAT IS NEW ON THE PAGE
  (app/templates/stats.html, routes_stats.py): (1) "Purchases per material" (stock received per month, each bar with
  its unit g, ml or pcs; both roles, no money). (2) "Spending per material" (MYR over the last 6 months, one row per
  material, the chart gets taller with more materials; Admin only). (3) "Supplier price comparison" table (cheapest
  offer per kg, per litre or per piece next to the price last paid, with "paid X% more" or "X% less"; Admin only; a
  note says these are estimates because the offer is before shipping and the paid total may include it). UNITS AND
  PRICES: every chart now has axis titles (Quantity used (g, ml or pcs), Quantity received, Number of events with
  whole numbers, Average days from ordering to arriving, MYR spent) and pop-ups that read "PLA Basic White: 250 g",
  "6 days", "2 events", "MYR 76.00 (1 purchase)"; money axes read MYR 100, MYR 200. The usage data now also carries
  "name" and "unit" per bar group. The old inline colours in stats.html were removed (theme.css decides). Employee
  page source still contains no "MYR", "Spending" or comparison table (tests prove it); the 3 new data addresses are
  in Agent F's address matrix. Checked in a browser as Admin, Employee and at 390 px with extra purchase data: no
  script errors, no sideways page scroll. Suite: 422 pass, 2 skipped, 6 expected failures. | NEXT: Agent G: add the
  new charts to PRESENTATION_NOTES.md and GLOSSARY.md if wanted. F-13 (delivery-time chart cut off on a phone) is
  still OPEN and not touched. | PROBLEMS: (1) the usage and purchases charts put g, ml and pcs on one axis, so a
  pcs bar (for example 20 pcs) looks tiny next to a 3,000 g bar; the pop-up gives the exact unit and number. A
  chart per unit would fix it (team decision). (2) "Price paid" on the comparison is the typed total divided by the
  quantity, so shipping inside the total makes it look higher than the offer. (3) The price comparison is a table,
  not a chart.

2026-11-26 | Agent E (new files at the team's request; no agent owns them) | DONE: a tracked record of the difference
  between the Admin and Employee profiles for the presentation. New file ROLE_DIFFERENCES.md (30-second summary, six
  tables by screen with Admin / Employee Yes or No and a plain note, what is the same for both roles, a dated
  decisions table, what is not built yet, and how to keep it true) and new test tests/test_role_differences.py: 24
  rows, each tried as a real logged-in Admin and Employee on a temporary database, plus 2 checks that the page says
  exactly what the proof says (a wrong Yes/No cell, a missing row or an unproven extra row makes the test fail; I
  tried all three). Guide Section 13 item 2 now says "two roles" and points to the file. | HOW TO KEEP IT TRUE: when
  a permission changes: guide first, then the row in ROLE_ROWS, then the page, then a line in its decisions table.
  | REQUESTS (R3): Agent G: link ROLE_DIFFERENCES.md from PRESENTATION_NOTES.md (topic 2, the roles) and README.md,
  and add a GLOSSARY.md line if wanted; the notes and README still say "three roles" in places. Agent F: you may
  fold test_role_differences.py into your list; it overlaps your SCREEN_MATRIX on purpose (yours checks status
  codes, mine checks what each role sees and says it in words). | PROBLEMS: the page covers screens that exist today;
  the activity log screen and the backup button are not built, so they are listed as "not built yet" and are not
  proven.

2026-11-26 | Agent E | DONE: the supplier price comparison is now also a CHART (team asked to go back to the statistics we
  had planned; the guide F7 line was updated first). New Admin-only data address /stats/data/price-comparison
  (admin_required) and two bar charts in the Statistics page, above the existing table: "Materials priced per kg or
  per litre" and "Materials priced per piece". They are separate because their prices are on very different scales
  (MYR 60 per kg against MYR 0.09 per piece would hide the small bars). Each material shows two bars: the cheapest
  supplier offer and the price last paid; the pop-up gives the supplier and the date (for example "Price last paid:
  MYR 75.00 per kg (Kuching Shop, 05 Nov 2026)"). Materials with neither an offer nor a purchase are left out; an
  offer with no purchase yet shows one bar. The table stays, as "the same numbers". Code: build_chart_point and
  get_price_comparison_chart in routes_stats.py; stats.html. Roles: Employee gets 403 on the address and the
  Employee page has no price chart (tests prove it); ROLE_DIFFERENCES.md and tests/test_role_differences.py have the
  new row; Agent F's address matrix has the new address. Checked in a browser (Admin, 390 px): no script errors, no
  sideways page scroll. Suite: 427 pass, 2 skipped, 6 expected failures. | STILL NOT BUILT from the plan: "Price paid
  per unit over time" (a line chart; it needs several purchases of the same material to show a trend) and one chart
  per unit for usage and purchases. F-13 (delivery-time chart cut off on a phone) is still open. | PROBLEMS: the same
  as before: "price paid" is the typed total divided by the quantity, so shipping inside the total makes it look higher
  than the offer.

2026-11-26 | Team decision (recorded by Agent E) | The statistics list for the Statistics page is COMPLETE. The supplier
  price comparison chart was the last one wanted. NOT being built (dropped, not postponed): "price paid per unit over
  time" and "one chart per unit for usage and purchases". Section 5 F7 already matches what is built, so no guide
  change. | Only open item on this page: F-13 (the delivery-time chart is cut off on a phone), which is a fix, not a
  new statistic. | None.


2026-11-26 | Agent H (interface and design; done at the team's request, touching Agent C's materials_list.html) | DONE: (1) "Last bought" note on the Record used page and the Materials list was unreadable (light-blue box with light text); app/static/theme.css now draws it as a dark card (Record used page) and soft moss text (Materials list). (2) Materials rows: "Record used" is the one filled button, "Record received" is outlined, Edit and Remove are under a "More" menu (Admin only; Employees see just the two record buttons). Changed app/templates/materials_list.html (markup only, same links, same POST form with csrf_token, same confirm box, no role logic) and theme.css (.row-actions, .row-more, .btn.danger). Checked in a browser as Admin and Employee at desktop width; whole suite 385 pass, 2 skipped, 6 expected failures. Also did a UI/UX review of login, Home, Materials, Suppliers, Statistics (Admin, desktop only). | NEXT (not done): empty "Low-stock events" chart shows a -1 to 1 axis, needs a minimum of 0 and an "No low-stock events yet" message (Agent E, stats.html); Materials table on a phone still scrolls sideways, so the buttons are off-screen (F-11), consider stacked cards under 720px; show the colour in material names on the list (two "PLA Basic" rows); move "Needs attention" higher on Home; Suppliers needs a search box and an ONLINE/LOCAL badge; Employee view, forms, Find supplier and Users pages were not reviewed. | NOTES: team members tried small local tweaks that are NOT in Git yet: OUT status pill as filled red with light text (needs a red outside the colour card, Agent H to confirm), the "Show only OK" filter button commented out in materials_list.html, and the order of "More" after Remove (CSS "order: 2" on ".row-more summary"). Commit them or drop them. The merged branch is main-0rpyg5-v2k49y; main-0rpyg5 has the "Last bought" fix only.

2026-11-26 | Agent H (done at the team's request, touching Agent C's routes_materials.py and tests/test_materials.py) | DONE: the Materials list is now sorted by urgency: OUT first, then LOW, then OK, with names A-Z inside each group (app/routes_materials.py, list_materials: two lines after the status is added; the status is worked out in Python, so the sort is too). New test test_materials_list_is_sorted_by_urgency in tests/test_materials.py: it adds materials so that A-Z order and urgency order differ, and checks the page lists them OUT, OUT, LOW, OK, OK (it fails without the sort, checked). Full suite: 386 pass, 2 skipped, 6 expected failures. | CORRECTION: the Home list (now called "Notifications") already shows OUT first, then LOW, names A-Z inside each group (app/alerts.py, get_materials_needing_attention; OK materials are not in that list), so it needed no change; the earlier note that it was not sorted was wrong. Filter and search still work on the sorted list (the sort runs before the filter).

2026-11-26 | Agent E (merge done at the team's request) | DONE: Agent H's work (branch main-0rpyg5-v2k49y on GitHub) is now
  merged into main-0rpyg5 together with the Statistics work, so one branch has both. What came in from Agent H: the
  Materials list shows ONE main button per row with Edit and Remove under "More" (materials_list.html, 2 lines in
  routes_materials.py), the Materials list is sorted OUT, LOW, OK (with a test in tests/test_materials.py), theme.css
  styles for them, and the Agent H status-log entries. The only text clash was this log (kept every entry from both
  sides). Checked in a browser (Admin): Materials page with the "More" menu and the Statistics page with all 8 charts
  together, no script errors, no sideways page scroll. Suite: 428 pass, 2 skipped, 6 expected failures. | NOT INCLUDED:
  anything Agent H has only on the team member's own computer. On 2026-11-26 their folder was on the branch
  main-0rpyg5-v2k49y in the middle of an unfinished merge, with 3 files edited but not saved to Git (routes_materials.py,
  theme.css, materials_list.html). Those edits are not on GitHub, so they are not here. Agent H: commit and push them (or
  send the diff) and they can be merged in the same way. | PROBLEMS: the unfinished merge in that folder is the OLD
  direction (main-0rpyg5 into main-0rpyg5-v2k49y); now that GitHub already has both merged, finish it with a normal
  commit, then pull, and expect only the status log to clash.

2026-11-26 | Agent E (brought in at the team's request from Agent H's unsaved edits) | DONE: the 3 unsaved edits found in the
  team member's own folder (diff pasted by them) are now in Git on main-0rpyg5. (1) Materials list sorted OUT, LOW, OK:
  already on the branch (same 2 lines), so nothing to add. (2) theme.css: the "More" menu word now comes after the
  buttons (order: 2). (3) theme.css: the OUT word is now a clear red with light text. THIS USES 2 COLOURS THAT ARE NOT
  IN THE 7-COLOUR PALETTE (#C62828 and #FFF4F0); I put them in the :root list as --out-red and --out-text (the file says
  every colour lives there). Earlier the team said "do not change the palette" for the restyle, so please confirm
  this red is wanted; reverting is one line (use hot orange again). (4) materials_list.html: the "Show only OK"
  button is hidden (a Jinja comment; the address ?status=OK still works). Checked in a browser: the OUT red, the
  hidden button and the "More" menu look right. Suite: 428 pass, 2 skipped, 6 expected failures. | NEXT: Agent H should
  work on the branch main-0rpyg5 from now on (not main-0rpyg5-v2k49y), or the two branches drift apart again. | PROBLEMS:
  Section 8 of the guide says "red = OUT"; the red now matches it, while the palette note in the theme file says 7
  colours: team to decide which wins.

2026-11-26 | Team decision + work (done by Agent E at the team's request; touches Agent F's tests) | REMOVED from the
  Statistics page, as chosen by the team member: (1) "Low-stock events per month" (line chart), (2) "Spending per
  supplier this month", (3) "Spending per material". Guide F7 and Section 15 (the line "Admin account: sees prices and
  the spending chart" now says the price comparison charts) were changed FIRST. WHAT WAS REMOVED: the three panels and
  their script in stats.html, the three data addresses (/stats/data/low-stock, /stats/data/spending,
  /stats/data/spending-by-material; they now answer 404 for everybody), the LOW_EVENTS_METHOD_CONFIRMED flag, the two
  unused functions count_low_stock_events and get_low_stock_chart, and the template flags spending_ready and
  low_events_ready. WHAT WAS KEPT ON PURPOSE (not asked for): the Home box "money spent this month" (and the functions
  behind it), the CSV download with its spending rows (Admin only), and the saving of low-stock events when someone
  records stock used (the table low_stock_events and the activity-log line stay; the events are just not charted).
  Remaining Statistics page: usage, purchases, average delivery time (both roles) and the supplier price comparison
  charts and table (Admin only), plus the CSV button (Admin only). TESTS: tests of the removed charts deleted or
  rewritten (tests/test_stats_dashboard.py; in Agent F's tests/test_review_agent_f.py: 3 address-matrix rows, 3 tests
  and the checklist test now check the price comparison instead); new tests prove the 3 addresses are 404 and the
  3 charts are not on the page for either role. ROLE_DIFFERENCES.md and its test lost the 3 rows and gained a
  decision line. Checked in a browser (Admin: 5 charts and the table; Employee: 3 charts; no script errors). Suite:
  420 pass, 2 skipped, 6 expected failures. | AGENT G (R3): README.md, GLOSSARY.md and PRESENTATION_NOTES.md may still
  mention the low-stock events chart and the spending charts; please remove them. If the team also wants the spending
  rows out of the CSV, or the low-stock event saving removed, say so. | PROBLEMS: none known.

2026-11-26 | Agent E (team decision: the table repeated the charts) | DONE: removed "The same numbers as a table" from the
  Supplier price comparison. Guide F7 changed FIRST. Removed: the table in stats.html (the estimates note stays under
  the two charts) and an unused style line; in routes_stats.py the table code (build_comparison_row,
  get_price_comparison and the comparison_rows value sent to the page). The two price charts, their data address
  (/stats/data/price-comparison, Admin only) and the pop-ups (supplier and date) are unchanged. NOTE: the words
  "Paid 25% more than the cheapest offer" lived only in the table, so they are gone; the charts show the two prices
  and the pop-up gives the supplier and date. (If the team wants the percentage back, it can go into the pop-up.)
  TESTS: the table test became a chart test (the price last paid comes from the NEWEST purchase); the role record
  (ROLE_DIFFERENCES.md and test_role_differences.py) lost the table row; TESTS.md updated. Checked in a browser: no
  table, 5 charts for Admin, no script errors. | AGENT G (R3): if the notes or README mention the comparison table,
  please remove that. | PROBLEMS: none known.

2026-11-26 | Agent E (team decision, requested by the team member) | DONE: "Average delivery time per supplier" (a bar chart) is
  replaced by a DELIVERY RANKING. Guide F7 changed FIRST (and its CSV line). HOW IT WORKS: on the Statistics page the
  user picks a material from a list ("All materials (average)" first, then every material that an active supplier
  sells); the suppliers are listed fastest first with a rank number, the name, ONLINE or LOCAL, the days, and an
  estimated arrival date (today in Malaysia time + the days, rounded up). The fastest get a "Fastest" word. Suppliers
  with the same days share a rank (1, 1, 3) and are ordered A to Z. For one material it uses each supplier's FASTEST
  active offer; for "All materials" it uses the average over everything the supplier sells (what the old chart
  showed). Switched-off offers and suppliers are left out. NO MONEY in it, so Admin and Employee both see it (tests
  prove the data has no price words). Code: get_ranking_materials, build_ranking_rows, get_delivery_ranking and the
  address /stats/data/delivery-ranking?material=... in routes_stats.py; stats.html (select box, list built with plain
  text, small layout styles using the theme's colour variables, no new colours). REMOVED: the chart, its address
  /stats/data/lead-times (now 404), the lead-chart script. KEPT: get_average_lead_times, which the CSV still uses
  ("Average delivery time" rows). Agent F's address matrix and 2 tests point to the new address (a test on a missing
  address would have passed for the wrong reason); ROLE_DIFFERENCES.md and its test have the new row; TESTS.md updated.
  Checked in a browser as Employee: the list, the choice of a material, ties, phone width 390 (no sideways scroll), no
  "MYR" in the page, no script errors. Also fixed "1 days" to "1 day". Suite: 428 pass, 2 skipped, 6 expected failures.
  | AGENT G (R3): README, GLOSSARY and PRESENTATION_NOTES may still say "average delivery time chart". | NOTE: the
  sample data has one supplier for most materials, so most rankings show one line until offers from more suppliers are
  added (Suppliers > Add material this supplier sells). F-13 (the old chart was cut off on a phone) is now moot,
  because that chart no longer exists. | PROBLEMS: none known.

2026-11-26 | Agent E (team request) | DONE: a SIDEBAR on the Statistics page, so nobody scrolls down to find a chart. Guide F7 changed
  FIRST. HOW IT WORKS: a menu on the left lists the statistics (Usage per material, Purchases per material, Delivery
  ranking and, for the Admin only, Supplier price comparison and "Download spreadsheet (CSV)"). Clicking an item shows
  ONLY that statistic and hides the others; the chosen item is marked (orange, aria-current). The address keeps the
  choice (/stats/#purchases), so a refresh, a bookmark or a shared link opens the same one; an unknown name shows the
  first. The menu stays in view while scrolling (sticky). On a phone (720 px or narrower) it becomes a row of buttons
  across the top that scrolls sideways inside itself (the page does not). Every item is at least 44 px tall (Section 8).
  Files: app/templates/stats.html only (layout styles use the theme's colour variables, no new colours; panels got ids,
  only the first is visible at the start; the old CSV button at the bottom moved into the sidebar; a short script
  showStatistic/showStatisticFromAddress; charts measure themselves again when their panel is shown, because Chart.js
  cannot size a chart inside a hidden panel). ROLES: an Employee's page has no price item, no price panel, no download
  link, no "MYR" and the script does not even know "price" (typing /stats/#price shows the first statistic); tests
  prove it. Checked in a browser: Admin and Employee, every item, deep link, reload, bad name, phone width 390 (no
  sideways page scroll), all charts correctly sized after switching, no script errors. 4 new tests; ROLE_DIFFERENCES.md
  and TESTS.md mention the sidebar. | NOTE: the page now needs its script to show anything past the first statistic;
  it needed Chart.js (from the internet) for the charts anyway. | AGENT G (R3): mention the sidebar in the notes if
  wanted. | PROBLEMS: none known. On a phone the usage chart's long legend still takes a lot of height (older issue, not
  caused by the sidebar).

2026-11-26 | Agent E (team decision: "it is not relevant any more"; touches Agent H's theme.css and Agent F's tests) | DONE: the
  Home box "Estimated money spent this month" is REMOVED. Guide F2 changed FIRST (now three boxes). WHAT CHANGED:
  home.html (the box and its text), routes_stats.py (show_dashboard no longer works out any money; the function
  format_money and the can_see_prices import, which nothing else used, are gone), theme.css (the light/dark pattern of
  the boxes is now light, dark, light: "odd boxes light" instead of "boxes 1 and 4"), the boxes are now one row of
  three on a screen wider than 640 px and one column below that. TESTS: the 3 tests of the money box became one
  test that proves Home has exactly three boxes and no money box and no "MYR" for either role; the format_money test
  and the "real money on Home" test were deleted; in Agent F's file one test lost its Home line (it still proves
  Employees see supplier prices and shipping). ROLE_DIFFERENCES.md and its test lost the money-box row ("three number
  boxes" now) and gained a decision line; TESTS.md updated. Checked in a browser: Admin, Employee and phone width 390
  (3 boxes, no "MYR" on Home, no sideways scroll, no script errors). | KEPT (not asked for): the money functions behind
  the CSV (get_month_spending, get_spending_by_supplier, SPENDING_METHOD_CONFIRMED), because the Admin CSV still
  has "Spending this month" and "Spending per material" rows; the "Last bought" money on Materials; supplier prices.
  | PROBLEMS / TEAM TO DECIDE: (1) Section 1 of the guide still says the statistics show "how much is spent"; after the
  team's removals that is only in the CSV and the price comparison, so the sentence may need rewording. (2) Section 4
  still says Employees see "money totals"; that now only means supplier prices, shipping and the "Last bought" total.
  (3) If the CSV spending rows should go too, say so. | AGENT G (R3): README, GLOSSARY and PRESENTATION_NOTES may still
  describe the money box on Home.

2026-11-26 | Agent E (team asked for this wording) | DONE: the two guide sentences that the team's removals made out of date were
  reworded (the guide, so nobody has to ask; no code changed). SECTION 1, item 5: was "Shows simple statistics (charts
  and numbers) so the boss can see what is used, what is running low, and how much is spent." Now: "Shows simple
  statistics (charts and a ranking) so the boss can see what is used, what is bought, which supplier delivers
  fastest, and how supplier prices compare." (What is running low is shown by the Home Notifications, item 3.)
  SECTION 4, Employee "Can": was "SEE supplier prices, shipping costs and money totals". Now: "SEE supplier prices,
  shipping costs and the total paid on the 'Last bought' note (team decision 2026-11-24; the Home 'money spent' box
  was removed on 2026-11-26)." SECTION 4, Sensitive data: was "Supplier prices and cost totals". Now: "Supplier prices,
  shipping costs and the 'Last bought' total paid ... The price comparison charts and the CSV download stay Admin
  only." Older log entries that say "money totals" (and the dated decision line in ROLE_DIFFERENCES.md) are history and were not changed. | AGENT G (R3): PRESENTATION_NOTES.md (about line 200) still says Employees see "money totals"; please use the new wording. | None.


2026-11-26 | Main Chat (team decision after the real user test with Ryan, done at the team's request across
  Agent C, E, H and F files) | USER TEST: Ryan from Stinablis (Jacob was not available) tested the app
  with a timer. Result: 7:16 baseline time; he got stuck on steps 1 and 2. His words: "Will use but need
  improvements. (Don't want confusing) As long can key in one data, its good." DECISION: fix the four
  highest-impact points. (1) A fast search box at the top of Materials. (2) Menu "Statistics" is now
  "Stock"; Home shows Current stock next to the quick-action shortcuts; the "Show only OK" button is
  removed. (3) Lists show OK first, then LOW, then OUT; the OUT badge is softened; "Needs attention" is
  now "Noti". (4) The low-stock events chart and the average delivery time chart are replaced by a
  Current stock chart with a unit choice (g, ml, pieces) and a Supplier speed ranking list (this also
  closes phone finding F-13). Sections 5 (F2, F3, F7) and 8 updated FIRST. All permission rules are
  unchanged (can_see_prices, can_manage_*, admin_required, CSV and spending still Admin only; no new
  money anywhere). No table was changed. | Then: app/alerts.py (list order), routes_materials.py and
  materials_list.html (search first, order, no Show OK), routes_stats.py + stats.html + home.html (Stock
  page, Current stock, speed ranking), base.html and theme.css (menu word, softer OUT), tests, README and
  PRESENTATION_NOTES. | CROSS-AGENT REQUESTS (R3, edits made at the team's request, please review): AGENT C
  (alerts.py, routes_materials.py, materials_list.html), AGENT E (routes_stats.py, home.html, stats.html),
  AGENT H (base.html menu word, theme.css OUT badge), AGENT F (menu word, matrix and new tests). The data
  addresses /stats/data/low-stock and /stats/data/lead-times still answer (their tests still pass) but no
  page draws them any more; the team may remove them later. | Ryan's quote is kept word for word in
  README.md and PRESENTATION_NOTES.md. CLAUDE.md.txt was NOT touched.

2026-11-26 | Main Chat (documentation only; no code changed) | VERIFIED DETAILS OF RYAN'S TEST, replacing the
  earlier note that the steps were not recorded. PRE-TEST BASELINE (Ryan, pre-test interview): Stinablis
  spends about 2 to 3 hours per week checking Shopee purchase history, local shop memory, a collaborator list
  and past receipts to find where materials were bought. TEST 1 (total time 7:16): (1) find where we bought
  standard resin; (2) find which supplier is cheapest for nuts; (3) add a new purchase. Ryan got stuck on
  Tasks 1 and 2 because the Materials list had no search bar and going between stock and supplier
  information was not direct. That is why the instant search bar on Materials and Current stock with quick
  actions on Home were added. His words: "Will use but need improvements. (Don't want confusing) As long can
  key in one data, its good." README.md and PRESENTATION_NOTES.md now carry these facts (the "ask the team
  which steps" note is gone; the "about 2 hours a week" figure is now a confirmed starting point, while the
  "30 minutes a week" target is still only a goal). | NEXT: run TEST 2 (PLA Orange, PETG Gray, add a new
  purchase) and write the time next to 7:16. Test 2 has NOT been timed or completed, so no faster post-fix
  time may be claimed. The sample data has no "PLA Orange" or "PETG Gray" (only PLA Basic White and Black and
  PETG Clear): add them first or test on the real data. | OPEN GAP (R4, team decision needed, nothing
  changed): the "Find supplier" page (/suggest/<id>) only lists ranked suppliers when the material is LOW or
  OUT, so for an OK item such as the nuts in the sample data Task 2 is still not a one-step job, and the
  Materials list has no "Find supplier" button. Should the comparison work for every item? Agent D owns the
  page and Agent C the Materials list. | CLAUDE.md.txt was NOT touched.

2026-11-26 | Add material with its supplier (Agent C's screen; built at the team's request, with a small
  refactor in Agent D's routes_suppliers.py) | The Admin-only "Add material" form now has an optional
  "Who sells it?" part: choose "No supplier for now" (default), an existing active supplier, or "A new
  supplier..." (name, ONLINE/LOCAL, address, phone, email, website, notes). When a supplier is chosen the
  Admin also fills in what they charge: pack size, price per pack (MYR), smallest order, shipping (MYR) and
  delivery days. The offer takes the material's unit. Material, supplier and offer are saved together (all
  or nothing) and the activity log gets MATERIAL_ADDED, SUPPLIER_ADDED and OFFER_ADDED lines. A supplier
  name that already exists is refused ("choose it from the list instead"). Employees still get 403 on the
  whole form. Reused code instead of copying it: routes_suppliers.py now has read_offer_numbers,
  insert_supplier and insert_offer, and its own "Add supplier" / "Add offer" screens use them (behaviour
  unchanged; its 29 tests pass). 16 new tests in tests/test_materials.py; all 162 tests pass. Checked in a
  phone-sized browser with the dark theme and CSRF switched on. | Agent F: add the form to the manual
  checks in TESTS.md. Agent D: please read the small change in routes_suppliers.py. Team: "Edit material"
  does not show suppliers (use the Suppliers page). | The Edit material form was not changed.

2026-11-26 | Merge of main-0rpyg5 into main-iyvssn (done at the team's request) | The team's desktop was on
  branch main-0rpyg5 (about 50 commits: Statistics changes, Agent H's Materials changes, "Record received"
  supplier and cost, low-stock events, review tests), which did not have the "Who sells it?" part of
  Add material. Merged main-0rpyg5 into main-iyvssn so both are in one place. Three conflicts, all
  additive, kept both sides: the import lines in app/routes_materials.py, the two blocks of tests in
  tests/test_materials.py, and this STATUS LOG. One real clash after the merge: both sides had a function
  called get_active_suppliers (mine took no argument, theirs takes the database). Removed mine and the Add
  material form now uses theirs. All 448 tests pass (2 skipped and 6 expected failures were already marked
  on main-0rpyg5). Tried in a browser with CSRF on: add a material with a new supplier, then Home,
  Materials, Suppliers, Statistics and Users all open. | Team: use branch main-iyvssn from now on (git
  checkout main-iyvssn, git pull), or merge it into main-0rpyg5 so there is only one line of work.
  | Anyone still committing to main-0rpyg5 will need to merge main-iyvssn.

2026-11-26 | Main Chat (merge of origin/main-iyvssn commit b51993b into main, at the team's request) | CHECKED
  before merging: the "Add material with its supplier" change keeps the Admin-only rule (add_material is still
  admin_required; Employees get 403), changes no table, schema.sql, sample data or permissions.py, and does not
  touch CLAUDE.md.txt. Its small refactor in routes_suppliers.py (read_offer_numbers, insert_supplier,
  insert_offer) keeps the Suppliers screens behaving the same. FIXED while merging: (1) the branch was built on an
  older main and defined a second get_active_suppliers() in routes_materials.py with no argument, which would have
  silently replaced main's get_active_suppliers(database) and crashed the Add material form; the extra one was
  removed and the form now calls main's. (2) The imports, the new tests (both sides kept) and this log (both sides
  kept) were merged by hand. Full suite: 421 passed, 2 skipped, 6 expected failures. | Agent F: add the form
  to the manual checks (the branch entry above already asks). Agent D: please read the small change in
  routes_suppliers.py. | The Edit material form still shows no supplier part. CLAUDE.md.txt was NOT touched.

2026-11-26 | Merge of main into main-iyvssn (done at the team's request; the team chose the designs below) |
  main and main-0rpyg5 had both redesigned Home and Statistics in different ways (main: Ryan's test fixes;
  main-0rpyg5: Notifications, procurement charts, delivery ranking, sidebar). Nine files conflicted. THE
  TEAM DECIDED: (1) Home: keep main-0rpyg5's ("Notifications" list; no Current stock list). (2) Statistics:
  keep main-0rpyg5's page and its menu word "Statistics" (usage, purchases, delivery ranking, price
  comparison, sidebar); main's "Stock" page, its unit choice chart and the "Supplier speed ranking" are NOT
  in this build. (3) OUT label: keep the solid red one (not the soft dashed one). TAKEN FROM main (no
  conflict with those choices): the fast search box first on Materials and live filtering, "Show only OK"
  removed, Materials list order OK first then LOW then OUT (Ryan's test; I chose this, the team can flip it
  in app/alerts.py sort_ok_low_out), error page and the other small changes, and Ryan's test notes in this
  log. Guide: F2, F7 and the OUT colour line in Section 8 kept as on main-0rpyg5; F3 (search, order, Add
  material "Who sells it?") taken from main. README.md, GLOSSARY.md, PRESENTATION_NOTES.md and TESTS.md
  kept as on main-0rpyg5 because main's versions described the pages not taken. Tests: removed the 11
  checks in tests/test_ryan_feedback.py that tested the Stock page, Current stock, "Noti", the menu word
  "Stock" and the soft OUT badge (those features are not in this build); the search, OK-first Materials
  order, hidden "Show only OK" and status-word checks stay. Restored the older menu and Home tests, and
  updated the Materials order test to OK first. All 454 tests pass (2 skipped and 6 expected failures were
  already marked). | Agent G: add Ryan's user-test facts (baseline 2 to 3 hours a week, Test 1 took 7:16, his
  quote; see the two Main Chat entries above) back into README.md and PRESENTATION_NOTES.md, which were
  kept at the main-0rpyg5 versions. The data addresses of main's Stock page are not present. | The two
  Main Chat entries above still describe main's Stock page, Noti and soft OUT; this entry overrides them.

2026-11-26 | Main Chat (group decisions after the 9bade66 merge; done at the team's request) | The group
  confirmed four points for main, starting from origin/main 9bade66. (1) Menu and page name stay
  "Statistics", and the 9bade66 Statistics page stays (delivery ranking per chosen material, no price
  table). So the earlier Main Chat decision to rename it "Stock", the Current stock chart with a unit choice
  and the Supplier speed ranking list (F7 text and status-log entry of 2026-11-26 above) are NOT part of
  main any more. (2) The simpler Home page, the "Notifications" label (not "Noti") and the red OUT badge from
  9bade66 stay; the calm dashed OUT badge and the Home "Current stock" list are NOT part of main. (3)
  origin/add-shopguard-materials is merged: 26 new sample materials (M014 to M039, including PLA+ Orange and
  PETG Grey) and a Materials list in two sections, "Filament & other materials" and "Hardware" (unit pcs).
  The OK first, then LOW, then OUT order now applies inside each section, and the test that checks it was
  changed to check each section. (4) README.md and PRESENTATION_NOTES.md get Ryan's test facts back (see
  the 2026-11-26 entry "VERIFIED DETAILS OF RYAN'S TEST"), written for the screens that really exist on
  main. Ryan's fixes that stay on main: search box first on Materials, OK/LOW/OUT order, "Show only OK"
  hidden. Ryan's fixes that were replaced by the group's own design: "Stock" menu word, Home Current stock,
  "Noti", calm OUT badge, Current stock chart and Supplier speed ranking. Permissions, tables and
  CLAUDE.md.txt were not touched. | OPEN GAP (R4, still undecided): the "Find supplier" page only lists
  suppliers for LOW or OUT items, so Ryan's Task 2 (cheapest supplier for nuts) is still not one step for an
  OK item, and the new sample items have no supplier offers. | Test 2 has NOT been timed or completed.

2026-11-26 | Agent E (landing the leftovers of pull request #2, at the team's request) | DONE: PR #2 was merged by the team
  member at 15:54, but two commits pushed to main-0rpyg5 afterwards did not go with it: (1) the removal of the Home box
  "Estimated money spent this month" (three boxes now) and (2) the guide rewording in Sections 1 and 4. I merged
  origin/main into main-0rpyg5 (it had moved on: search-first Materials list, optional supplier and offer details on the
  Add material form, Ryan's pre-test feedback work and tests). Only this status log clashed (kept every entry from both
  sides); every file merged without edits. The Home box is still gone and the three-box light/dark pattern is still in
  theme.css. Suite on the combined code: 450 pass, 2 skipped, 6 expected failures. A new pull request carries these
  commits into main. | NONE. | None.

2026-11-26 | Agent E (team request; touches Agent H's theme.css) | DONE: the OUT word on the Home box is now the SAME red as the OUT
  tag on the Materials page (filled red --out-red, light text --out-text, solid border). Before, a later change had
  made it a dashed neutral outline ("calm, not an alarm"), which also became invisible on a light card (light text on a
  light box). Only CSS: app/static/theme.css line for ".tile.out .word", plus the stale comment on --hot-orange (it
  said OUT is neutral). The colours are the two extra ones already in the :root list (#C62828 and #FFF4F0, not part of
  the 7-colour palette; confirmed wanted by this request). Checked in a browser: the Home OUT word and the Materials OUT
  tag have identical computed colours, and the word reads well on a light box and on a dark box. | NOTE FOR TEAM:
  the team member is trying different colours for the 1st and 3rd Home boxes locally (previews A to D were sent);
  that choice is NOT in Git yet. | NONE. | None.

2026-11-26 | Agent E (team request; touches Agent H's theme.css) | DONE: the words LOW and OUT on the Home boxes are now bold
  (font-weight 700 on ".tile .word" in app/static/theme.css, one word added to one line). The same words on the Materials
  page tags (OK, LOW, OUT) were already bold, so nothing changed there. Checked in a browser: computed weight is 700 for
  the Home LOW and OUT and for the Materials OK, LOW and OUT tags. Only CSS, no page or test changed. | NONE. | None.

2026-11-26 | Agent E (team request; touches Agent H's shared look only by reusing its existing tag classes) | DONE: on Home, each
  Notifications line now shows its status as the SAME coloured box as the Materials page (LOW orange, OUT red; classes
  "tag tag-LOW" / "tag tag-OUT" from theme.css), placed just LEFT of the "Find supplier" button (readability). The old plain
  bold "- LOW:" word in the sentence is gone. Guide F2 changed FIRST. Files: app/templates/home.html (one small wrapper
  ".row-end", one style line), tests/test_stats_dashboard.py (1 new test: box comes before the button, OUT before LOW, same for
  Admin and Employee, no MYR). Order, button links, empty text and permissions unchanged. Checked in a browser as Admin,
  Employee and phone width 390: no sideways scroll, no "MYR", boxes look the same as on Materials. | NEXT: none. If the team
  wants the box at the far LEFT of each line instead, it is a small move in home.html. | None.

2026-11-26 | Agent E (team choice, option D; touches Agent H's theme.css) | DONE: Home boxes 1 and 3 (the "light" ones) are now deep moss
  (#4F5A3C) with light text, so the text stands out; box 2 stays dark. Only CSS: app/static/theme.css (new variable --deep-moss in the
  :root list, and the ".tile:nth-child(odd)" rule). THIS IS A COLOUR OUTSIDE THE 7-COLOUR PALETTE (like --out-red); the team picked it
  from options A to D, so it counts as confirmed. LOW and OUT words keep their own colours. | Agent H: please keep it. Team: anyone with
  a local edit to theme.css should drop it (git stash drop) to avoid a conflict. | None.

2026-11-26 | Agent E (team request after the phone test; touches Agent H's theme.css) | DONE: the Materials page now FITS a phone screen
  (F-11 for this page). CAUSE: on a phone each material is already a card (Agent C's 640 px layout), but theme.css still forced every
  table to be at least 880 px wide ("body table { min-width: 880px }") and the Materials columns had their own minimums (200, 300 and
  380 px), so each card was wider than the screen and the right side ("More", the end of the "Not bought through this app yet" note)
  was cut off. FIX: a new block at the end of app/static/theme.css, only for screens 640 px or narrower: the table and its cells get no
  minimum width and long words may wrap. Desktop and tablet are unchanged. Guide: no change (Section 8 already says mobile-friendly).
  Checked in a browser at width 390 (Admin): the page and the card box do not scroll sideways, "Record used", "Record received" and
  "More" are all visible ("More" wraps under the buttons). | NOT DONE: the Suppliers and Supplier detail pages still use the wide-table
  layout on a phone (F-11 there; Agent D owns suppliers.html and supplier_detail.html); phone numbers are still not tappable (F-12,
  Agent D). | None.

2026-11-26 | Agent E (team request; touches Agent D's suppliers.html, supplier_detail.html and suggest.html, and Agent H's theme.css) | DONE: the
  supplier pages now FIT a phone screen (F-11 for these pages), the same way as Materials. THREE TABLES changed: the Suppliers list, "Materials
  this supplier sells" on a supplier page, and the Find supplier table (suggest.html, which the Home Notifications buttons open). Markup only: the
  table box got the class "cards", the header row the class "head", and every cell a data-label (Name, Type, Phone ...). On a screen 640 px or
  narrower each row becomes a small card ("Name: ...", "Phone: ...") and the header row is hidden; on a bigger screen nothing changes. The CSS is
  one shared block at the end of app/static/theme.css (".cards"). No link, form, csrf_token or permission check was touched: the Change / Switch
  off buttons still show only under can_manage, the money cells only under show_prices (Rule C7). Checked in a browser at width 390 as Admin and
  Employee on all three pages: no sideways scroll for the page or the table box, labels read well. Full suite passes. | NOT DONE: phone numbers and
  emails are still plain text, not tappable (F-12, Agent D). The Find supplier page says "1 days" for a one-day lead time (small wording bug, Agent D).
  | None.

2026-11-26 | Agent E (team request after the phone test) | DONE: on the Statistics page the colour key of the "Usage per material" and "Purchases per
  material" charts no longer eats into the chart. CAUSE: Chart.js drew the key INSIDE the chart box (300 px tall); on a phone, with up to 8 materials,
  the key took most of that height, squeezed the plot and ran into the Y axis. FIX (app/templates/stats.html only): the built-in key is switched
  off for these two charts, and the same key is written as a plain list UNDER the chart: a colour square and the material name with its unit,
  for example "ABS Grey (g)" (words still never rely on colour alone). The chart now keeps its full height, the Y axis is clear, and the list wraps
  to as many lines as needed. Same on desktop (the key moved from above the chart to below it). Pop-ups, axis titles, data and permissions are
  unchanged; both roles see these two charts. Checked in a browser at width 390 (Employee) and 1100 (Admin): no sideways page scroll, no script
  errors, key lists match the materials. Full suite passes. | NOT DONE: the price comparison charts (Admin only) have their own legend; not touched
  because the team did not report a problem there. | None.

2026-11-26 | Agent D (suppliers & suggestion) | DONE: wording fix on the Find supplier page. A lead time of 1 now reads
  "1 day" (any other number reads "N days"), and the sentence "No supplier can deliver ... within N days" follows the same
  rule. Only app/templates/suggest.html changed (two lines, wording only, no permission logic, Rule C7). supplier_detail.html
  was left alone: its column header already says "(days)". 1 new test in tests/test_suppliers_suggest.py (1 day, 7 days, and
  the "within 1 day" / "within 0 days" sentence). | None. | None.

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
  5. Shows simple statistics (charts and numbers) so the boss can see
     what is used, what is running low, and how much is spent.
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
  Cannot:
  - See or change supplier prices (costs).
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
- Supplier prices and cost totals.
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
    - Four big boxes at the top:
        * Total number of materials
        * Number of materials LOW on stock (shown in red)
        * Number of materials OUT of stock (shown in dark red)
        * Estimated money spent this month (Admin only)
    - A "Needs attention" list: the low and out-of-stock materials, with
      a button to see the suggested supplier.

F3. MATERIALS SCREEN
    - A table of all materials: name, type (for example PLA, PETG, resin),
      colour, quantity left, unit (grams, millilitres, pieces), and
      status (OK / LOW / OUT).
    - Search box and filter buttons (for example "show only LOW").
    - Add / edit / delete a material: ADMIN only.
    - "Record used" and "Record received" buttons: everyone.

F4. SUPPLIERS SCREEN (ADMIN can change; EMPLOYEE can only view)
    - One row per supplier: name, type (ONLINE or LOCAL), address,
      phone, email, website, and notes.
    - Each supplier has a list of materials they sell, with:
        * Price per unit (Admin only)
        * Minimum order quantity
        * Lead time in days (how long from ordering to arriving)
        * Shipping cost (Admin only)

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
    - Admin sees cost. Employee sees supplier name, lead time, arrival
      date, and contact details, but not prices.

F7. STATISTICS SCREEN (ADMIN sees everything; EMPLOYEE sees usage only)
    - Usage per material per week or per month (bar chart).
    - Number of low-stock events per month (line chart).
    - Spending per supplier (pie or bar chart) - ADMIN only.
    - Average lead time per supplier.
    - Export to spreadsheet (CSV) - ADMIN only.

F8. USER MANAGEMENT (ADMIN only)
    - Add user, change role, reset password, disable account.
    - Never delete a user who has records; disable them instead.

F9. ACTIVITY LOG (ADMIN only)
    - Every change is written down: who, what, when. Example:
      "Ali changed price of PLA from RM 80 to RM 85, 19 Nov 2026 20:40".
    - Nobody can edit or delete this log.

Currency: Malaysian Ringgit (RM). [CONFIRM] Use RM everywhere.


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

ORDER OF WORK
  1. Database (A)  ->  2. Login and roles (B)  ->  3. Materials (C) and
  Suppliers (D) in parallel  ->  4. Statistics (E)  ->  5. Testing (F)
  ->  6. Documentation (G).
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
  2. The three user roles and what each can do.
  3. One feature end-to-end: for example, "what happens when someone
     clicks Record used?" (Screen -> Server checks permission -> Stock
     number goes down -> Row is written to the history -> If low, the
     Home screen shows the warning.)
  4. How the best supplier is picked (Section 7 example).
  5. How we stopped employees from seeing prices (permissions.py).
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
[ ] Employee cannot see any price in any response (check the page source).
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
[ ] Employee account: cannot see prices, cannot add a supplier.
[ ] Admin account: sees prices and the spending chart.
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

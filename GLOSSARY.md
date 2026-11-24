# Glossary: what the technical words mean

Plain-language meanings of the words used in our code and guide. Each entry says what the word
means and, where it helps, **where we use it**. If you meet a word that is not here, add it
(or ask Agent G).

Contents: [The big picture](#the-big-picture) · [Database](#database) · [Web and Flask](#web-and-flask) ·
[Login and security](#login-and-security) · [Web status numbers](#web-status-numbers-403-and-friends) ·
[Pages and charts](#pages-and-charts) · [Dates and money](#dates-and-money) ·
[Our own words](#our-own-words-business-rules) · [Testing](#testing) · [Tools, Git and licenses](#tools-git-and-licenses)

---

## The big picture

- **Web application:** a program you use in a web browser instead of installing it. Ours is a
  website that only logged-in staff can use.
- **Server:** the computer that runs the application and checks the rules. Everything important
  (who may do what) is decided here, never only on the screen.
- **Client / browser:** the program on your phone or computer (Chrome, Edge...) that shows the pages
  the server sends.
- **Request and response:** your browser *asks* for a page (request); the server *answers* with the
  page (response).
- **Python:** the programming language we write in. Chosen because it is easy to read.
- **Library (or package):** code written by other people that we install and use, so we do not
  rewrite it. Ours: Flask, pytest. **Dependency** means a library our project needs.
- **Function:** a small named piece of code that does one job, for example `get_status(...)`. Our
  rule (C3): every function has a one-line comment above it saying what it does.
- **Constant:** a fixed value written in CAPITAL LETTERS, for example `MAX_WRONG_PASSWORDS = 5`.
- **Dictionary:** a list of labelled values, for example `{"status": "LOW", "name": "PLA"}`.
- **Open source:** software whose code is public and free to read and often to reuse, under a
  *license* (see [License](#tools-git-and-licenses)).
- **PRD (Product Requirements Document):** the document that says what we are building and why.
  Ours is `CLAUDE.md`.
- **Agent (A to H):** one team member or AI helper that owns certain files (guide Section 11).

## Database

- **Database:** a set of linked spreadsheets stored in one file. Ours is `data/tracker.db`.
- **SQLite:** the kind of database we use. It is a single file, so there is no database server to
  install and a backup is just a file copy.
- **Table:** one spreadsheet inside the database, for example `materials`. **Row** = one line
  (one material). **Column** = one heading (for example `reorder_level`).
- **Schema:** the plan that says which tables and columns exist. It lives in `app/schema.sql`.
- **SQL:** the language used to talk to the database ("get all materials", "change this quantity").
  You see it in the code as text such as `SELECT * FROM materials`.
- **Query:** one question or instruction sent to the database.
- **Placeholder (`?`):** in our SQL, a `?` marks a spot where a value is filled in safely. This stops
  **SQL injection**, an attack where someone types SQL code into a form box to trick the database.
  We never glue what a person typed into the SQL text.
- **Primary key (`id`):** the unique label of a row, for example `M001` for one material.
- **Foreign key (`REFERENCES`):** a link from one table to another, for example an offer points to
  a supplier and a material. The database refuses a link to something that does not exist
  (`PRAGMA foreign_keys = ON` switches this check on).
- **CHECK rule:** a rule the database enforces itself, for example the unit must be `g`, `ml` or
  `pcs`, and quantity can never be below zero.
- **Commit and rollback:** *commit* = save the changes for good; *rollback* = undo everything since
  the last commit. When recording stock fails halfway, we roll back so nothing is half-saved.
- **`quantity_on_hand`:** the number of grams, millilitres or pieces we have now.
- **Stock movement (`stock_movements` table):** one history row for every change to stock:
  `USED`, `RECEIVED` or `ADJUSTED` (the starting stock of a new material). These rows are only
  added, never edited.
- **Activity log (`activity_log` table):** the "who did what, and when" record (F9). Rows are only
  added, never edited or deleted. Login, lock, price changes and stock changes all write to it.
- **Switched off / `is_active`:** we never delete a material, supplier or user that has history
  (rule C9). We set `is_active = 0` ("switched off") so it disappears from the lists but its history
  stays. Programmers call this a *soft delete*.
- **Sample data:** invented data in `sample_data/` used to try the app. It is **not** real
  Stinablis data and every supplier name starts with "SAMPLE".
- **CSV (comma-separated values):** a plain text file that a spreadsheet program such as Excel can
  open. The Admin's statistics download is a CSV.
- **UUID:** a long random code used so every new row gets an id that no other row has.

## Web and Flask

- **Flask:** the small library (a *web framework*) that lets Python answer web requests. It is
  the heart of the app.
- **Route (or address / URL path):** a web address that the app answers, for example
  `/materials/` or `/suggest/M001`. In the code a route is written as `@something.route("/...")`.
- **Blueprint:** a bundle of related routes kept in one file so the app stays tidy. We have one for
  login (`auth_blueprint`), materials, suppliers and statistics. `app/__init__.py` plugs them all in.
- **`create_app`:** the function in `app/__init__.py` that builds the whole web application and
  plugs in the blueprints.
- **View function / page function:** the Python function that runs when someone opens a route and
  returns the page.
- **GET and POST:** the two kinds of request. **GET** = "show me this page" (safe, changes nothing).
  **POST** = "here is a form, please act on it" (can change data). Everything that changes data in our
  app is a POST; this is why logging out is POST only.
- **Form:** the boxes and button on a page. What the person typed arrives at the server as a POST.
- **Redirect (status `302`):** the server answers "go to that other page instead". For example,
  after a good login you are redirected to Home.
- **Template (Jinja):** an HTML page with blanks that Python fills in (names, numbers, the user).
  Templates live in `app/templates/`. **Jinja** is the system that fills them in. `base.html` is the
  frame (top bar and menu) shared by the other pages.
- **Flash message:** the short one-time message at the top of a page, such as "Added PLA".
- **Request / `g` / context processor:** Flask helpers. `g` holds things for one request only (the
  open database, the current user). The context processor makes `current_user` available inside
  every page.
- **Environment variable:** a setting that lives outside the code, in your terminal window. We use
  one: `STINABLIS_SECRET_KEY`. This keeps secrets out of Git (rule C6).
- **Decorator (`@login_required`, `@admin_required`):** a line written above a function that adds a
  check *before* the function runs. It is how every page asks `permissions.py` "may this person
  in?".
- **API (and endpoint):** a set of web addresses that programs (not people) use to ask the server
  for data. Our statistics charts ask addresses such as `/stats/data/usage` for numbers. Each such
  address is an **endpoint**.
- **JSON:** a simple text format for sending data between server and page, for example
  `{"labels": ["Nov"], "amounts": [3]}`. The chart addresses answer in JSON.
- **Regular expression (`NUMBER_PATTERN`):** a short pattern that checks text has the right shape,
  for example "digits, then optionally a dot and one or two digits". We use it to reject letters
  in number boxes.

## Login and security

- **Login / log out:** proving who you are with a username and password; ending that proof.
- **Password hash (scrambled password):** we never save the password itself. We save a scrambled
  version made by a one-way recipe, so even the person who owns the database cannot read it. When
  you log in, we scramble what you typed the same way and compare. Made by `werkzeug.security`.
- **Hash:** the scrambled result of that recipe. You cannot turn it back into the password.
- **Account lock:** after 5 wrong passwords the account is locked for 15 minutes (F1). This slows
  down people who try thousands of passwords (a *brute-force attack*).
- **Session:** how the site remembers you are logged in while you click around. After login the
  server stores your user id in the session.
- **Cookie:** a tiny piece of text the browser keeps and sends back with every request. Ours holds
  the (signed) session. Settings we use: **HttpOnly** (page scripts cannot read the cookie) and
  **SameSite=Lax** (the browser will not send it along with most requests started by other
  websites).
- **Secret key (`SECRET_KEY`):** a long random text that signs the session cookie so nobody can
  fake it. It must stay secret, so it comes from the environment variable and is never saved in
  Git. Without it the app refuses to start.
- **Role:** the label that decides what a user may do. We have two: **ADMIN** and **EMPLOYEE**.
- **Users screen (F8):** the Admin-only page (`app/routes_users.py`) to add a user, change a role,
  reset a password (this also unlocks the account) and switch an account off or on. Nothing is
  deleted. An Admin cannot switch off or demote themselves, and the last active Admin cannot be
  switched off.
- **Permission:** one thing a role may or may not do, for example "see prices" or "manage suppliers".
  All permission rules live in `app/permissions.py` as functions such as `can_see_prices(user)` and
  `can_manage_suppliers(user)`. Screen files must only ask these functions (rule C7).
- **Server-side check:** the rule is checked on the server, not just by hiding a button. A person
  who types a forbidden address by hand is still blocked.
- **Deny by default:** if in doubt, say no. Not logged in, switched off, or an unknown role gets
  nothing.
- **CSRF (cross-site request forgery):** an attack where another website tricks your browser into
  sending a request to ours while you are logged in. The usual defence is a secret token in each
  form. **We built this** (`app/csrf.py`): every form that changes data carries a hidden `csrf_token`
  field, and the server answers 400 ("page has expired") if it is missing or wrong. The SameSite cookie
  setting is a second layer. **CSRF token:** that secret one-time value; it is made new for each
  login session. Only the automatic tests switch the check off (`CSRF_ENABLED`).
- **Authentication vs authorization:** *authentication* = "who are you?" (login). *Authorization* =
  "what may you do?" (roles and permissions).

## Web status numbers (403 and friends)

Every answer from the server starts with a number that says how it went.

| Number | Name | Meaning in our app |
|---|---|---|
| **200** | OK | The page was sent normally |
| **302** | Redirect | "Go to that other page" (for example to Home after login, or to the login page if you are not logged in) |
| **400** | Bad request | The form had a problem (for example letters in a quantity box, or a form that has expired). Shown with a plain-words message; the error pages have a **Back to Home** button |
| **401** | Unauthorized | Wrong username or password |
| **403** | Forbidden | You are logged in but **not allowed**. An Employee typing an admin address gets this. The page says so in plain words and has a **Back to Home** button |
| **404** | Not found | There is no such page, or the material or supplier is switched off. Also shown in plain words with a **Back to Home** button |
| **405** | Method not allowed | You used GET on an address that only accepts POST (or the other way round) |
| **500** | Server error | A bug in our code. Report it in the status log |

## Pages and charts

- **HTML:** the language that describes what is on a page (headings, tables, buttons).
- **CSS:** the language that describes how a page looks (colours, sizes). In our files you see it
  inside `<style>`.
- **JavaScript (JS):** code that runs inside the browser. We use a small amount, only to draw charts.
- **Chart.js:** a free library that draws the bar and line charts. The Statistics page loads it from
  the internet (from a **CDN**), so that page needs a connection to draw charts.
- **CDN (content delivery network):** a public website that hosts shared library files for others
  to load.
- **Responsive / mobile-friendly:** the page rearranges itself so it works on a phone at the printer.
- **Tap size (44 px):** buttons and links on the new and changed screens are at least about 44 pixels
  tall, so a thumb can tap them without hitting the wrong thing.
- **Plain-English error page:** when you have no permission (403), a page is not found (404) or a form
  has expired (400), the app shows one short sentence in everyday words and a **Back to Home**
  button. The browser still receives the real error number. Code: `show_plain_error` in
  `app/__init__.py` and `app/templates/error_page.html`.

## Dates and money

- **UTC:** the world's standard clock. We store every date and time in UTC (rule in Section 6).
- **UTC+8 (Malaysia time):** Kuching time is 8 hours ahead of UTC. The screens add 8 hours when
  they show a date. For example 16:00 UTC on 31 Oct shows as 00:00 on 1 Nov.
- **Timestamp:** a date and time saved with a row, for example `created_at`.
- **MYR:** Malaysian Ringgit. Every money number on screen is written like `MYR 72.00`.
- **Rounding:** `ROUND(..., 2)` keeps two decimal places so tiny computer errors do not creep in
  (for example 0.1 + 0.2 must be 0.3).

## Our own words (business rules)

- **Material:** one thing we stock (a filament colour, a resin, nuts). It has a **unit**: `g`
  (grams), `ml` (millilitres) or `pcs` (pieces).
- **Pieces (`pcs`) and hardware items:** small things counted one by one, such as screws, springs,
  magnets, fidget clickers and keychain rings. The system handles them like any other material, next to
  `g` and `ml` items. **The hardware in our demo data is SAMPLE data only** (names start with
  "SAMPLE"); what hardware Stinablis really tracks is still [CONFIRM WITH FOUNDER] (guide Section 2 and
  Section 16 Q1, Rule R4).
- **Reorder level:** the quantity at which we should order more (for example 500 g).
- **Status OK / LOW / OUT:** `OUT` = none left (quantity is zero). `LOW` = quantity is at or below the
  reorder level, so it is time to order. `OK` = enough in stock. The Materials page explains these three
  words in one plain sentence, and the word is always shown, not just a colour (green / orange / red).
- **Needs attention:** the Home list of LOW and OUT materials, OUT first.
- **Supplier:** a shop that sells materials. Type `LOCAL` or `ONLINE`.
- **Offer (`supplier_offers`):** one row saying "this supplier sells this material at this price".
- **Pack:** what an offer is sold in (for example one 1000 g spool). The price is **per pack**, not
  per gram. In `app/schema.sql`, supplier offers are priced per pack (`price_per_pack_myr`), not per
  single gram, millilitre, or piece.
- **Minimum order (packs):** the fewest packs the supplier will sell in one order.
- **Lead time:** how many days from ordering to arrival.
- **Estimated arrival:** today (Malaysia time) + lead time days.
- **Quantity needed:** (reorder level x 2) minus what we have now. Marked **[CONFIRM]** with the
  founder in the guide.
- **Estimated cost:** number of packs x price per pack + shipping. All costs and dates on screen are
  **estimates** and the page says so.
- **Find supplier / suggestion:** the page that ranks suppliers for a LOW or OUT material (cheapest
  total first, then shortest lead time). Code in `app/suggest.py`.
- **Last bought (purchase memory):** a short line on the Materials list and on the Record used / Record
  received pages: who the material was last bought from, how much, the date and, if someone typed it,
  the total paid in MYR. It is read from the newest "received" line that names a supplier or a cost. The
  money part is shown to Admin and Employee (view only, `can_see_prices`); changing prices is still
  Admin only and answers 403 to anyone else. Code: `get_last_bought` in `app/routes_materials.py`.
- **Total paid / Bought from:** two optional boxes on "Record received". They feed the money numbers:
  Home's money box adds up the real totals typed here for the current month, and the Admin-only spending
  chart groups them per supplier. A received line with no total counts as MYR 0.
- **Record used / Record received:** the two buttons that change stock. They are the only way the
  quantity changes.
- **Low-stock event:** the moment a "Record used" drops a material from OK to LOW or OUT. One row is
  saved in the `low_stock_events` table at that moment, and the Statistics chart counts the rows per
  month (Malaysia time). Further drops while it stays LOW or OUT do not count again.
- **Not set up yet:** what a screen says when the team has not yet decided how to calculate that
  number. It is switched off on purpose (rule R4: do not guess). Money spent and low-stock events used
  to say this; both are now switched on.

## Testing

- **Automatic test:** a small program that checks one rule of the app and says pass or fail. We run
  all of them with `python -m pytest tests`.
- **pytest:** the tool that finds and runs our tests.
- **Test client:** a pretend browser inside a test; it logs in and opens pages without opening a
  real browser.
- **Fixture:** a ready-made starting situation shared by tests (for example "a fresh database with
  one admin").
- **Temporary database (`tmp_path`):** tests build their own throw-away database so they never
  touch `data/tracker.db`.
- **Manual test:** a person clicks through the app with a checklist (Section 15 of the guide).

## Tools, Git and licenses

- **Virtual environment (`.venv`):** a private folder of Python libraries for this project only, so
  it does not mix with other projects. Git ignores it.
- **pip:** the tool that installs Python libraries. We run `pip install -r requirements.txt`.
- **`requirements.txt`:** the list of libraries (and allowed versions) the project needs, so everyone
  installs the same ones.
- **Git:** the history book of every change to the code. Each saved change is a **commit** with a
  short message.
- **GitHub:** the website where we keep the shared copy of the Git history. **Push** = send your
  commits to GitHub. **Clone** = download a copy.
- **`.gitignore`:** the list of files Git must skip: the database (`data/`), `.venv/`, and
  `__pycache__/`.
- **Command line / terminal / PowerShell:** the text window where you type commands.
- **License:** the owner's written permission that says how others may reuse a project's code.
  **MIT** is a short, permissive license: you may reuse the code if you keep the copyright
  notice. Rule C10: before copying any code, check its license, add a comment with the source link,
  and explain it here.
- **Open-source projects we studied (ideas only):** see `PRESENTATION_NOTES.md`, topic 6. No
  code from them is in our project.

### Code and libraries we use from other people (rule C10)

| What | Used for | License (from the project's own page; re-check before the final presentation) |
|---|---|---|
| Flask (and Werkzeug, Jinja) | The web framework, password scrambling, page templates | BSD-3-Clause |
| pytest | Running the automatic tests | MIT |
| Chart.js 4.4.1 (loaded from the jsDelivr CDN) | Drawing the statistics charts | MIT |

We **install or load** these libraries; we did not copy their source code into our files. As of
2026-11-24 a search of `app/`, `tests/` and `sample_data/` finds no comment, link or notice that
credits copied code, and no file mentions Spoolman, InvenTree, FilaOps, OSSMS or Stockify. If a team
member pastes code from anywhere, they must add the source link and license in a comment and add a
row to this table (rule C10).

# Glossary: what the technical words mean

Plain-language meanings of the words used in this project (guide Section 13, Rule C10). Each word is
explained in one or two sentences, with an example from our own tracker where that helps.
Words are grouped by topic, and A-Z within each group.

---

## 1. The business words

| Word | Meaning |
|---|---|
| **Activity log** | The list of "who did what, and when". Example: "boss switched off worker, 24 Nov 2026 14:05". Nobody can edit or delete it. |
| **Admin** | The owner, manager or trusted person. Can change everything. |
| **Employee** | General staff, for example a printer operator. Can record stock and see prices, but cannot change materials, suppliers, prices or users. |
| **Estimate** | A best guess. Costs and arrival dates on the suggestion screen are estimates, and the screen says so. |
| **Lead time** | How many days pass from ordering to arrival. Arrival date = today + lead time. |
| **LOW / OUT / OK** | The three stock statuses. LOW: quantity is at or below the reorder level. OUT: quantity is zero. OK: anything else. We always write the word, not only a colour. |
| **Material** | Something we keep in stock, for example PLA filament, PETG, resin or nuts. |
| **Minimum order** | The smallest number of packs a supplier will sell. Example: 5 spools. |
| **MYR** | Malaysian Ringgit, our currency. Example: "MYR 72.00". |
| **Needs attention list** | The Home page list of materials that are LOW or OUT. |
| **Offer** | One supplier selling one material, with its price, pack size, shipping, minimum order and lead time. |
| **Pack** | The unit a supplier sells, for example one 1 kg spool or one 1 L bottle. Prices are per pack, not per gram. |
| **Quantity on hand** | How much of a material is in stock right now. |
| **Record received** | The button for "new stock arrived". It adds to the stock. |
| **Record used** | The button for "we used some". It reduces the stock and can never go below zero. |
| **Reorder level** | The quantity at which we should order more. Example: reorder at 500 g. |
| **Stock** | The amount of materials we have on the shelf. |
| **Supplier** | A company or shop we buy from. It is ONLINE or LOCAL. |
| **Switched off** | How we "remove" something. The record stays with all its history but no longer shows in normal lists (Rule C9). |

---

## 2. The words about how the system works

| Word | Meaning |
|---|---|
| **Application (app)** | The program that runs our website. |
| **Blueprint** | A Flask way to keep one topic's screens together in one file. Example: `routes_materials.py` holds the Materials blueprint. |
| **Browser** | The program you use to open websites, for example Chrome or Edge. |
| **Client** | In this project, the browser (or a test pretending to be one). |
| **Database** | A set of linked spreadsheets stored in one file. Ours is `data/tracker.db`. |
| **Endpoint / route** | One web address the app answers, for example `/materials/`. The "routes" files list them. |
| **Flask** | The small Python library that runs our website. |
| **Form** | A web page with boxes to fill in and a button to send them. |
| **Foreign key** | A link from one table to another. Example: an offer points to a supplier and to a material. The database checks that the target exists. |
| **GET and POST** | The two kinds of requests. GET asks to see a page. POST sends data to change something. Changing things is always POST. |
| **Hash / scrambled password** | We never store a password. We store a one-way scramble of it. Even the database owner cannot read it back. At login we scramble what you typed and compare. |
| **HTML** | The language web pages are written in. |
| **HTTP status code** | A number the server sends back. 200 = fine, 302 = "go to another page", 403 = "not allowed", 404 = "not found", 500 = "the server broke". |
| **Jinja (template)** | The tool that fills a page with real data. A template is an HTML file with gaps such as `{{ material['name'] }}`. |
| **JSON** | A plain-text format for sending data to a page. The charts use it. |
| **Library** | Ready-made code written by other people that we use. See the table at the end. |
| **Login / session / cookie** | After a correct login, the server gives your browser a small signed note called a cookie. It proves you logged in, so you do not type your password on every page. The time you stay logged in is a session. |
| **Migration / upgrade** | A safe change to the database layout that keeps the existing data. |
| **Python** | The programming language we use. |
| **Redirect** | The server answers "go to this other page" (status 302). Example: after login you are sent to Home. |
| **Request** | What the browser sends to the server. |
| **Response** | What the server sends back: a page, or data. |
| **Row** | One line in a table, for example one material. |
| **Schema** | The plan of the database: its tables and columns. Ours is in `app/schema.sql`. |
| **Secret key** | A long private text that signs the login cookie. It is set outside the code (the `STINABLIS_SECRET_KEY` setting) and never put in Git. |
| **Server** | The computer that runs the app and checks every rule. |
| **SQL** | The language used to ask the database for data. |
| **SQLite** | The database program we use. The whole database is one file and needs no separate server. |
| **Table** | One "spreadsheet" in the database, for example `materials` or `users`. |
| **Test client** | A pretend browser used by the automatic tests. |
| **Timezone / UTC** | UTC is the world reference time. We store every date in UTC and show it in Malaysia time (UTC+8). Example: 16:00 UTC shows as 00:00 the next day. |
| **Virtual environment (`.venv`)** | A private folder of libraries for this project only, so it does not mix with other Python programs. |
| **Web address (URL)** | The text you type in the browser, for example `http://localhost:5000/users/`. |

---

## 3. The words about safety

| Word | Meaning |
|---|---|
| **Account lock** | After 5 wrong passwords the account is locked for 15 minutes. |
| **Authentication** | Proving who you are (logging in). |
| **Authorization / permission** | Deciding what you may do once we know who you are. The rules are in `app/permissions.py`. |
| **CSRF (cross-site request forgery)** | A trick where a bad web page makes your browser send a form to our site while you are logged in, so the site does something you did not mean. A CSRF token (a hidden random value in each form) stops it. We do not have tokens yet. This is an open item. |
| **Checked on the server** | Every rule is enforced by the server, not just by hiding buttons. An Employee who types an Admin address still gets "not allowed" (403). |
| **Deny by default** | If in doubt, refuse. It is easier to allow later than to undo a leak. |
| **HttpOnly cookie** | A setting that stops page scripts from reading the login cookie. |
| **SameSite cookie** | A setting that tells the browser not to send our cookie when another website triggers a form post. It is our protection against CSRF for now. |
| **Sensitive data** | Information that must be protected, such as passwords. |
| **Spreadsheet formula injection** | A trap where text in a cell starts with `=`, `+`, `-` or `@` and a spreadsheet program runs it as a formula. The CSV download adds an apostrophe in front of such text. |

---

## 4. The words about our code and testing

| Word | Meaning |
|---|---|
| **Admin-only page guard (`admin_required`)** | A small check placed above a screen's code. It sends logged-out people to login and answers 403 to anyone who is not an Admin. |
| **Automatic test** | A small program that checks our app still works. We run all of them with `python -m pytest tests`. |
| **Branch** | A separate line of work in Git. Ours is `main-iyvssn`. |
| **Commit** | One saved step in Git, with a short message describing it. |
| **CSV** | A plain spreadsheet file (comma-separated values). Our sample data and the Admin download use it. |
| **Fixture** | In tests, the code that builds the temporary database before each check. |
| **Git** | A history book of every change to the code. |
| **GitHub** | The website where the shared copy of the project lives. |
| **Pull / push** | Pull: get the newest code from GitHub. Push: send your commits to GitHub. |
| **pytest** | The tool that runs our automatic tests. |
| **README** | The short "how to run it" file. |
| **Sample data** | Invented data in `sample_data/` used for testing. It is not real Stinablis data. |
| **STATUS LOG** | The list at the bottom of `CLAUDE.md` where each agent writes what it did, what is left, and any problem. |
| **Stash** | A way in Git to put unsaved changes safely aside. |

---

## 5. The words about the screens

| Word | Meaning |
|---|---|
| **Chart.js** | A library that draws the charts on the Statistics page. It is loaded from the internet. |
| **Dashboard** | The Home page with the big number boxes and the Needs attention list. |
| **Responsive / mobile-friendly** | The page changes its layout to fit a phone or tablet. |
| **Stock movement** | One row in the history: USED, RECEIVED or ADJUSTED, with the quantity, who did it and when. Stock changes only through movements. |
| **ADJUSTED** | A movement type for a correction. Today it is used only for a new material's starting quantity. |

---

## 6. Libraries we use

| Library | What for | Licence |
|---|---|---|
| Python | The language | PSF (free to use) |
| Flask | The website framework | BSD-3-Clause |
| Werkzeug | Scrambles passwords and is used inside Flask | BSD-3-Clause |
| Jinja | Fills pages with data | BSD-3-Clause |
| SQLite | The database (built into Python) | Public domain |
| pytest | Runs the automatic tests | MIT |
| Chart.js | Draws the charts | MIT |

Per Rule C10: we have **not copied code** from the open-source projects in Section 3 of the guide
(Spoolman, InvenTree, FilaOps, OSSMS, Stockify and the small filament trackers). We used them only for ideas:
role permissions, low-stock alerts and screen layout. Before copying any code from them, check the licence
first and credit the source in a comment and in this file.

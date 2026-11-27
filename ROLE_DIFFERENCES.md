# Admin and Employee: what is different

**For the presentation.** This page lists, in plain words, what each role can see and do in the Stinablis Material & Supplier Tracker.
Every row of the tables below is **checked by an automatic test** (`tests/test_role_differences.py`) against the real website, so
this page cannot say something the app does not do. Last checked: 2026-11-26.

## The 30-second version

- There are **two roles**: **Admin** (the owner or manager) and **Employee** (operators at the printers).
- **Employees can see almost everything** they need to work: stock levels, suppliers, prices, the "Find supplier" suggestions and
  the usage statistics. They can **record stock used and received**.
- **Employees cannot change anything about the business data**: no adding or editing materials, suppliers or prices, no user
  accounts, no money panel (spending & stock value) and no spreadsheet download. **Only the Admin types what was paid** for a delivery.
- Every rule is checked **on the server**, not just by hiding buttons. An Employee who types a forbidden web address still gets a
  plain "not allowed" page with a **Back to Home** button.

## How to read the tables

"Yes" means that role can do or see it. "No" means the server refuses it (the page answers 403 "not allowed" or 404 "not found").

### Home

| What | Admin | Employee | Notes |
|---|---|---|---|
| See the Home dashboard with the three number boxes | Yes | Yes | Total, LOW and OUT. |
| See the Notifications list with Find supplier buttons | Yes | Yes | The LOW and OUT materials, OUT first. |

### Materials

| What | Admin | Employee | Notes |
|---|---|---|---|
| See the materials list and stock levels | Yes | Yes | Status is always written: OK, LOW or OUT. |
| Record stock used | Yes | Yes | Writes a history line and may create a low-stock event. |
| Record stock received | Yes | Yes | Employees record the quantity only. |
| Type the supplier and total paid on Record received | Yes | No | Admin only (Agent A design "Option B"). The boxes are not drawn for Employees, and typing the money anyway gets 403 and nothing is saved. |
| See the Last bought note (supplier, date and money) | Yes | Yes | The money part follows the "see prices" rule. |
| Add, edit or remove a material | Yes | No | "Remove" only switches a material off; its history stays. |
| Edit quantity (set stock to the real count, with a reason) | Yes | No | Admin only (2026-11-27). Saved as a "Stock correction" line plus an activity-log line; it never counts as usage or as a purchase. Employees get 403 on the page and on the save. |
| Use Quick log to record stock used without leaving the page | Yes | Yes | Same rules as Record used (2026-11-27); no money on the page. |

### Suppliers

| What | Admin | Employee | Notes |
|---|---|---|---|
| See the suppliers list and supplier details | Yes | Yes | Includes phone, email and website. Still to confirm with the founder. |
| See supplier prices and shipping costs | Yes | Yes | Team decision 2026-11-24. |
| See a switched-off supplier | Yes | No | Switched-off suppliers are hidden from Employees (404). |
| Add, change or switch off a supplier or its prices | Yes | No | Employees get 403, even with a complete, valid form. |
| Use Find supplier (estimated cost and arrival date) | Yes | Yes | The cost is shown as an estimate. |

### Statistics

The Statistics page has a sidebar that lists only the statistics the role may open: three for an Employee, and for the Admin
also spending & stock value and the spreadsheet download. Clicking one shows it on its own, so nobody scrolls.

| What | Admin | Employee | Notes |
|---|---|---|---|
| See the usage per material chart | Yes | Yes | A Unit choice (Filament (g), Resin (ml) or Hardware (pcs)) keeps every bar on one scale. |
| See days of stock left (no money) | Yes | Yes | A plain table: In stock, Days left, Lead time and a Status pill ("Order now", "Low" or "OK"). No money, so it is safe for Employees. |
| See the delivery ranking of suppliers for a chosen material | Yes | Yes | Fastest supplier first, with the days and an estimated arrival date; the material choice appears only when some material has two or more suppliers. No money in it. |
| See spending and stock value (MYR) | Yes | No | Admin only: the total spent this month with a breakdown by supplier, and the estimated value of the stock on hand. The Employee page does not even contain the word "MYR". |
| Download the statistics spreadsheet (CSV) | Yes | No | Admin only. |

### Users

| What | Admin | Employee | Notes |
|---|---|---|---|
| Open the Users screen | Yes | No | The Users link in the menu is only drawn for Admin. |
| Add a user, change a role, reset a password or switch an account on or off | Yes | No | An Admin cannot switch off or demote themselves, and the last Admin cannot be switched off. |

## The same for both roles

- Both log in with a username and a password. After 5 wrong passwords the account is locked for 15 minutes.
- Both see dates in Malaysia time (UTC+8) and money in MYR.
- Both are protected by the same safety rules: scrambled passwords, a security token on every form, and every change written to the
  activity log.
- Nobody deletes records. Things are switched off, and their history stays.

## Why the roles are different (decisions we made)

| Date | Decision |
|---|---|
| 2026-11-23 | First plan: Employees see no prices at all. |
| 2026-11-24 | **Employees may SEE prices, shipping costs and money totals**, but still cannot change suppliers, offers or materials. |
| 2026-11-24 | The spending chart and the CSV download stay **Admin only** (the spending charts were removed later, see 2026-11-26). |
| 2026-11-24 | **Only the Admin types the supplier and total paid** on Record received (Option B). Employee lines have no total, so they count as MYR 0 in money spent. |
| 2026-11-24 | The "Last bought" note is shown to both roles (the money part follows the "see prices" rule). |
| 2026-11-24 | The Users screen is Admin only. |
| 2026-11-26 | Procurement statistics: **purchases per material is for both roles; the supplier price comparison (charts) is Admin only**. |
| 2026-11-27 | **Statistics cleaned up:** usage has a Unit choice (g, ml, pcs); new "Days of stock left" for both roles (no money); "Purchases per material" and "Supplier price comparison" removed and replaced by the Admin-only "Spending & stock value". The CSV is unchanged. |
| 2026-11-26 | **Removed from the Statistics page:** the low-stock events chart, the spending per supplier chart and the spending per material chart. The Home money box and the CSV download stay. |
| 2026-11-26 | **Removed from the Home page:** the "estimated money spent this month" box (the team said it is not relevant any more). Home now has three boxes and no money for either role. |

## Not built yet (so they are not in the tables)

- An **activity log screen** (the log is written, but no screen shows it). When built, it is Admin only.
- A **one-click database backup** button. When built, it is Admin only.

## How we keep this page true

1. When a permission changes, **change the guide first** (`CLAUDE.md`, Sections 4 and 5), then the code.
2. Change the row in `ROLE_ROWS` in `tests/test_role_differences.py` and the matching row in this page, and add a line to the
   decisions table above.
3. Run `python -m pytest tests/test_role_differences.py`. It fails if this page and the real website disagree, or if a row here has
   no proof, so a forgotten update cannot reach the presentation.

# Test Summary (one section per agent)

**How to run all automatic tests:** `.venv\bin\python.exe -m pytest tests`
Tests use a temporary database, never the real `data/tracker.db`.

| Agent | Area | Automatic tests | Manual test | Status |
|---|---|---|---|---|
| A | Database | not recorded yet | not recorded yet | Pending |
| B | Login and roles | 24 pass | 8 of 8 pass | Done |
| C | Materials and stock | 28 pass | 3 of 3 pass | Done |
| D | Suppliers and suggestion | 29 pass | 3 of 3 pass | Done |
| E | Statistics and dashboard | 27 pass | 3 of 3 pass | Done |
| F | Full review of all roles | not started | not started | Pending |

---

## Agent B: Login and roles (`tests/test_auth_permissions.py`)

| What we prove | Guide rule | Result |
|---|---|---|
| Good login works; wrong password and wrong username look the same | F1 | Pass |
| 5 wrong passwords lock the account for about 15 minutes | F1, Security | Pass |
| 4 wrong passwords do not lock; the lock ends after 15 minutes | F1 | Pass |
| A good login resets the wrong-password count | F1 | Pass |
| Even the correct password is refused while locked | F1 | Pass |
| Switched-off accounts cannot log in, even if already logged in | Section 4 | Pass |
| Accounts with no password cannot log in; short passwords refused | Security | Pass |
| Passwords are stored scrambled, not readable | Security | Pass |
| Logout ends the session; logout by link is refused | F1 | Pass |
| Not logged in means sent to the login page | Section 4 | Pass |
| Employee typing an admin address gets "not allowed" (403) | Section 4 | Pass |
| Employee is also blocked when sending data to an admin page | Section 4 | Pass |
| Admin and Employee can see prices; switched-off, not logged in and unknown roles cannot (changed 2026-11-24) | Section 4 | Pass |
| Employee can see prices but still cannot manage materials, suppliers, users or the activity log | Section 4 | Pass |
| Login, failed login and lock are written to the activity log | F9 | Pass |
| The real app needs a login and refuses to start without a secret key | Security | Pass |

**Manual test (done by the founder in the browser):**
1. Admin login works. Pass
2. Employee login works. Pass
3. 5 wrong passwords lock the account. Pass
4. Correct password is refused while locked. Pass
5. Menu bar (Home, Materials, Suppliers) shows after login, not on the login page. Pass
6. Each menu link opens its page. Pass
7. Menu wraps on a narrow window with no sideways scrolling. Pass
8. Log out still works with the menu present. Pass
9. Statistics link added to the menu (checked by the automatic menu test; browser check still to do). Pass (automatic)

**Not covered yet:** CSRF protection on forms, an Admin screen to unlock accounts.

---

## Agent C: Materials and stock (`tests/test_materials.py`)

| What we prove | Guide rule | Result |
|---|---|---|
| OK / LOW / OUT rule: at or below reorder level is LOW, zero is OUT | F5, Section 7 | Pass |
| Needs-attention list (OUT first) and counts by status | F5 | Pass |
| Checklist: add (reorder 500, qty 800) is OK; use 400 is LOW; use 400 more is OUT | Section 15 | Pass |
| Starting stock is written to the history as a movement | Section 6, C8 | Pass |
| Used / received change the quantity, write a history row and an activity log row | C8 | Pass |
| Cannot take out more than is in stock; nothing changes | Section 6 | Pass |
| Letters, minus, zero, 1e5, nan, inf, 3 decimals, huge numbers and over-long notes are refused with plain words | Section 8, 14 | Pass |
| Decimal amounts (0.1 + 0.2) do not drift | Section 6 | Pass |
| History dates show in Malaysia time (UTC 16:00 shows as 00:00 next day) | Section 15 | Pass |
| Not logged in means sent to login (every materials address) | Section 4 | Pass |
| Employee gets 403 on add / edit / remove, by address and by sending data; nothing changes | Section 4 | Pass |
| Employee page has no Add / Edit / Remove buttons and no prices (page source checked) | Section 4, 14 | Pass |
| Edit logs what changed and ignores quantity and unit sent by hand | C8, Section 6 | Pass |
| Remove only switches the material off; row and history stay | C9 | Pass |
| Search, OK / LOW / OUT filter; "%" typed in search is a plain letter | F3 | Pass |

**Manual test (done by the team in the browser, 2026-11-23):**
1. Log in as Admin, add a material, record used until LOW and then OUT. Pass
2. Log in as Employee: Record used works, no Add / Edit / Remove buttons. Pass
3. Open the Materials page on a phone-sized window. Pass

**Not covered yet:** CSRF tokens on forms; admin "correct the stock count" (ADJUSTED) screen.

---

## Agent D: Suppliers and suggestion (`tests/test_suppliers_suggest.py`)

| What we prove | Guide rule | Result |
|---|---|---|
| Quantity needed = (reorder level x 2) minus stock; rounded up to whole packs; never below the minimum order | Section 7 | Pass |
| Cost = packs x price per pack + shipping | Section 7 | Pass |
| Cheapest total is listed first; same cost is ordered by shortest lead time | F6, Section 15 | Pass |
| Arrival date = today + lead time days; "today" uses Malaysia time (UTC+8) | Section 7, 15 | Pass |
| "Needed within N days" leaves out suppliers that are too slow | F6 rule 1 | Pass |
| Switched-off suppliers and offers, and offers in a different unit, are never suggested | C9 | Pass |
| OK material says "nothing to order"; LOW and OUT show the status word and the word "estimate" | F5, F6, Section 8 | Pass |
| Employee suggestion data has no money keys; the page source has no MYR or price | F6, Section 4, 14 | Pass |
| Employee supplier list and detail pages show no prices or shipping; lead time and contacts are shown | F4, Section 4 | Pass |
| Admin sees prices and the Change / Add buttons | F4 | Pass |
| Employee cannot see switched-off suppliers (404) | C9 | Pass |
| Not logged in means sent to login | Section 4 | Pass |
| Employee gets 403 on every add / edit / switch address, by address and by sending data; nothing changes | Section 4, 14 | Pass |
| Admin add supplier / add offer / change price write activity log lines (price change shows old and new) | C8, F9 | Pass |
| Switching off keeps the record; no delete address exists | C9 | Pass |
| Letters, minus, zero, nan, inf, decimals in whole-number fields, over-long text, empty name, wrong type refused in plain words | Section 8, 14 | Pass |

**Manual test (done by the team in the browser, 2026-11-23):**
1. Admin: add a supplier, add an offer for PLA White, then open Find supplier for a LOW material. Pass (2026-11-23, including the "needed within N days" box)
2. Employee: Suppliers and Find supplier pages show names, lead time, arrival date and contacts, but no money. Pass (2026-11-23, also: letters in price refused, switch-off hidden from Employee, Employee blocked from /suppliers/new)
3. Open the Suppliers page on a phone-sized window. Pass (2026-11-23, real phone: /suppliers, /suppliers/S001, /suggest/M001)

**Not covered yet:** CSRF tokens on forms.

---


## Agent E: Home dashboard and statistics (`tests/test_stats_dashboard.py`)

| What we prove | Guide rule | Result |
|---|---|---|
| Home boxes show total, LOW and OUT counts, with the words LOW and OUT | F2, Section 8 | Pass |
| "Notifications" (was "Needs attention") lists LOW and OUT materials (OUT first), each with a Find supplier link | F2 | Pass |
| Purchases per material: RECEIVED lines per month with the unit; no money in the data (both roles) | F7 | Pass |
| Removed 2026-11-26: low-stock events, spending per supplier and spending per material charts; their addresses answer 404 and the page has none of them | F7 | Pass |
| Every chart names its unit or MYR in the axis title; Employee page has no "MYR", "Spending" or price comparison | F7, Sec 4 | Pass |
| CSV lists purchases and spending per material (Admin only) | F7 | Pass |
| Price comparison charts: numbers per kg / litre and per piece, the newest purchase is the price last paid, offer with no purchase kept, nothing for materials with neither; Admin only (Employee 403, no chart on the Employee page). The table with the same numbers was removed 2026-11-26 | F7 | Pass |
| Admin versus Employee table (ROLE_DIFFERENCES.md): 24 rows proven against the real website, and the page says the same as the proof | Sec 4, 13 | Pass |
| Admin Home has the money box; Employee Home has no money box and no "MYR" anywhere | F2, Section 4, 14 | Pass |
| Employee gets 403 on the CSV download and the spending data address | Section 4, 14 | Pass |
| Not logged in is sent to login on every statistics address | Section 4 | Pass |
| Admin can download the CSV; Employee statistics page has no spending, no MYR, no download button | F7 | Pass |
| Employee chart data (usage, delivery time, low-stock) contains no price words or numbers | Section 4, 14 | Pass |
| Usage chart adds USED rows only, by month and by week (week starts Monday) | F7 | Pass |
| A movement at 17:00 UTC on 31 Oct counts in November (Malaysia time, UTC+8) | Section 15 | Pass |
| Average delivery time per supplier ignores switched-off offers | F7 | Pass |
| Low-stock events: saved when Record used drops a material OK to LOW or OUT (once per drop). The chart that counted them was removed on 2026-11-26; the events are still saved | F5 | Pass |
| Money spent = real "Total paid" from Record received, per supplier, Malaysia-time month | F2, F7 | Pass |
| PROPOSED spending method (received stock x cheapest offer) and PROPOSED low-event method (drop from OK) calculate as written | R4 (switched off) | Pass |
| Money prints as "MYR 72.00"; CSV cells cannot run as spreadsheet formulas | Section 5 | Pass |

**Manual test (done by the team in the browser and on a real phone, 2026-11-24):**
1. Employee on Statistics: no spending per supplier, no spreadsheet download. Pass
2. Employee typing /stats/export.csv: "Forbidden" page, no file. Pass
3. Admin and Employee on a real phone (no sideways scroll, charts draw, Employee sees no money). Pass (2026-11-24)

**Not covered yet:** the real spending and low-stock numbers (waiting for the team's answers).

---

## Agents A, F

Add a section here when each agent finishes. Use the same format: what we prove, which guide rule, and the result.

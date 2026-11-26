=====================================================================
SAMPLE DATA FOR THE STINABLIS TRACKER (FAKE DATA - FOR TESTING ONLY)
=====================================================================

WHAT THIS IS
- Invented data used because the founder's answers are not yet available.
- Not real Stinablis data. Do not show these numbers, names or prices
  to the founder or the judges as real facts.
- Suppliers S001-S005 start with "SAMPLE"; all suppliers use example.com emails
  and placeholder addresses.
- Currency: all prices and costs are in MYR (Malaysian Ringgit).
- Usernames are sample_admin and sample_employee. Passwords are NOT in
  these files. Set them during setup and never save them in Git.

FILES
- materials.csv        : 13 materials (g, ml and pcs items) with stock on hand and
                         reorder level. The 5 hardware pieces (SAMPLE M4 screws, springs,
                         magnets, fidget clicker kit, keychain rings) are DEMO items only:
                         the founder has not confirmed what hardware Stinablis tracks
                         (guide Section 2 and Section 16 Q1).
- suppliers.csv        : 21 suppliers (12 local in Kuching/Sarawak, 9 online) with contact info.
                         S001-S005 are the original SAMPLE suppliers. S006-S021 use the shop names
                         from the team's list (9 Kuching, 7 West Malaysia/online). Their phones,
                         emails, addresses and ALL prices are invented placeholders, not real quotes.
                         S021 (BudgetFil) is a BAD BATCH demo: its offers are switched off.
- supplier_offers.csv  : 163 offers. Every material has 2 or more active offers.
                         Which supplier sells which material, with price,
                         pack size, shipping, minimum order and lead time
- stock_movements.csv  : sample history of used and received stock
- users.csv            : 2 sample accounts (one Admin, one Employee)

LAYOUT CHANGE (please note)
The guide's table plan (Section 6) had price_per_unit. Prices are
per spool or per bottle, not per gram, so supplier_offers now has
pack_size, pack_unit, and price_per_pack_myr. Update Section 6 of the
guide to match.

ASSUMPTIONS (the guide's Section 16 questions, answered by guessing)
Question 1 - Materials used most and units bought in:
  ASSUMED: PLA, PETG, ABS, TPU, resin, plus hardware and cleaning
  supplies. Filament bought in 1 kg spools. Resin bought in 1 L bottles.
  Replace when the founder answers.
Question 2 - Reorder levels:
  ASSUMED: 500 g to 1000 g for filament; 1000 ml for resin and alcohol;
  50 pcs for nuts. Replace with the founder's real numbers.
Question 3 - Online or local suppliers and lead times:
  ASSUMED: local shops 1 to 2 days; online shops 6 to 7 days.
  Shipping: RM 18 to RM 25 per online order.
Question 4 - Are prices before or after shipping, and is tax included?
  ASSUMED: prices are before shipping, and tax is NOT included.
  Shipping is stored separately.
Question 5 - Who is Admin and who are employees?
  ASSUMED: one admin account and one employee account (this file).
Question 6 - Should employees see supplier contact details?
  ASSUMED: yes, they can view contact details but cannot edit them.
  (Team decision 2026-11-24: employees can also SEE prices and shipping
  costs. They still cannot change them.)
Question 7 - Email alerts or on-screen alerts only?
  ASSUMED: on-screen alerts only for version 1.
Question 8 - Track which printer used which material?
  ASSUMED: no. This is a version 2 idea.
Question 9 - Existing spreadsheets to import?
  ASSUMED: none. Data is typed in fresh.

EXPECTED RESULTS (for testing the rules in Section 7 and Section 15)
Materials and their status, using the rule "LOW when quantity is at or
below the reorder level, OUT when quantity is zero":
  M001 PLA Basic White ........ 830 g  vs reorder 1000 g -> LOW
  M002 PLA Basic Black ........ 1450 g vs reorder 1000 g -> OK
  M003 PETG Clear ............. 240 g  vs reorder 500 g  -> LOW
  M004 ABS Grey ............... 0 g    vs reorder 500 g  -> OUT
  M005 TPU 95A Black .......... 380 g  vs reorder 300 g  -> OK
  M006 Standard Resin Grey .... 500 ml vs reorder 1000 ml -> LOW
  M007 M3 Hex Nuts ............ 85 pcs vs reorder 50 pcs -> OK
  M008 Isopropyl Alcohol ...... 900 ml vs reorder 1000 ml -> LOW

Example supplier suggestion for M001 (rule from Section 7):
  Quantity needed = (reorder level x 2) - on hand
                  = (1000 x 2) - 830 = 1170 g
  Spools needed   = round up 1170 / 1000 = 2 spools
  Option S001 local : 2 x RM 72.00 + RM 0.00 shipping = RM 144.00, arrives in 1 day
  Option S003 online: the minimum order is 5 spools, so 5 x RM 58.00 + RM 18.00 shipping
                      = RM 308.00, arrives in 7 days
  Note: the local shop is both cheaper and faster here, so it is listed first.
  The guide says to pick "in time" first, but does not define "in time."
  This is a question for the team to decide (see below).

Example for M004 ABS (OUT, zero stock):
  Needed = (500 x 2) - 0 = 1000 g = 1 spool.
  Only supplier S003 sells it: RM 75.00 + RM 18.00 = RM 93.00, arrives in 7 days.

OPEN ISSUE FOUND WHILE BUILDING THIS DATA
- The guide does not define "deliver in time." Suggested decision for the
  team: a supplier is "in time" if lead time is less than or equal to the
  number of days until stock would run out. Add this to Section 7 once
  agreed.

REPLACE THESE WHEN THE FOUNDER ANSWERS
Delete this data folder once real numbers exist, and load the real data
through the database setup script. Never keep fake supplier names in the
final demo.

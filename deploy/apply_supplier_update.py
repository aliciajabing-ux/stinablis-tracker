#!/usr/bin/env python3
# WHAT THIS FILE DOES: One-time, safe update of the Stinablis preview folder (the spool-care version unpacked from the zip).
#   It (1) backs up the database and the two Materials files, (2) swaps the old multi-supplier patch for the clean
#   "one supplier per material" code, removes "Not bought through this app yet.", (3) updates the sample CSV files and
#   setup_database.py, (4) runs "upgrade" and "sync-suppliers", (5) checks the result.
#   It edits by exact text anchors. If an anchor is not found it STOPS and changes NOTHING (files are only written at
#   the end, and put back from the backups if a check fails). Spool-care code is never replaced, only counted before/after.
# WHO CAN USE IT: Developers. Run inside /home/stinablisdemo/stinablis_new_preview:  python3 apply_supplier_update.py
import ast, os, re, shutil, sqlite3, subprocess, sys, time

ROOT = os.getcwd()
ROUTES = os.path.join(ROOT, "app", "routes_materials.py")
TEMPLATE = os.path.join(ROOT, "app", "templates", "materials_list.html")
SETUP = os.path.join(ROOT, "app", "setup_database.py")
DATABASE = os.path.join(ROOT, "data", "tracker.db")
SUPPLIERS_CSV = os.path.join(ROOT, "sample_data", "suppliers.csv")
OFFERS_CSV = os.path.join(ROOT, "sample_data", "supplier_offers.csv")
MOVEMENTS_CSV = os.path.join(ROOT, "sample_data", "stock_movements.csv")
SPOOL_WORDS = ["Open Spool", "Mark Dried", "spool", "printer", "chip", "640px", "390px", "@media"]

NEW_SUPPLIERS = r'''id,name,supplier_type,address,phone,email,website,notes,is_active
S001,Kuching 3D Filament Supply,LOCAL,"Jalan Pending, Kuching, Sarawak",+60-82-331-201,sales@kuching3d.example,,Local Kuching filament pickup & urgent spools,yes
S002,Sarawak Maker & Print Hub,LOCAL,"Batu Kawa, Kuching, Sarawak",+60-82-455-812,orders@sarawakmaker.example,,"Local backup filament, PEI plates & adhesives",yes
S003,3D Gadgets Malaysia (Shopee),ONLINE,Kuala Lumpur,+60-3-7890-1120,shop@3dgadgets-my.example,https://shopee.com.my,"Primary online filament, nozzles & extruder parts",yes
S004,MY Resin & Engineering Store,ONLINE,"Subang Jaya, Selangor",+60-3-5631-9044,resin@myengineering.example,https://shopee.com.my,"Online engineering resin, IPA & specialty polymers",yes
S005,Pending Industrial Hardware,LOCAL,"Pending Industrial Estate, Kuching, Sarawak",+60-82-339-770,hub@pendinghardware.example,,"Local screws, magnets, bearings & workshop tools",yes
S006,Bambu Lab Official MY (Shopee),ONLINE,"Shah Alam, Selangor",+60-3-5510-8821,my.store@bambulab-dist.example,https://shopee.com.my,"Official Bambu filaments, hotends & build plates",yes
S007,Sunlu & eSUN Malaysia Hub,ONLINE,"Puchong, Selangor",+60-3-8062-4410,orders@filamenthub.example,https://lazada.com.my,"Bulk PLA+, PETG & Matte spools",yes
S008,Tabuan Jaya Fasteners & Hardware,LOCAL,"Tabuan Jaya, Kuching, Sarawak",+60-82-364-910,sales@tjhardware.example,,"Same-day M3/M4 bolts, heat-set inserts & springs",yes
S009,Kota Sentosa Electronics & Maker,LOCAL,"Kota Sentosa, Kuching, Sarawak",+60-82-618-204,info@ksmaker.example,,"Thermistors, heater cartridges, fans & PTFE tubes",yes
S010,Cytron Technologies (Penang),ONLINE,"Bukit Mertajam, Penang",+60-4-548-0668,support@cytron.example,https://my.cytron.io,"Maker electronics, steppers & specialty parts",yes
'''
NEW_OFFERS = r'''id,supplier_id,material_id,pack_size,pack_unit,price_per_pack_myr,minimum_order_packs,shipping_cost_myr,lead_time_days,is_active
O001,S001,M001,1000,g,58.00,1,0.00,2,yes
O002,S001,M002,1000,g,72.00,1,0.00,1,yes
O003,S003,M003,1000,g,85.00,1,18.00,7,yes
O004,S003,M004,1000,g,75.00,1,18.00,7,yes
O005,S003,M005,1000,g,99.00,1,18.00,7,yes
O006,S004,M006,1000,ml,165.00,1,25.00,6,yes
O007,S005,M007,100,pcs,8.50,1,0.00,1,yes
O008,S004,M008,1000,ml,31.00,1,18.00,7,yes
O009,S005,M009,100,pcs,12.00,1,0.00,1,yes
O010,S005,M010,50,pcs,9.00,1,0.00,1,yes
O011,S005,M011,100,pcs,38.00,1,0.00,1,yes
O012,S002,M012,10,pcs,25.00,1,0.00,1,yes
O013,S005,M013,100,pcs,6.50,1,0.00,1,yes
O014,S007,M014,1000,g,70.00,1,18.00,7,yes
O015,S001,M015,1000,g,75.50,1,0.00,2,yes
O016,S003,M016,1000,g,80.00,1,18.00,7,yes
O017,S003,M017,1000,g,80.00,1,18.00,7,yes
O018,S006,M018,1000,g,88.00,1,0.00,1,yes
O019,S007,M019,1000,g,70.00,1,18.00,7,yes
O020,S008,M020,100,pcs,9.50,1,0.00,2,yes
O021,S008,M021,100,pcs,11.50,1,0.00,2,yes
O022,S008,M022,100,pcs,10.50,1,0.00,2,yes
O023,S008,M023,100,pcs,14.50,1,0.00,2,yes
O024,S008,M024,100,pcs,6.50,1,0.00,2,yes
O025,S008,M025,100,pcs,7.50,1,0.00,2,yes
O026,S008,M026,50,pcs,31.00,1,0.00,2,yes
O027,S008,M027,50,pcs,33.00,1,0.00,2,yes
O028,S005,M028,10,pcs,20.00,1,0.00,2,yes
O029,S010,M029,4,pcs,27.00,1,0.00,2,yes
O030,S005,M030,20,pcs,24.50,1,0.00,2,yes
O031,S005,M031,20,pcs,29.00,1,0.00,2,yes
O032,S009,M032,10,pcs,24.50,1,0.00,2,yes
O033,S002,M033,20,pcs,13.00,1,0.00,2,yes
O034,S002,M034,20,pcs,10.00,1,0.00,2,yes
O035,S002,M035,100,pcs,9.00,1,0.00,2,yes
O036,S008,M036,50,pcs,11.00,1,0.00,2,yes
O037,S005,M037,20,pcs,10.00,1,0.00,2,yes
O038,S002,M038,20,pcs,7.50,1,0.00,2,yes
O039,S002,M039,2,pcs,16.00,1,0.00,2,yes
'''
ROUTE_HELPERS = r'''NOT_NAMED_SUPPLIER = "a supplier that was not named"     # the words get_last_bought uses when a purchase has no supplier


# Returns {material id: supplier name}: ONE supplier per material, from its active offers. If a material has
# more than one active offer, the fastest delivery wins, then the lowest pack price, then the lowest offer id.
def get_offer_supplier_names(database):
    rows = database.execute(
        "SELECT o.material_id, s.name FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.is_active = 1 AND s.is_active = 1 "
        "ORDER BY o.material_id, o.lead_time_days, o.price_per_pack_myr, o.id").fetchall()
    names = {}
    for row in rows:
        names.setdefault(row["material_id"], row["name"])     # the first row per material is the winner
    return names


# Returns the one supplier to show for a material: the supplier it was last bought from (if a purchase named
# one), otherwise the supplier of its active offer, otherwise None.
def pick_material_supplier(material, offer_supplier_names):
    last_bought = material.get("last_bought")
    if last_bought and last_bought["supplier"] != NOT_NAMED_SUPPLIER:
        return last_bought["supplier"]
    return offer_supplier_names.get(material["id"])


'''
SETUP_BLOCK = r'''# Makes an existing database match sample_data/suppliers.csv and supplier_offers.csv: the sample suppliers are
# added or renamed, and each sample material gets exactly ONE active offer. Other offers on those materials are
# switched off (never deleted, Rule C9). Suppliers and materials that are not in the sample files are not touched.
def sync_sample_suppliers(database_file=DATABASE_FILE):
    if not os.path.exists(database_file):
        print("STOP: there is no database to sync. Run this script without arguments to build one.")
        return
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    for supplier in read_sample_rows("suppliers"):
        sync_one_supplier(connection, supplier)
    offers = read_sample_rows("supplier_offers")
    sample_material_ids = [row["id"] for row in read_sample_rows("materials")]
    marks = ", ".join("?" for _ in sample_material_ids)
    connection.execute(f"UPDATE supplier_offers SET is_active = 0 WHERE material_id IN ({marks})", sample_material_ids)
    for offer in offers:
        sync_one_offer(connection, offer)
    connection.commit()
    connection.close()
    print(f"Synced {len(offers)} offers: each sample material now has exactly one active supplier offer.")


# Adds one sample supplier, or updates the name, type and contact details of the one with the same id.
def sync_one_supplier(connection, supplier):
    known = connection.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier["id"],)).fetchone()
    if known is None:
        columns = list(supplier.keys())
        marks = ", ".join("?" for _ in columns)
        connection.execute(f"INSERT INTO suppliers ({', '.join(columns)}) VALUES ({marks})", [supplier[c] for c in columns])
        print(f"Added supplier {supplier['id']} {supplier['name']}")
        return
    connection.execute(
        "UPDATE suppliers SET name = ?, supplier_type = ?, address = ?, phone = ?, email = ?, website = ?, notes = ?, "
        "is_active = 1 WHERE id = ?",
        (supplier["name"], supplier["supplier_type"], supplier["address"], supplier["phone"], supplier["email"],
         supplier["website"], supplier["notes"], supplier["id"]))
    print(f"Updated supplier {supplier['id']} {supplier['name']}")


# Switches on the offer of this supplier and material (reusing an old row if there is one), or adds it.
def sync_one_offer(connection, offer):
    old = connection.execute("SELECT id FROM supplier_offers WHERE supplier_id = ? AND material_id = ? ORDER BY id",
                             (offer["supplier_id"], offer["material_id"])).fetchone()
    values = (offer["pack_size"], offer["pack_unit"], offer["price_per_pack_myr"], offer["minimum_order_packs"],
              offer["shipping_cost_myr"], offer["lead_time_days"])
    if old is not None:
        connection.execute(
            "UPDATE supplier_offers SET pack_size = ?, pack_unit = ?, price_per_pack_myr = ?, minimum_order_packs = ?, "
            "shipping_cost_myr = ?, lead_time_days = ?, is_active = 1 WHERE id = ?", values + (old["id"],))
        return
    offer_id = offer["id"]
    while connection.execute("SELECT 1 FROM supplier_offers WHERE id = ?", (offer_id,)).fetchone():
        offer_id = "O" + str(int(offer_id[1:]) + 1000)     # the sample id is taken by another row: use a free one
    connection.execute(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "minimum_order_packs, shipping_cost_myr, lead_time_days, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (offer_id, offer["supplier_id"], offer["material_id"]) + values)


'''
OLD_T001 = "T001,M001,RECEIVED,1000,Sample delivery from S003,U001,2026-11-10 02:00:00,S003,76.00"
NEW_T001 = "T001,M001,RECEIVED,1000,Sample delivery from S001,U001,2026-11-10 02:00:00,S001,58.00"


# Stops the whole update with a plain message (nothing has been written yet when this is used before STEP 3).
def stop(message):
    print("\nSTOPPED, NOTHING WAS CHANGED:", message)
    sys.exit(1)


# Returns the text of a file.
def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# Returns {word: how many times it appears} for the spool-care words (case-insensitive).
def count_words(text):
    return {word: text.lower().count(word.lower()) for word in SPOOL_WORDS}


# Returns (first line, last line) numbers (1-based) of the top-level function with this name, or None.
def find_function(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return first, node.end_lineno
    return None


# Changes materials routes: removes the old patch, adds the one-supplier helpers and two lines in the list route.
def patch_routes(source):
    lines = source.split("\n")
    old = find_function(source, "_attach_material_suppliers")
    if old:                                            # remove the old multi-supplier helper (and its comment line)
        first, last = old
        if first >= 2 and lines[first - 2].lstrip().startswith("#"):
            first -= 1
        del lines[first - 1:last]
    kept = []
    for line in lines:                                 # remove calls to the old helper
        if "_attach_material_suppliers" in line:
            if not (line.strip().startswith("_attach_material_suppliers(") and line.strip().endswith(")")):
                stop("the old helper is used in a way I cannot remove safely: " + line.strip())
            continue
        kept.append(line)
    text = "\n".join(kept)
    if "def get_offer_supplier_names" not in text:
        anchor = re.search(r"^@materials_blueprint\.route\(\"/\"\)\n@login_required\ndef list_materials", text, re.M)
        if anchor is None:
            stop("could not find list_materials() in routes_materials.py")
        start = anchor.start()
        while start > 0 and text[:start].rstrip("\n").split("\n")[-1].startswith("#"):    # keep its comment line with it
            start = text[:start].rstrip("\n").rfind("\n") + 1
        text = text[:start] + ROUTE_HELPERS + text[start:]
    return add_supplier_lines(text)


# Adds the supplier_name lines next to the existing last_bought line in list_materials (skips if already there).
def add_supplier_lines(text):
    if "pick_material_supplier(material" in text.split("def list_materials", 1)[1].split("\ndef ", 1)[0]:
        return text
    lines = text.split("\n")
    found = [i for i, line in enumerate(lines) if 'material["last_bought"] = get_last_bought(' in line]
    if len(found) != 1:
        stop('expected exactly one line with material["last_bought"] = get_last_bought( , found %d' % len(found))
    i = found[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    loop = i - 1
    while loop >= 0 and not lines[loop].strip().startswith("for material in materials:"):
        loop -= 1
    if loop < 0 or i - loop > 3:
        stop("the last_bought line is not inside a simple 'for material in materials:' loop")
    loop_indent = lines[loop][:len(lines[loop]) - len(lines[loop].lstrip())]
    lines.insert(i + 1, indent + 'material["supplier_name"] = pick_material_supplier(material, offer_supplier_names)')
    lines.insert(loop, loop_indent + "offer_supplier_names = get_offer_supplier_names(get_db())")
    return "\n".join(lines)


# Changes the Materials template: one Supplier line, no "Not bought through this app yet." text.
def patch_template(source):
    lines = source.split("\n")
    kept = []
    for line in lines:                                 # remove the old one-line Supplier memo(s) from the quick patch
        if 'class="memo">Supplier' in line:
            if line.count("<span") != line.count("</span>"):
                stop("an old Supplier line spans several lines; I cannot remove it safely: " + line.strip())
            continue
        kept.append(line)
    text = "\n".join(kept)
    fallback = '{% else %}<span class="memo">Not bought through this app yet.</span>{% endif %}'
    if fallback in text:
        text = text.replace(fallback, "{% endif %}")
    if "Not bought through this app yet" in text:
        stop('the text "Not bought through this app yet" is still in a form I do not recognise')
    marker = "{% if material.last_bought %}"
    if text.count(marker) != 1:
        stop("expected exactly one %s in materials_list.html, found %d" % (marker, text.count(marker)))
    supplier_line = '{% if material.supplier_name %}<span class="memo">Supplier: {{ material.supplier_name }}</span>{% endif %}'
    at = text.index(marker)
    line_start = text.rfind("\n", 0, at) + 1
    indent = text[line_start:at]
    return text[:line_start] + indent + supplier_line + "\n" + text[line_start:]


# Adds the sync-suppliers command to setup_database.py (skips if already there).
def patch_setup(source):
    if "def sync_sample_suppliers" in source:
        return source
    for needed in ("def read_sample_rows", "DATABASE_FILE ="):
        if needed not in source:
            stop("setup_database.py has no '%s'; it is different from the one I expect" % needed)
    anchor = source.find("# Builds all the tables from schema.sql")
    if anchor < 0:
        anchor = source.index("def build_database")
    text = source[:anchor] + SETUP_BLOCK + source[anchor:]
    call = re.search(r'(    if len\(sys\.argv\) > 1 and sys\.argv\[1\] == "upgrade":\n        upgrade_database\(\)\n)', text)
    if call is None:
        stop('could not find the "upgrade" command block at the bottom of setup_database.py')
    return text.replace(call.group(1), call.group(1) + '    elif len(sys.argv) > 1 and sys.argv[1] == "sync-suppliers":\n        sync_sample_suppliers()\n', 1)


# Checks the patched Python and the patched template are valid before anything is written.
def check_syntax(routes_text, template_text, setup_text):
    ast.parse(routes_text)
    ast.parse(setup_text)
    try:
        import jinja2
        jinja2.Environment().parse(template_text)
    except ImportError:
        print("  (jinja2 not importable here, template syntax not pre-checked)")
    if template_text.count("Supplier: {{ material.supplier_name }}") != 1:
        stop("the template would not have exactly one Supplier line")


# ---------------------------------------------------------------- run
print("Folder:", ROOT)
for path in (ROUTES, TEMPLATE, SETUP, DATABASE, SUPPLIERS_CSV, OFFERS_CSV):
    if not os.path.exists(path):
        stop("missing file: " + path + "  (run this inside /home/stinablisdemo/stinablis_new_preview)")
stamp = time.strftime("%Y%m%d-%H%M%S")
backup_folder = os.path.join(ROOT, "backup_" + stamp)
os.makedirs(backup_folder)
for path in (DATABASE, ROUTES, TEMPLATE, SETUP, SUPPLIERS_CSV, OFFERS_CSV, MOVEMENTS_CSV):
    if os.path.exists(path):
        shutil.copy2(path, os.path.join(backup_folder, os.path.basename(path)))
print("STEP 1 backups saved in", backup_folder)

old_routes, old_template, old_setup = read(ROUTES), read(TEMPLATE), read(SETUP)
new_routes, new_template, new_setup = patch_routes(old_routes), patch_template(old_template), patch_setup(old_setup)
check_syntax(new_routes, new_template, new_setup)
before, after = count_words(old_template + old_routes), count_words(new_template + new_routes)
print("STEP 2 spool-care words before -> after:", {w: (before[w], after[w]) for w in SPOOL_WORDS})
if any(after[w] < before[w] for w in SPOOL_WORDS):
    stop("a spool-care word would disappear; that must not happen")

for path, text in ((ROUTES, new_routes), (TEMPLATE, new_template), (SETUP, new_setup)):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
for path, text in ((SUPPLIERS_CSV, NEW_SUPPLIERS), (OFFERS_CSV, NEW_OFFERS)):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
if os.path.exists(MOVEMENTS_CSV):
    movements = read(MOVEMENTS_CSV)
    if OLD_T001 in movements:
        with open(MOVEMENTS_CSV, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(movements.replace(OLD_T001, NEW_T001))
print("STEP 3 files updated")

def restore():
    for name, path in (("tracker.db", DATABASE), ("routes_materials.py", ROUTES), ("materials_list.html", TEMPLATE),
                       ("setup_database.py", SETUP), ("suppliers.csv", SUPPLIERS_CSV), ("supplier_offers.csv", OFFERS_CSV)):
        shutil.copy2(os.path.join(backup_folder, name), path)
    print("Files restored from", backup_folder)

for command in ("upgrade", "sync-suppliers"):
    print("STEP 4 python3 app/setup_database.py", command)
    result = subprocess.run([sys.executable, os.path.join("app", "setup_database.py"), command], cwd=ROOT)
    if result.returncode != 0:
        restore()
        stop("setup_database.py " + command + " failed")

connection = sqlite3.connect(DATABASE)
t001 = connection.execute("SELECT supplier_id, note FROM stock_movements WHERE id = 'T001'").fetchone()
if t001 == ("S003", "Sample delivery from S003"):         # the untouched sample purchase of M001: point it at M001's supplier
    connection.execute("UPDATE stock_movements SET supplier_id = 'S001', note = 'Sample delivery from S001', "
                       "total_cost_myr = 58.00 WHERE id = 'T001'")
    connection.commit()
    print("       sample purchase T001 now names S001 (matches M001's supplier)")
suppliers = connection.execute("SELECT COUNT(*) FROM suppliers WHERE is_active = 1").fetchone()[0]
offers = connection.execute("SELECT COUNT(*), COUNT(DISTINCT material_id) FROM supplier_offers WHERE is_active = 1").fetchone()
materials = connection.execute("SELECT COUNT(*) FROM materials WHERE is_active = 1").fetchone()[0]
doubles = connection.execute("SELECT COUNT(*) FROM (SELECT material_id FROM supplier_offers WHERE is_active = 1 "
                             "GROUP BY material_id HAVING COUNT(*) > 1)").fetchone()[0]
none_at_all = connection.execute("SELECT COUNT(*) FROM materials m WHERE m.is_active = 1 AND NOT EXISTS (SELECT 1 FROM supplier_offers o "
                                 "WHERE o.material_id = m.id AND o.is_active = 1)").fetchone()[0]
connection.close()
print("STEP 5 CHECK: active suppliers = %d, active offers = %d (for %d materials), active materials = %d, "
      "materials with 2+ offers = %d, materials with no offer = %d" % (suppliers, offers[0], offers[1], materials, doubles, none_at_all))
final_template, final_routes = read(TEMPLATE), read(ROUTES)
problems = []
if suppliers < 10: problems.append("fewer than 10 active suppliers")
if offers[0] != offers[1] or doubles: problems.append("some material has more than one active offer")
if none_at_all: problems.append("some active material has no supplier offer")
if "Not bought through this app yet" in final_template: problems.append("old fallback text still in template")
if "_attach_material_suppliers" in final_routes or "_attach_material_suppliers" in final_template: problems.append("old patch still present")
print("       spool-care controls in materials_list.html:",
      {w: final_template.lower().count(w.lower()) for w in ("Open Spool", "Mark Dried", "640px", "390px")})
if problems:
    print("PROBLEMS:", problems)
    restore()
    stop("the final check failed (files restored; the database was already synced, restore data/tracker.db from the backup if needed)")
print("\nALL GOOD. Now click Reload on the Web tab. Backups are in", backup_folder)

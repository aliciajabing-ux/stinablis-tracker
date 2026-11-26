# WHAT THIS FILE DOES: Decides if a material is OK, LOW or OUT, and lists the materials that need attention.
# WHO CAN USE IT: Both (Admin and Employee both see low-stock warnings).
#
# The rule (guide Sections 5 F5 and 7):
#   quantity is zero (or less)           -> OUT
#   quantity is at or below reorder level -> LOW
#   anything else                         -> OK

STATUS_OK = "OK"
STATUS_LOW = "LOW"
STATUS_OUT = "OUT"


STATUS_ORDER = {STATUS_OK: 0, STATUS_LOW: 1, STATUS_OUT: 2}   # lists show OK first, then LOW, then OUT (Ryan's test)


# Returns the materials (each with a "status" word) listed OK first, then LOW, then OUT, then by name and colour.
def sort_ok_low_out(materials):
    return sorted(materials, key=lambda m: (STATUS_ORDER[m["status"]], (m["name"] or "").lower(),
                                            (m["colour"] or "").lower()))


# Returns "OUT", "LOW" or "OK" for one material, from its quantity and its reorder level.
def get_status(quantity_on_hand, reorder_level):
    if quantity_on_hand <= 0:
        return STATUS_OUT
    if quantity_on_hand <= reorder_level:
        return STATUS_LOW
    return STATUS_OK


# Returns a plain dictionary copy of a material row with a "status" word added.
def add_status(material_row):
    material = dict(material_row)
    material["status"] = get_status(material["quantity_on_hand"], material["reorder_level"])
    return material


# Returns every active material that is LOW or OUT (OUT first), each with its "status" word.
def get_materials_needing_attention(database):
    rows = database.execute(
        "SELECT * FROM materials WHERE is_active = 1 ORDER BY name, colour"
    ).fetchall()
    needing_attention = [add_status(row) for row in rows]
    needing_attention = [m for m in needing_attention if m["status"] != STATUS_OK]
    return sorted(needing_attention, key=lambda m: m["status"] != STATUS_OUT)


# Returns how many active materials there are in total and how many are OK, LOW and OUT.
def count_materials_by_status(database):
    counts = {"TOTAL": 0, STATUS_OK: 0, STATUS_LOW: 0, STATUS_OUT: 0}
    rows = database.execute("SELECT quantity_on_hand, reorder_level FROM materials WHERE is_active = 1")
    for row in rows:
        counts["TOTAL"] += 1
        counts[get_status(row["quantity_on_hand"], row["reorder_level"])] += 1
    return counts

# WHAT THIS FILE DOES: The Materials screens: list with search and filter, add / edit / remove a material
#   (Admin), and "Record used" / "Record received" (everyone). Every stock change is written to the history.
# WHO CAN USE IT: Both. Adding, editing and removing is Admin only; recording stock is Admin and Employee.

import re
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.alerts import STATUS_LOW, STATUS_OK, STATUS_OUT, add_status, get_status, sort_ok_low_out
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import (admin_required, can_correct_stock, can_manage_materials, can_record_purchase_cost, can_record_stock,
                             can_see_prices, login_required)
from app.spool_care import (DAY_FORMAT, DRY_AFTER_HIGHEST, DRY_AFTER_LOWEST, DRYER_AFTER_DAYS, FILAMENT_UNIT, add_spool_care, has_open_date, is_filament, is_resin, parse_day,
                              today_malaysia)
from app.routes_suppliers import FormProblem, insert_offer, insert_supplier, read_offer_numbers, read_supplier_form

materials_blueprint = Blueprint("materials", __name__, url_prefix="/materials", template_folder="templates")


# Gives the material pages the default and the limits of "Dry after (days)" (the form shows the default when nothing is saved).
@materials_blueprint.context_processor
def dry_after_numbers():
    return {"default_dry_days": DRYER_AFTER_DAYS, "dry_days_lowest": DRY_AFTER_LOWEST, "dry_days_highest": DRY_AFTER_HIGHEST}

UNITS = ("g", "ml", "pcs")
MAX_NUMBER = 1000000
MAX_TEXT_LENGTH = 100
MAX_NOTE_LENGTH = 200
NUMBER_PATTERN = re.compile(r"^\d{1,7}(\.\d{1,2})?$")
MOVEMENT_WORDS = {"USED": "Used", "RECEIVED": "Received", "ADJUSTED": "Starting stock"}
KIND_TO_MOVEMENT = {"used": "USED", "received": "RECEIVED"}
CORRECTION_PREFIX = "Stock correction"       # an ADJUSTED line that starts its note with this is a correction, not a starting stock
CORRECTION_NOTE_PATTERN = re.compile(r"^" + CORRECTION_PREFIX + r": ([\d.]+) -> ([\d.]+)")
STATUS_WORDS = (STATUS_OK, STATUS_LOW, STATUS_OUT)
NUMBER_HELP = "Please type the {label} as a number, for example 200"
FLOW_PATTERN = re.compile(r"^\d(\.\d{1,3})?$")      # EXPERIMENT 2026-11-26: for example 0.96
SPOOL_ACTIONS = {"open": ("opened_date", "SPOOL_OPENED", "Opened"), "dried": ("last_dried_date", "SPOOL_DRIED", "Marked dried")}
NEW_SUPPLIER = "new"      # the value of the "Who sells it?" drop-down for "a new supplier"
SUPPLIER_FIELDS = ("name", "supplier_type", "address", "phone", "email", "website", "notes")


# Returns the number typed in a form box, or None if it is not a plain number (letters, minus, too big...).
def read_number(text, allow_zero):
    text = (text or "").strip().replace(",", "")
    if not NUMBER_PATTERN.match(text):
        return None
    number = round(float(text), 2)
    if number > MAX_NUMBER or (number == 0 and not allow_zero):
        return None
    return number


# Returns a text box value with spaces trimmed and cut to the allowed length (None if too long).
def read_text(text, longest):
    text = (text or "").strip()
    return text if len(text) <= longest else None


# Turns a UTC date text from the database into Malaysia time (UTC+8) for the screen.
def to_malaysia_time(utc_text):
    if not utc_text:
        return ""
    local_time = datetime.strptime(utc_text, TIME_FORMAT) + timedelta(hours=8)
    return local_time.strftime("%d %b %Y %H:%M")


# Returns the address of the Materials list with the same search words and filter the person had (from ?q= and ?status=).
def get_list_address():
    return url_for("materials.list_materials", **get_list_arguments())


# Returns the search words and filter of this request as a small dictionary (to add to links that go to another page and back).
def get_list_arguments():
    arguments = {}
    search_text = request.args.get("q", "").strip()[:MAX_TEXT_LENGTH]
    if search_text:
        arguments["q"] = search_text
    if request.args.get("status") in STATUS_WORDS:
        arguments["status"] = request.args["status"]
    return arguments


# Returns the plain word and the amount (with + or - for a correction) to show for one history line.
def describe_movement(movement_type, quantity, note):
    match = CORRECTION_NOTE_PATTERN.match(note or "") if movement_type == "ADJUSTED" else None
    if match is None:
        return MOVEMENT_WORDS[movement_type], f"{quantity:g}"
    sign = "+" if float(match.group(2)) > float(match.group(1)) else "-"
    return "Stock correction", f"{sign}{quantity:g}"


# Writes one line to the activity log about a material (who, what, when).
def write_material_log(database, user_id, action, material_id, details):
    database.execute(
        "INSERT INTO activity_log (id, user_id, action, table_name, record_id, details, created_at) "
        "VALUES (?, ?, ?, 'materials', ?, ?, ?)",
        ("L" + uuid.uuid4().hex[:12], user_id, action, material_id, details, utc_now().strftime(TIME_FORMAT)),
    )


# Finds one active material by its id. Shows a "not found" page if there is none.
def find_active_material(material_id):
    material = get_db().execute("SELECT * FROM materials WHERE id = ? AND is_active = 1", (material_id,)).fetchone()
    if material is None:
        abort(404)
    return material


# Reads the add / edit form. Returns (values, list of plain-language problems).
def read_material_form(form, is_new, unit=None):
    problems = []
    name = read_text(form.get("name"), MAX_TEXT_LENGTH)
    material_type = read_text(form.get("material_type"), MAX_TEXT_LENGTH)
    colour = read_text(form.get("colour"), MAX_TEXT_LENGTH)
    reorder_level = read_number(form.get("reorder_level"), allow_zero=True)
    if not name:
        problems.append("Please type a name for the material (up to 100 letters).")
    if material_type is None or colour is None:
        problems.append("Type and colour must be 100 letters or fewer.")
    if reorder_level is None:
        problems.append(NUMBER_HELP.format(label="reorder level") + " (0 or more).")
    values = {"name": name, "material_type": material_type, "colour": colour, "reorder_level": reorder_level}
    if is_new:
        values["unit"] = form.get("unit")
        values["starting_quantity"] = read_number(form.get("starting_quantity") or "0", allow_zero=True)
        if values["unit"] not in UNITS:
            problems.append("Please choose a unit: grams, millilitres or pieces.")
        if values["starting_quantity"] is None:
            problems.append(NUMBER_HELP.format(label="starting quantity") + " (0 or more).")
        unit = values["unit"]
    if unit == FILAMENT_UNIT:
        extras, extra_problems = read_filament_extras(form, is_new)
        values.update(extras)
        problems += extra_problems
    elif unit == "ml" and not is_new and "opened_date" in form:       # a resin bottle: only its opened date can be corrected
        values["opened_date"], bottle_problems = read_bottle_date(form)
        problems += bottle_problems
    return values, problems


# Reads a whole number between low and high from a form box. Returns (number or None, True if the box was fine).
def read_whole_number(text, low, high):
    text = (text or "").strip()
    if not text:
        return None, True
    if text.isdigit() and low <= int(text) <= high:
        return int(text), True
    return None, False


# EXPERIMENT 2026-11-26: reads the optional saved printer settings (and, when editing, the two spool dates) of a filament item.
def read_filament_extras(form, is_new):
    problems = []
    nozzle, nozzle_ok = read_whole_number(form.get("nozzle_temp"), 100, 400)
    bed, bed_ok = read_whole_number(form.get("bed_temp"), 0, 150)
    flow_text = (form.get("flow_rate") or "").strip()
    flow = float(flow_text) if FLOW_PATTERN.match(flow_text) and 0.5 <= float(flow_text) <= 1.5 else None
    note = read_text(form.get("drying_note"), MAX_TEXT_LENGTH)
    dry_after, dry_after_ok = read_whole_number(form.get("dry_after_days"), DRY_AFTER_LOWEST, DRY_AFTER_HIGHEST)
    for ok, message in ((dry_after_ok, f"\"Dry after (days)\" must be a whole number from {DRY_AFTER_LOWEST} to {DRY_AFTER_HIGHEST}, "
                                       f"for example {DRYER_AFTER_DAYS}. Leave it empty to use {DRYER_AFTER_DAYS}."),
                        (nozzle_ok, "The nozzle temperature must be a whole number from 100 to 400, for example 235."),
                        (bed_ok, "The bed temperature must be a whole number from 0 to 150, for example 75."),
                        (flow is not None or not flow_text, "The flow rate must be a number from 0.5 to 1.5, for example 0.96."),
                        (note is not None, f"The drying note must be {MAX_TEXT_LENGTH} letters or fewer.")):
        if not ok:
            problems.append(message)
    extras = {"nozzle_temp": nozzle, "bed_temp": bed, "flow_rate": flow, "drying_note": note or None, "dry_after_days": dry_after}
    if not is_new:
        date_values, date_problems = read_spool_dates(form)
        extras.update(date_values)
        problems += date_problems
    return extras, problems


# Reads the optional "bottle opened on" date typed on "Edit material" for a resin bottle. Returns (date text or None, problems).
def read_bottle_date(form):
    text = (form.get("opened_date") or "").strip()
    opened = parse_day(text)
    if text and opened is None:
        return None, ["Please type the date like 2026-11-20 (year-month-day), or leave it empty."]
    if opened and opened > today_malaysia():
        return None, ["The opened date cannot be in the future."]
    return text or None, []


# Reads the two optional spool dates typed on "Edit material" (empty = not set). Returns (values, problems).
def read_spool_dates(form):
    opened_text, dried_text = (form.get("opened_date") or "").strip(), (form.get("last_dried_date") or "").strip()
    opened, dried = parse_day(opened_text), parse_day(dried_text)
    problems = []
    if (opened_text and opened is None) or (dried_text and dried is None):
        problems.append("Please type the spool dates like 2026-11-20 (year-month-day), or leave them empty.")
    elif opened and opened > today_malaysia() or dried and dried > today_malaysia():
        problems.append("A spool date cannot be in the future.")
    elif dried and not opened:
        problems.append("Please type the date it was opened too, because drying only counts for an opened spool.")
    elif dried and opened and dried < opened:
        problems.append("The last dried date cannot be earlier than the date it was opened.")
    return {"opened_date": opened_text or None, "last_dried_date": dried_text or None}, problems


# Records stock used or received: changes the quantity AND writes the history row. Returns True if it worked.
def record_stock_change(database, material, movement_type, quantity, note, user, supplier=None, total_cost=None,
                        reset_spool=False):
    if movement_type == "USED":
        changed = database.execute(
            "UPDATE materials SET quantity_on_hand = ROUND(quantity_on_hand - ?, 2), updated_at = ? "
            "WHERE id = ? AND is_active = 1 AND quantity_on_hand >= ?",
            (quantity, utc_now().strftime(TIME_FORMAT), material["id"], quantity)).rowcount
    else:
        changed = database.execute(
            "UPDATE materials SET quantity_on_hand = ROUND(quantity_on_hand + ?, 2), updated_at = ? "
            "WHERE id = ? AND is_active = 1",
            (quantity, utc_now().strftime(TIME_FORMAT), material["id"])).rowcount
    if changed == 0:
        database.rollback()
        return False
    movement_id = add_movement_rows(database, material, movement_type, quantity, note, user, supplier, total_cost)
    if movement_type == "USED":
        write_low_stock_event_if_needed(database, material, movement_id, user)
    if reset_spool and movement_type == "RECEIVED" and has_open_date(material):
        reset_spool_dates(database, material, user)
    database.commit()
    return True


# Makes a spool or bottle "Sealed" again: clears the opened and dried dates and writes the activity-log line (no commit here).
def reset_spool_dates(database, material, user):
    database.execute("UPDATE materials SET opened_date = NULL, last_dried_date = NULL, updated_at = ? WHERE id = ?",
                     (utc_now().strftime(TIME_FORMAT), material["id"]))
    write_material_log(database, user["id"], "SPOOL_RESET", material["id"],
                       f"New sealed {'bottle' if is_resin(material) else 'spool'} received: opened and dried dates of "
                       f"{material['name']} {material['colour'] or ''} cleared.".replace("  ", " "))


# Writes a low_stock_events row and an activity-log line if this material has just fallen from OK to LOW or OUT
# (no commit here). The row points to the USED movement that caused the drop.
def write_low_stock_event_if_needed(database, material, movement_id, user):
    after = database.execute("SELECT quantity_on_hand FROM materials WHERE id = ?", (material["id"],)).fetchone()[0]
    status_before = get_status(material["quantity_on_hand"], material["reorder_level"])
    status_after = get_status(after, material["reorder_level"])
    if status_before != STATUS_OK or status_after == STATUS_OK:
        return
    database.execute(
        "INSERT INTO low_stock_events (id, material_id, status, quantity_at_event, reorder_level_at_event, "
        "movement_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("E" + uuid.uuid4().hex[:12], material["id"], status_after, after, material["reorder_level"], movement_id,
         utc_now().strftime(TIME_FORMAT)))
    write_material_log(database, user["id"], "LOW_STOCK_EVENT", material["id"],
                       f"{material['name']} is now {status_after} ({after:g} {material['unit']}, "
                       f"reorder level {material['reorder_level']:g}).")


# Adds the stock_movements row and the activity_log row for one stock change (no commit here). Returns the movement id.
def add_movement_rows(database, material, movement_type, quantity, note, user, supplier=None, total_cost=None):
    now_text = utc_now().strftime(TIME_FORMAT)
    movement_id = "S" + uuid.uuid4().hex[:12]
    database.execute(
        "INSERT INTO stock_movements (id, material_id, movement_type, quantity, note, user_id, created_at, "
        "supplier_id, total_cost_myr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (movement_id, material["id"], movement_type, quantity, note, user["id"], now_text,
         supplier["id"] if supplier else None, total_cost))
    new_quantity = database.execute(
        "SELECT quantity_on_hand FROM materials WHERE id = ?", (material["id"],)).fetchone()[0]
    details = f"{MOVEMENT_WORDS[movement_type]} {quantity:g} {material['unit']} of {material['name']}. Now {new_quantity:g} {material['unit']}."
    if supplier is not None and total_cost is not None:
        details += f" Paid MYR {total_cost:.2f} to {supplier['name']}."
    write_material_log(database, user["id"], "STOCK_" + movement_type, material["id"], details)
    return movement_id


# Returns the search words as a safe database pattern (so % and _ typed by a person are plain letters).
def make_search_pattern(search_text):
    safe_text = search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + safe_text + "%"


# Template helper: True when a material row is a resin bottle (so its Edit form can show the "bottle opened on" box).
@materials_blueprint.app_template_test("resin_bottle")
def resin_bottle(material):
    return bool(material) and is_resin(material)


# Template word helper: shows "pcs" as the plain word "pieces" (g and ml stay as they are).
@materials_blueprint.app_template_filter("unit_word")
def unit_word(unit):
    return "pieces" if unit == "pcs" else unit


# Returns a plain "last bought" description for one material (supplier, amount, date, and money only if
# show_money is True), or None if nothing was ever received with a supplier or a cost.
def get_last_bought(database, material, show_money):
    row = database.execute(
        "SELECT m.quantity, m.total_cost_myr, m.created_at, s.name AS supplier_name FROM stock_movements m "
        "LEFT JOIN suppliers s ON s.id = m.supplier_id WHERE m.material_id = ? AND m.movement_type = 'RECEIVED' "
        "AND (m.supplier_id IS NOT NULL OR m.total_cost_myr IS NOT NULL) "
        "ORDER BY m.created_at DESC, m.rowid DESC LIMIT 1", (material["id"],)).fetchone()
    if row is None:
        return None
    return {"supplier": row["supplier_name"] or "a supplier that was not named",
            "amount": f"{row['quantity']:g} {unit_word(material['unit'])}", "when": to_malaysia_time(row["created_at"])[:11],
            "cost": row["total_cost_myr"] if show_money else None}


NOT_NAMED_SUPPLIER = "a supplier that was not named"     # the words get_last_bought uses when a purchase has no supplier


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


# Shows the table of all active materials, with the search box and the OK / LOW / OUT filter.
@materials_blueprint.route("/")
@login_required
def list_materials():
    search_text = request.args.get("q", "").strip()[:MAX_TEXT_LENGTH]
    status_filter = request.args.get("status", "")
    pattern = make_search_pattern(search_text)
    rows = get_db().execute(
        "SELECT * FROM materials WHERE is_active = 1 AND (name LIKE ? ESCAPE '\\' OR material_type LIKE ? ESCAPE '\\' "
        "OR colour LIKE ? ESCAPE '\\') ORDER BY name, colour", (pattern, pattern, pattern)).fetchall()
    materials = [add_status(row) for row in rows]
    urgency_order = {STATUS_OUT: 0, STATUS_LOW: 1, STATUS_OK: 2}
    materials.sort(key=lambda material: urgency_order[material["status"]])
    if status_filter in (STATUS_OK, STATUS_LOW, STATUS_OUT):
        materials = [m for m in materials if m["status"] == status_filter]
    materials = sort_ok_low_out(materials)
    today = today_malaysia()
    materials = [add_spool_care(material, today) for material in materials]      # EXPERIMENT 2026-11-26: spool chip + settings line
    show_money = can_see_prices(get_current_user())
    offer_supplier_names = get_offer_supplier_names(get_db())
    for material in materials:
        material["last_bought"] = get_last_bought(get_db(), material, show_money)
        material["supplier_name"] = pick_material_supplier(material, offer_supplier_names)
    # One Materials tab, two sections: only filament spools (grams) are "Filament"; resin, alcohol, hardware and the rest are "Other materials".
    top_section = [m for m in materials if is_filament(m) or is_resin(m)]
    sections = [("Filament & Resin", top_section),
                ("Other materials", [m for m in materials if m not in top_section])]
    return render_template("materials_list.html", materials=materials, sections=sections, search_text=search_text,
                           status_filter=status_filter, can_manage=can_manage_materials(get_current_user()))


# Shows the "Add material" form again, filled in, with the given problems (status 400 when there are some).
def show_new_material_form(problems):
    return render_template("materials_form.html", material=None, form=request.form, problems=problems,
                           units=UNITS, suppliers=get_active_suppliers(get_db())), (400 if problems else 200)


# Reads the optional "Who sells it?" part of the Add material form.
# Returns None if no supplier was chosen (or a problem was added to the list), otherwise a dictionary.
def read_supplier_part(form, database, problems):
    choice = form.get("supplier_choice", "")
    if not choice:
        return None
    part = {}
    try:
        if choice == NEW_SUPPLIER:
            part["supplier_fields"] = read_new_supplier_fields(form, database)
        else:
            part["supplier"] = database.execute(
                "SELECT id, name FROM suppliers WHERE id = ? AND is_active = 1", (choice,)).fetchone()
            if part["supplier"] is None:
                raise FormProblem("Please choose a supplier from the list.")
        part["offer_numbers"] = read_offer_numbers(form)
    except FormProblem as problem:
        problems.append(str(problem))
        return None
    return part


# Returns the checked details of a brand-new supplier from the Add material form (boxes start with "new_").
def read_new_supplier_fields(form, database):
    fields = read_supplier_form({name: form.get("new_" + name, "") for name in SUPPLIER_FIELDS})
    same_name = database.execute("SELECT 1 FROM suppliers WHERE lower(name) = lower(?)", (fields["name"],)).fetchone()
    if same_name:
        raise FormProblem("A supplier with that name already exists. Please choose it from the list instead.")
    return fields


# Saves the chosen or new supplier and the offer "this supplier sells this material" (no commit here).
def save_supplier_part(database, part, material_id, unit):
    if "supplier_fields" in part:
        supplier_id = insert_supplier(database, part["supplier_fields"])
        supplier_name = part["supplier_fields"]["name"]
    else:
        supplier_id, supplier_name = part["supplier"]["id"], part["supplier"]["name"]
    insert_offer(database, supplier_id, supplier_name,
                 {"material_id": material_id, "pack_unit": unit, **part["offer_numbers"]})
    return supplier_name


# Shows the "Add material" form (Admin only) and saves the new material, and optionally its supplier.
@materials_blueprint.route("/new", methods=["GET", "POST"])
@admin_required
def add_material():
    if request.method == "GET":
        return show_new_material_form([])
    database = get_db()
    values, problems = read_material_form(request.form, is_new=True)
    supplier_part = read_supplier_part(request.form, database, problems)
    if problems:
        return show_new_material_form(problems)
    material_id = save_new_material(database, values, get_current_user(), commit=False)
    message = f"Added {values['name']}."
    if supplier_part:
        supplier_name = save_supplier_part(database, supplier_part, material_id, values["unit"])
        message = f"Added {values['name']}, sold by {supplier_name}."
    database.commit()
    flash(message)
    return redirect(url_for("materials.list_materials"))


# Saves a new material and, if there is starting stock, a "starting stock" history row. Returns its id.
# With commit=False the caller saves everything together (so a problem later saves nothing).
def save_new_material(database, values, user, commit=True):
    material_id = "M" + uuid.uuid4().hex[:8]
    now_text = utc_now().strftime(TIME_FORMAT)
    database.execute(
        "INSERT INTO materials (id, name, material_type, colour, unit, quantity_on_hand, reorder_level, "
        "is_active, created_at, updated_at, nozzle_temp, bed_temp, flow_rate, drying_note, dry_after_days) "
        "VALUES (?, ?, ?, ?, ?, 0, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
        (material_id, values["name"], values["material_type"], values["colour"], values["unit"],
         values["reorder_level"], now_text, now_text, values.get("nozzle_temp"), values.get("bed_temp"),
         values.get("flow_rate"), values.get("drying_note"), values.get("dry_after_days")))
    write_material_log(database, user["id"], "MATERIAL_ADDED", material_id,
                       f"Added {values['name']} ({values['unit']}), reorder level {values['reorder_level']:g}.")
    if values["starting_quantity"] > 0:
        material = database.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        database.execute("UPDATE materials SET quantity_on_hand = ? WHERE id = ?", (values["starting_quantity"], material_id))
        add_movement_rows(database, material, "ADJUSTED", values["starting_quantity"], "Starting stock", user)
    if commit:
        database.commit()
    return material_id


# Shows the "Edit material" form (Admin only) and saves changes. Quantity and unit cannot be changed here.
@materials_blueprint.route("/<material_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_material(material_id):
    material = find_active_material(material_id)
    if request.method == "GET":
        return render_template("materials_form.html", material=material, form=material, problems=[], units=UNITS)
    values, problems = read_material_form(request.form, is_new=False, unit=material["unit"])
    if problems:
        return render_template("materials_form.html", material=material, form=request.form, problems=problems, units=UNITS), 400
    save_material_changes(get_db(), material, values, get_current_user())
    flash(f"Saved {values['name']}.")
    return redirect(url_for("materials.list_materials"))


# Saves the edited fields and writes what changed to the activity log.
def save_material_changes(database, material, values, user):
    database.execute(
        "UPDATE materials SET name = ?, material_type = ?, colour = ?, reorder_level = ?, updated_at = ? WHERE id = ?",
        (values["name"], values["material_type"], values["colour"], values["reorder_level"],
         utc_now().strftime(TIME_FORMAT), material["id"]))
    changes = []
    for field in ("name", "material_type", "colour", "reorder_level"):
        if material[field] != values[field]:
            changes.append(f"{field} from {material[field]} to {values[field]}")
    changes += save_filament_extras(database, material, values)
    write_material_log(database, user["id"], "MATERIAL_CHANGED", material["id"],
                       "Changed " + (", ".join(changes) if changes else "nothing") + f" for {material['name']}.")
    database.commit()


# EXPERIMENT 2026-11-26: saves the printer settings and spool dates of a filament item. Returns what changed (for the log).
def save_filament_extras(database, material, values):
    if is_resin(material):
        return save_bottle_date(database, material, values)
    if not is_filament(material):
        return []
    fields = ("nozzle_temp", "bed_temp", "flow_rate", "drying_note", "dry_after_days", "opened_date", "last_dried_date")
    database.execute("UPDATE materials SET nozzle_temp = ?, bed_temp = ?, flow_rate = ?, drying_note = ?, "
                     "dry_after_days = ?, opened_date = ?, last_dried_date = ? WHERE id = ?",
                     (*(values[field] for field in fields), material["id"]))
    return [f"{field} from {material[field]} to {values[field]}" for field in fields if material[field] != values[field]]


# Saves the corrected "bottle opened on" date of a resin bottle (only when the Edit form sent it). Returns what changed.
def save_bottle_date(database, material, values):
    if "opened_date" not in values or material["opened_date"] == values["opened_date"]:
        return []
    database.execute("UPDATE materials SET opened_date = ? WHERE id = ?", (values["opened_date"], material["id"]))
    return [f"opened_date from {material['opened_date']} to {values['opened_date']}"]


# Removes a material from the lists (Admin only). The row and its history stay; it is only switched off.
@materials_blueprint.route("/<material_id>/remove", methods=["POST"])
@admin_required
def remove_material(material_id):
    material = find_active_material(material_id)
    database = get_db()
    database.execute("UPDATE materials SET is_active = 0, updated_at = ? WHERE id = ?",
                     (utc_now().strftime(TIME_FORMAT), material["id"]))
    write_material_log(database, get_current_user()["id"], "MATERIAL_REMOVED", material["id"],
                       f"Removed {material['name']} from the lists (history kept).")
    database.commit()
    flash(f"Removed {material['name']} from the list. Its history is kept.")
    return redirect(url_for("materials.list_materials"))


# EXPERIMENT 2026-11-26: one-tap "Open Spool Today" / "Mark Dried Today" on a filament item (Admin and Employee).
# It only saves today's Malaysia date and writes a line to the activity log. Resin bottles get "Open Bottle Today" only (no drying);
# anything that is not filament or resin is refused (404).
@materials_blueprint.route("/<material_id>/spool/<action>", methods=["POST"])
@login_required
def spool_action(material_id, action):
    user = get_current_user()
    if not can_record_stock(user):
        abort(403)
    if action not in SPOOL_ACTIONS:
        abort(404)
    material = find_active_material(material_id)
    if not (is_filament(material) if action == "dried" else has_open_date(material)):
        abort(404)                      # "dried" is for filament only; "open" is for filament and resin only
    back = url_for("home") if request.form.get("back") == "home" else url_for("materials.list_materials")
    column, log_action, words = SPOOL_ACTIONS[action]
    if is_resin(material):
        log_action, words = "BOTTLE_OPENED", "Opened bottle of"
    if column == "opened_date" and material["opened_date"]:
        flash(f"{material['name']} was already opened on {material['opened_date']}. Nothing changed.")
    elif column == "last_dried_date" and not material["opened_date"]:
        flash(f"Press \"Open Spool Today\" first, then \"Mark Dried Today\" for {material['name']}.")
    else:
        save_spool_day(get_db(), material, column, log_action, words, user)
        flash(f"{words} {material['name']} today.")
    return redirect(back)


# Saves today's date in one spool column and writes the activity-log line (this function does the commit).
def save_spool_day(database, material, column, log_action, words, user):
    today_text = today_malaysia().strftime(DAY_FORMAT)
    database.execute(f"UPDATE materials SET {column} = ?, updated_at = ? WHERE id = ?",    # column comes from SPOOL_ACTIONS only
                     (today_text, utc_now().strftime(TIME_FORMAT), material["id"]))
    write_material_log(database, user["id"], log_action, material["id"],
                       f"{words} {material['name']} {material['colour'] or ''} on {today_text}.".replace("  ", " "))
    database.commit()


# Shows the "Record used" / "Record received" form and saves it (Admin and Employee).
@materials_blueprint.route("/<material_id>/record/<kind>", methods=["GET", "POST"])
@login_required
def record_stock(material_id, kind):
    user = get_current_user()
    if not can_record_stock(user):
        abort(403)
    if kind not in KIND_TO_MOVEMENT:
        abort(404)
    material = find_active_material(material_id)
    if request.method == "GET":
        return show_record_form(material, kind, [], "", {})
    reset_spool = kind == "received" and has_open_date(material) and request.form.get("new_sealed") == "yes"
    quantity = read_number(request.form.get("quantity"), allow_zero=False)
    note = read_text(request.form.get("note"), MAX_NOTE_LENGTH)
    problems = check_record_input(material, kind, quantity, note)
    supplier, total_cost = None, None
    if kind == "received" and not can_record_purchase_cost(user):
        if request.form.get("supplier_id") or request.form.get("total_cost"):
            abort(403)          # only the Admin may type money; never trust the page alone
    elif kind == "received":
        supplier, total_cost, purchase_problems = read_purchase_form(get_db(), request.form)
        problems += purchase_problems
    if not problems and not record_stock_change(get_db(), material, KIND_TO_MOVEMENT[kind], quantity, note, user,
                                                supplier, total_cost, reset_spool):
        problems = [f"There is not enough {material['name']} in stock to take out {quantity:g} {material['unit']}."]
    if problems:
        return show_record_form(material, kind, problems, request.form.get("quantity", ""), request.form), 400
    flash(f"{MOVEMENT_WORDS[KIND_TO_MOVEMENT[kind]]} {quantity:g} {material['unit']} of {material['name']}."
          + (" Marked as a new sealed " + ("bottle." if is_resin(material) else "spool.") if reset_spool else ""))
    return redirect(get_list_address())          # back to the SAME search the person had


# Returns the plain-language problems with a "record stock" form (an empty list if it is fine).
def check_record_input(material, kind, quantity, note):
    problems = []
    if quantity is None:
        problems.append(NUMBER_HELP.format(label="quantity") + " (more than 0).")
    elif kind == "used" and quantity > material["quantity_on_hand"]:
        problems.append(f"There is only {material['quantity_on_hand']:g} {material['unit']} of {material['name']} left, "
                        f"so you cannot take out {quantity:g}.")
    if note is None:
        problems.append(f"The note must be {MAX_NOTE_LENGTH} letters or fewer.")
    return problems


# Returns the active suppliers (for the "Bought from" list on the Record received form).
def get_active_suppliers(database):
    return database.execute("SELECT id, name, supplier_type FROM suppliers WHERE is_active = 1 ORDER BY name").fetchall()


# Reads the optional "Bought from" and "Total paid" boxes. Returns (supplier row or None, cost or None, problems).
def read_purchase_form(database, form):
    problems = []
    supplier = None
    supplier_id = (form.get("supplier_id") or "").strip()
    if supplier_id:
        supplier = database.execute("SELECT id, name FROM suppliers WHERE id = ? AND is_active = 1",
                                    (supplier_id,)).fetchone()
        if supplier is None:
            problems.append("Please choose a supplier from the list.")
    cost_text = (form.get("total_cost") or "").strip()
    total_cost = read_number(cost_text, allow_zero=True) if cost_text else None
    if cost_text and total_cost is None:
        problems.append(NUMBER_HELP.format(label="total paid") + " (0 or more).")
    elif total_cost is not None and supplier is None and not problems:
        problems.append("Please choose which supplier you paid, or leave the money box empty.")
    return supplier, total_cost, problems


# Shows the record form with the material's status and its last 10 history lines (in Malaysia time).
def show_record_form(material, kind, problems, typed_quantity, typed_form):
    can_enter_money = kind == "received" and can_record_purchase_cost(get_current_user())
    history = get_db().execute(
        "SELECT m.movement_type, m.quantity, m.note, m.created_at, u.username FROM stock_movements m "
        "JOIN users u ON u.id = m.user_id WHERE m.material_id = ? ORDER BY m.created_at DESC, m.rowid DESC LIMIT 10",
        (material["id"],)).fetchall()
    history_lines = []
    for row in history:
        word, amount = describe_movement(row["movement_type"], row["quantity"], row["note"])
        history_lines.append({"type": word, "amount": amount, "note": row["note"],
                              "when": to_malaysia_time(row["created_at"]), "who": row["username"]})
    material_with_status = add_status(material)
    last_bought = get_last_bought(get_db(), material_with_status, can_see_prices(get_current_user()))
    return render_template("materials_record.html", material=material_with_status, kind=kind, problems=problems,
                           typed_quantity=typed_quantity, history=history_lines, typed=typed_form, last_bought=last_bought,
                           can_enter_money=can_enter_money, suppliers=get_active_suppliers(get_db()) if can_enter_money else [],
                           can_reset_spool=kind == "received" and has_open_date(material),
                           reset_is_resin=is_resin(material), back_address=get_list_address())



# Returns the plain-language problems with the "Correct stock" form (an empty list if it is fine).
def check_correction_input(material, new_quantity, reason):
    problems = []
    if new_quantity is None:
        problems.append(NUMBER_HELP.format(label="real count") + " (0 or more).")
    elif new_quantity == material["quantity_on_hand"]:
        problems.append(f"The app already says {material['quantity_on_hand']:g} {material['unit']}. Nothing to correct.")
    if not reason:
        problems.append("Please type a short reason, for example \"Physical shelf count\".")
    elif len(reason) > MAX_NOTE_LENGTH:
        problems.append(f"The reason must be {MAX_NOTE_LENGTH} letters or fewer.")
    return problems


# Sets the stock to the real count: one ADJUSTED line (the size of the difference, the note says which way and why)
# and one activity-log line. Returns False if the stock changed while the Admin was typing (nothing is saved then).
def correct_stock(database, material, new_quantity, reason, user):
    old_quantity = material["quantity_on_hand"]
    difference = round(new_quantity - old_quantity, 2)
    now_text = utc_now().strftime(TIME_FORMAT)
    changed = database.execute("UPDATE materials SET quantity_on_hand = ?, updated_at = ? WHERE id = ? AND is_active = 1 "
                               "AND quantity_on_hand = ?", (new_quantity, now_text, material["id"], old_quantity)).rowcount
    if changed == 0:
        database.rollback()
        return False
    note = (f"{CORRECTION_PREFIX}: {old_quantity:g} -> {new_quantity:g} {material['unit']} "
            f"({difference:+g}). Reason: {reason}")
    database.execute("INSERT INTO stock_movements (id, material_id, movement_type, quantity, note, user_id, created_at) "
                     "VALUES (?, ?, 'ADJUSTED', ?, ?, ?, ?)",
                     ("S" + uuid.uuid4().hex[:12], material["id"], abs(difference), note, user["id"], now_text))
    write_material_log(database, user["id"], "STOCK_CORRECTED", material["id"],
                       f"{material['name']} corrected from {old_quantity:g} to {new_quantity:g} {material['unit']} "
                       f"({difference:+g}). Reason: {reason}")
    database.commit()
    return True


# Shows the Admin-only "Correct stock" form ("Set stock to") and saves it. Employees get 403 (page and save).
@materials_blueprint.route("/<material_id>/correct", methods=["GET", "POST"])
@login_required
def correct_stock_screen(material_id):
    user = get_current_user()
    if not can_correct_stock(user):
        abort(403)
    material = add_status(find_active_material(material_id))
    if request.method == "GET":
        return render_template("materials_correct.html", material=material, problems=[], typed={},
                               back_address=get_list_address())
    new_quantity = read_number(request.form.get("new_quantity"), allow_zero=True)
    reason = (request.form.get("reason") or "").strip()
    problems = check_correction_input(material, new_quantity, reason)
    if not problems and not correct_stock(get_db(), material, new_quantity, reason, user):
        problems = [f"The stock of {material['name']} changed while you were typing. Please check the number and try again."]
    if problems:
        return render_template("materials_correct.html", material=material, problems=problems, typed=request.form,
                               back_address=get_list_address()), 400
    flash(f"Stock of {material['name']} is now {new_quantity:g} {material['unit']}. The correction is saved in the history.")
    return redirect(get_list_address())

# WHAT THIS FILE DOES: The Materials screens: list with search and filter, add / edit / remove a material
#   (Admin), and "Record used" / "Record received" (everyone). Every stock change is written to the history.
# WHO CAN USE IT: Both. Adding, editing and removing is Admin only; recording stock is Admin and Employee.

import re
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.alerts import STATUS_LOW, STATUS_OK, STATUS_OUT, add_status, get_status, sort_ok_low_out
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import (admin_required, can_manage_materials, can_record_purchase_cost, can_record_stock,
                             can_see_prices, login_required)
from app.routes_suppliers import FormProblem, insert_offer, insert_supplier, read_offer_numbers, read_supplier_form

materials_blueprint = Blueprint("materials", __name__, url_prefix="/materials", template_folder="templates")

UNITS = ("g", "ml", "pcs")
MAX_NUMBER = 1000000
MAX_TEXT_LENGTH = 100
MAX_NOTE_LENGTH = 200
NUMBER_PATTERN = re.compile(r"^\d{1,7}(\.\d{1,2})?$")
MOVEMENT_WORDS = {"USED": "Used", "RECEIVED": "Received", "ADJUSTED": "Starting stock"}
KIND_TO_MOVEMENT = {"used": "USED", "received": "RECEIVED"}
NUMBER_HELP = "Please type the {label} as a number, for example 200"
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
def read_material_form(form, is_new):
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
    return values, problems


# Records stock used or received: changes the quantity AND writes the history row. Returns True if it worked.
def record_stock_change(database, material, movement_type, quantity, note, user, supplier=None, total_cost=None):
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
    database.commit()
    return True


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
    if status_filter in (STATUS_OK, STATUS_LOW, STATUS_OUT):
        materials = [m for m in materials if m["status"] == status_filter]
    materials = sort_ok_low_out(materials)
    show_money = can_see_prices(get_current_user())
    for material in materials:
        material["last_bought"] = get_last_bought(get_db(), material, show_money)
    return render_template("materials_list.html", materials=materials, search_text=search_text,
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
        "is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, 1, ?, ?)",
        (material_id, values["name"], values["material_type"], values["colour"], values["unit"],
         values["reorder_level"], now_text, now_text))
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
    values, problems = read_material_form(request.form, is_new=False)
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
    write_material_log(database, user["id"], "MATERIAL_CHANGED", material["id"],
                       "Changed " + (", ".join(changes) if changes else "nothing") + f" for {material['name']}.")
    database.commit()


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
                                                supplier, total_cost):
        problems = [f"There is not enough {material['name']} in stock to take out {quantity:g} {material['unit']}."]
    if problems:
        return show_record_form(material, kind, problems, request.form.get("quantity", ""), request.form), 400
    flash(f"{MOVEMENT_WORDS[KIND_TO_MOVEMENT[kind]]} {quantity:g} {material['unit']} of {material['name']}.")
    return redirect(url_for("materials.list_materials"))


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
    history_lines = [{"type": MOVEMENT_WORDS[row["movement_type"]], "quantity": row["quantity"], "note": row["note"],
                      "when": to_malaysia_time(row["created_at"]), "who": row["username"]} for row in history]
    material_with_status = add_status(material)
    last_bought = get_last_bought(get_db(), material_with_status, can_see_prices(get_current_user()))
    return render_template("materials_record.html", material=material_with_status, kind=kind, problems=problems,
                           typed_quantity=typed_quantity, history=history_lines, typed=typed_form, last_bought=last_bought,
                           can_enter_money=can_enter_money, suppliers=get_active_suppliers(get_db()) if can_enter_money else [])

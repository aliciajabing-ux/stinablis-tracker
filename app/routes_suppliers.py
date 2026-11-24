# WHAT THIS FILE DOES: The Suppliers screens (list, details, add/change supplier, add/change offer) and the "Find supplier" suggestion screen.
# WHO CAN USE IT: Both can look and get suggestions; only Admin can add, change or switch off (checked in permissions.py).

import uuid

from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.alerts import STATUS_OK, add_status
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import admin_required, can_manage_suppliers, can_see_prices, login_required
from app.suggest import get_suggestions

suppliers_blueprint = Blueprint("suppliers", __name__)

SUPPLIER_TYPES = ["LOCAL", "ONLINE"]
UNITS = ["g", "ml", "pcs"]


# Raised when a form field is wrong. The message is plain language shown to the person.
class FormProblem(Exception):
    pass


# Returns a text field, trimmed. Refuses empty (if required) or too long text.
def read_text(form, field, label, max_length, required=False):
    value = form.get(field, "").strip()
    if required and not value:
        raise FormProblem(f"Please fill in the {label}.")
    if len(value) > max_length:
        raise FormProblem(f"The {label} is too long. Please use at most {max_length} letters.")
    return value


# Returns a number from a form field. Refuses letters, negative numbers and silly sizes.
def read_number(form, field, label, whole_number=False, smallest=0, largest=1000000):
    text = form.get(field, "").strip()
    try:
        number = int(text) if whole_number else float(text)
    except ValueError:
        raise FormProblem(f"Please type the {label} as a number, for example 20.") from None
    if number != number or number < smallest or number > largest:
        raise FormProblem(f"The {label} must be a number from {smallest} to {largest}.")
    return number


# Returns the checked supplier fields from the form as a dictionary.
def read_supplier_form(form):
    supplier_type = form.get("supplier_type", "")
    if supplier_type not in SUPPLIER_TYPES:
        raise FormProblem("Please choose ONLINE or LOCAL.")
    return {
        "name": read_text(form, "name", "supplier name", 100, required=True),
        "supplier_type": supplier_type,
        "address": read_text(form, "address", "address", 200),
        "phone": read_text(form, "phone", "phone number", 30),
        "email": read_text(form, "email", "email", 100),
        "website": read_text(form, "website", "website", 200),
        "notes": read_text(form, "notes", "notes", 500),
    }


# Returns the checked offer fields from the form as a dictionary.
def read_offer_form(form, database):
    pack_unit = form.get("pack_unit", "")
    material = database.execute("SELECT id FROM materials WHERE id = ? AND is_active = 1",
                                (form.get("material_id", ""),)).fetchone()
    if pack_unit not in UNITS or material is None:
        raise FormProblem("Please choose a material and a unit.")
    return {
        "material_id": material["id"],
        "pack_unit": pack_unit,
        "pack_size": read_number(form, "pack_size", "pack size", smallest=0.001),
        "price_per_pack_myr": read_number(form, "price_per_pack_myr", "price"),
        "minimum_order_packs": read_number(form, "minimum_order_packs", "minimum order", True, smallest=1),
        "shipping_cost_myr": read_number(form, "shipping_cost_myr", "shipping cost"),
        "lead_time_days": read_number(form, "lead_time_days", "lead time in days", True, largest=365),
    }


# Writes one line to the activity log about a supplier or an offer (who, what, when).
def log_change(database, action, table_name, record_id, details):
    database.execute(
        "INSERT INTO activity_log (id, user_id, action, table_name, record_id, details, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("L" + uuid.uuid4().hex[:12], get_current_user()["id"], action, table_name, record_id, details,
         utc_now().strftime(TIME_FORMAT)),
    )


# Returns a new id such as "S006" or "O012": the letter plus the next free number.
def make_next_id(database, table_name, letter):
    ids = [row["id"] for row in database.execute(f"SELECT id FROM {table_name}")]
    numbers = [int(i[1:]) for i in ids if i[1:].isdigit()]
    return f"{letter}{max(numbers, default=0) + 1:03d}"


# Returns the supplier row, or stops with "not found" (Employees cannot open switched-off suppliers).
def get_supplier_or_404(database, supplier_id):
    supplier = database.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    if supplier is None or (supplier["is_active"] == 0 and not can_manage_suppliers(get_current_user())):
        abort(404)
    return supplier


# Returns the offers of one supplier. Price and shipping columns are read for Admin and Employee (see only).
def get_offers_for_supplier(database, supplier_id, show_prices):
    money = ", o.price_per_pack_myr, o.shipping_cost_myr" if show_prices else ""
    return database.execute(
        "SELECT o.id, o.material_id, o.pack_size, o.pack_unit, o.minimum_order_packs, o.lead_time_days, "
        f"o.is_active, m.name AS material_name, m.colour AS material_colour{money} "
        "FROM supplier_offers o JOIN materials m ON m.id = o.material_id "
        "WHERE o.supplier_id = ? ORDER BY m.name, m.colour", (supplier_id,)).fetchall()


# Returns the list of active materials for the "which material" drop-down.
def get_material_choices(database):
    return database.execute("SELECT id, name, colour, unit FROM materials WHERE is_active = 1 "
                            "ORDER BY name, colour").fetchall()


# Shows all suppliers (Admin also sees switched-off ones).
@suppliers_blueprint.route("/suppliers")
@login_required
def supplier_list():
    admin_view = can_manage_suppliers(get_current_user())
    query = "SELECT * FROM suppliers" + ("" if admin_view else " WHERE is_active = 1") + " ORDER BY name"
    return render_template("suppliers.html", suppliers=get_db().execute(query).fetchall())


# Shows one supplier with contact details and the materials it sells.
@suppliers_blueprint.route("/suppliers/<supplier_id>")
@login_required
def supplier_detail(supplier_id):
    database = get_db()
    supplier = get_supplier_or_404(database, supplier_id)
    show_prices = can_see_prices(get_current_user())
    can_manage = can_manage_suppliers(get_current_user())
    offers = get_offers_for_supplier(database, supplier_id, show_prices)
    if not can_manage:
        offers = [offer for offer in offers if offer["is_active"] == 1]
    return render_template("supplier_detail.html", supplier=supplier, offers=offers,
                           show_prices=show_prices, can_manage=can_manage)


# Admin only: shows the "Add supplier" form and saves a new supplier.
@suppliers_blueprint.route("/suppliers/new", methods=["GET", "POST"])
@admin_required
def supplier_new():
    if request.method == "GET":
        return render_template("supplier_form.html", supplier=None, message="")
    try:
        fields = read_supplier_form(request.form)
    except FormProblem as problem:
        return render_template("supplier_form.html", supplier=request.form, message=str(problem)), 400
    database = get_db()
    new_id = make_next_id(database, "suppliers", "S")
    database.execute("INSERT INTO suppliers (id, name, supplier_type, address, phone, email, website, notes) "
                     "VALUES (:id, :name, :supplier_type, :address, :phone, :email, :website, :notes)",
                     {**fields, "id": new_id})
    log_change(database, "SUPPLIER_ADDED", "suppliers", new_id, f"Added supplier {fields['name']}")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=new_id))


# Admin only: shows the "Change supplier" form and saves the changes.
@suppliers_blueprint.route("/suppliers/<supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def supplier_edit(supplier_id):
    database = get_db()
    supplier = get_supplier_or_404(database, supplier_id)
    if request.method == "GET":
        return render_template("supplier_form.html", supplier=supplier, message="")
    try:
        fields = read_supplier_form(request.form)
    except FormProblem as problem:
        return render_template("supplier_form.html", supplier=request.form, message=str(problem)), 400
    database.execute("UPDATE suppliers SET name=:name, supplier_type=:supplier_type, address=:address, "
                     "phone=:phone, email=:email, website=:website, notes=:notes, "
                     "updated_at=CURRENT_TIMESTAMP WHERE id=:id", {**fields, "id": supplier_id})
    log_change(database, "SUPPLIER_CHANGED", "suppliers", supplier_id, f"Changed supplier {fields['name']}")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier_id))


# Admin only: switches a supplier off or on (records are never deleted, Rule C9).
@suppliers_blueprint.route("/suppliers/<supplier_id>/switch", methods=["POST"])
@admin_required
def supplier_switch(supplier_id):
    database = get_db()
    supplier = get_supplier_or_404(database, supplier_id)
    new_state = 0 if supplier["is_active"] == 1 else 1
    database.execute("UPDATE suppliers SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (new_state, supplier_id))
    word = "SWITCHED_ON" if new_state else "SWITCHED_OFF"
    log_change(database, "SUPPLIER_" + word, "suppliers", supplier_id, f"Supplier {supplier['name']} {word.lower()}")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier_id))


# Admin only: shows the "Add offer" form and saves a new offer (a material this supplier sells).
@suppliers_blueprint.route("/suppliers/<supplier_id>/offers/new", methods=["GET", "POST"])
@admin_required
def offer_new(supplier_id):
    database = get_db()
    supplier = get_supplier_or_404(database, supplier_id)
    materials = get_material_choices(database)
    if request.method == "GET":
        return render_template("offer_form.html", supplier=supplier, offer=None, materials=materials, message="")
    try:
        fields = read_offer_form(request.form, database)
    except FormProblem as problem:
        return render_template("offer_form.html", supplier=supplier, offer=request.form, materials=materials,
                               message=str(problem)), 400
    new_id = make_next_id(database, "supplier_offers", "O")
    database.execute(
        "INSERT INTO supplier_offers (id, supplier_id, material_id, pack_size, pack_unit, price_per_pack_myr, "
        "minimum_order_packs, shipping_cost_myr, lead_time_days) VALUES (:id, :supplier_id, :material_id, "
        ":pack_size, :pack_unit, :price_per_pack_myr, :minimum_order_packs, :shipping_cost_myr, :lead_time_days)",
        {**fields, "id": new_id, "supplier_id": supplier_id})
    log_change(database, "OFFER_ADDED", "supplier_offers", new_id,
               f"{supplier['name']} sells {fields['material_id']} at MYR {fields['price_per_pack_myr']:.2f} per pack")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier_id))


# Admin only: shows the "Change offer" form and saves it. The old and new price go to the activity log.
@suppliers_blueprint.route("/offers/<offer_id>/edit", methods=["GET", "POST"])
@admin_required
def offer_edit(offer_id):
    database = get_db()
    offer = database.execute("SELECT * FROM supplier_offers WHERE id = ?", (offer_id,)).fetchone()
    if offer is None:
        abort(404)
    supplier = get_supplier_or_404(database, offer["supplier_id"])
    materials = get_material_choices(database)
    if request.method == "GET":
        return render_template("offer_form.html", supplier=supplier, offer=offer, materials=materials, message="")
    try:
        fields = read_offer_form(request.form, database)
    except FormProblem as problem:
        return render_template("offer_form.html", supplier=supplier, offer=request.form, materials=materials,
                               message=str(problem)), 400
    database.execute(
        "UPDATE supplier_offers SET material_id=:material_id, pack_size=:pack_size, pack_unit=:pack_unit, "
        "price_per_pack_myr=:price_per_pack_myr, minimum_order_packs=:minimum_order_packs, "
        "shipping_cost_myr=:shipping_cost_myr, lead_time_days=:lead_time_days WHERE id=:id",
        {**fields, "id": offer_id})
    log_change(database, "OFFER_CHANGED", "supplier_offers", offer_id,
               f"Price changed from MYR {offer['price_per_pack_myr']:.2f} to MYR {fields['price_per_pack_myr']:.2f} "
               f"({supplier['name']}, {fields['material_id']})")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier["id"]))


# Admin only: switches an offer off or on (never deleted, Rule C9).
@suppliers_blueprint.route("/offers/<offer_id>/switch", methods=["POST"])
@admin_required
def offer_switch(offer_id):
    database = get_db()
    offer = database.execute("SELECT * FROM supplier_offers WHERE id = ?", (offer_id,)).fetchone()
    if offer is None:
        abort(404)
    new_state = 0 if offer["is_active"] == 1 else 1
    database.execute("UPDATE supplier_offers SET is_active = ? WHERE id = ?", (new_state, offer_id))
    word = "ON" if new_state else "OFF"
    log_change(database, "OFFER_SWITCHED_" + word, "supplier_offers", offer_id, f"Offer {offer_id} switched {word.lower()}")
    database.commit()
    return redirect(url_for("suppliers.supplier_detail", supplier_id=offer["supplier_id"]))


# Shows the ranked supplier suggestions for one LOW or OUT material ("Find supplier").
@suppliers_blueprint.route("/suggest/<material_id>")
@login_required
def suggest_supplier(material_id):
    database = get_db()
    row = database.execute("SELECT * FROM materials WHERE id = ? AND is_active = 1", (material_id,)).fetchone()
    if row is None:
        abort(404)
    material = add_status(row)
    days_text = request.args.get("days", "").strip()
    days_allowed = int(days_text) if days_text.isdigit() and int(days_text) < 1000 else None
    show_prices = can_see_prices(get_current_user())
    suggestions = []
    if material["status"] != STATUS_OK:
        suggestions = get_suggestions(database, material, show_prices, days_allowed)
    return render_template("suggest.html", material=material, suggestions=suggestions,
                           show_prices=show_prices, days_allowed=days_allowed)

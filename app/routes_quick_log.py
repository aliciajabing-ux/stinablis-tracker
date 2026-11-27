# WHAT THIS FILE DOES: The "Quick log" page: a search box and, for every material, a number box and a "Record used" button
#   that saves the usage WITHOUT leaving the page. It uses the same checks and the same history as the normal Record used screen.
# WHO CAN USE IT: Both (Admin and Employee). It only records stock USED; it never shows money.

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from app.alerts import add_status
from app.auth import get_current_user, get_db
from app.permissions import can_record_stock, login_required
from app.routes_materials import (MAX_TEXT_LENGTH, MOVEMENT_WORDS, check_record_input, find_active_material,
                                  make_search_pattern, read_number, record_stock_change, unit_word)

quick_log_blueprint = Blueprint("quick_log", __name__, template_folder="templates")


# Returns True when the page's script asked for a JSON answer (so it can update the row without reloading).
def wants_json():
    return "application/json" in request.headers.get("Accept", "")


# Shows every active material (filtered by ?q=) with a quantity box and a "Record used" button.
@quick_log_blueprint.route("/quick-log")
@login_required
def quick_log_page():
    if not can_record_stock(get_current_user()):
        abort(403)
    search_text = request.args.get("q", "").strip()[:MAX_TEXT_LENGTH]
    pattern = make_search_pattern(search_text)
    rows = get_db().execute(
        "SELECT * FROM materials WHERE is_active = 1 AND (name LIKE ? ESCAPE '\\' OR material_type LIKE ? ESCAPE '\\' "
        "OR colour LIKE ? ESCAPE '\\') ORDER BY name, colour", (pattern, pattern, pattern)).fetchall()
    return render_template("quick_log.html", materials=[add_status(row) for row in rows], search_text=search_text)


# Records stock USED for one material. With the script it answers JSON (the page updates in place); without it, it
# flashes a message and comes back to the page with the same search.
@quick_log_blueprint.route("/quick-log/<material_id>", methods=["POST"])
@login_required
def quick_log_save(material_id):
    user = get_current_user()
    if not can_record_stock(user):
        abort(403)
    material = find_active_material(material_id)
    quantity = read_number(request.form.get("quantity"), allow_zero=False)
    problems = check_record_input(material, "used", quantity, "")
    if not problems and not record_stock_change(get_db(), material, "USED", quantity, "Quick log", user):
        problems = [f"There is not enough {material['name']} in stock to take out {quantity:g} {material['unit']}."]
    after = add_status(find_active_material(material_id))
    search_text = request.form.get("q", "").strip()[:MAX_TEXT_LENGTH]
    if problems:
        if wants_json():
            return jsonify(ok=False, problems=problems), 400
        flash(" ".join(problems))
        return redirect(url_for("quick_log.quick_log_page", q=search_text or None))
    message = f"{MOVEMENT_WORDS['USED']} {quantity:g} {material['unit']} of {material['name']}."
    if wants_json():
        return jsonify(ok=True, message=message, left=f"{after['quantity_on_hand']:g} {unit_word(after['unit'])}",
                       status=after["status"])
    flash(message)
    return redirect(url_for("quick_log.quick_log_page", q=search_text or None))

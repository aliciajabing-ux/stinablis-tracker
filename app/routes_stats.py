# WHAT THIS FILE DOES: The Home dashboard (four boxes and the "Notifications" list) and the Statistics screen
#   (usage, purchases, the delivery ranking, the supplier price comparison, and the CSV download).
# WHO CAN USE IT: Both. The money box is for Admin and Employee (view only); the price comparison and the CSV download are Admin only. All checked on the server.
#
# Money spent = the "Total paid" typed on each "Record received" line (with its supplier), added up per month.
# It feeds the Home box and the CSV. Procurement statistics (decision 2026-11-26) are built from the same lines:
# purchases per material (no money, both roles) and the supplier price comparison, as a table and as charts (Admin only).
# REMOVED on 2026-11-26 (team decision): the low-stock events chart, the spending per supplier chart and the spending
# per material chart. Low-stock events are still saved in low_stock_events (Agent C writes them); they are just not charted.

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, render_template, request

from app.alerts import count_materials_by_status, get_materials_needing_attention
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import admin_required, can_see_prices, is_admin, login_required

stats_blueprint = Blueprint("stats", __name__, url_prefix="/stats", template_folder="templates")

SPENDING_METHOD_CONFIRMED = True       # money spent = real totals typed on "Record received"
MALAYSIA_HOURS_AHEAD_OF_UTC = 8
PERIODS_SHOWN = 6                      # how many weeks or months the charts show
MOST_USED_MATERIALS_SHOWN = 8
SPREADSHEET_DANGER_STARTS = ("=", "+", "-", "@")


# Returns the current Malaysia time (UTC+8) as a datetime.
def malaysia_now():
    return utc_now() + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)


# Turns a UTC date text from the database into a Malaysia-time datetime.
def to_malaysia_time(utc_text):
    return datetime.strptime(utc_text, TIME_FORMAT) + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)


# Returns money as text, for example "MYR 72.00".
def format_money(amount):
    return "MYR {:,.2f}".format(amount)


# Returns the week (starting Monday) or month a Malaysia-time moment belongs to, as a date.
def period_start(moment, period):
    if period == "week":
        return moment.date() - timedelta(days=moment.weekday())
    return moment.date().replace(day=1)


# Returns the start dates of the last few weeks or months, oldest first, ending with the current one.
def recent_period_starts(period, today):
    starts = []
    current = period_start(datetime.combine(today, datetime.min.time()), period)
    for _ in range(PERIODS_SHOWN):
        starts.append(current)
        previous_day = current - timedelta(days=1 if period == "month" else 7)
        current = period_start(datetime.combine(previous_day, datetime.min.time()), period)
    return list(reversed(starts))


# Returns the words shown under a chart bar, for example "Nov 2026" or "Week of 17 Nov".
def period_label(start, period):
    if period == "week":
        return "Week of " + start.strftime("%d %b")
    return start.strftime("%b %Y")


# Returns the quantity of one kind of stock change (USED or RECEIVED) per material for each recent week or month.
# Only quantities are read here, never any money. Each bar group carries its unit for the pop-up text.
def get_quantity_by_period(database, movement_type, period, now=None):
    now = now or malaysia_now()
    starts = recent_period_starts(period, now.date())
    totals = {}
    rows = database.execute(
        "SELECT m.id, m.name, m.colour, m.unit, s.quantity, s.created_at FROM stock_movements s "
        "JOIN materials m ON m.id = s.material_id WHERE s.movement_type = ?", (movement_type,)).fetchall()
    for row in rows:
        start = period_start(to_malaysia_time(row["created_at"]), period)
        if start in starts:
            name = " ".join(part for part in (row["name"], row["colour"]) if part)
            entry = totals.setdefault(name + " (" + row["unit"] + ")", {"name": name, "unit": row["unit"], "by": {s: 0 for s in starts}})
            entry["by"][start] += row["quantity"]
    ranked = sorted(totals.items(), key=lambda item: -sum(item[1]["by"].values()))[:MOST_USED_MATERIALS_SHOWN]
    return {"labels": [period_label(s, period) for s in starts],
            "datasets": [{"label": label, "name": entry["name"], "unit": entry["unit"],
                          "data": [round(entry["by"][s], 2) for s in starts]} for label, entry in ranked]}


# Returns usage per material for each recent week or month, ready for the bar chart (no money inside).
def get_usage_by_period(database, period, now=None):
    return get_quantity_by_period(database, "USED", period, now)


# Returns the stock received per material for each recent month, ready for the bar chart (no money inside).
def get_purchases_by_material(database, now=None):
    return get_quantity_by_period(database, "RECEIVED", "month", now)


# Returns the materials that at least one active supplier sells, for the "choose a material" list (no prices read).
def get_ranking_materials(database):
    rows = database.execute(
        "SELECT DISTINCT m.id, m.name, m.colour, m.unit FROM materials m "
        "JOIN supplier_offers o ON o.material_id = m.id JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE m.is_active = 1 AND o.is_active = 1 AND s.is_active = 1 ORDER BY m.name, m.colour").fetchall()
    return [{"id": r["id"], "label": " ".join(p for p in (r["name"], r["colour"]) if p) + " (" + r["unit"] + ")"} for r in rows]


# Turns database rows (supplier, type, days) already sorted fastest first into ranked lines. Same days share a rank
# (1, 1, 3). The arrival date is today plus the days, rounded up (an estimate).
def build_ranking_rows(rows, today, is_average):
    ranked, previous_days, previous_rank = [], None, 0
    for position, row in enumerate(rows, start=1):
        days = round(row["days"], 1) if is_average else int(row["days"])
        rank = previous_rank if days == previous_days else position
        previous_days, previous_rank = days, rank
        arrival = today + timedelta(days=int(-(-days // 1)))
        days_text = "{:g} day".format(days) + ("" if days == 1 else "s") + (" on average" if is_average else "")
        ranked.append({"rank": rank, "supplier": row["name"], "type": row["supplier_type"].lower(),
                       "days_text": days_text, "arrival": arrival.strftime("%d %b")})
    return ranked


# Returns the suppliers ranked from the fastest to the slowest delivery. With a material id: the fastest days each
# active supplier offers for that material. With no id: the average over everything the supplier sells. No money.
def get_delivery_ranking(database, material_id="", today=None):
    today = today or malaysia_now().date()
    if material_id:
        rows = database.execute(
            "SELECT s.name, s.supplier_type, MIN(o.lead_time_days) AS days FROM supplier_offers o "
            "JOIN suppliers s ON s.id = o.supplier_id WHERE o.is_active = 1 AND s.is_active = 1 AND o.material_id = ? "
            "GROUP BY s.id ORDER BY days, s.name", (material_id,)).fetchall()
    else:
        rows = database.execute(
            "SELECT s.name, s.supplier_type, AVG(o.lead_time_days) AS days FROM supplier_offers o "
            "JOIN suppliers s ON s.id = o.supplier_id WHERE o.is_active = 1 AND s.is_active = 1 "
            "GROUP BY s.id ORDER BY days, s.name").fetchall()
    return {"is_average": not material_id, "rows": build_ranking_rows(rows, today, not material_id)}


# Returns the average delivery time in days for each active supplier (no prices read at all). Used by the CSV.
def get_average_lead_times(database):
    rows = database.execute(
        "SELECT s.name, s.supplier_type, AVG(o.lead_time_days) AS average_days "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.is_active = 1 AND s.is_active = 1 GROUP BY s.id ORDER BY average_days, s.name").fetchall()
    return {"labels": [r["name"] + " (" + r["supplier_type"].lower() + ")" for r in rows],
            "days": [round(r["average_days"], 1) for r in rows]}


# Returns {supplier name: MYR} of what was really paid for stock received in the month that starts on month_start.
# Only "Record received" lines where someone typed a supplier and a total are counted.
def get_spending_by_supplier(database, month_start):
    spending = {}
    rows = database.execute(
        "SELECT s.name AS supplier_name, m.total_cost_myr, m.created_at FROM stock_movements m "
        "JOIN suppliers s ON s.id = m.supplier_id "
        "WHERE m.movement_type = 'RECEIVED' AND m.total_cost_myr IS NOT NULL")
    for row in rows.fetchall():
        if period_start(to_malaysia_time(row["created_at"]), "month") != month_start:
            continue
        name = row["supplier_name"]
        spending[name] = spending.get(name, 0) + row["total_cost_myr"]
    return spending


# Returns the MYR really paid per material over the last few months (Admin only), biggest first.
# Only "Record received" lines where someone typed a total are counted; "purchases" counts those lines.
def get_spending_by_material(database, now=None):
    now = now or malaysia_now()
    starts = recent_period_starts("month", now.date())
    spent = {}
    rows = database.execute(
        "SELECT m.name, m.colour, m.unit, s.total_cost_myr, s.created_at FROM stock_movements s "
        "JOIN materials m ON m.id = s.material_id "
        "WHERE s.movement_type = 'RECEIVED' AND s.total_cost_myr IS NOT NULL").fetchall()
    for row in rows:
        if period_start(to_malaysia_time(row["created_at"]), "month") not in starts:
            continue
        label = " ".join(part for part in (row["name"], row["colour"]) if part) + " (" + row["unit"] + ")"
        entry = spent.setdefault(label, {"amount": 0, "purchases": 0})
        entry["amount"] += row["total_cost_myr"]
        entry["purchases"] += 1
    ranked = sorted(spent.items(), key=lambda item: -item[1]["amount"])
    return {"labels": [label for label, _ in ranked], "amounts": [round(e["amount"], 2) for _, e in ranked],
            "purchases": [e["purchases"] for _, e in ranked]}


# Returns how to show a price per unit in plain words: (how many units one price covers, the words).
def price_unit_words(unit):
    if unit == "g":
        return 1000, "per kg"
    if unit == "ml":
        return 1000, "per litre"
    return 1, "per piece"


# Returns the cheapest active supplier offer for a material as (supplier name, MYR per single unit), or None.
def find_cheapest_unit_offer(database, material_id, unit):
    return database.execute(
        "SELECT s.name AS supplier_name, o.price_per_pack_myr / o.pack_size AS price_per_unit "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.material_id = ? AND o.is_active = 1 AND s.is_active = 1 AND o.pack_unit = ? "
        "ORDER BY price_per_unit LIMIT 1", (material_id, unit)).fetchone()


# Returns the newest "Record received" line with a total paid for a material, or None.
def find_last_paid(database, material_id):
    return database.execute(
        "SELECT s.quantity, s.total_cost_myr, s.created_at, sup.name AS supplier_name FROM stock_movements s "
        "LEFT JOIN suppliers sup ON sup.id = s.supplier_id "
        "WHERE s.material_id = ? AND s.movement_type = 'RECEIVED' AND s.total_cost_myr IS NOT NULL AND s.quantity > 0 "
        "ORDER BY s.created_at DESC, s.rowid DESC LIMIT 1", (material_id,)).fetchone()


# Returns one material's numbers for the price comparison chart, or None when it has neither an offer nor a purchase.
# Prices are MYR per kg, per litre or per piece (Admin only; estimates, the offer is before shipping).
def build_chart_point(database, material):
    scale, words = price_unit_words(material["unit"])
    offer = find_cheapest_unit_offer(database, material["id"], material["unit"])
    paid = find_last_paid(database, material["id"])
    if offer is None and paid is None:
        return None
    name = " ".join(part for part in (material["name"], material["colour"]) if part)
    return {"group": "per_piece" if material["unit"] == "pcs" else "per_kg_litre",
            "label": name + " (" + words + ")", "words": words,
            "offer": round(offer["price_per_unit"] * scale, 2) if offer else None,
            "offer_supplier": offer["supplier_name"] if offer else "",
            "paid": round(paid["total_cost_myr"] / paid["quantity"] * scale, 2) if paid else None,
            "paid_supplier": (paid["supplier_name"] or "supplier not typed") if paid else "",
            "paid_date": to_malaysia_time(paid["created_at"]).strftime("%d %b %Y") if paid else ""}


# Returns the price comparison chart numbers in two groups: per kg or litre, and per piece (their prices are on very
# different scales, so each group gets its own chart). Admin only.
def get_price_comparison_chart(database):
    keys = ("labels", "words", "offer", "offer_supplier", "paid", "paid_supplier", "paid_date")
    groups = {"per_kg_litre": {key: [] for key in keys}, "per_piece": {key: [] for key in keys}}
    materials = database.execute(
        "SELECT id, name, colour, unit FROM materials WHERE is_active = 1 ORDER BY name, colour").fetchall()
    for material in materials:
        point = build_chart_point(database, material)
        if point is None:
            continue
        group = groups[point["group"]]
        group["labels"].append(point["label"])
        for key in keys[1:]:
            group[key].append(point[key])
    return groups


# Returns the Admin-only spending numbers for this month, or None if the team has not confirmed the method.
def get_month_spending(database):
    if not SPENDING_METHOD_CONFIRMED:
        return None
    by_supplier = get_spending_by_supplier(database, period_start(malaysia_now(), "month"))
    return {"by_supplier": by_supplier, "total": sum(by_supplier.values())}


# Shows the Home dashboard: four boxes and the "Notifications" list.
def show_dashboard():
    database = get_db()
    show_money = can_see_prices(get_current_user())
    context = {"counts": count_materials_by_status(database),
               "attention": get_materials_needing_attention(database),
               "show_money": show_money, "month_name": malaysia_now().strftime("%B %Y")}
    if show_money:
        spending = get_month_spending(database)
        context["month_total_text"] = format_money(spending["total"]) if spending else None
    return render_template("home.html", **context)


# Shows the Statistics page (the charts fetch their numbers from the data addresses below).
@stats_blueprint.route("/")
@login_required
def statistics_page():
    admin_tools = is_admin(get_current_user())
    return render_template("stats.html", show_admin_tools=admin_tools,
                           now_text=malaysia_now().strftime("%d %b %Y %H:%M"),
                           ranking_materials=get_ranking_materials(get_db()))


# Sends usage numbers (per week or month) to the bar chart.
@stats_blueprint.route("/data/usage")
@login_required
def usage_data():
    period = "week" if request.args.get("period") == "week" else "month"
    return jsonify(get_usage_by_period(get_db(), period))


# Sends the stock received per material per month to the purchases bar chart (quantities and units only, no money).
@stats_blueprint.route("/data/purchases")
@login_required
def purchases_data():
    return jsonify(get_purchases_by_material(get_db()))


# Sends the supplier price comparison numbers to the two price charts. Admin only.
@stats_blueprint.route("/data/price-comparison")
@admin_required
def price_comparison_data():
    return jsonify(get_price_comparison_chart(get_db()))


# Sends the delivery ranking (fastest supplier first) for the chosen material, or for all materials.
@stats_blueprint.route("/data/delivery-ranking")
@login_required
def delivery_ranking_data():
    return jsonify(get_delivery_ranking(get_db(), request.args.get("material", "")))


# Returns text that is safe to open in a spreadsheet (a leading = + - @ could run as a formula).
def make_cell_safe(value):
    text = str(value)
    return "'" + text if text.startswith(SPREADSHEET_DANGER_STARTS) else text


# Builds the CSV rows: usage per month, average delivery days, and spending (only once confirmed).
def build_export_rows(database):
    rows = [["Report", "Name", "Period", "Value", "Unit"]]
    usage = get_usage_by_period(database, "month")
    for dataset in usage["datasets"]:
        for label, amount in zip(usage["labels"], dataset["data"]):
            rows.append(["Used", dataset["name"], label, amount, dataset["unit"]])
    lead_times = get_average_lead_times(database)
    for name, days in zip(lead_times["labels"], lead_times["days"]):
        rows.append(["Average delivery time", name, "", days, "days"])
    spending = get_month_spending(database)
    for name, amount in (spending["by_supplier"].items() if spending else []):
        rows.append(["Spending this month", name, malaysia_now().strftime("%b %Y"), round(amount, 2), "MYR"])
    rows.extend(build_procurement_rows(database))
    return rows


# Builds the CSV rows for purchases per material and spending per material (the CSV is Admin only).
def build_procurement_rows(database):
    rows = []
    purchases = get_purchases_by_material(database)
    for dataset in purchases["datasets"]:
        for label, amount in zip(purchases["labels"], dataset["data"]):
            rows.append(["Purchased (received)", dataset["name"], label, amount, dataset["unit"]])
    spending = get_spending_by_material(database)
    for name, amount in zip(spending["labels"], spending["amounts"]):
        rows.append(["Spending per material (last 6 months)", name, "", amount, "MYR"])
    return rows


# Sends the spreadsheet (CSV) download. Admin only; Employees get "not allowed" (403).
@stats_blueprint.route("/export.csv")
@admin_required
def export_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in build_export_rows(get_db()):
        writer.writerow([make_cell_safe(cell) for cell in row])
    file_name = "stinablis-statistics-" + malaysia_now().date().strftime("%Y-%m-%d") + ".csv"
    return Response(buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=" + file_name})

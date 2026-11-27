# WHAT THIS FILE DOES: The Home dashboard (three boxes and the "Notifications" list) and the Statistics screen
#   (usage per unit, days of stock left, the delivery ranking, Admin-only spending and stock value, and the CSV download).
# WHO CAN USE IT: Both. The spending and stock value panel and the CSV download are Admin only, checked on the server.
#
# Money spent = the "Total paid" typed on each "Record received" line (with its supplier), added up per month.
# Stock value = stock on hand x the price per unit of the cheapest active supplier offer (an estimate, before shipping).
# REMOVED on 2026-11-26 and 2026-11-27 (team decisions): the low-stock events chart, the spending charts, the purchases
# chart and the price comparison charts. Low-stock events are still saved in low_stock_events; the CSV still lists
# purchases and spending per material.

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, render_template, request

from app.alerts import count_materials_by_status, get_materials_needing_attention
from app.spool_care import get_dryer_alerts, get_resin_alerts
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import admin_required, is_admin, login_required

stats_blueprint = Blueprint("stats", __name__, url_prefix="/stats", template_folder="templates")

SPENDING_METHOD_CONFIRMED = True       # money spent = real totals typed on "Record received"
MALAYSIA_HOURS_AHEAD_OF_UTC = 8
PERIODS_SHOWN = 6                      # how many weeks or months the charts show
MOST_USED_MATERIALS_SHOWN = 8
USAGE_UNITS = ("g", "ml", "pcs")       # the Unit choice on the usage chart; "g" (filament) is the default
DEFAULT_USAGE_UNIT = "g"
DAYS_LEFT_WINDOW_DAYS = 30             # average daily use is measured over the last 30 days
DAYS_LEFT_CLOSE_MARGIN_DAYS = 7        # "Low" badge: days left is within this many days of the supplier lead time (team guess)
SPREADSHEET_DANGER_STARTS = ("=", "+", "-", "@")


# Returns the current Malaysia time (UTC+8) as a datetime.
def malaysia_now():
    return utc_now() + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)


# Turns a UTC date text from the database into a Malaysia-time datetime.
def to_malaysia_time(utc_text):
    return datetime.strptime(utc_text, TIME_FORMAT) + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)


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
# With a unit ("g", "ml" or "pcs") only materials counted in that unit are read, so the bars share one scale.
def get_quantity_by_period(database, movement_type, period, now=None, unit=None):
    now = now or malaysia_now()
    starts = recent_period_starts(period, now.date())
    totals = {}
    sql = ("SELECT m.id, m.name, m.colour, m.unit, s.quantity, s.created_at FROM stock_movements s "
           "JOIN materials m ON m.id = s.material_id WHERE s.movement_type = ?")
    values = [movement_type]
    if unit:
        sql += " AND m.unit = ?"
        values.append(unit)
    rows = database.execute(sql, values).fetchall()
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
# With unit=None every unit is included (the CSV uses that); the chart always passes one unit.
def get_usage_by_period(database, period, now=None, unit=None):
    return get_quantity_by_period(database, "USED", period, now, unit)


# Returns the stock received per material for each recent month, ready for the bar chart (no money inside).
def get_purchases_by_material(database, now=None):
    return get_quantity_by_period(database, "RECEIVED", "month", now)


# Returns every active material for the "Rank suppliers for:" drop-down, A to Z (for example "ABS Grey", "PLA White").
# No prices are read. A material nobody sells simply shows an empty ranking.
def get_ranking_materials(database):
    rows = database.execute(
        "SELECT id, name, colour FROM materials WHERE is_active = 1 ORDER BY lower(name), lower(colour), id").fetchall()
    return [{"id": r["id"], "label": " ".join(p for p in (r["name"], r["colour"]) if p)} for r in rows]


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


# Returns the fastest delivery (days) of the active supplier offers for each material id, as {material id: days}.
def get_fastest_lead_times(database):
    rows = database.execute(
        "SELECT o.material_id, MIN(o.lead_time_days) AS days FROM supplier_offers o "
        "JOIN suppliers s ON s.id = o.supplier_id WHERE o.is_active = 1 AND s.is_active = 1 GROUP BY o.material_id").fetchall()
    return {row["material_id"]: row["days"] for row in rows}


# Returns the badge words for one material: "Order now" when the stock runs out no later than a delivery would arrive,
# "Low" when it is within a week of that, otherwise "". A material with no supplier has lead time 0 here.
def days_left_badge(days_left, lead_time_days):
    lead = lead_time_days or 0
    if days_left <= lead:
        return "Order now"
    if days_left <= lead + DAYS_LEFT_CLOSE_MARGIN_DAYS:
        return "Low"
    return ""


# Returns active materials USED in the last 30 days (Malaysia time) with their estimated days of stock left, fewest first.
# Average daily use = quantity used in the 30 days / 30. Days left = stock on hand / average daily use. No money.
def get_days_of_stock_left(database, now=None):
    now = now or malaysia_now()
    window_start = now - timedelta(days=DAYS_LEFT_WINDOW_DAYS)
    used = {}
    rows = database.execute(
        "SELECT material_id, quantity, created_at FROM stock_movements WHERE movement_type = 'USED'").fetchall()
    for row in rows:
        moment = to_malaysia_time(row["created_at"])
        if window_start < moment <= now:
            used[row["material_id"]] = used.get(row["material_id"], 0) + row["quantity"]
    lead_times = get_fastest_lead_times(database)
    result = []
    materials = database.execute(
        "SELECT id, name, colour, unit, quantity_on_hand FROM materials WHERE is_active = 1").fetchall()
    for material in materials:
        average_daily = used.get(material["id"], 0) / DAYS_LEFT_WINDOW_DAYS
        if average_daily <= 0:
            continue
        days_left = material["quantity_on_hand"] / average_daily
        lead_time = lead_times.get(material["id"])
        result.append({"name": " ".join(p for p in (material["name"], material["colour"]) if p),
                       "stock": material["quantity_on_hand"], "unit": material["unit"],
                       "average_daily": average_daily, "days_left": days_left, "lead_time_days": lead_time,
                       "badge": days_left_badge(days_left, lead_time)})
    result.sort(key=lambda item: (item["days_left"], item["name"]))
    return result


# Returns the estimated value of all stock on hand in MYR (Admin only): stock x the price per unit of the cheapest active
# supplier offer in the material's own unit (before shipping). Also says how many materials had no price and were left out.
def get_stock_value(database):
    total, priced, unpriced = 0.0, 0, 0
    materials = database.execute(
        "SELECT id, unit, quantity_on_hand FROM materials WHERE is_active = 1 AND quantity_on_hand > 0").fetchall()
    for material in materials:
        offer = find_cheapest_unit_offer(database, material["id"], material["unit"])
        if offer is None:
            unpriced += 1
            continue
        total += material["quantity_on_hand"] * offer["price_per_unit"]
        priced += 1
    return {"total": total, "priced": priced, "unpriced": unpriced}


# Returns the cheapest active supplier offer for a material as (supplier name, MYR per single unit), or None.
def find_cheapest_unit_offer(database, material_id, unit):
    return database.execute(
        "SELECT s.name AS supplier_name, o.price_per_pack_myr / o.pack_size AS price_per_unit "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.material_id = ? AND o.is_active = 1 AND s.is_active = 1 AND o.pack_unit = ? "
        "ORDER BY price_per_unit LIMIT 1", (material_id, unit)).fetchone()


# Returns the Admin-only "Spending & stock value" numbers: this month's spending by supplier (biggest first) and stock value.
def get_spending_and_stock_value(database):
    spending = get_month_spending(database) or {"by_supplier": {}, "total": 0}
    by_supplier = sorted(spending["by_supplier"].items(), key=lambda item: (-item[1], item[0]))
    return {"month": malaysia_now().strftime("%B %Y"), "spent_total": spending["total"],
            "spent_by_supplier": by_supplier, "stock": get_stock_value(database)}


# Returns the Admin-only spending numbers for this month, or None if the team has not confirmed the method.
def get_month_spending(database):
    if not SPENDING_METHOD_CONFIRMED:
        return None
    by_supplier = get_spending_by_supplier(database, period_start(malaysia_now(), "month"))
    return {"by_supplier": by_supplier, "total": sum(by_supplier.values())}


# Shows the Home dashboard: three boxes and the "Notifications" list.
def show_dashboard():
    database = get_db()
    return render_template("home.html", counts=count_materials_by_status(database),
                           attention=get_materials_needing_attention(database),
                           dryer_alerts=get_dryer_alerts(database),      # EXPERIMENT 2026-11-26: spools to dry before use
                           resin_alerts=get_resin_alerts(database))      # 2026-11-27: resin bottles open 180 days or more


# Shows the Statistics page (the charts fetch their numbers from the data addresses below).
@stats_blueprint.route("/")
@login_required
def statistics_page():
    admin_tools = is_admin(get_current_user())
    database = get_db()
    ranking_materials = get_ranking_materials(database)
    chosen_material = request.args.get("material", "")
    if chosen_material not in [material["id"] for material in ranking_materials]:
        chosen_material = ""                  # an unknown ?material= falls back to "All materials (average)"
    return render_template("stats.html", show_admin_tools=admin_tools,
                           now_text=malaysia_now().strftime("%d %b %Y %H:%M"),
                           ranking_materials=ranking_materials, chosen_material=chosen_material,
                           ranking=get_delivery_ranking(database, chosen_material),
                           days_left_rows=get_days_of_stock_left(database),
                           lead_margin_days=DAYS_LEFT_CLOSE_MARGIN_DAYS,
                           money=get_spending_and_stock_value(database) if admin_tools else None)


# Sends usage numbers (?period=week|month and ?unit=g|ml|pcs) to the bar chart. A wrong value falls back to month and g.
@stats_blueprint.route("/data/usage")
@login_required
def usage_data():
    period = "week" if request.args.get("period") == "week" else "month"
    unit = request.args.get("unit")
    unit = unit if unit in USAGE_UNITS else DEFAULT_USAGE_UNIT
    return jsonify(get_usage_by_period(get_db(), period, unit=unit))


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

# WHAT THIS FILE DOES: The Home dashboard (four boxes and the "Needs attention" list) and the Statistics screen
#   (usage chart, low-stock chart, spending, average delivery time, and the CSV download).
# WHO CAN USE IT: Both. Money (spending box, spending chart, CSV download) is Admin only, checked on the server.
#
# Two things are NOT confirmed by the team yet (guide Rule R4), so the screens say "not set up yet":
#   1. How "money spent" is worked out (SPENDING_METHOD_CONFIRMED).
#   2. How a "low-stock event" is counted (LOW_EVENTS_METHOD_CONFIRMED).
# The proposed methods are written below and tested, but switched off. See the STATUS LOG questions.

import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, render_template, request

from app.alerts import (STATUS_OK, count_materials_by_status, get_materials_needing_attention,
                        get_status)
from app.auth import TIME_FORMAT, get_current_user, get_db, utc_now
from app.permissions import admin_required, can_see_prices, is_admin, login_required

stats_blueprint = Blueprint("stats", __name__, url_prefix="/stats", template_folder="templates")

SPENDING_METHOD_CONFIRMED = False      # team must answer the STATUS LOG question first
LOW_EVENTS_METHOD_CONFIRMED = False    # team must answer the STATUS LOG question first
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


# Returns usage per material for each recent week or month, ready for the bar chart (no money inside).
def get_usage_by_period(database, period, now=None):
    now = now or malaysia_now()
    starts = recent_period_starts(period, now.date())
    totals = {}
    rows = database.execute(
        "SELECT m.id, m.name, m.colour, m.unit, s.quantity, s.created_at FROM stock_movements s "
        "JOIN materials m ON m.id = s.material_id WHERE s.movement_type = 'USED'").fetchall()
    for row in rows:
        start = period_start(to_malaysia_time(row["created_at"]), period)
        if start in starts:
            name = " ".join(part for part in (row["name"], row["colour"]) if part) + " (" + row["unit"] + ")"
            totals.setdefault(name, {s: 0 for s in starts})[start] += row["quantity"]
    ranked = sorted(totals.items(), key=lambda item: -sum(item[1].values()))[:MOST_USED_MATERIALS_SHOWN]
    return {"labels": [period_label(s, period) for s in starts],
            "datasets": [{"label": name, "data": [round(by_start[s], 2) for s in starts]}
                         for name, by_start in ranked]}


# Returns every stock change of every material in time order, with the material's reorder level.
def read_stock_history(database):
    return database.execute(
        "SELECT s.material_id, s.movement_type, s.quantity, s.created_at, m.reorder_level "
        "FROM stock_movements s JOIN materials m ON m.id = s.material_id "
        "ORDER BY s.created_at, s.id").fetchall()


# PROPOSED (not confirmed): a low-stock event is one USED row that moves a material from OK to LOW or OUT.
# Returns {month start date: number of events}. Starting stock and received stock add; used stock subtracts.
def count_low_stock_events(database):
    quantity = {}
    events = {}
    for row in read_stock_history(database):
        before = quantity.get(row["material_id"], 0)
        sign = -1 if row["movement_type"] == "USED" else 1
        after = before + sign * row["quantity"]
        quantity[row["material_id"]] = after
        went_low = get_status(before, row["reorder_level"]) == STATUS_OK and \
            get_status(after, row["reorder_level"]) != STATUS_OK
        if row["movement_type"] == "USED" and went_low:
            month = period_start(to_malaysia_time(row["created_at"]), "month")
            events[month] = events.get(month, 0) + 1
    return events


# Returns the low-stock events per month for the line chart (counts only, no money).
def get_low_stock_chart(database, now=None):
    now = now or malaysia_now()
    starts = recent_period_starts("month", now.date())
    events = count_low_stock_events(database)
    return {"labels": [period_label(s, "month") for s in starts],
            "counts": [events.get(s, 0) for s in starts]}


# Returns the average delivery time in days for each active supplier (no prices read at all).
def get_average_lead_times(database):
    rows = database.execute(
        "SELECT s.name, s.supplier_type, AVG(o.lead_time_days) AS average_days "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.is_active = 1 AND s.is_active = 1 GROUP BY s.id ORDER BY average_days, s.name").fetchall()
    return {"labels": [r["name"] + " (" + r["supplier_type"].lower() + ")" for r in rows],
            "days": [round(r["average_days"], 1) for r in rows]}


# Returns the cheapest-per-unit active offer for a material (supplier name, price per unit), or None.
def find_cheapest_offer(database, material_id):
    return database.execute(
        "SELECT s.name AS supplier_name, o.price_per_pack_myr / o.pack_size AS price_per_unit "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "JOIN materials m ON m.id = o.material_id "
        "WHERE o.material_id = ? AND o.is_active = 1 AND o.pack_unit = m.unit "
        "ORDER BY price_per_unit LIMIT 1", (material_id,)).fetchone()


# PROPOSED (not confirmed): money spent = RECEIVED quantity x cheapest active offer's price per unit.
# Returns {supplier name: MYR} for received stock in the month that starts on month_start.
def get_spending_by_supplier(database, month_start):
    spending = {}
    rows = database.execute(
        "SELECT material_id, quantity, created_at FROM stock_movements WHERE movement_type = 'RECEIVED'")
    for row in rows.fetchall():
        if period_start(to_malaysia_time(row["created_at"]), "month") != month_start:
            continue
        offer = find_cheapest_offer(database, row["material_id"])
        if offer is not None:
            name = offer["supplier_name"]
            spending[name] = spending.get(name, 0) + row["quantity"] * offer["price_per_unit"]
    return spending


# Returns the Admin-only spending numbers for this month, or None if the team has not confirmed the method.
def get_month_spending(database):
    if not SPENDING_METHOD_CONFIRMED:
        return None
    by_supplier = get_spending_by_supplier(database, period_start(malaysia_now(), "month"))
    return {"by_supplier": by_supplier, "total": sum(by_supplier.values())}


# Shows the Home dashboard: four boxes and the "Needs attention" list.
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
    return render_template("stats.html", show_admin_tools=is_admin(get_current_user()),
                           now_text=malaysia_now().strftime("%d %b %Y %H:%M"),
                           spending_ready=SPENDING_METHOD_CONFIRMED,
                           low_events_ready=LOW_EVENTS_METHOD_CONFIRMED)


# Sends usage numbers (per week or month) to the bar chart.
@stats_blueprint.route("/data/usage")
@login_required
def usage_data():
    period = "week" if request.args.get("period") == "week" else "month"
    return jsonify(get_usage_by_period(get_db(), period))


# Sends low-stock events per month to the line chart (empty until the team confirms the counting rule).
@stats_blueprint.route("/data/low-stock")
@login_required
def low_stock_data():
    if not LOW_EVENTS_METHOD_CONFIRMED:
        return jsonify({"labels": [], "counts": []})
    return jsonify(get_low_stock_chart(get_db()))


# Sends average delivery days per supplier to the chart.
@stats_blueprint.route("/data/lead-times")
@login_required
def lead_time_data():
    return jsonify(get_average_lead_times(get_db()))


# Sends spending per supplier this month to the chart. Admin only.
@stats_blueprint.route("/data/spending")
@admin_required
def spending_data():
    spending = get_month_spending(get_db())
    by_supplier = spending["by_supplier"] if spending else {}
    return jsonify({"labels": list(by_supplier), "amounts": [round(v, 2) for v in by_supplier.values()]})


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
            rows.append(["Used", dataset["label"], label, amount, ""])
    lead_times = get_average_lead_times(database)
    for name, days in zip(lead_times["labels"], lead_times["days"]):
        rows.append(["Average delivery time", name, "", days, "days"])
    spending = get_month_spending(database)
    for name, amount in (spending["by_supplier"].items() if spending else []):
        rows.append(["Spending this month", name, malaysia_now().strftime("%b %Y"), round(amount, 2), "MYR"])
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

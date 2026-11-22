# WHAT THIS FILE DOES: Picks the best supplier to order from for a material that is LOW or OUT, and works out the estimated cost and arrival date.
# WHO CAN USE IT: Both (Admin sees costs; Employee gets the same list with the money numbers removed).
#
# The rules (guide Sections 5 F6 and 7). All numbers are ESTIMATES.
#   Quantity needed = (reorder level x 2) minus current quantity, rounded UP to whole packs
#                     (and never fewer packs than the supplier's minimum order).  [CONFIRM with founder]
#   Cost            = number of packs x price per pack + shipping cost.
#   Arrival date    = today (Malaysia time) + the supplier's lead time in days.
#   Best order      = 1. only suppliers that can deliver in time, 2. lowest cost, 3. shortest lead time.

import math
from datetime import timedelta

from app.auth import utc_now

MALAYSIA_HOURS_AHEAD_OF_UTC = 8
MONEY_KEYS = ["price_per_pack_myr", "shipping_cost_myr", "estimated_cost_myr"]


# Returns today's date in Malaysia time (UTC+8).
def get_today_in_malaysia():
    return (utc_now() + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)).date()


# Returns how much of the material we want to buy: (reorder level x 2) minus what we have, never below zero.
def get_quantity_needed(material):
    return max(material["reorder_level"] * 2 - material["quantity_on_hand"], 0)


# Returns how many packs to buy: enough to cover the quantity needed, and at least the supplier's minimum.
def get_packs_to_order(quantity_needed, pack_size, minimum_order_packs):
    packs_for_quantity = math.ceil(quantity_needed / pack_size)
    return max(packs_for_quantity, minimum_order_packs)


# Returns the estimated cost in MYR: number of packs x price per pack, plus shipping.
def get_estimated_cost(packs_to_order, price_per_pack_myr, shipping_cost_myr):
    return round(packs_to_order * price_per_pack_myr + shipping_cost_myr, 2)


# Returns one suggestion (a dictionary) that describes what ordering from one supplier would look like.
def build_suggestion(offer, material, today):
    quantity_needed = get_quantity_needed(material)
    packs = get_packs_to_order(quantity_needed, offer["pack_size"], offer["minimum_order_packs"])
    return {
        "supplier_id": offer["supplier_id"],
        "supplier_name": offer["supplier_name"],
        "supplier_type": offer["supplier_type"],
        "phone": offer["phone"],
        "email": offer["email"],
        "website": offer["website"],
        "address": offer["address"],
        "pack_size": offer["pack_size"],
        "pack_unit": offer["pack_unit"],
        "packs_to_order": packs,
        "lead_time_days": offer["lead_time_days"],
        "arrival_date": today + timedelta(days=offer["lead_time_days"]),
        "price_per_pack_myr": offer["price_per_pack_myr"],
        "shipping_cost_myr": offer["shipping_cost_myr"],
        "estimated_cost_myr": get_estimated_cost(packs, offer["price_per_pack_myr"], offer["shipping_cost_myr"]),
    }


# Returns the active offers for one material from active suppliers, using the same unit as the material.
def find_offers_for_material(database, material):
    return database.execute(
        "SELECT o.*, s.name AS supplier_name, s.supplier_type, s.phone, s.email, s.website, s.address "
        "FROM supplier_offers o JOIN suppliers s ON s.id = o.supplier_id "
        "WHERE o.material_id = ? AND o.is_active = 1 AND s.is_active = 1 AND o.pack_unit = ?",
        (material["id"], material["unit"]),
    ).fetchall()


# Returns the suggestions sorted best first: in time, then lowest cost, then shortest lead time.
# "days_allowed" is how many days the person can wait; None means any lead time is fine.
def sort_suggestions(suggestions, days_allowed=None):
    if days_allowed is not None:
        suggestions = [s for s in suggestions if s["lead_time_days"] <= days_allowed]
    return sorted(suggestions, key=lambda s: (s["estimated_cost_myr"], s["lead_time_days"]))


# Returns the same suggestions with every money number taken out (for Employee accounts).
def remove_money(suggestions):
    return [{key: value for key, value in s.items() if key not in MONEY_KEYS} for s in suggestions]


# Returns the ranked suggestions for one material (a database row). Money is removed unless show_prices is True.
def get_suggestions(database, material, show_prices, days_allowed=None, today=None):
    today = today or get_today_in_malaysia()
    offers = find_offers_for_material(database, material)
    suggestions = [build_suggestion(offer, material, today) for offer in offers]
    ranked = sort_suggestions(suggestions, days_allowed)
    return ranked if show_prices else remove_money(ranked)

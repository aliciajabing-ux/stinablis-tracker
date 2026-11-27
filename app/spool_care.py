# WHAT THIS FILE DOES: Works out "spool care" for filament items (how long a spool has been open, and whether it should go
#   in a dry box or a dryer) and writes the one-line "saved printer settings" summary. Filament = only items counted in grams (spools).
#   Resin, alcohol and other liquids (ml) and hardware (pieces) are never filament.
# WHO CAN USE IT: Both (Admin and Employee see the chips; the numbers are plain days, no money).
#
# EXPERIMENT (branch exp-spool-care-preview, 2026-11-26). The two day limits are a team guess, to be confirmed with the founder:
#   Sealed (never opened)  -> "Sealed"
#   open for less than 7 days -> "Open Xd"
#   open for 7 days or more   -> "Open Xd - Dry box recommended"
#   open for 21 days or more  -> "Open Xd - Put in dryer before use"
# X = days since the LATER of the open date and the last dried date (drying "restarts the clock").

from datetime import datetime, timedelta

from app.auth import utc_now

DRY_BOX_AFTER_DAYS = 7
DRYER_AFTER_DAYS = 21
FILAMENT_UNIT = "g"
DAY_FORMAT = "%Y-%m-%d"
MALAYSIA_HOURS_AHEAD_OF_UTC = 8
DEGREE_C = "°C"
DOT = "·"


# Returns today's date in Malaysia (UTC+8), the day that spool dates are counted in.
def today_malaysia():
    return (utc_now() + timedelta(hours=MALAYSIA_HOURS_AHEAD_OF_UTC)).date()


# Turns "2026-11-20" into a date, or returns None if the text is empty or not a real date.
def parse_day(text):
    try:
        return datetime.strptime((text or "").strip(), DAY_FORMAT).date()
    except ValueError:
        return None


# Returns True only for filament spools (counted in grams). Resin and alcohol (ml) and hardware (pcs) are never touched by spool care.
def is_filament(material):
    return material["unit"] == FILAMENT_UNIT


# Returns the spool-care facts for one filament item, or None for anything else. "today" can be given for tests.
def get_spool_care(material, today=None):
    if not is_filament(material):
        return None
    today = today or today_malaysia()
    opened = parse_day(material["opened_date"])
    if opened is None:
        return {"state": "sealed", "days": None, "chip": "Sealed", "needs_dryer": False,
                "can_open": True, "can_dry": False}
    started = max(opened, parse_day(material["last_dried_date"]) or opened)
    days = max((today - started).days, 0)
    state = "dryer" if days >= DRYER_AFTER_DAYS else "dry_box" if days >= DRY_BOX_AFTER_DAYS else "open"
    advice = {"dryer": "Put in dryer before use", "dry_box": "Dry box recommended", "open": ""}[state]
    chip = f"Open {days}d {DOT} {advice}" if advice else f"Open {days}d"
    return {"state": state, "days": days, "chip": chip, "needs_dryer": state == "dryer",
            "can_open": False, "can_dry": True}


# Returns the saved printer settings as one line, for example "Nozzle 235 C - Bed 75 C - Flow 0.96 - Dry 65 C / 6h".
# Returns None for hardware or when nothing was saved.
def format_printer_settings(material):
    if not is_filament(material):
        return None
    parts = []
    if material["nozzle_temp"] is not None:
        parts.append(f"Nozzle {material['nozzle_temp']:g} {DEGREE_C}")
    if material["bed_temp"] is not None:
        parts.append(f"Bed {material['bed_temp']:g} {DEGREE_C}")
    if material["flow_rate"] is not None:
        parts.append(f"Flow {material['flow_rate']:g}")
    if (material["drying_note"] or "").strip():
        parts.append("Dry " + material["drying_note"].strip())
    return f" {DOT} ".join(parts) or None


# Returns a dictionary copy of a material row with its spool care ("care") and settings line ("settings_line") added.
def add_spool_care(material_row, today=None):
    material = dict(material_row)
    material["care"] = get_spool_care(material, today)
    material["settings_line"] = format_printer_settings(material)
    return material


# Returns the active filament items that must go in a dryer before use (for the Home Notifications), longest open first.
def get_dryer_alerts(database, today=None):
    rows = database.execute(
        "SELECT * FROM materials WHERE is_active = 1 AND unit = 'g' AND opened_date IS NOT NULL").fetchall()
    cared = [add_spool_care(row, today) for row in rows]
    return sorted((m for m in cared if m["care"]["needs_dryer"]), key=lambda m: -m["care"]["days"])

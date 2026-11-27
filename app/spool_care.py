# WHAT THIS FILE DOES: Works out "spool care" for filament spools (open, dry box, dryer) and "bottle care" for resin bottles
#   (sealed, open, check after 180 days; never any drying), and writes the "saved printer settings" line (filament only).
# WHO CAN USE IT: Both (Admin and Employee see the chips; the numbers are plain days, no money).
# Filament = items in grams. Resin = a liquid (ml) with "resin" in its type or name. Alcohol and hardware get no care at all.
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
RESIN_UNIT = "ml"
RESIN_WORD = "resin"
RESIN_CHECK_AFTER_DAYS = 180      # an opened resin bottle is "check before print" from this many days (team guess, R4)
DASH = "\u2014"
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


# Returns True for resin bottles: a liquid (ml) with the word "resin" in its type or name. Isopropyl alcohol is NOT resin.
def is_resin(material):
    if material["unit"] != RESIN_UNIT:
        return False
    words = f"{_text(material, 'material_type')} {_text(material, 'name')}".lower()
    return RESIN_WORD in words


# Returns one text column of a material (row or dictionary), or "" when it is missing or empty.
def _text(material, column):
    try:
        return material[column] or ""
    except (KeyError, IndexError):
        return ""


# Returns True for anything that has a "Open ... Today" button: filament spools and resin bottles. Nothing else.
def has_open_date(material):
    return is_filament(material) or is_resin(material)


# Returns the bottle facts for one resin item: sealed, open, or aged (opened 180 days ago or more). No drying for resin.
def get_resin_care(material, today=None):
    today = today or today_malaysia()
    opened = parse_day(material["opened_date"])
    if opened is None:
        return {"kind": "resin", "state": "sealed", "days": None, "chip": "Sealed bottle", "needs_dryer": False,
                "needs_check": False, "can_open": True, "can_dry": False, "open_label": "Open Bottle Today"}
    days = max((today - opened).days, 0)
    aged = days >= RESIN_CHECK_AFTER_DAYS
    chip = f"Open {days}d {DASH} check resin" if aged else f"Bottle open {days}d"
    return {"kind": "resin", "state": "aged" if aged else "open", "days": days, "chip": chip, "needs_dryer": False,
            "needs_check": aged, "can_open": False, "can_dry": False, "open_label": "Open Bottle Today"}


# Returns the spool-care facts for one filament spool or resin bottle, or None for anything else. "today" can be given for tests.
def get_spool_care(material, today=None):
    if is_resin(material):
        return get_resin_care(material, today)
    if not is_filament(material):
        return None
    today = today or today_malaysia()
    opened = parse_day(material["opened_date"])
    if opened is None:
        return {"kind": "filament", "state": "sealed", "days": None, "chip": "Sealed", "needs_dryer": False,
                "needs_check": False, "can_open": True, "can_dry": False, "open_label": "Open Spool Today"}
    started = max(opened, parse_day(material["last_dried_date"]) or opened)
    days = max((today - started).days, 0)
    state = "dryer" if days >= DRYER_AFTER_DAYS else "dry_box" if days >= DRY_BOX_AFTER_DAYS else "open"
    advice = {"dryer": "Put in dryer before use", "dry_box": "Dry box recommended", "open": ""}[state]
    chip = f"Open {days}d {DOT} {advice}" if advice else f"Open {days}d"
    return {"kind": "filament", "state": state, "days": days, "chip": chip, "needs_dryer": state == "dryer",
            "needs_check": False, "can_open": False, "can_dry": True, "open_label": "Open Spool Today"}


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


# Returns the active resin bottles that have been open 180 days or more (for the Home Notifications), longest open first.
# This is NOT a drying alert: resin is never dried.
def get_resin_alerts(database, today=None):
    rows = database.execute(
        "SELECT * FROM materials WHERE is_active = 1 AND unit = 'ml' AND opened_date IS NOT NULL").fetchall()
    cared = [add_spool_care(row, today) for row in rows if is_resin(row)]
    return sorted((m for m in cared if m["care"]["needs_check"]), key=lambda m: -m["care"]["days"])

# WHAT THIS FILE DOES: Turns a supplier's phone number and email into tap-able links (tel:, WhatsApp, mailto:).
# WHO CAN USE IT: Both (Admin and Employee see the same links; seeing contact details is not changing them).
#
# Rules: a value that does not look like a phone number or an email is left as plain text (no link).
# WhatsApp (https://wa.me/<digits>) needs the country code and digits only. Malaysia is +60, so a local
# number that starts with a single 0 (for example 082-111 222) becomes 6082111222.

import re

from flask import Blueprint

contact_blueprint = Blueprint("contact_links", __name__)

MALAYSIA_CODE = "60"
SHORTEST_PHONE_DIGITS = 8
LONGEST_PHONE_DIGITS = 15
EMAIL_PATTERN = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")


# Returns only the digits of a phone number, or "" if it does not look like one (too short or too long).
def get_phone_digits(phone):
    digits = re.sub(r"\D", "", phone or "")
    if not SHORTEST_PHONE_DIGITS <= len(digits) <= LONGEST_PHONE_DIGITS:
        return ""
    return digits


# Returns the "tel:" address for a phone number (a leading + is kept), or "" if it is not a phone number.
def get_tel_address(phone):
    digits = get_phone_digits(phone)
    if not digits:
        return ""
    return "tel:" + ("+" if (phone or "").strip().startswith("+") else "") + digits


# Returns the WhatsApp address (https://wa.me/<digits only>) for a phone number, or "" if it is not a phone number.
def get_whatsapp_address(phone):
    digits = get_phone_digits(phone)
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]                                   # 0060... is the same as +60...
    elif digits.startswith("0"):
        digits = MALAYSIA_CODE + digits[1:]                   # local Malaysian number
    return "https://wa.me/" + digits


# Returns the "mailto:" address for an email, or "" if the text does not look like an email.
def get_mailto_address(email):
    email = (email or "").strip()
    return "mailto:" + email if EMAIL_PATTERN.match(email) else ""


# Gives the templates the three helpers (used by the contact_links.html macros).
@contact_blueprint.app_template_filter("tel_address")
def tel_address_filter(phone):
    return get_tel_address(phone)


@contact_blueprint.app_template_filter("whatsapp_address")
def whatsapp_address_filter(phone):
    return get_whatsapp_address(phone)


@contact_blueprint.app_template_filter("mailto_address")
def mailto_address_filter(email):
    return get_mailto_address(email)

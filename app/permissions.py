# WHAT THIS FILE DOES: Holds the rules of who can do what. Every screen file asks this file before acting.
# WHO CAN USE IT: Both (it is the gatekeeper for Admin and Employee).
#
# Rule: if in doubt, DENY. Anyone not logged in, switched off, or with an unknown role gets nothing.

from functools import wraps

from flask import abort, redirect, request, url_for

from app.auth import get_current_user

ADMIN_ROLE = "ADMIN"
EMPLOYEE_ROLE = "EMPLOYEE"


# Returns True if the user is an active admin, otherwise False.
def is_admin(user):
    return user is not None and user["is_active"] == 1 and user["role"] == ADMIN_ROLE


# Returns True if the user is an active employee, otherwise False.
def is_employee(user):
    return user is not None and user["is_active"] == 1 and user["role"] == EMPLOYEE_ROLE


# Returns True if the user may SEE supplier prices, shipping costs and money totals (Admin and Employee,
# team decision 2026-11-24). Seeing is not changing: only Admin can change prices.
def can_see_prices(user):
    return is_admin(user) or is_employee(user)


# Returns True if the user may add, change or remove materials (Admin only).
def can_manage_materials(user):
    return is_admin(user)


# Returns True if the user may add, change or remove suppliers and their offers (Admin only).
def can_manage_suppliers(user):
    return is_admin(user)


# Returns True if the user may create, change or switch off accounts (Admin only).
def can_manage_users(user):
    return is_admin(user)


# Returns True if the user may read the activity log (Admin only).
def can_view_activity_log(user):
    return is_admin(user)


# Returns True if the user may record stock used or received (Admin and Employee).
def can_record_stock(user):
    return is_admin(user) or is_employee(user)


# Page guard: the person must be logged in, otherwise they are sent to the login page.
def login_required(view_function):
    @wraps(view_function)
    def checked_view(*args, **kwargs):
        if get_current_user() is None:
            return redirect(url_for("auth.login"))
        return view_function(*args, **kwargs)
    return checked_view


# Page guard: the person must be an Admin. Employees get a plain "not allowed" page (403).
def admin_required(view_function):
    @wraps(view_function)
    def checked_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("auth.login"))
        if not is_admin(user):
            abort(403)
        return view_function(*args, **kwargs)
    return checked_view

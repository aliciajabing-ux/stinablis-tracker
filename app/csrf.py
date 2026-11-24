# WHAT THIS FILE DOES: Protects every form that changes data from "forged" requests sent by other websites (CSRF).
# WHO CAN USE IT: Both (it runs automatically for Admin and Employee, and on the login page).
#
# How it works in plain words: each browser session gets a secret random code. Every form carries that
# code in a hidden box. When a form is sent, the server compares the two. A bad website cannot know the
# code, so its fake form is refused.

import hmac
import secrets

from flask import abort, request, session

TOKEN_SESSION_KEY = "csrf_token"
TOKEN_FORM_FIELD = "csrf_token"
TOKEN_HEADER = "X-CSRF-Token"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


# Returns this browser session's secret code, making a new one the first time.
def get_csrf_token():
    if TOKEN_SESSION_KEY not in session:
        session[TOKEN_SESSION_KEY] = secrets.token_hex(32)
    return session[TOKEN_SESSION_KEY]


# Returns True if the code sent with the request matches the one saved in the session.
def request_has_valid_token():
    saved_token = session.get(TOKEN_SESSION_KEY)
    sent_token = request.form.get(TOKEN_FORM_FIELD) or request.headers.get(TOKEN_HEADER)
    if not saved_token or not sent_token:
        return False
    return hmac.compare_digest(saved_token, sent_token)


# Starts CSRF protection on the website: checks every change, and gives templates {{ csrf_token() }}.
def start_csrf_protection(website):
    # Runs before every request: refuses any change (POST etc.) that does not carry the right code.
    @website.before_request
    def check_csrf_token():
        if not website.config.get("CSRF_ENABLED", True):
            return
        if request.method in SAFE_METHODS:
            return
        if not request_has_valid_token():
            abort(400, description="This page has expired. Please go back, reload the page and try again.")

    @website.context_processor
    def add_csrf_token_to_templates():
        return {"csrf_token": get_csrf_token}

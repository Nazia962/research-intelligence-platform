"""Pro licence keys without user accounts.

A key looks like  RIP-PRO-20271231-NAZIA-ABCDEFGHIJKL  and is signed with
LICENSE_SECRET, so it cannot be forged without that secret. Generate keys with
`python make_license.py`. Keys expire, can be revoked via LICENSE_REVOKED, and
are remembered per private workspace link.
"""
import base64
import hashlib
import hmac
import re
from datetime import date, datetime, timedelta

from . import config, db


def _sign(payload):
    digest = hmac.new(config.LICENSE_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.b32encode(digest).decode().rstrip("=")[:12]


def make_key(customer, days=30, plan="PRO", today=None):
    if not config.LICENSE_SECRET:
        raise ValueError("Set LICENSE_SECRET in .env first.")
    expiry = ((today or date.today()) + timedelta(days=days)).strftime("%Y%m%d")
    cid = re.sub(r"[^A-Za-z0-9]", "", customer).upper()[:12] or "USER"
    payload = f"RIP-{plan}-{expiry}-{cid}"
    return f"{payload}-{_sign(payload)}"


def verify_key(key, today=None):
    """Return (valid, message, expiry_date_or_None)."""
    if not config.MONETIZATION_ENABLED:
        return False, "Licences are disabled (LICENSE_SECRET is not set).", None
    key = (key or "").strip().upper()
    parts = key.split("-")
    if len(parts) != 5 or parts[0] != "RIP":
        return False, "That does not look like a valid key.", None
    payload, sig = "-".join(parts[:4]), parts[4]
    if not hmac.compare_digest(sig, _sign(payload)):
        return False, "That key is not valid.", None
    try:
        expiry = datetime.strptime(parts[2], "%Y%m%d").date()
    except ValueError:
        return False, "That key is not valid.", None
    if key in config.LICENSE_REVOKED:
        return False, "That key has been revoked.", None
    if expiry < (today or date.today()):
        return False, f"That key expired on {expiry:%d %b %Y}.", expiry
    return True, f"Pro is active until {expiry:%d %b %Y}.", expiry


def activate(owner, key):
    ok, msg, _ = verify_key(key)
    if ok:
        db.license_set(owner, key.strip().upper())
    return ok, msg


def current_plan(owner):
    """'open' (limits switched off), 'pro' or 'free'."""
    if not config.MONETIZATION_ENABLED:
        return "open"
    key = db.license_get(owner)
    return "pro" if key and verify_key(key)[0] else "free"


def plan_info(owner):
    key = db.license_get(owner) if config.MONETIZATION_ENABLED else ""
    return verify_key(key) if key else (False, "", None)

"""Local account authentication for the Streamlit MVP.

For public production deployment, replace this with a mature identity provider and
secure server-side sessions. Passwords are never stored in plain text.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
from services import config


def _connect():
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created REAL NOT NULL DEFAULT (strftime('%s','now'))
    )""")
    conn.commit()
    return conn


def _valid_email(email):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email or ""))


def create_user(name, email, password):
    name = (name or "").strip()[:80]
    email = (email or "").strip().lower()
    if len(name) < 2:
        return False, "Please enter your name (at least 2 characters)."
    if not _valid_email(email):
        return False, "Enter a valid email address."
    if len(password or "") < 8:
        return False, "Use a password with at least 8 characters."
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    conn = _connect()
    try:
        conn.execute("INSERT INTO users(email, display_name, password_hash, salt) VALUES(?,?,?,?)",
                     (email, name, hashed.hex(), salt.hex()))
        conn.commit()
        return True, {"email": email, "name": name}
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists. Please sign in."
    finally:
        conn.close()


def authenticate(email, password):
    email = (email or "").strip().lower()
    conn = _connect()
    try:
        row = conn.execute("SELECT email, display_name, password_hash, salt FROM users WHERE email=?", (email,)).fetchone()
    finally:
        conn.close()
    # Do a hash even for an unknown account to reduce obvious timing differences.
    salt = bytes.fromhex(row[3]) if row else b"research-platform-dummy-salt"
    expected = row[2] if row else "0" * 64
    actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, 310_000).hex()
    if not hmac.compare_digest(actual, expected):
        return False, "Email or password is incorrect."
    return True, {"email": row[0], "name": row[1]}

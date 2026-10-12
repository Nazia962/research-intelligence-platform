"""Tiny SQLite layer: cache, usage counters, licences, full-text store.
Workspaces use the same database (see workspace_service.py)."""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import date

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS fulltext (
    key TEXT PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
    day TEXT NOT NULL, owner TEXT NOT NULL, calls INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, owner));
CREATE TABLE IF NOT EXISTS licenses (
    owner TEXT PRIMARY KEY, license_key TEXT NOT NULL, activated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, name TEXT NOT NULL,
    created REAL NOT NULL, updated REAL NOT NULL, UNIQUE (owner, name));
CREATE TABLE IF NOT EXISTS ws_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER NOT NULL,
    paper_key TEXT NOT NULL, paper_json TEXT NOT NULL, added REAL NOT NULL,
    UNIQUE (workspace_id, paper_key));
CREATE TABLE IF NOT EXISTS ws_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER NOT NULL,
    paper_key TEXT, kind TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
    created REAL NOT NULL);
"""

_ready_for = None


@contextmanager
def connect():
    """Yield a connection (committed on success, always closed)."""
    global _ready_for
    path = config.DB_PATH
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        if _ready_for != str(path):
            conn.executescript(SCHEMA)
            conn.execute("DELETE FROM cache WHERE created < ?", (time.time() - 60 * 86400,))
            conn.commit()
            _ready_for = str(path)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- cache ---------------------------------------------------------------
def cache_get(key, max_age=None):
    with connect() as c:
        row = c.execute("SELECT value, created FROM cache WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    if max_age is not None and time.time() - row["created"] > max_age:
        return None
    try:
        return json.loads(row["value"])
    except ValueError:
        return None


def cache_set(key, value):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO cache (key, value, created) VALUES (?,?,?)",
                  (key, json.dumps(value, ensure_ascii=False), time.time()))


# ---- full text (uploaded PDFs and fetched papers) -------------------------
def fulltext_get(key):
    with connect() as c:
        row = c.execute("SELECT text FROM fulltext WHERE key=?", (key,)).fetchone()
    return row["text"] if row else ""


def fulltext_set(key, text):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO fulltext (key, text, created) VALUES (?,?,?)",
                  (key, text, time.time()))


# ---- usage counters --------------------------------------------------------
def _today():
    return date.today().isoformat()


def usage_count(owner):
    with connect() as c:
        row = c.execute("SELECT calls FROM usage WHERE day=? AND owner=?", (_today(), owner)).fetchone()
    return row["calls"] if row else 0


def usage_total():
    with connect() as c:
        row = c.execute("SELECT COALESCE(SUM(calls),0) AS n FROM usage WHERE day=?", (_today(),)).fetchone()
    return row["n"]


def usage_add(owner, n=1):
    with connect() as c:
        c.execute("INSERT INTO usage (day, owner, calls) VALUES (?,?,?) "
                  "ON CONFLICT(day, owner) DO UPDATE SET calls = calls + excluded.calls",
                  (_today(), owner, n))


# ---- licences ---------------------------------------------------------------
def license_get(owner):
    with connect() as c:
        row = c.execute("SELECT license_key FROM licenses WHERE owner=?", (owner,)).fetchone()
    return row["license_key"] if row else ""


def license_set(owner, key):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO licenses (owner, license_key, activated) VALUES (?,?,?)",
                  (owner, key, time.time()))

"""Saved research workspaces. No login: every workspace belongs to a private
'owner code' kept in the page URL (?space=...), and every call checks it."""
import json
import time

from . import db
from .paper_model import make_key, new_paper, safe_url

KINDS = {"analysis": "AI analysis", "gaps": "Research gaps", "plan": "Project plan",
         "comparison": "Paper comparison", "note": "Note"}
MAX_IMPORT_PAPERS, MAX_IMPORT_ITEMS, MAX_TEXT = 200, 500, 200_000


def _owns(conn, owner, ws_id):
    return conn.execute("SELECT 1 FROM workspaces WHERE id=? AND owner=?", (ws_id, owner)).fetchone() is not None


def list_workspaces(owner):
    with db.connect() as c:
        rows = c.execute(
            "SELECT w.id, w.name, w.updated, "
            "(SELECT COUNT(*) FROM ws_papers p WHERE p.workspace_id=w.id) AS papers, "
            "(SELECT COUNT(*) FROM ws_items i WHERE i.workspace_id=w.id) AS items "
            "FROM workspaces w WHERE w.owner=? ORDER BY w.updated DESC", (owner,)).fetchall()
    return [dict(r) for r in rows]


def create_workspace(owner, name):
    name = " ".join((name or "").split())[:80]
    if not name:
        return None, "Please give the workspace a name."
    now = time.time()
    with db.connect() as c:
        if c.execute("SELECT 1 FROM workspaces WHERE owner=? AND name=?", (owner, name)).fetchone():
            return None, "You already have a workspace with that name."
        cur = c.execute("INSERT INTO workspaces (owner, name, created, updated) VALUES (?,?,?,?)", (owner, name, now, now))
        return cur.lastrowid, ""


def rename_workspace(owner, ws_id, name):
    name = " ".join((name or "").split())[:80]
    if not name:
        return False
    with db.connect() as c:
        try:
            cur = c.execute("UPDATE workspaces SET name=?, updated=? WHERE id=? AND owner=?", (name, time.time(), ws_id, owner))
        except Exception:
            return False
        return cur.rowcount > 0


def delete_workspace(owner, ws_id):
    with db.connect() as c:
        if not _owns(c, owner, ws_id):
            return
        c.execute("DELETE FROM ws_papers WHERE workspace_id=?", (ws_id,))
        c.execute("DELETE FROM ws_items WHERE workspace_id=?", (ws_id,))
        c.execute("DELETE FROM workspaces WHERE id=?", (ws_id,))


def _touch(conn, ws_id):
    conn.execute("UPDATE workspaces SET updated=? WHERE id=?", (time.time(), ws_id))


def add_papers(owner, ws_id, papers, max_papers=None):
    """Add papers; returns (added, skipped_existing, skipped_over_limit)."""
    added = dup = over = 0
    with db.connect() as c:
        if not _owns(c, owner, ws_id):
            return 0, 0, 0
        count = c.execute("SELECT COUNT(*) AS n FROM ws_papers WHERE workspace_id=?", (ws_id,)).fetchone()["n"]
        for p in papers:
            if c.execute("SELECT 1 FROM ws_papers WHERE workspace_id=? AND paper_key=?", (ws_id, p["key"])).fetchone():
                dup += 1
            elif max_papers is not None and count >= max_papers:
                over += 1
            else:
                c.execute("INSERT INTO ws_papers (workspace_id, paper_key, paper_json, added) VALUES (?,?,?,?)",
                          (ws_id, p["key"], json.dumps(p, ensure_ascii=False), time.time()))
                count += 1
                added += 1
        _touch(c, ws_id)
    return added, dup, over


def list_papers(owner, ws_id):
    with db.connect() as c:
        if not _owns(c, owner, ws_id):
            return []
        rows = c.execute("SELECT paper_json FROM ws_papers WHERE workspace_id=? ORDER BY added DESC", (ws_id,)).fetchall()
    return [json.loads(r["paper_json"]) for r in rows]


def remove_paper(owner, ws_id, paper_key):
    with db.connect() as c:
        if _owns(c, owner, ws_id):
            c.execute("DELETE FROM ws_papers WHERE workspace_id=? AND paper_key=?", (ws_id, paper_key))
            _touch(c, ws_id)


def save_item(owner, ws_id, kind, title, content, paper_key=None):
    if kind not in KINDS or not (content or "").strip():
        return None
    with db.connect() as c:
        if not _owns(c, owner, ws_id):
            return None
        cur = c.execute("INSERT INTO ws_items (workspace_id, paper_key, kind, title, content, created) VALUES (?,?,?,?,?,?)",
                        (ws_id, paper_key, kind, (title or KINDS[kind])[:200], content[:MAX_TEXT], time.time()))
        _touch(c, ws_id)
        return cur.lastrowid


def list_items(owner, ws_id, kind=None):
    with db.connect() as c:
        if not _owns(c, owner, ws_id):
            return []
        sql, args = "SELECT * FROM ws_items WHERE workspace_id=?", [ws_id]
        if kind:
            sql, args = sql + " AND kind=?", args + [kind]
        rows = c.execute(sql + " ORDER BY created DESC", args).fetchall()
    return [dict(r) for r in rows]


def delete_item(owner, ws_id, item_id):
    with db.connect() as c:
        if _owns(c, owner, ws_id):
            c.execute("DELETE FROM ws_items WHERE id=? AND workspace_id=?", (item_id, ws_id))


# --------------------------------------------------------- backup / restore
def export_json(owner, ws_id):
    with db.connect() as c:
        row = c.execute("SELECT name FROM workspaces WHERE id=? AND owner=?", (ws_id, owner)).fetchone()
    if not row:
        return ""
    items = [{k: i[k] for k in ("kind", "title", "content", "paper_key", "created")} for i in list_items(owner, ws_id)]
    return json.dumps({"app": "research-intelligence-platform", "version": 1, "name": row["name"],
                       "papers": list_papers(owner, ws_id), "items": items}, ensure_ascii=False, indent=2)


def import_json(owner, text, max_papers=None):
    """Create a new workspace from a backup file. Returns (ws_id, message)."""
    try:
        data = json.loads(text)
        assert isinstance(data, dict) and data.get("app") == "research-intelligence-platform"
        raw_papers, raw_items = list(data.get("papers", []))[:MAX_IMPORT_PAPERS], list(data.get("items", []))[:MAX_IMPORT_ITEMS]
    except (ValueError, AssertionError, TypeError):
        return None, "That file is not a workspace backup from this app."
    base = " ".join(str(data.get("name", "Imported workspace")).split())[:70] or "Imported workspace"
    ws_id = None
    for n in range(50):
        ws_id, _ = create_workspace(owner, base if n == 0 else f"{base} (imported {n})")
        if ws_id:
            break
    if ws_id is None:
        return None, "Could not create a workspace."
    allowed = set(new_paper().keys()) - {"is_survey"}
    papers = []
    for p in raw_papers:
        if isinstance(p, dict) and p.get("title"):
            paper = new_paper(**{k: v for k, v in p.items() if k in allowed})
            paper["url"], paper["pdf_url"] = safe_url(paper["url"]), safe_url(paper["pdf_url"])
            paper["key"] = str(p.get("key") or make_key(paper["doi"], paper["title"]))[:32]
            papers.append(paper)
    add_papers(owner, ws_id, papers, max_papers)
    for it in raw_items:
        if isinstance(it, dict):
            save_item(owner, ws_id, it.get("kind", "note") if it.get("kind") in KINDS else "note",
                      str(it.get("title", "")), str(it.get("content", "")), it.get("paper_key"))
    return ws_id, f"Imported {len(papers)} papers and {len(raw_items)} saved items."

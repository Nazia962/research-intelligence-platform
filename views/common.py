"""State, sidebar and small UI helpers shared by every page."""
import html
import re
import secrets

import streamlit as st

from services import (ai_service, citation_service, config, db, export_service, license_service,
                      paper_service, quota, workspace_service)
from services.paper_model import SOURCE_LABELS, authors_text, publication_text, safe_url

MODES = ["🟢 Beginner Mode", "🔵 Technical Mode"]
esc = html.escape
NEW_WS = "➕ Create new workspace…"


# ------------------------------------------------------------------ state
def init_state():
    ss = st.session_state
    for key, default in {"page": "home", "mode": MODES[0], "results": None, "search_id": 0, "sel": {},
                         "paper_index": {}, "shown": 10, "selected_paper": None, "ai_out": {},
                         "compare_papers": [], "compare_out": None, "agent_run": None, "planner_ctx": None, "plan_out": None,
                         "active_ws": None}.items():
        ss.setdefault(key, default)
    user = ss.get("authenticated_user")
    if user:
        ss["owner"] = "account:" + user["email"]
        return
    code = str(st.query_params.get("space", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", code):
        code = secrets.token_urlsafe(9)
    if st.query_params.get("space") != code:
        st.query_params["space"] = code
    ss["owner"] = code


def owner():
    return st.session_state["owner"]


def plan():
    return license_service.current_plan(owner())


def limits():
    return quota.limits_for(plan())


def goto(page):
    st.session_state["page"] = page


def set_mode(mode):
    st.session_state["mode"] = mode


def mode_name():
    return ai_service.norm_mode(st.session_state["mode"])


# ---------------------------------------------------------------- sidebar
NAV = [("home", "⌕  Paper Search"), ("discovery", "◈  Research Radar"), ("agent", "✦  Research Agent"), ("analysis", "◎  Paper Analysis"), ("compare", "⇄  Compare Papers"), ("workspace", "▤  Workspaces"), ("planner", "⌁  Project Planner")]
if config.MONETIZATION_ENABLED:          # Pro plan screens only appear once you switch licensing on
    NAV.append(("pricing", "⭐ Plans"))
PAGE_GROUP = {"results": "home"}


def render_sidebar():
    current = PAGE_GROUP.get(st.session_state["page"], st.session_state["page"])
    with st.sidebar:
        st.markdown('<div class="brand">RESEARCH INTELLIGENCE</div><div class="brand-sub">DISCOVERY WORKSPACE</div>', unsafe_allow_html=True)
        for page, label in NAV:
            st.button(label, key=f"nav_{page}", width="stretch", on_click=goto, args=(page,),
                      type="primary" if current == page else "secondary")
        p = plan()
        if p == "open":
            status = "<b>All features unlocked</b><br>No limits are active."
        elif p == "pro":
            status = f"<b>⭐ Pro plan</b><br>{esc(license_service.plan_info(owner())[1])}"
        else:
            used, cap = quota.used_today(owner()), config.FREE_AI_PER_DAY
            status = f"<b>Free plan</b><br>AI generations today: <b>{min(used, cap)}/{cap}</b><br>Cached results are free."
        st.markdown(f'<div class="side-card">{status}</div>', unsafe_allow_html=True)
        providers = ai_service.ai_providers()
        st.markdown('<div class="side-card"><b>AI:</b> ' + (esc(", ".join(providers)) if providers else "not configured (extractive mode)") + "</div>",
                    unsafe_allow_html=True)
        from services.config import SERPAPI_KEY
        serp_status = "connected when searches run" if SERPAPI_KEY else "key not configured"
        st.markdown('<div class="side-card"><b>SerpApi:</b> ' + esc(serp_status) + '</div>', unsafe_allow_html=True)
        user = st.session_state.get("authenticated_user")
        if user:
            st.markdown(f'<div class="side-card"><b>Signed in</b><br>{esc(user["name"])}<br><small>{esc(user["email"])}</small></div>', unsafe_allow_html=True)
            if st.button("Log out", key="account_logout", width="stretch"):
                st.session_state["authenticated_user"] = None
                st.session_state["guest_mode"] = False
                st.session_state["owner"] = ""
                st.rerun()
        else:
            st.markdown(f'<div class="side-card"><b>Guest space</b><br><code>{esc(owner())}</code><br>'
                        "Guest workspace links may be shared. Avoid sensitive information.</div>", unsafe_allow_html=True)


# ----------------------------------------------------------- paper display
def badge(text, cls=""):
    return f'<span class="badge-pill {cls}">{esc(text)}</span>'


def paper_badges(p):
    out = []
    if p.get("year"):
        out.append(badge(f"📅 {p['year']}"))
    if p.get("citations") is not None:
        out.append(badge(f"📈 {p['citations']:,} citations"))
    if p.get("is_oa") or p.get("pdf_url"):
        out.append(badge("🔓 Open access", "badge-oa"))
    if p.get("is_survey"):
        out.append(badge("📘 Survey: good starting point", "badge-survey"))
    if p.get("type") == "preprint":
        out.append(badge("🧪 Preprint"))
    out += [badge(SOURCE_LABELS.get(s, s), "badge-src") for s in p.get("sources", [])]
    return "".join(out)


def paper_header_html(p, abstract_chars=0):
    abstract = p.get("abstract", "")
    abs_html = ""
    if abstract_chars and abstract:
        shown = abstract if len(abstract) <= abstract_chars else abstract[:abstract_chars].rsplit(" ", 1)[0] + "…"
        abs_html = f'<div class="pc-abs">{esc(shown)}</div>'
    return (f'<div class="pc-title">{esc(p["title"])}</div>'
            f'<div class="pc-meta">{esc(authors_text(p))} · {esc(publication_text(p))}</div>'
            f'<div>{paper_badges(p)}</div>{abs_html}')


def link_buttons(p, key):
    cols = st.columns(2)
    if safe_url(p.get("url")):
        cols[0].link_button("🔗 View source", safe_url(p["url"]), width="stretch")
    if safe_url(p.get("pdf_url")):
        cols[1].link_button("📄 Open PDF", safe_url(p["pdf_url"]), width="stretch")


def open_paper(paper):
    st.session_state["selected_paper"] = paper
    st.session_state["page"] = "analysis"


# -------------------------------------------------------------- AI helpers
def run_ai(task, *args):
    """Run an ai_service task, honouring daily limits, and count only real AI calls."""
    allowed, reason = quota.can_use_ai(owner(), plan())
    res = task(*args, live_allowed=allowed)
    if res.source == "live":
        quota.record_ai_use(owner())
    elif res.source == "limit":
        res.note = reason
    return res


def result_banner(res):
    if res.source == "cache":
        st.caption("⚡ Instant result from cache (no AI quota used).")
    elif res.source == "live":
        st.caption(f"🧠 Generated by {res.model}")
    elif res.source == "offline":
        st.warning(f"{res.note} Showing an extractive result built from the paper text instead.")
    elif res.source == "limit":
        st.warning(f"{res.note} Showing an extractive result instead.")
        if config.MONETIZATION_ENABLED:
            st.button("⭐ See the Pro plan", key=f"upgrade_{abs(hash(res.note)) % 9999}_{id(res)}", on_click=goto, args=("pricing",))


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_")[:50] or "export"


@st.cache_data(show_spinner=False, max_entries=24)
def _docx_bytes(md, title, watermark):
    return export_service.markdown_to_docx(md, title, watermark)


@st.cache_data(show_spinner=False, max_entries=24)
def _pdf_bytes(md, title, watermark):
    return export_service.markdown_to_pdf(md, title, watermark)


def download_row(md, title, key):
    wm = export_service.FREE_WATERMARK if limits().watermark else None
    base = slug(title)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Markdown", md, f"{base}.md", "text/markdown", key=f"{key}_md", width="stretch")
    c2.download_button("⬇️ Word (.docx)", _docx_bytes(md, title, wm), f"{base}.docx", key=f"{key}_docx", width="stretch",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    c3.download_button("⬇️ PDF", _pdf_bytes(md, title, wm), f"{base}.pdf", "application/pdf", key=f"{key}_pdf", width="stretch")
    if wm:
        st.caption("Free plan exports include a small footer note. Pro exports are clean.")


def cite_panel(papers, key):
    style = st.radio("Citation style", citation_service.STYLES, horizontal=True, key=f"{key}_style")
    text = citation_service.format_many(papers, style)
    try:
        st.code(text, language=None, wrap_lines=True)
    except TypeError:
        st.code(text, language=None)
    ext = citation_service.file_extension(style)
    st.download_button(f"⬇️ Download references (.{ext})", text, f"references.{ext}", key=f"{key}_dl")


# ---------------------------------------------------------------- workspaces
def _create_ws_cb(key):
    name = st.session_state.get(f"{key}_new", "")
    count = len(workspace_service.list_workspaces(owner()))
    if count >= limits().workspaces:
        st.session_state[f"{key}_err"] = f"The Free plan allows {config.FREE_WORKSPACES} workspaces. Delete one or upgrade to Pro."
        return
    ws_id, err = workspace_service.create_workspace(owner(), name)
    if err:
        st.session_state[f"{key}_err"] = err
    else:
        st.session_state[f"{key}_err"] = ""
        st.session_state[key] = ws_id
        st.session_state["active_ws"] = ws_id


def workspace_picker(key, label="Workspace"):
    """Select (or create) a workspace. Returns its id, or None if none is selected."""
    wss = workspace_service.list_workspaces(owner())
    info = {w["id"]: w for w in wss}
    options = [w["id"] for w in wss] + [NEW_WS]
    active = st.session_state.get("active_ws")
    if key not in st.session_state:
        st.session_state[key] = active if active in info else options[0]
    elif st.session_state[key] not in options:
        st.session_state[key] = options[0]
    choice = st.selectbox(label, options, key=key,
                          format_func=lambda x: NEW_WS if x == NEW_WS else f"{info[x]['name']}  ({info[x]['papers']} papers)")
    if choice == NEW_WS:
        st.text_input("Name for the new workspace", key=f"{key}_new", placeholder="e.g. Final-year project: intrusion detection")
        st.button("Create workspace", key=f"{key}_create", on_click=_create_ws_cb, args=(key,))
        if st.session_state.get(f"{key}_err"):
            st.error(st.session_state[f"{key}_err"])
        return None
    st.session_state["active_ws"] = choice
    return choice


def save_papers_ui(papers, key):
    """Pick a workspace and save the given papers into it."""
    ws_id = workspace_picker(f"{key}_ws")
    if st.button(f"💾 Save {len(papers)} paper{'s' if len(papers) != 1 else ''}", key=f"{key}_save", disabled=ws_id is None or not papers):
        added, dup, over = workspace_service.add_papers(owner(), ws_id, papers, limits().papers_per_workspace)
        msg = f"Saved {added} new paper{'s' if added != 1 else ''}."
        if dup:
            msg += f" {dup} already there."
        if over:
            msg += f" {over} not saved: the Free plan keeps up to {config.FREE_PAPERS_PER_WORKSPACE} papers per workspace."
        (st.warning if over else st.success)(msg)


def save_item_ui(kind, title, content, key, paper_key=None):
    ws_id = workspace_picker(f"{key}_ws")
    if st.button("💾 Save to this workspace", key=f"{key}_save", disabled=ws_id is None):
        if workspace_service.save_item(owner(), ws_id, kind, title, content, paper_key):
            st.success("Saved. Find it under My workspaces → Saved insights.")
        else:
            st.error("Nothing to save.")


def fulltext_status(paper):
    return bool(db.fulltext_get(paper["key"]))


def get_abstract(paper):
    if paper.get("abstract"):
        return paper["abstract"]
    stored = db.fulltext_get(paper["key"])
    return paper_service.extract_abstract_from_text(stored) if stored else ""


# ------------------------------------------------------ honesty labels
def provenance(kind):
    """Small label telling the reader where a block of text comes from."""
    label = {"meta": ("✅ Verified metadata", "badge-oa"),
             "text": ("📄 From the paper text", ""),
             "ai": ("🧠 AI interpretation: verify against the paper", "badge-survey")}[kind]
    st.markdown(badge(*label), unsafe_allow_html=True)

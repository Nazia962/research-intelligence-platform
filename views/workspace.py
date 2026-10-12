"""Saved workspaces (no login: access is by private link)."""
import streamlit as st

from services import citation_service, config, export_service, workspace_service
from . import common as C


def _open_for_analysis(paper):
    C.open_paper(paper)


def _compare(papers):
    st.session_state["compare_papers"] = papers
    st.session_state["compare_out"] = None
    st.session_state["page"] = "compare"


def _remove_paper(ws_id, key):
    workspace_service.remove_paper(C.owner(), ws_id, key)


def _delete_item(ws_id, item_id):
    workspace_service.delete_item(C.owner(), ws_id, item_id)


def _delete_ws(ws_id):
    workspace_service.delete_workspace(C.owner(), ws_id)
    st.session_state["active_ws"] = None


def render():
    ss, owner = st.session_state, C.owner()
    st.markdown('<div class="page-title">📚 My <span class="gradient-text">workspaces</span></div>'
                '<div class="section-sub">Group papers and insights by project. Your workspaces live behind your private link, so no account is needed.</div>',
                unsafe_allow_html=True)
    st.info("💡 Bookmark this page. Anyone with the link can open your workspaces, and a new browser without it starts empty. "
            "Download a backup below to be safe.")

    wss = workspace_service.list_workspaces(owner)
    top1, top2 = st.columns(2)
    with top1.expander("➕ New workspace", expanded=not wss):
        C.workspace_picker("wsmgr_new_picker", "Pick or create")
    with top2.expander("📥 Restore from a backup file"):
        up = st.file_uploader("Workspace backup (.json)", type=["json"], key="ws_restore")
        if up is not None and st.button("Restore", key="ws_restore_go"):
            ws_id, msg = workspace_service.import_json(owner, up.getvalue().decode("utf-8", "ignore"), C.limits().papers_per_workspace)
            if ws_id:
                ss["active_ws"] = ws_id
                st.success(msg or "Restored.")
                st.rerun()
            else:
                st.error(msg)

    wss = workspace_service.list_workspaces(owner)
    if not wss:
        st.caption("No workspaces yet. Create one above, or save papers from a search.")
        return
    ids = [w["id"] for w in wss]
    if ss.get("active_ws") not in ids:
        ss["active_ws"] = ids[0]
    ws_id = st.selectbox("Open workspace", ids, key="ws_open", index=ids.index(ss["active_ws"]),
                         format_func=lambda i: next(f"{w['name']} ({w['papers']} papers, {w['items']} insights)" for w in wss if w["id"] == i))
    ss["active_ws"] = ws_id
    ws = next(w for w in wss if w["id"] == ws_id)
    papers = workspace_service.list_papers(owner, ws_id)
    items = workspace_service.list_items(owner, ws_id)

    tp, ti, te, tm = st.tabs([f"📄 Papers ({len(papers)})", f"💡 Saved insights ({len(items)})", "📦 Export", "⚙️ Manage"])
    with tp:
        if not papers:
            st.caption("No papers saved yet. Use “Save to workspace” in the search results.")
        pick = []
        for p in papers:
            with st.container(border=True, key=f"card_wsp_{p['key']}"):
                st.markdown(C.paper_header_html(p), unsafe_allow_html=True)
                a, b, c = st.columns(3)
                a.button("📖 Analyse", key=f"wso_{p['key']}", width="stretch", on_click=_open_for_analysis, args=(p,))
                if c.button("🗑️ Remove", key=f"wsr_{p['key']}", width="stretch"):
                    _remove_paper(ws_id, p["key"])
                    st.rerun()
                if b.checkbox("Compare", key=f"wsc_{p['key']}"):
                    pick.append(p)
        lim = C.limits().compare_max
        if pick:
            st.button(f"📊 Compare {len(pick)} selected", type="primary", key="ws_cmp", disabled=not (2 <= len(pick) <= lim),
                      on_click=_compare, args=(pick,))
            if len(pick) > lim:
                st.caption(f"Compare up to {lim} papers at a time.")
        if papers:
            st.button("🎯 Plan a project from this workspace", key="ws_plan", on_click=C.goto, args=("planner",))
    with ti:
        if not items:
            st.caption("Nothing saved yet. Save analyses, gaps, comparisons and plans from their pages.")
        for it in items:
            with st.expander(f"{it['kind'].title()}: {it['title']}"):
                st.markdown(it["content"])
                st.button("🗑️ Delete", key=f"wsd_{it['id']}", on_click=_delete_item, args=(ws_id, it["id"]))
    with te:
        style = st.radio("Reference style", citation_service.STYLES, horizontal=True, key="ws_style")
        brief = export_service.build_brief(ws["name"], papers, items, style)
        C.download_row(f"# Research brief: {ws['name']}\n\n{brief}", f"Research brief {ws['name']}", "ws_brief")
        if papers:
            refs = citation_service.format_many(papers, style)
            ext = citation_service.file_extension(style)
            st.download_button(f"⬇️ References only (.{ext})", refs, f"references.{ext}", key="ws_refs")
        st.download_button("💾 Backup (.json)", workspace_service.export_json(owner, ws_id), f"{C.slug(ws['name'])}_backup.json",
                           "application/json", key="ws_backup")
    with tm:
        new = st.text_input("Rename workspace", value=ws["name"], key=f"ws_rename_{ws_id}")
        if st.button("Rename", key="ws_rename_go"):
            if workspace_service.rename_workspace(owner, ws_id, new):
                st.rerun()
            else:
                st.error("Could not rename (empty or duplicate name).")
        st.divider()
        st.warning("Deleting a workspace removes its papers and insights for good.")
        if st.checkbox("I understand", key=f"ws_confirm_{ws_id}"):
            st.button("🗑️ Delete this workspace", key="ws_delete", on_click=_delete_ws, args=(ws_id,))

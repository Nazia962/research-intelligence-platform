"""Search results: filters, sorting, selection, bulk actions."""
import streamlit as st

from services import ranking, sources
from services.paper_model import safe_url
from . import common as C


def _toggle(key):
    ss = st.session_state
    paper = ss["paper_index"].get(key)
    if ss.get(f"sel_{key}") and paper:
        ss["sel"][key] = paper
    else:
        ss["sel"].pop(key, None)


def _go_compare(papers):
    st.session_state["compare_papers"] = list(papers)
    st.session_state["compare_out"] = None
    st.session_state["page"] = "compare"


def _go_agent():
    st.session_state["page"] = "agent"


def _more():
    st.session_state["shown"] += 10


def _result_card(p):
    key = p["key"]
    selected = key in st.session_state["sel"]
    with st.container(border=True, key=f"card_{'selected_' if selected else ''}res_{key}"):
        c0, c1 = st.columns([1, 14])
        c0.checkbox("Select", value=selected, key=f"sel_{key}", label_visibility="collapsed", on_change=_toggle, args=(key,))
        c1.markdown(C.paper_header_html(p, abstract_chars=420), unsafe_allow_html=True)
        if len(p.get("abstract", "")) > 420:
            with st.expander("Read full abstract"):
                st.text(p["abstract"])
        elif not p.get("abstract"):
            st.caption("No abstract was provided by the sources. Open the paper to try its full text.")
        b0, b1, b2 = st.columns(3)
        b0.button("📖 Open paper", key=f"open_{key}", type="primary", width="stretch", on_click=C.open_paper, args=(p,))
        if safe_url(p.get("url")):
            b1.link_button("🔗 View source", safe_url(p["url"]), width="stretch")
        if safe_url(p.get("pdf_url")):
            b2.link_button("📄 Open PDF", safe_url(p["pdf_url"]), width="stretch")


def render():
    ss = st.session_state
    res = ss.get("results")
    if not res:
        st.info("Start a search first.")
        st.button("← Go to search", on_click=C.goto, args=("home",))
        return
    papers = res["papers"]
    sid = ss["search_id"]

    st.markdown('<div class="page-title">📚 Research <span class="gradient-text">results</span></div>', unsafe_allow_html=True)
    st.markdown(C.badge(f"🔎 {res['query']}") + C.badge(ss["mode"]) + C.badge(f"{len(papers)} papers after merging"), unsafe_allow_html=True)
    counts = " · ".join(f"{sources.source_label(s)} {n}" for s, n in res["counts"].items())
    st.caption(f"Found per source: {counts}")
    if res["errors"]:
        with st.expander(f"⚠️ {len(res['errors'])} source(s) did not respond (the rest still worked)"):
            for s, err in res["errors"].items():
                st.write(f"**{sources.source_label(s)}**: {err}")
            st.caption("Run the search again later to retry. Free services sometimes throttle requests.")

    with st.expander("🎚️ Filters & sorting", expanded=True):
        r1, r2, r3 = st.columns(3)
        sort = r1.selectbox("Sort by", ranking.SORT_OPTIONS, key=f"f_sort_{sid}")
        ptype = r2.selectbox("Paper type", ranking.TYPE_OPTIONS, key=f"f_type_{sid}")
        min_c = r3.number_input("Minimum citations", min_value=0, value=0, step=10, key=f"f_cites_{sid}")
        r4, r5, r6 = st.columns(3)
        lo, hi = ranking.year_bounds(papers)
        year_range = r4.slider("Publication year", lo, hi, (lo, hi), key=f"f_year_{sid}") if lo and hi and lo < hi else None
        title_kw = r5.text_input("Title contains", key=f"f_title_{sid}")
        src_choice = r6.multiselect("Sources", list(res["counts"]), key=f"f_src_{sid}", format_func=sources.source_label)
        k1, k2 = st.columns(2)
        oa = k1.checkbox("Open access only", key=f"f_oa_{sid}")
        has_abs = k2.checkbox("Only papers with an abstract", key=f"f_abs_{sid}")

    shown_all = ranking.sort_papers(
        ranking.apply_filters(papers, year_range, oa, ptype, int(min_c), title_kw, src_choice, has_abs), sort)
    st.markdown(f"**{len(shown_all)}** paper{'s' if len(shown_all) != 1 else ''} match your filters"
                + (f" · **{len(ss['sel'])}** selected" if ss["sel"] else ""))

    st.button("✦ Find web sources, news, patents & trends (research agent)", key="to_agent", width="stretch", on_click=_go_agent)
    sel = list(ss["sel"].values())
    with st.container(border=True, key="card_bulk"):
        a, b = st.columns([1, 1])
        limit = C.limits().compare_max
        too_many = len(sel) > limit
        a.button(f"📊 Compare selected ({len(sel)})", type="primary", width="stretch", key="bulk_compare",
                 disabled=len(sel) < 2 or too_many, on_click=_go_compare, args=(sel,))
        if too_many:
            a.caption(f"Compare up to {limit} papers at a time.")
        elif len(sel) < 2:
            a.caption("Tick two or more papers to compare them.")
        b.button("🗑️ Clear selection", width="stretch", key="bulk_clear", disabled=not sel,
                 on_click=lambda: (ss["sel"].clear(), [ss.pop(k) for k in [k for k in ss if str(k).startswith("sel_")]]))
        if sel:
            t1, t2 = st.tabs(["💾 Save to workspace", "📚 Cite selected"])
            with t1:
                C.save_papers_ui(sel, "bulk")
            with t2:
                C.cite_panel(sel, "bulk_cite")

    if not shown_all:
        st.info("No papers match these filters. Try widening the year range or clearing the filters.")
    for p in shown_all[:ss["shown"]]:
        _result_card(p)
    if len(shown_all) > ss["shown"]:
        st.button(f"Show 10 more ({len(shown_all) - ss['shown']} remaining)", key="more", width="stretch", on_click=_more)

    st.divider()
    st.button("← New search", key="new_search", on_click=C.goto, args=("home",))

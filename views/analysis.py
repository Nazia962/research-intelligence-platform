"""Single paper: metadata, full-text status, AI analysis, research gaps."""
import streamlit as st

from services import ai_service, paper_service
from . import common as C


def _text_for(paper):
    """Full text if obtainable, else empty. Returns (text, info dict)."""
    info = paper_service.get_full_text(paper)
    return (info["text"] if info["success"] else ""), info


def _to_planner(paper, gaps_text):
    st.session_state["planner_ctx"] = {"papers": [paper], "gaps": gaps_text}
    st.session_state["plan_out"] = None
    st.session_state["page"] = "planner"


def render():
    ss = st.session_state
    paper = ss.get("selected_paper")
    if not paper:
        st.info("Open a paper from the search results first.")
        st.button("← Go to search", on_click=C.goto, args=("home",))
        return
    key = paper["key"]
    outs = ss["ai_out"].setdefault(key, {})

    st.markdown('<div class="page-title">🧠 Paper <span class="gradient-text">analysis</span></div>', unsafe_allow_html=True)
    with st.container(border=True, key="card_paper_head"):
        C.provenance("meta")
        st.markdown(C.paper_header_html(paper), unsafe_allow_html=True)
        C.link_buttons(paper, key)
        abstract = C.get_abstract(paper)
        if abstract:
            with st.expander("Abstract", expanded=True):
                C.provenance("text" if not paper.get("abstract") else "meta")
                st.write(abstract)
        else:
            st.caption("No abstract is available for this paper. Nothing has been made up: try loading the full text below.")

    with st.container(border=True, key="card_pdf"):
        st.markdown("**📄 Paper text**")
        if C.fulltext_status(paper):
            st.success("PDF text is available for this paper.")
        else:
            st.caption("Full text is fetched from open-access links when you run an analysis. "
                       "If the paper is paywalled you can upload the PDF yourself.")
        up = st.file_uploader("Upload the PDF of this paper (optional)", type=["pdf"], key=f"pdf_{key}")
        if up is not None and st.button("Use this PDF", key=f"usepdf_{key}"):
            ok, msg = paper_service.attach_pdf_to_paper(paper, up.getvalue())
            (st.success if ok else st.error)(msg)

    st.markdown(C.badge(ss["mode"]), unsafe_allow_html=True)
    a, b = st.columns(2)
    do_analysis = a.button("🔍 Analyse paper", type="primary", width="stretch", key=f"an_{key}")
    do_gaps = b.button("🎯 Find research gaps", type="primary", width="stretch", key=f"gp_{key}")

    mode = C.mode_name()
    if do_analysis or do_gaps:
        with st.spinner("Collecting paper text…"):
            text, info = _text_for(paper)
        if not text:
            st.warning(f"{info['message']} The analysis will use only the title and abstract, so it will be less detailed.")
        else:
            st.caption(f"✅ {info['message']}")
        if do_analysis:
            with st.spinner("Analysing…"):
                outs["analysis"] = C.run_ai(ai_service.analyze_paper, paper, mode, text)
        if do_gaps:
            with st.spinner("Looking for gaps…"):
                outs["gaps"] = C.run_ai(ai_service.detect_research_gaps, paper, mode, text)

    for kind, label, note in (("analysis", "Paper analysis", "analysis"), ("gaps", "Possible research gaps", "gaps")):
        res = outs.get(kind)
        if not res:
            continue
        with st.container(border=True, key=f"card_out_{kind}_{key}"):
            st.markdown(f"### {label}")
            C.result_banner(res)
            C.provenance("ai" if res.ok else "text")
            st.markdown(res.text)
            if kind == "gaps":
                st.caption("Suggested gaps are hypotheses from one paper. Check the literature before claiming novelty.")
            with st.expander("💾 Save / download"):
                C.save_item_ui(kind, f"{label}: {paper['title'][:90]}", res.text, f"save_{kind}_{key}", key)
                C.download_row(f"# {label}\n\n**{paper['title']}**\n\n{res.text}", f"{label} {paper['title']}", f"dl_{kind}_{key}")

    if outs.get("gaps"):
        st.button("🗺️ Turn these gaps into a project plan", key=f"toplan_{key}", type="primary", width="stretch",
                  on_click=_to_planner, args=(paper, outs["gaps"].text))

    with st.expander("📚 Cite / save this paper"):
        C.cite_panel([paper], f"cite_{key}")
        C.save_papers_ui([paper], f"sp_{key}")

    st.divider()
    st.button("← Back to results", key="back_res", on_click=C.goto, args=("results" if ss.get("results") else "home",))

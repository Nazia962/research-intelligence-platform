"""Multi-paper comparison table."""
import pandas as pd
import streamlit as st

from services import ai_service, export_service, paper_service
from . import common as C

COLS = [("paper", "Paper"), ("problem", "Problem"), ("method", "Method"), ("dataset", "Dataset"),
        ("results", "Results"), ("limitations", "Limitations")]


def _to_planner(papers, text):
    st.session_state["planner_ctx"] = {"papers": papers, "gaps": text}
    st.session_state["plan_out"] = None
    st.session_state["page"] = "planner"


def render():
    ss = st.session_state
    papers = ss.get("compare_papers") or []
    st.markdown('<div class="page-title">📊 Compare <span class="gradient-text">papers</span></div>', unsafe_allow_html=True)
    if len(papers) < 2:
        st.info("Select at least two papers in the search results to compare them.")
        st.button("← Back to results", on_click=C.goto, args=("results" if ss.get("results") else "home",))
        return
    st.markdown(C.badge(ss["mode"]) + C.badge(f"{len(papers)} papers"), unsafe_allow_html=True)
    for i, p in enumerate(papers, 1):
        st.markdown(f"**{i}.** {p['title']} ({p.get('year') or 'n.d.'})")

    if st.button("📊 Build comparison table", type="primary", width="stretch", key="run_compare"):
        texts, missing = {}, 0
        with st.spinner("Collecting paper text where it is openly available…"):
            for p in papers:
                info = paper_service.get_full_text(p)
                if info["success"]:
                    texts[p["key"]] = info["text"]
                else:
                    missing += 1
        if missing:
            st.caption(f"Full text was not available for {missing} paper(s); those use title and abstract only.")
        with st.spinner("Comparing…"):
            ss["compare_out"] = C.run_ai(ai_service.compare_papers, papers, texts, C.mode_name())

    res = ss.get("compare_out")
    if res:
        C.result_banner(res)
        data = ai_service.parse_comparison(res.text)
        with st.container(border=True, key="card_compare_out"):
            C.provenance("ai" if res.ok else "text")
            if data:
                df = pd.DataFrame([{label: r.get(k, "") for k, label in COLS} for r in data["papers"]])
                st.dataframe(df, width="stretch", hide_index=True)
                for k, label in (("common_themes", "Common themes"), ("key_differences", "Key differences"),
                                 ("opportunity", "Opportunity for new work")):
                    if data.get(k):
                        st.markdown(f"**{label}.** {data[k]}")
                md = export_service.comparison_markdown(data)
            else:
                st.markdown(res.text)
                md = res.text
            st.caption("Cells marked “Not available” mean the source text did not say. Nothing was filled in by guesswork.")
        with st.expander("💾 Save / download"):
            C.save_item_ui("comparison", f"Comparison of {len(papers)} papers", md, "save_cmp")
            C.download_row(f"# Paper comparison\n\n{md}", "Paper comparison", "dl_cmp")
        st.button("🗺️ Plan a project from these papers", key="cmp_plan", type="primary", width="stretch",
                  on_click=_to_planner, args=(papers, md))
    st.divider()
    st.button("← Back to results", key="cmp_back", on_click=C.goto, args=("results" if ss.get("results") else "home",))

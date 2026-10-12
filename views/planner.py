"""Student research-to-project planner."""
import streamlit as st

from services import ai_service, workspace_service
from . import common as C

TYPES = ["Final-year project", "Mini project", "Research paper", "Thesis", "Hackathon / demo"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]


def render():
    ss = st.session_state
    st.markdown('<div class="page-title">🎯 Project <span class="gradient-text">planner</span></div>'
                '<div class="section-sub">Turn papers and research gaps into a project you can finish, with a week-by-week roadmap.</div>',
                unsafe_allow_html=True)
    ctx = ss.get("planner_ctx")
    papers = list(ctx["papers"]) if ctx else []
    gaps = ctx["gaps"] if ctx else ""

    with st.container(border=True, key="card_plan_src"):
        st.markdown("**1. Choose the source material**")
        ws_papers = []
        wss = workspace_service.list_workspaces(C.owner())
        if wss:
            ws_id = st.selectbox("Load papers from a workspace (optional)", [None] + [w["id"] for w in wss], key="plan_ws",
                                 format_func=lambda x: "None" if x is None else next(w["name"] for w in wss if w["id"] == x))
            if ws_id is not None:
                ws_papers = workspace_service.list_papers(C.owner(), ws_id)
                saved_gaps = workspace_service.list_items(C.owner(), ws_id, "gaps")
                if saved_gaps and not gaps:
                    gaps = "\n\n".join(i["content"] for i in saved_gaps[:3])
        pool = {p["key"]: p for p in papers + ws_papers}
        chosen = st.multiselect("Papers to base the plan on", list(pool), default=list(pool)[:6], key=f"plan_papers_{len(pool)}",
                                format_func=lambda k: pool[k]["title"][:90])
        gaps = st.text_area("Research gaps / notes (optional, edit freely)", value=gaps, height=140, key=f"plan_gaps_{hash(gaps) % 99999}",
                            help="Paste gaps found earlier, or write your own interests.")

    with st.container(border=True, key="card_plan_params"):
        st.markdown("**2. Describe your situation**")
        c1, c2, c3, c4 = st.columns(4)
        ptype = c1.selectbox("Project type", TYPES, key="plan_type")
        weeks = c2.slider("Weeks available", 4, 24, 12, key="plan_weeks")
        team = c3.number_input("Team size", 1, 8, 1, key="plan_team")
        level = c4.selectbox("Skill level", LEVELS, key="plan_level")
        constraints = st.text_input("Constraints (optional)", key="plan_constraints",
                                    placeholder="e.g. no GPU, laptop only, must use Python")

    sel = [pool[k] for k in chosen]
    if not sel and not gaps.strip():
        st.info("Pick at least one paper or write a few notes to get started.")
    if st.button("🗺️ Generate project plan", type="primary", width="stretch", key="run_plan",
                 disabled=not sel and not gaps.strip()):
        params = {"project_type": ptype, "weeks": weeks, "team": int(team), "level": level, "constraints": constraints}
        with st.spinner("Planning…"):
            ss["plan_out"] = C.run_ai(ai_service.plan_project, sel, gaps, params, C.mode_name())

    res = ss.get("plan_out")
    if res:
        with st.container(border=True, key="card_plan_out"):
            C.result_banner(res)
            C.provenance("ai" if res.ok else "text")
            st.markdown(res.text)
            st.caption("Tools and datasets are suggestions. Check that each one exists and fits your constraints.")
        with st.expander("💾 Save / download", expanded=True):
            C.save_item_ui("plan", f"{ptype} plan ({weeks} weeks)", res.text, "save_plan")
            C.download_row(f"# {ptype}: project plan\n\n{res.text}", f"{ptype} plan", "dl_plan")

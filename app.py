"""Research Intelligence Platform: entry point. Run with: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Research Intelligence Platform", page_icon="🔬", layout="wide")

from views import agent, analysis, auth, common as C, compare, discovery, home, planner, pricing, results, theme, workspace  # noqa: E402

PAGES = {"home": home, "agent": agent, "results": results, "analysis": analysis, "compare": compare,
         "discovery": discovery, "workspace": workspace, "planner": planner, "pricing": pricing}

theme.inject()
if not auth.render_gate():
    st.stop()
C.init_state()
C.render_sidebar()
PAGES.get(st.session_state["page"], home).render()

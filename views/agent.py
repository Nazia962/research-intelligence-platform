"""Research agent page: live SerpApi evidence (Scholar + web + news) and an evidence brief."""
import streamlit as st

from services import agent_service, quota, serpapi_service
from . import common as C

KIND = {"paper": ("📄 Papers (Google Scholar)", "paper"), "web": ("🌐 Web sources", "web"), "news": ("📰 Recent news", "news"),
        "patent": ("⚖️ Patents (prior art)", "patent"), "trend": ("📈 Search interest", "trend")}
TOOL_LABEL = {"search_scholar": "Google Scholar", "search_web": "Google Search", "search_news": "Google News",
              "search_patents": "Google Patents", "check_trend": "Google Trends"}


def _run(question):
    allowed, reason = quota.can_use_ai(C.owner(), C.plan())
    with st.spinner("The agent is searching…"):
        run = agent_service.run_agent(question, C.mode_name(), live_allowed=allowed)
    if run.mode == "agent" and run.model:
        quota.record_ai_use(C.owner())
    if not allowed and not run.note:
        run.note = reason
    st.session_state["agent_run"] = run


def _evidence_md(run):
    lines = [f"# Evidence brief: {run.question}", "", run.answer, "", "## Sources (from SerpApi)"]
    for i, e in enumerate(run.evidence, 1):
        lines.append(f"{i}. ({e['kind']}) {e['title']}, {e['source']}{', ' + str(e['date']) if e['date'] else ''}. {e['url']}")
    return "\n".join(lines)


def _plan(run):
    st.session_state["planner_ctx"] = {"papers": [], "gaps": run.answer}
    st.session_state["plan_out"] = None
    st.session_state["page"] = "planner"


def render():
    ss = st.session_state
    st.markdown('<div class="page-title">🤖 Research <span class="gradient-text">agent</span></div>'
                '<div class="section-sub">Ask a research question. The agent chooses between Google Scholar, Search, News, Patents and Trends '
                'through SerpApi, reads what comes back, and writes a brief that cites only those results.</div>', unsafe_allow_html=True)
    if not serpapi_service.configured():
        st.warning("SerpApi is not configured. Add `SERPAPI_KEY` to your `.env` file (free plan: 250 searches per month) and restart the app.")
    default = (ss.get("results") or {}).get("query", "") or ss.get("topic_input", "")
    question = st.text_input("Research question", value=default, key="agent_q",
                             placeholder="e.g. How well do explainable AI methods work for intrusion detection?")
    st.caption("Each run uses about 3–5 SerpApi searches. Repeated questions are cached for 24 hours and cost nothing.")
    if st.button("🔎 Run research agent", type="primary", width="stretch", key="agent_run_btn",
                 disabled=len(question.strip()) < 5 or not serpapi_service.configured()):
        _run(question.strip())

    run = ss.get("agent_run")
    if not run:
        return
    if run.note:
        st.warning(run.note)
    with st.container(border=True, key="card_agent_trace"):
        st.markdown("**🛠️ What the agent did**")
        if run.mode == "agent":
            st.caption(f"The AI ({run.model}) chose each search below after reading the earlier results.")
        else:
            st.caption("The AI was not available, so a fixed plan ran all three searches. The summary below is extractive, not AI-written.")
        for i, s in enumerate(run.steps, 1):
            status = f"⚠️ {s['error']}" if s["error"] else f"{s['count']} results" + (" (cached)" if s["cached"] else "")
            st.markdown(f"{i}. **{TOOL_LABEL.get(s['tool'], s['tool'])}** · “{s['query']}” · {status}")
    if not run.evidence:
        return
    with st.container(border=True, key="card_agent_brief"):
        st.markdown("### Evidence brief")
        C.provenance("ai" if run.mode == "agent" else "text")
        st.markdown(run.answer)
        st.caption("Numbers in [brackets] refer to the source list below. Snippets are short: open the source before relying on a claim.")
    with st.container(border=True, key="card_agent_sources"):
        st.markdown("### Sources")
        C.provenance("meta")
        for i, e in enumerate(run.evidence, 1):
            meta = " · ".join(x for x in (e["source"], str(e["date"])) if x)
            st.markdown(f"**[{i}]** {C.badge(KIND[e['kind']][0])} [{e['title']}]({e['url']})  \n<small>{C.esc(meta)}</small>",
                        unsafe_allow_html=True)
    with st.expander("💾 Save / download"):
        C.save_item_ui("note", f"Evidence brief: {run.question[:80]}", _evidence_md(run), "save_agent")
        C.download_row(_evidence_md(run), f"Evidence brief {run.question}", "dl_agent")
    st.button("🗺️ Turn this into a project plan", type="primary", width="stretch", key="agent_plan", on_click=_plan, args=(run,))

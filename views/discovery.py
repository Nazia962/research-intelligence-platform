"""Cross-source research discovery: Google Scholar, Google Search, and Google News."""
import streamlit as st

from services import ai_service, discovery_service
from services.config import SERPAPI_KEY
from . import common as C


def render():
    st.markdown('<div class="page-title">Research <span class="gradient-text">Radar</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">One research question. Three live discovery channels. A source-aware synthesis.</div>', unsafe_allow_html=True)
    st.markdown("Search scholarly literature, institutional resources, and recent reporting in one workflow. Search results are evidence leads—not proof of a claim or of novelty.")

    with st.container(border=True, key="card_radar_query"):
        query = st.text_input("Research question or topic", key="radar_query", placeholder="e.g. explainable AI for early cancer detection")
        c1, c2 = st.columns([3, 1])
        c1.caption("Uses SerpApi's Google Scholar, Google Search and Google News engines. Results are cached for six hours.")
        run = c2.button("Run research sweep", type="primary", width="stretch", disabled=not query.strip(), key="run_radar")

    if not SERPAPI_KEY:
        st.warning("SerpApi is not configured yet. Add SERPAPI_KEY to your local .env or deployment secrets, then restart the app.")
        with st.expander("Where do I get the key?"):
            st.markdown("Create a key at [SerpApi](https://serpapi.com/users/sign_up?plan=free), put it in `.env` as `SERPAPI_KEY=...`, and never commit `.env` to GitHub.")

    if run:
        with st.spinner("Searching Scholar, the web and recent news…"):
            st.session_state["radar_results"] = discovery_service.research_sweep(query.strip())
            st.session_state["radar_query_last"] = query.strip()
            st.session_state["radar_synthesis"] = None

    data = st.session_state.get("radar_results")
    if not data:
        with st.container(border=True, key="card_radar_how"):
            st.markdown("### How the research sweep works")
            cols = st.columns(3)
            cols[0].markdown("**01 · Scholarly evidence**\n\nPapers, authors, years, citation counts and available PDF links.")
            cols[1].markdown("**02 · Research context**\n\nUniversity, lab, institutional and technical webpages.")
            cols[2].markdown("**03 · Recent developments**\n\nNews coverage that can reveal new announcements or emerging themes.")
        return

    errors = data.get("errors", {})
    if errors:
        with st.expander("Some sources returned errors", expanded=True):
            for source, message in errors.items():
                st.warning(f"{source.title()}: {message}")

    scholar, web, news = st.tabs(["📚 Google Scholar", "🌐 Google Search", "📰 Google News"])
    with scholar:
        papers = data.get("scholar") or []
        st.caption(f"{len(papers)} scholarly results · Google Scholar via SerpApi")
        if not papers:
            st.info("No Scholar results were returned. Check the query, API key and account quota.")
        for i, paper in enumerate(papers):
            with st.container(border=True, key=f"radar_scholar_{i}"):
                st.markdown(f"**{paper.get('title') or 'Untitled paper'}**")
                authors = ", ".join(paper.get("authors", [])[:5]) or "Authors not listed"
                details = [authors, str(paper.get("year") or "Year unavailable"), paper.get("venue") or "Venue unavailable"]
                if paper.get("citations") is not None:
                    details.append(f"{paper['citations']:,} citations")
                st.caption(" · ".join(details))
                if paper.get("abstract"):
                    st.write(paper["abstract"][:700] + ("…" if len(paper["abstract"]) > 700 else ""))
                links = st.columns(2)
                if paper.get("url"):
                    links[0].link_button("Open paper", paper["url"], width="stretch")
                if paper.get("pdf_url"):
                    links[1].link_button("Open PDF", paper["pdf_url"], width="stretch")
                if st.button("Use in paper analysis", key=f"radar_use_{i}"):
                    st.session_state["selected_paper"] = paper
                    st.session_state["page"] = "analysis"
                    st.rerun()
    with web:
        st.caption("General web search · treat sources according to their type and authority.")
        if data.get("web"):
            st.markdown(data["web"])
        else:
            st.info("No web results were returned for this search.")
    with news:
        st.caption("Google News · reporting is contextual evidence, not a substitute for scientific papers.")
        if data.get("news"):
            st.markdown(data["news"])
        else:
            st.info("No news results were returned for this search.")

    st.divider()
    st.markdown("### AI research brief")
    st.caption("The brief uses retrieved search snippets and metadata. Verify important claims against the linked original sources.")
    if st.button("Generate cross-source research brief", type="primary", key="radar_synth"):
        paper_lines = []
        for p in data.get("scholar", [])[:8]:
            paper_lines.append(f"- {p.get('title')} ({p.get('year') or 'year unknown'}); authors: {', '.join(p.get('authors', [])[:4])}; citations: {p.get('citations')}; abstract/snippet: {p.get('abstract','')[:900]}; URL: {p.get('url','')}")
        prompt = f"""You are a careful research assistant. Prepare a concise cross-source research brief for this topic: {st.session_state.get('radar_query_last', query)}.
Use only the evidence below. Separate scholarly literature, general web context, and news. Identify recurring themes, potential disagreements, useful follow-up questions, and evidence limitations. Do not claim a gap is novel or proven. Clearly say when the search evidence is insufficient. Cite the provided URLs inline where relevant. Treat news as reporting, not scientific validation.

SCHOLAR RESULTS:\n{chr(10).join(paper_lines) or 'No Scholar results.'}

GOOGLE SEARCH RESULTS:\n{data.get('web','')[:10000] or 'No web results.'}

GOOGLE NEWS RESULTS:\n{data.get('news','')[:10000] or 'No news results.'}
"""
        fallback = "A live AI provider is not configured or is unavailable. Review the three result tabs above and follow the original source links."
        with st.spinner("Synthesizing the collected evidence…"):
            st.session_state["radar_synthesis"] = C.run_ai(ai_service.generate, "research_radar", prompt, fallback)

    synthesis = st.session_state.get("radar_synthesis")
    if synthesis:
        with st.container(border=True, key="card_radar_synthesis"):
            C.result_banner(synthesis)
            st.markdown(synthesis.text)
            C.download_row(f"# Research brief: {st.session_state.get('radar_query_last', '')}\n\n{synthesis.text}", "Research brief", "radar_brief")

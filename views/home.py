"""Landing page + search box."""
import streamlit as st

from services import paper_service, sources
from . import common as C

EXAMPLES = [("🧠 Explainable AI in Healthcare", "Explainable AI for healthcare diagnosis"),
            ("🛡️ AI for Cybersecurity", "AI for network intrusion detection"),
            ("🌍 Machine Learning for Climate", "Machine learning for climate prediction")]

HERO = """
<div class="hero">
  <span class="badge-pill">✨ Free research companion for students</span>
  <div class="main-title">A smarter way to<br><span class="gradient-text">discover, understand &amp; plan research.</span></div>
  <div class="hero-text">Search free scholarly sources, understand papers with AI, find research gaps,
  and turn them into a project plan you can actually finish.</div>
  <span class="badge-pill">🔎 Multi-source literature search</span><span class="badge-pill">◈ Scholar · Web · News Radar</span>
  <span class="badge-pill">🧠 AI-assisted synthesis</span><span class="badge-pill">📊 Compare · Cite · Export</span>
</div>"""


def _set_topic(value):
    st.session_state["topic_input"] = value


def _mode_card(col, mode, title, text, key):
    selected = st.session_state["mode"] == mode
    with col:
        with st.container(border=True, key=f"card_{'selected_' if selected else ''}mode_{key}"):
            st.markdown(f'<div class="mode-title">{title}</div><div class="mode-text">{text}</div>', unsafe_allow_html=True)
            st.button("✓ Selected" if selected else "Choose", key=f"choose_{key}", width="stretch",
                      type="primary" if selected else "secondary", on_click=C.set_mode, args=(mode,))


def _run_search(query, chosen):
    with st.spinner("🔍 Searching free scholarly sources…"):
        out = sources.search_all(query, chosen)
    if not out["papers"]:
        st.error("No papers were found. Try different keywords, or check the source messages below.")
        for src, err in out["errors"].items():
            st.caption(f"⚠️ {sources.source_label(src)}: {err}")
        return
    ss = st.session_state
    ss.update(results=out, search_id=ss["search_id"] + 1, sel={}, shown=10, selected_paper=None,
              paper_index={p["key"]: p for p in out["papers"]}, page="results")
    st.rerun()


def render():
    st.markdown(HERO, unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="section-title">🎓 Choose your explanation level</div>'
                '<div class="section-sub">You can change this at any time.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    _mode_card(c1, C.MODES[0], "🟢 Beginner Mode",
               "For students and first-time researchers. Plain language, defined terms, step-by-step explanations.", "b")
    _mode_card(c2, C.MODES[1], "🔵 Technical Mode",
               "For researchers and advanced students. Precise terminology, methodology and validity discussion.", "t")

    st.markdown('<div class="section-title" style="margin-top:1rem">🔎 What are you researching?</div>', unsafe_allow_html=True)
    topic = st.text_input("Research topic", key="topic_input", label_visibility="collapsed",
                          placeholder="Example: Explainable AI for network intrusion detection")
    with st.expander("⚙️ Choose sources"):
        available = sources.available_sources()
        chosen = st.multiselect("Search these sources", available, default=available, key="chosen_sources",
                                format_func=sources.source_label)
        st.caption("All sources are free. Google Scholar appears when SerpApi is configured. Use Research Radar for Google Search and Google News discovery.")
    if st.button("🚀 Start research", type="primary", width="stretch", key="start_search"):
        if len(topic.strip()) < 3:
            st.warning("Please type a research topic first (at least 3 characters).")
        elif not chosen:
            st.warning("Select at least one source.")
        else:
            _run_search(topic.strip(), chosen)

    st.markdown('<div class="section-sub" style="margin-top:1rem">💡 Try an example</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (label, value) in zip(cols, EXAMPLES):
        col.button(label, width="stretch", key=f"ex_{value}", on_click=_set_topic, args=(value,))

    st.divider()
    with st.container(border=True, key="card_upload"):
        st.markdown('<div class="section-title">📄 Already have a paper?</div>'
                    '<div class="section-sub">Upload a text-based PDF (up to 20 MB) and analyse it directly. Scanned PDFs are not supported.</div>',
                    unsafe_allow_html=True)
        up = st.file_uploader("Upload a PDF", type=["pdf"], key="home_pdf", label_visibility="collapsed")
        st.caption("🔒 The text is sent to the configured AI service only when you click an AI action. Free AI tiers may use submitted text "
                   "to improve their products, so avoid confidential or unpublished work.")
        if st.button("Read this PDF", type="primary", key="home_pdf_go", disabled=up is None):
            with st.spinner("Reading the PDF…"):
                paper, msg = paper_service.make_uploaded_paper(up.name, up.getvalue())
            if paper:
                C.open_paper(paper)
                st.rerun()
            else:
                st.error(msg)

    st.markdown('<div class="footer-note" style="margin-top:1rem">Verified metadata comes from the source APIs. AI text is an interpretation: '
                'always check important claims against the original paper. Suggested gaps do not guarantee novelty.</div>',
                unsafe_allow_html=True)

"""Warm cream + plum theme (matches the AI Psych Buddy look)."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

:root {
  --plum:#5b3a5e; --plum-dark:#482e4b; --plum-soft:#f3eaf3; --coral:#d0685a; --sage:#5f8f86;
  --ink:#2f2733; --muted:#6f6571; --line:#e6dce6; --card:rgba(255,255,255,.88);
}

html, body, .stApp, .stApp * { font-family:'Nunito','Segoe UI',sans-serif; }
.material-symbols-rounded, [data-testid="stIconMaterial"], .stApp span[class*="material"] {
  font-family:'Material Symbols Rounded' !important; }

.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background:
    radial-gradient(circle at 8% 92%, rgba(247,200,195,.55) 0%, transparent 38%),
    radial-gradient(circle at 92% 8%, rgba(200,232,214,.60) 0%, transparent 40%),
    linear-gradient(135deg,#fbf3ee 0%,#f8f2f7 50%,#f1f7f3 100%) !important;
  color:var(--ink) !important; }
[data-testid="stHeader"] { background:transparent !important; }
.block-container { padding-top:2.2rem !important; padding-bottom:2.5rem; max-width:1100px; }
h1,h2,h3,h4,h5,p,li,label,strong,[data-testid="stMarkdownContainer"] { color:var(--ink); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--muted) !important; }
hr { border-color:var(--line) !important; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background:linear-gradient(180deg,#fbf3ee 0%,#f3eaf3 100%) !important;
  border-right:1px solid var(--line); }
.brand { font-size:1.25rem; font-weight:900; letter-spacing:-.02em; color:var(--ink); margin:.2rem 0 .1rem; }
.brand-sub { font-size:.72rem; font-weight:800; letter-spacing:.14em; color:var(--sage); text-transform:uppercase; margin-bottom:.8rem; }
.side-card { background:rgba(255,255,255,.8); border:1px solid var(--line); border-radius:16px; padding:.8rem .9rem;
  font-size:.86rem; line-height:1.45; margin:.6rem 0; color:var(--ink); }
.side-card b { color:var(--plum); }

/* ---------- hero / titles ---------- */
.hero { text-align:center; padding:.4rem 0 .6rem; }
.main-title { font-size:3rem; font-weight:900; letter-spacing:-.03em; line-height:1.12; margin:.5rem 0 .4rem; color:var(--ink) !important; }
.gradient-text { background:linear-gradient(90deg,#d0685a 0%,#a9806f 50%,#5f8f86 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; color:transparent !important; }
.page-title { font-size:2.2rem; font-weight:900; letter-spacing:-.02em; color:var(--ink) !important; margin-bottom:.2rem; }
.subtitle { font-size:1.08rem; color:var(--muted) !important; margin-bottom:1rem; }
.hero-text { max-width:660px; margin:0 auto 1rem; color:var(--muted) !important; font-size:1.02rem; line-height:1.6; }
.section-title { font-size:1.55rem; font-weight:800; margin:.2rem 0 .3rem; color:var(--ink) !important; }
.section-sub { font-size:1.02rem; font-weight:600; margin-bottom:.8rem; color:var(--muted) !important; }

/* ---------- badges ---------- */
.badge-pill { display:inline-block; padding:.22rem .75rem; border:1px solid var(--line); border-radius:999px;
  background:rgba(255,255,255,.92); font-size:.76rem; font-weight:700; color:var(--ink); margin:0 .25rem .35rem 0;
  box-shadow:0 2px 8px rgba(91,58,94,.05); }
.badge-oa { background:#eaf5ef; border-color:#cfe6da; color:#2f6f56; }
.badge-survey { background:#fcebe8; border-color:#f3cfc9; color:#a14437; }
.badge-src { background:#f6f1f7; color:var(--muted); font-weight:600; }

/* ---------- cards (st.container(key="card_...")) ---------- */
div[class*="st-key-card"] { background:var(--card); border:1px solid var(--line) !important; border-radius:20px !important;
  box-shadow:0 10px 30px rgba(91,58,94,.07); padding:1.1rem 1.2rem !important; margin-bottom:.9rem; }
div[class*="st-key-selected"] { border:2px solid var(--plum) !important; box-shadow:0 12px 34px rgba(91,58,94,.16); }
.pc-title { font-size:1.12rem; font-weight:800; line-height:1.35; color:var(--ink); margin-bottom:.15rem; }
.pc-meta { font-size:.88rem; color:var(--muted); margin-bottom:.45rem; }
.pc-abs { font-size:.94rem; line-height:1.55; color:#453b49; margin-top:.3rem; }
.mode-title { font-size:1.2rem; font-weight:800; margin-bottom:.4rem; }
.mode-text { font-size:.96rem; line-height:1.55; color:var(--muted); min-height:3.6rem; }
.price { font-size:1.9rem; font-weight:900; color:var(--plum); }
.feature { font-size:.95rem; line-height:1.9; }

/* ---------- inputs ---------- */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stNumberInput"] input {
  background:#fff !important; color:var(--ink) !important; border:1.5px solid #d9cad9 !important; border-radius:14px !important; }
div[data-testid="stTextInput"] input { padding:.8rem 1.1rem !important; min-height:3.1rem !important; font-size:1.04rem !important; }
div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
  border-color:var(--plum) !important; box-shadow:0 0 0 3px rgba(91,58,94,.14) !important; }
div[data-baseweb="select"] > div { background:#fff !important; border:1.5px solid #d9cad9 !important; border-radius:14px !important; color:var(--ink) !important; }
[data-testid="stFileUploaderDropzone"] { background:#fff !important; border:1.5px dashed #cdb9cd !important; border-radius:16px !important; }

/* ---------- buttons ---------- */
div[data-testid="stButton"] > button:not([kind="primary"]), div[data-testid="stDownloadButton"] > button, div[data-testid="stLinkButton"] > a {
  background:#fff !important; color:var(--plum) !important; border:1.5px solid #cdb9cd !important; border-radius:999px !important;
  font-weight:800 !important; min-height:2.8rem; transition:all .18s ease; }
div[data-testid="stButton"] > button:not([kind="primary"]) p, div[data-testid="stDownloadButton"] > button p, div[data-testid="stLinkButton"] > a p {
  color:var(--plum) !important; font-weight:800 !important; }
div[data-testid="stButton"] > button:not([kind="primary"]):hover, div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stLinkButton"] > a:hover {
  background:var(--plum-soft) !important; border-color:var(--plum) !important; transform:translateY(-1px); }
div[data-testid="stButton"] > button[kind="primary"] { background:var(--plum) !important; color:#fff !important; border:1.5px solid var(--plum) !important;
  border-radius:999px !important; font-weight:800 !important; min-height:2.9rem; box-shadow:0 8px 20px rgba(91,58,94,.28); transition:all .18s ease; }
div[data-testid="stButton"] > button[kind="primary"] p { color:#fff !important; font-weight:800 !important; }
div[data-testid="stButton"] > button[kind="primary"]:hover { background:var(--plum-dark) !important; border-color:var(--plum-dark) !important; transform:translateY(-1px); }
div[data-testid="stButton"] > button:disabled { opacity:.5; }

/* ---------- alerts, expanders, tabs, tables ---------- */
[data-testid="stAlert"] { background:rgba(255,255,255,.92) !important; border:1px solid var(--line) !important; border-radius:14px !important; }
[data-testid="stAlert"] p { color:var(--ink) !important; }
[data-testid="stExpander"] { background:var(--card) !important; border:1px solid var(--line) !important; border-radius:14px !important; }
button[data-baseweb="tab"] { font-weight:800 !important; }
[data-testid="stSpinner"] p { color:var(--plum) !important; }
[data-testid="stTable"] table { border-collapse:collapse; background:#fff; }
[data-testid="stTable"] th { background:var(--plum-soft) !important; color:var(--plum) !important; font-size:.85rem; }
[data-testid="stTable"] td, [data-testid="stTable"] th { border:1px solid var(--line) !important; vertical-align:top; font-size:.84rem; line-height:1.45; padding:.5rem .6rem; }
.footer-note { color:var(--muted) !important; background:rgba(255,255,255,.75); border:1px solid var(--line); padding:14px 18px;
  border-radius:16px; text-align:center; font-size:.92rem; }

@media (max-width:700px) {
  .main-title { font-size:2.1rem !important; } .page-title { font-size:1.7rem !important; }
  .block-container { padding-top:1.2rem !important; }
}
div[data-testid="stFormSubmitButton"] > button { background:var(--plum) !important; border:1.5px solid var(--plum) !important; border-radius:999px !important; }
div[data-testid="stFormSubmitButton"] > button, div[data-testid="stFormSubmitButton"] > button p { color:#fff !important; font-weight:800 !important; }
div[data-testid="stFormSubmitButton"] > button:hover { background:var(--plum-dark) !important; }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)

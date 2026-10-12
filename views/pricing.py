"""Plans page. Only reachable when LICENSE_SECRET is set (monetisation switched on)."""
import streamlit as st

from services import config, license_service
from . import common as C


def render():
    st.markdown('<div class="page-title">⭐ <span class="gradient-text">Plans</span></div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a.container(border=True, key="card_free_plan"):
        st.markdown(f"### Free\n- {config.FREE_AI_PER_DAY} AI generations per day\n- Compare up to {config.FREE_COMPARE_MAX} papers\n"
                    f"- {config.FREE_WORKSPACES} workspaces, {config.FREE_PAPERS_PER_WORKSPACE} papers each\n- Exports carry a small footer note")
    with b.container(border=True, key="card_selected_pro_plan"):
        st.markdown(f"### Pro: {config.PRO_PRICE_TEXT}\n- Many more AI generations\n- Compare up to {config.PRO_COMPARE_MAX} papers\n"
                    "- Unlimited workspaces and papers\n- Clean exports")
        if config.PAYMENT_LINK:
            st.link_button("Get a Pro key", config.PAYMENT_LINK, width="stretch")
    st.caption("Cached results never use your daily AI allowance.")
    key = st.text_input("Have a Pro key?", key="license_key", placeholder="RIP-PRO-YYYYMMDD-NAME-SIGNATURE")
    if st.button("Activate", key="activate", type="primary"):
        ok, msg = license_service.activate(C.owner(), key)
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()

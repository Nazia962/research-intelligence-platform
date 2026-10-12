"""Sign-in and sign-up screen."""
import streamlit as st
from services import auth_service


def render_gate():
    if st.session_state.get("authenticated_user") or st.session_state.get("guest_mode"):
        return True

    st.markdown("""
    <style>
    .auth-wrap{max-width:760px;margin:3vh auto 0;display:grid;grid-template-columns:1fr;gap:20px;align-items:stretch}
    .auth-hero{border-radius:24px;padding:38px 32px;background:radial-gradient(circle at 15% 10%,#f8dcd7 0,transparent 42%),radial-gradient(circle at 90% 85%,#d9eee2 0,transparent 45%),#fffaf4;border:1px solid #eee5df;min-height:auto;text-align:center}
    .auth-card{border:1px solid #eee5df;background:white;border-radius:24px;padding:26px;box-shadow:0 12px 36px rgba(65,45,55,.07)}
    .auth-brand{font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#5b3a5e}
    .auth-title{font-size:clamp(30px,4vw,46px);line-height:1.12;font-weight:800;color:#382b3b;margin:24px 0 16px}
    .auth-gradient{background:linear-gradient(90deg,#c76d66,#719c81);-webkit-background-clip:text;background-clip:text;color:transparent}
    .auth-muted{color:#685f68;line-height:1.65}
    @media(max-width:750px){.auth-wrap{grid-template-columns:1fr;margin:0 auto}.auth-hero{min-height:auto;padding:26px}}
    </style>
    <div class="auth-wrap">
      <section class="auth-hero"><div class="auth-brand">🔬 Research Intelligence Platform</div>
      <div class="auth-title">Discover evidence.<br><span class="auth-gradient">Build better research.</span></div>
      <p class="auth-muted">Find scholarly papers, understand methods and findings, explore research gaps, and turn ideas into a practical project plan.</p>
      <p class="auth-muted">✦ Multi-source scholarly discovery<br>✦ AI-assisted paper understanding<br>✦ Research workspaces and project planning</p></section>
    </div>
    """, unsafe_allow_html=True)

    _, panel, _ = st.columns([0.55, 1.0, 0.55])
    with panel:
        st.markdown("### Welcome")
        st.caption("Sign in to keep your research organized, or explore without an account.")
        login_tab, signup_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("Email address", key="login_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                ok, result = auth_service.authenticate(email, password)
                if ok:
                    st.session_state["authenticated_user"] = result
                    st.session_state["guest_mode"] = False
                    st.rerun()
                else:
                    st.error(result)
        with signup_tab:
            with st.form("signup_form", clear_on_submit=True):
                name = st.text_input("Your name", placeholder="Student name")
                email = st.text_input("Email address", key="signup_email", placeholder="you@example.com")
                password = st.text_input("Password (8+ characters)", type="password", key="signup_password")
                confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account", type="primary", width="stretch")
            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, result = auth_service.create_user(name, email, password)
                    if ok:
                        st.session_state["authenticated_user"] = result
                        st.session_state["guest_mode"] = False
                        st.success("Account created. Welcome!")
                        st.rerun()
                    else:
                        st.error(result)
        st.divider()
        if st.button("Continue as guest", width="stretch"):
            st.session_state["guest_mode"] = True
            st.session_state["authenticated_user"] = None
            st.rerun()
        st.caption("Guest workspaces use a shareable space link. Do not store sensitive information in guest mode.")
    return False

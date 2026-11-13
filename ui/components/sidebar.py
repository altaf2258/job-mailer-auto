import streamlit as st

def render_sidebar(user):
    """Renders candidate card and interactive tile navigation."""
    with st.sidebar:
        st.markdown(f"""
            <div class="user-profile-badge">
                <h4>💼 Job Mailer Pro</h4>
                <p><strong>{user['full_name']}</strong></p>
                <p style="color: #9d9db8; font-size: 0.8rem;">{user['primary_title']}</p>
                <p style="color: #6d6d88; font-size: 0.78rem;">📧 {user['email']}</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<p style='font-size:0.72rem; text-transform:uppercase; letter-spacing:1px; color:#787895; margin: 4px 4px 4px 4px; font-weight:700;'>Main Menu</p>", unsafe_allow_html=True)

        nav_items = [
            ("📋 Discovered Jobs", "📋 Discovered Jobs"),
            ("🚀 Run Outreach", "🚀 Run Outreach"),
            ("⏰ Custom Timing Slots", "⏰ Custom Timing Slots"),
            ("🔑 Credentials & API Keys", "🔑 Credentials & API Keys"),
            ("🎯 Roles & Cities", "🎯 Roles & Cities Preferences"),
            ("👤 Resumes & Profile", "👤 My Resumes & Profile"),
            ("📝 Template Studio", "📝 Custom Template Studio")
        ]

        for label, target_nav in nav_items:
            is_selected = (st.session_state.active_nav_tile == target_nav)
            btn_type = "primary" if is_selected else "secondary"
            if st.button(label, key=f"nav_tile_{target_nav}", type=btn_type, use_container_width=True):
                st.session_state.active_nav_tile = target_nav
                st.rerun()

        st.markdown("<div style='margin-top: 6px;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Log Out", key="logout_btn", type="secondary", use_container_width=True):
            from core.db import destroy_session
            token = st.session_state.get("session_token") or st.query_params.get("session_token")
            if token:
                destroy_session(token)
            if "session_token" in st.query_params:
                del st.query_params["session_token"]
            # Clear all session state keys to ensure new or re-logging users get a clean slate
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.session_token = None
            st.rerun()

    return st.session_state.active_nav_tile


"""
Job Mailer Pro - Modern Streamlit Dashboard
Architected with clean modular views & components.
"""
import warnings

# Filter out Python 3.14+ event loop and harmless Windows socket connection reset deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import streamlit as st
from core.db import init_db, get_profile_by_id, validate_and_refresh_session, destroy_session
from ui.components.theme import apply_custom_theme
from ui.components.auth import render_auth_gate
from ui.components.sidebar import render_sidebar
from ui.components.header import render_metrics_header

from ui.views.jobs_view import render_jobs_view
from ui.views.outreach_view import render_outreach_view
from ui.views.slots_view import render_slots_view
from ui.views.credentials_view import render_credentials_view
from ui.views.preferences_view import render_preferences_view
from ui.views.profile_view import render_profile_view
from ui.views.templates_view import render_templates_view

# Page Configuration
st.set_page_config(
    page_title="Job Mailer Pro - Portal", 
    page_icon="💼", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema, tracking server & custom styles
init_db()
apply_custom_theme()

# Launch background tracking server for opens and clicks
from core.tracker import start_tracking_server
start_tracking_server(port=8585)

# Launch in-app automatic timing slot scheduler (monitors custom slots 24/7)
from core.scheduler import start_inapp_scheduler
start_inapp_scheduler()

# Session State Initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "session_token" not in st.session_state:
    st.session_state.session_token = None
if "active_nav_tile" not in st.session_state:
    st.session_state.active_nav_tile = "📋 Discovered Jobs"
if "is_fetching" not in st.session_state:
    st.session_state.is_fetching = False
if "is_sending" not in st.session_state:
    st.session_state.is_sending = False
if "fetch_stop_requested" not in st.session_state:
    st.session_state.fetch_stop_requested = False
if "send_stop_requested" not in st.session_state:
    st.session_state.send_stop_requested = False

# --- PERSISTENT SESSION & HARD REFRESH RECOVERY (1-HOUR INACTIVITY TIMEOUT) ---
url_token = st.query_params.get("session_token")
current_token = st.session_state.session_token or url_token

if current_token:
    validated_uid = validate_and_refresh_session(current_token)
    if validated_uid:
        # Active session found within 1 hour: restore authentication state seamlessly
        st.session_state.authenticated = True
        st.session_state.user_id = validated_uid
        st.session_state.session_token = current_token
        st.query_params["session_token"] = current_token
    else:
        # Session expired (> 1 hour inactivity) or invalid: clean up and force logout
        if "session_token" in st.query_params:
            del st.query_params["session_token"]
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.session_token = None
        st.warning("⏱️ Session expired due to 1 hour of inactivity. Please sign in again.")

# 1. GATEKEEPER: LOGIN / SIGN-UP
if not st.session_state.authenticated:
    render_auth_gate()

# 2. AUTHENTICATED CONTEXT
user = get_profile_by_id(st.session_state.user_id)
if not user:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.rerun()

# 3. SIDEBAR NAVIGATION
selected_nav = render_sidebar(user)

# 4. COMPACT TOP HEADER METRICS (Always visible, filtered by user)
render_metrics_header(user["id"])

# 5. VIEW ROUTER
if selected_nav == "📋 Discovered Jobs":
    render_jobs_view(user)
elif selected_nav == "🚀 Run Outreach":
    render_outreach_view(user)
elif selected_nav == "⏰ Custom Timing Slots":
    render_slots_view(user)
elif selected_nav == "🔑 Credentials & API Keys":
    render_credentials_view(user)
elif selected_nav == "🎯 Roles & Cities Preferences":
    render_preferences_view(user)
elif selected_nav == "👤 My Resumes & Profile":
    render_profile_view(user)
elif selected_nav == "📝 Custom Template Studio":
    render_templates_view(user)

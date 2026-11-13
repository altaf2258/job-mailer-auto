import streamlit as st
from core.db import get_stats

def render_metrics_header(user_id):
    """Renders top compact candidate metrics including email opens and link clicks."""
    stats = get_stats(user_id=user_id)
    scol1, scol2, scol3, scol4, scol5, scol6 = st.columns(6)
    with scol1:
        st.metric("Total Jobs Found", stats["total"])
    with scol2:
        st.metric("Pending Dispatch", stats["pending"])
    with scol3:
        st.metric("No Email Available", stats.get("no_email", 0))
    with scol4:
        st.metric("Contacted", stats["sent"])
    with scol5:
        st.metric("🟢 Emails Opened", stats.get("opened", 0))
    with scol6:
        st.metric("🔵 Links Clicked", stats.get("clicked", 0))

    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)


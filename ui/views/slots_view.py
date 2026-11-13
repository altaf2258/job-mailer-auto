import streamlit as st
import time
from core.db import update_user_profile, get_profile_by_id

def render_slots_view(user):
    st.subheader("⏰ Configure Your 3 Daily Outreach Timing Slots")
    st.markdown("Customize the 3 hours of the day when your automated job applications should dispatch, along with how many emails to send in each window.")

    # Always fetch fresh profile from DB
    db_user = get_profile_by_id(user["id"])
    if db_user:
        user = db_user

    current_slots = user.get("custom_slots") or [
        {"hour": 10, "limit": 10, "name": "Morning Window"},
        {"hour": 14, "limit": 10, "name": "Afternoon Window"},
        {"hour": 17, "limit": 5, "name": "Evening Window"}
    ]

    # Show live system status banner
    import datetime
    current_hour = datetime.datetime.now().hour
    current_time_str = datetime.datetime.now().strftime("%I:%M %p")
    
    st.info(f"🕒 **Current System Time:** {current_time_str} (Hour: {current_hour}:00). The automated background dispatcher evaluates and triggers your configured slots automatically.")

    with st.form("custom_slots_form"):
        slot_cols = st.columns(3)
        updated_slots = []
        hours_options = {h: f"{h:02d}:00 ({'AM' if h < 12 else 'PM'})" for h in range(24)}

        for idx, col in enumerate(slot_cols):
            with col:
                st.markdown(f"#### 🕒 Slot {idx+1}")
                slot_data = current_slots[idx] if idx < len(current_slots) else {"hour": 10, "limit": 10, "name": f"Slot {idx+1}"}
                
                slot_name = st.text_input(f"Slot {idx+1} Label", value=slot_data.get("name", f"Slot {idx+1}"), key=f"slot_name_{idx}")
                selected_hour = st.selectbox(
                    f"Send Time",
                    options=list(hours_options.keys()),
                    format_func=lambda h: hours_options[h],
                    index=int(slot_data.get("hour", 10)),
                    key=f"slot_hour_{idx}"
                )
                slot_limit = st.number_input(f"Max Emails to Send", min_value=1, max_value=100, value=int(slot_data.get("limit", 10)), key=f"slot_limit_{idx}")

                updated_slots.append({
                    "name": slot_name,
                    "hour": selected_hour,
                    "limit": slot_limit
                })

        submit_slots = st.form_submit_button("💾 Save 3 Timing Slots", type="primary")
        if submit_slots:
            try:
                update_user_profile(
                    user_id=user["id"],
                    full_name=user.get("full_name", ""),
                    email=user.get("email", ""),
                    custom_slots=updated_slots
                )
                st.toast("✅ Your 3 daily timing slots have been updated!", icon="⏰")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.toast(f"❌ Failed to save slots: {e}", icon="⚠️")


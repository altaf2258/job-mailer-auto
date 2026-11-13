import streamlit as st
import time
from core.db import update_user_profile

def render_credentials_view(user):
    st.subheader("🔑 Credentials & API Keys")
    st.markdown("Manage your personal RapidAPI Key and Gmail App Password.")

    has_smtp = bool(user.get("smtp_password"))
    has_rapid = bool(user.get("rapidapi_key"))
    has_gemini = bool(user.get("gemini_api_key"))

    with st.form("credentials_form"):
        cred_col1, cred_col2, cred_col3 = st.columns(3)

        with cred_col1:
            st.markdown("#### 📧 Gmail SMTP")
            edit_email = st.text_input("Your Sender Gmail Address", value=user.get("email", ""))
            
            if has_smtp:
                st.success("🔒 App Password: **Saved**")
                edit_smtp_pwd = st.text_input(
                    "Update App Password:", 
                    value="", 
                    type="password",
                    placeholder="Leave blank to keep"
                )
            else:
                st.warning("⚠️ No App Password.")
                edit_smtp_pwd = st.text_input(
                    "Enter Google App Password:", 
                    value="", 
                    type="password",
                    placeholder="16-digit app password"
                )

        with cred_col2:
            st.markdown("#### ⚡ RapidAPI Key")
            if has_rapid:
                st.success("🔒 RapidAPI Key: **Saved**")
                edit_rapid_key = st.text_input(
                    "Update RapidAPI Key:", 
                    value="", 
                    type="password",
                    placeholder="Leave blank to keep"
                )
            else:
                st.warning("⚠️ No RapidAPI key.")
                edit_rapid_key = st.text_input(
                    "Enter RapidAPI Key:", 
                    value="", 
                    type="password",
                    placeholder="Personal RapidAPI key"
                )

        with cred_col3:
            st.markdown("#### 🤖 Gemini AI Key")
            st.caption("Powers AI Hyper-Personalized pitches tailored to each job description.")
            if has_gemini:
                st.success("🔒 Gemini Key: **Saved**")
                edit_gemini_key = st.text_input(
                    "Update Gemini API Key:", 
                    value="", 
                    type="password",
                    placeholder="Leave blank to keep"
                )
            else:
                st.info("💡 Optional (Generates standard tailored pitches if empty)")
                edit_gemini_key = st.text_input(
                    "Enter Google Gemini API Key:", 
                    value="", 
                    type="password",
                    placeholder="AI Studio Gemini API key"
                )

        submit_creds = st.form_submit_button("💾 Save Credentials Securely", type="primary")

        if submit_creds:
            try:
                update_user_profile(
                    user_id=user["id"],
                    full_name=user.get("full_name", ""),
                    email=edit_email,
                    smtp_password=edit_smtp_pwd if edit_smtp_pwd.strip() else None,
                    rapidapi_key=edit_rapid_key if edit_rapid_key.strip() else None,
                    gemini_api_key=edit_gemini_key if edit_gemini_key.strip() else None
                )
                st.toast("✅ Credentials saved and encrypted successfully!", icon="🔑")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.toast(f"❌ Failed to save credentials: {e}", icon="⚠️")


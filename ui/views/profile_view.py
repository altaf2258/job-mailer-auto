import streamlit as st
import os
import time
from core.db import update_user_profile, get_user_resumes, save_user_resume, delete_user_resume

def render_profile_view(user):
    st.subheader("My Candidate Profile & Multiple Resumes")
    pcol1, pcol2 = st.columns([1, 1])

    with pcol1:
        st.markdown("#### Contact Information")
        with st.form("profile_contact_form"):
            edit_full_name = st.text_input("Full Name", value=user.get("full_name", ""))
            edit_phone = st.text_input("Phone Number", value=user.get("phone", "") or "")
            edit_linkedin = st.text_input("LinkedIn Profile URL", value=user.get("linkedin", "") or "")
            edit_years = st.number_input("Years of Experience", min_value=0, max_value=30, value=int(user.get("years_experience", 3)))
            edit_title = st.text_input("Primary Title", value=user.get("primary_title", "Software Engineer"))

            submit_contact = st.form_submit_button("💾 Save Contact Information", type="primary")
            if submit_contact:
                try:
                    update_user_profile(
                        user_id=user["id"],
                        full_name=edit_full_name,
                        email=user.get("email", ""),
                        phone=edit_phone,
                        linkedin=edit_linkedin,
                        years_exp=edit_years,
                        primary_title=edit_title
                    )
                    st.toast("✅ Profile contact details updated successfully!", icon="👤")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.toast(f"❌ Failed to update contact info: {e}", icon="⚠️")

    with pcol2:
        st.markdown("#### 📄 Tailored Resumes by Role & Technology")
        st.caption("Upload dedicated resumes for each sub-role (Angular, React, Node.js, etc.). The system automatically selects and attaches the exact matching resume for each job opportunity!")

        pid = user["id"]
        current_resumes = get_user_resumes(pid)
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", f"user_{pid}")
        os.makedirs(upload_dir, exist_ok=True)

        # Tabbed interface for Sub-Roles vs Main Categories
        tab_subroles, tab_main = st.tabs(["🎯 Sub-Role Resumes (Angular, React, Node...)", "📁 General Category Resumes"])

        with tab_subroles:
            st.caption("Targeted sub-role resumes have **highest priority** during email dispatch.")
            
            # Catalog of popular sub-roles + user's target roles
            predefined_subroles = [
                ("ANGULAR", "Angular Developer"),
                ("REACT", "React.js Developer"),
                ("NEXTJS", "Next.js Developer"),
                ("NODEJS", "Node.js Developer"),
                ("MERN", "MERN Stack Developer"),
                ("MEAN", "MEAN Stack Developer"),
                ("VUE", "Vue.js Developer"),
                ("PYTHON", "Python / Django Developer"),
                ("JAVA", "Java Developer"),
                ("DOTNET", ".NET / C# Developer"),
                ("FLUTTER", "Flutter Developer"),
                ("ANDROID", "Android Developer")
            ]

            # Allow user to pick or upload for a specific sub-role
            selected_sub = st.selectbox(
                "Select Technology / Sub-Role to Manage:",
                options=[code for code, name in predefined_subroles],
                format_func=lambda code: dict(predefined_subroles).get(code, code),
                key="select_subrole_resume"
            )

            curr_sub_res = current_resumes.get(selected_sub)
            if curr_sub_res:
                st.success(f"Attached for **{dict(predefined_subroles).get(selected_sub)}**: `{curr_sub_res['file_name']}`")
                del_btn = st.button(f"🗑️ Remove {selected_sub} Resume", key=f"del_{selected_sub}", type="secondary")
                if del_btn:
                    delete_user_resume(pid, selected_sub)
                    st.toast(f"Removed {selected_sub} resume", icon="🗑️")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info(f"No specific resume attached for **{dict(predefined_subroles).get(selected_sub)}** yet (will fall back to general category).")

            sub_file = st.file_uploader(f"Upload {selected_sub} Resume (PDF)", type=["pdf"], key=f"uploader_sub_{selected_sub}")
            if sub_file is not None:
                try:
                    dest_path = os.path.join(upload_dir, f"{selected_sub.lower()}_{sub_file.name}")
                    with open(dest_path, "wb") as f:
                        f.write(sub_file.read())
                    save_user_resume(pid, selected_sub, sub_file.name, dest_path)
                    st.toast(f"✅ Saved {selected_sub} resume: {sub_file.name}", icon="📄")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.toast(f"❌ Failed to save resume: {e}", icon="⚠️")

            st.markdown("---")
            st.markdown("##### Currently Active Sub-Role Resumes:")
            active_subs = [code for code, name in predefined_subroles if code in current_resumes]
            if active_subs:
                for code in active_subs:
                    st.markdown(f"- **{dict(predefined_subroles).get(code)}**: `{current_resumes[code]['file_name']}`")
            else:
                st.caption("No sub-role resumes uploaded yet.")

        with tab_main:
            st.caption("Used as fallback whenever a job does not match a specific sub-technology.")
            main_categories = ["FRONTEND", "BACKEND", "FULLSTACK", "DEVOPS", "DEFAULT"]

            for cat in main_categories:
                with st.expander(f"📁 {cat} Resume", expanded=(cat in ["FULLSTACK", "FRONTEND"])):
                    curr_res = current_resumes.get(cat)
                    if curr_res:
                        st.success(f"Attached: `{curr_res['file_name']}`")
                    else:
                        st.warning("No resume attached yet.")

                    up_file = st.file_uploader(f"Upload {cat} Resume (PDF)", type=["pdf"], key=f"res_{pid}_{cat}")
                    if up_file is not None:
                        try:
                            dest_path = os.path.join(upload_dir, f"{cat.lower()}_{up_file.name}")
                            with open(dest_path, "wb") as f:
                                f.write(up_file.read())
                            save_user_resume(pid, cat, up_file.name, dest_path)
                            st.toast(f"✅ Saved {cat} resume: {up_file.name}", icon="📄")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.toast(f"❌ Failed to save resume: {e}", icon="⚠️")


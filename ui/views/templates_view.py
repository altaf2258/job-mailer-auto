import streamlit as st
from core.db import get_user_template, save_user_template
from core.personalizer import render_pitch_for_profile

def render_templates_view(user):
    st.subheader("Dynamic Email Template Builder (Per Category)")
    st.caption("Customize subject lines and pitches for each role category. Variables available: `{{ contact_name }}`, `{{ role }}`, `{{ company }}`, `{{ city }}`, `{{ candidate.full_name }}`, `{{ candidate.phone }}`, `{{ candidate.linkedin }}`.")

    pid = user["id"]
    selected_cat = st.selectbox("Select Role Category to Customize:", ["FRONTEND", "BACKEND", "FULLSTACK", "DEVOPS"])
    
    sub_val, body_val = get_user_template(pid, selected_cat)
    
    if not sub_val or not body_val:
        default_sub = f"{{{{ candidate.full_name }}}} – {selected_cat.title()} Engineer ({{{{ candidate.years_experience }}}} YOE) – {{{{ role }}}}"
        default_body = f"""Hi {{{{ contact_name }}}},

I came across the open {{{{ role }}}} role at {{{{ company }}}}{{{{ ' in ' + city if city else '' }}}} and wanted to reach out directly.

I am a Software Engineer with {{{{ candidate.years_experience }}}} years of experience specializing in {selected_cat.title()} architecture.

Highlights from my experience:
• Scalable Architecture: Engineered production platforms with zero unauthorized access incidents and lazy-loaded modular design.
• Performance: Built reactive data pipelines and optimized APIs for high-throughput enterprise systems.

Given your team's presence{{{{ ' in ' + city if city else '' }}}}, I would love to contribute to your engineering roadmaps.

LinkedIn: {{{{ candidate.linkedin }}}}
Phone: {{{{ candidate.phone }}}}

I have attached my tailored {selected_cat.title()} resume for your review. Would you be open to a 10-minute introductory call this week?

Best regards,
{{{{ candidate.full_name }}}}
"""
        sub_val = default_sub
        body_val = default_body

    new_subject = st.text_input("Subject Template", value=sub_val, key=f"tpl_sub_{selected_cat}")
    new_body = st.text_area("Body Template", value=body_val, height=350, key=f"tpl_body_{selected_cat}")

    if st.button("💾 Save Custom Template", type="primary"):
        try:
            save_user_template(pid, selected_cat, new_subject, new_body)
            st.toast(f"✅ Custom template for {selected_cat} saved successfully!", icon="📝")
        except Exception as e:
            st.toast(f"❌ Failed to save template: {e}", icon="⚠️")

    st.markdown("#### Live Template Preview")
    preview_lead = {
        "contact_name": "Sarah Miller",
        "company": "Acme Technologies",
        "role": f"Senior {selected_cat.title()} Developer",
        "city": "Bangalore"
    }
    test_sub, test_body = render_pitch_for_profile(user, preview_lead, selected_cat)
    st.text_input("Rendered Subject Preview", value=test_sub, disabled=True)
    st.text_area("Rendered Body Preview", value=test_body, height=250, disabled=True)


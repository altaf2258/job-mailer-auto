import streamlit as st
import time
from core.constants import ROLE_CATEGORIES, CITY_PRESETS
from core.db import update_user_profile, get_profile_by_id

ALL_SYSTEM_ROLES = [r for cat_roles in ROLE_CATEGORIES.values() for r in cat_roles]

def render_preferences_view(user):
    st.subheader("🎯 Target Roles & Preferred Cities")
    # Always pull freshly from database to guarantee exact persistence across reloads/logins
    db_user = get_profile_by_id(user["id"])
    if db_user:
        user = db_user

    # For new or existing users, respect exactly what is in target_roles (empty list if none selected)
    curr_user_roles = user.get("target_roles") if user.get("target_roles") is not None else []
    curr_user_cities = user.get("target_cities") if user.get("target_cities") is not None else []
    curr_excl = user.get("excluded_companies") if user.get("excluded_companies") is not None else []

    st.markdown("### 1. Select Target Job Roles by Category")
    selected_roles_by_user = []

    for category_name, sub_roles in ROLE_CATEGORIES.items():
        with st.expander(f"📌 {category_name} ({len(sub_roles)} options)", expanded=(category_name in ["Full Stack Development", "Frontend Engineering"])):
            current_selected_in_cat = [r for r in sub_roles if r in curr_user_roles]
            chosen_in_cat = st.multiselect(
                f"Choose sub-roles under {category_name}:",
                options=sub_roles,
                default=current_selected_in_cat,
                key=f"role_cat_{category_name}"
            )
            selected_roles_by_user.extend(chosen_in_cat)

    custom_roles_existing = [r for r in curr_user_roles if r not in ALL_SYSTEM_ROLES]
    custom_roles_input = st.text_input(
        "➕ Add Custom Role(s) (comma-separated, optional):",
        value=", ".join(custom_roles_existing),
        placeholder="e.g. AI Prompt Engineer, Rust Developer"
    )
    if custom_roles_input:
        for cr in custom_roles_input.split(","):
            if cr.strip() and cr.strip() not in selected_roles_by_user:
                selected_roles_by_user.append(cr.strip())

    st.markdown(f"**Selected Roles ({len(selected_roles_by_user)}):** `{', '.join(selected_roles_by_user) if selected_roles_by_user else 'None'}`")
    st.divider()

    st.markdown("### 2. Select Preferred Cities")
    st.caption("💡 **Tip:** If you leave this empty (select no cities), the system will search **All Over India**!")
    all_city_options = list(dict.fromkeys(CITY_PRESETS + curr_user_cities))
    chosen_cities = st.multiselect(
        "Select Cities to Target for Jobs:",
        options=all_city_options,
        default=[c for c in curr_user_cities if c in all_city_options],
        key="city_multiselect"
    )

    custom_city_input = st.text_input("➕ Add Custom City (optional):", placeholder="e.g. Ahmedabad, Mysore")
    if custom_city_input:
        for cc in custom_city_input.split(","):
            if cc.strip() and cc.strip() not in chosen_cities:
                chosen_cities.append(cc.strip())

    st.divider()
    st.markdown("### 3. Exclude Companies (Blocklist)")
    excl_companies_str = st.text_area("Never apply to these companies (one per line):", value="\n".join(curr_excl), height=80)

    if st.button("💾 Save Roles, Cities & Blacklist", type="primary"):
        try:
            cleaned_excl = [e.strip() for e in excl_companies_str.split("\n") if e.strip()]
            update_user_profile(
                user_id=user["id"],
                full_name=user.get("full_name", ""),
                email=user.get("email", ""),
                target_roles=selected_roles_by_user,
                target_cities=chosen_cities,
                excluded_companies=cleaned_excl
            )
            st.toast("✅ Target roles, cities, and blacklist saved successfully!", icon="🎯")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.toast(f"❌ Failed to save preferences: {e}", icon="⚠️")


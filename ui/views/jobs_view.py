import streamlit as st
import pandas as pd
from core.db import get_connection

def render_jobs_view(user):
    st.subheader("Discovered Jobs Database")

    conn = get_connection()
    df_leads = pd.read_sql_query(f"""
        SELECT l.id, l.company, l.role, l.city, 
               COALESCE(l.email, '— [No Email Found] —') AS email, 
               l.category, l.status,
               CASE 
                   WHEN s.resume_viewed_at IS NOT NULL THEN '🟣 Resume Viewed'
                   WHEN s.link_clicked_at IS NOT NULL THEN '🔵 Clicked Portfolio'
                   WHEN s.opened_at IS NOT NULL THEN '🟢 Email Opened'
                   WHEN l.status = 'SENT' THEN '⚪ Delivered'
                   ELSE l.status 
               END AS engagement,
               COALESCE(s.open_count, 0) AS opens,
               COALESCE(s.resume_view_count, 0) AS resume_views,
               COALESCE(s.click_count, 0) AS link_clicks,
               COALESCE(l.website, '—') AS website,
               COALESCE(l.job_description, '—') AS job_description,
               COALESCE(l.posted_at, l.created_at) AS posted_date,
               l.email_source, l.created_at 
        FROM leads l
        LEFT JOIN sent_logs s ON l.id = s.lead_id AND s.profile_id = {int(user['id'])}
        WHERE l.is_deleted = 0 AND l.user_id = {int(user['id'])}
        ORDER BY l.id DESC, l.created_at DESC
    """, conn)
    conn.close()

    if not df_leads.empty:
        # Search Filters Bar
        f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.5, 1.5, 1.5])
        with f_col1:
            city_search = st.text_input("🏙️ Filter City", placeholder="e.g. Pune, Bangalore")
        with f_col2:
            company_search = st.text_input("🏢 Filter Company", placeholder="e.g. Google, Tech")
        with f_col3:
            role_search = st.text_input("💼 Filter Role", placeholder="e.g. Frontend, React")
        with f_col4:
            status_filter = st.multiselect(
                "📌 Status", 
                options=df_leads["status"].unique().tolist(), 
                default=df_leads["status"].unique().tolist()
            )

        filtered_df = df_leads.copy()
        if status_filter:
            filtered_df = filtered_df[filtered_df["status"].isin(status_filter)]
        if city_search.strip():
            filtered_df = filtered_df[filtered_df["city"].str.contains(city_search.strip(), case=False, na=False)]
        if company_search.strip():
            filtered_df = filtered_df[filtered_df["company"].str.contains(company_search.strip(), case=False, na=False)]
        if role_search.strip():
            filtered_df = filtered_df[filtered_df["role"].str.contains(role_search.strip(), case=False, na=False)]

        total_rows = len(filtered_df)

        if total_rows > 0:
            filtered_df.insert(0, "S.No", range(1, total_rows + 1))
            page_size = 20
            total_pages = max(1, (total_rows + page_size - 1) // page_size)

            if "job_page_num" not in st.session_state:
                st.session_state.job_page_num = 1
            if st.session_state.job_page_num > total_pages:
                st.session_state.job_page_num = 1

            start_idx = (st.session_state.job_page_num - 1) * page_size
            end_idx = min(start_idx + page_size, total_rows)

            page_df = filtered_df.iloc[start_idx:end_idx].copy()

            # Clean Table display: Company, Role, City, Email, Status, Engagement, Website & Job Description
            display_columns = ["S.No", "company", "role", "city", "email", "category", "engagement", "opens", "resume_views", "link_clicks", "posted_date", "website", "job_description"]
            st.dataframe(
                page_df[display_columns],
                column_config={
                    "engagement": st.column_config.TextColumn(
                        "HR Engagement",
                        help="Live Recruiter Activity: 🟢 Opened, 🟣 Resume Viewed, 🔵 Clicked Link, ⚪ Delivered",
                        width="medium"
                    ),
                    "opens": st.column_config.NumberColumn(
                        "Email Opens",
                        help="Number of times email was opened by HR",
                        format="%d"
                    ),
                    "resume_views": st.column_config.NumberColumn(
                        "Resume Views",
                        help="Number of times your tailored PDF resume was clicked/viewed",
                        format="%d"
                    ),
                    "link_clicks": st.column_config.NumberColumn(
                        "Portfolio Clicks",
                        help="Number of times your LinkedIn / Portfolio link was clicked",
                        format="%d"
                    ),
                    "posted_date": st.column_config.DatetimeColumn(
                        "Job Posted At",
                        help="Exact date job was published (within 7 days)",
                        format="D MMM YYYY, h:mm a"
                    ),
                    "website": st.column_config.LinkColumn(
                        "Website",
                        help="Company Career / Official Website",
                        display_text="🌐 Visit Site"
                    ),
                    "job_description": st.column_config.TextColumn(
                        "Job Description",
                        help="Full job summary and requirements",
                        width="medium"
                    )
                },
                hide_index=True,
                width="stretch"
            )

            # Pagination Controls Below Table
            b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns([2, 1, 1.5, 1, 2])
            with b_col2:
                if st.button("⬅️ Previous", disabled=(st.session_state.job_page_num <= 1), use_container_width=True):
                    st.session_state.job_page_num -= 1
                    st.rerun()
            with b_col3:
                st.markdown(
                    f"<p style='text-align: center; margin-top: 6px; font-weight: bold;'>Page {st.session_state.job_page_num} of {total_pages} ({total_rows} leads)</p>", 
                    unsafe_allow_html=True
                )
            with b_col4:
                if st.button("Next ➡️", disabled=(st.session_state.job_page_num >= total_pages), use_container_width=True):
                    st.session_state.job_page_num += 1
                    st.rerun()
        else:
            st.warning("No jobs match your search filters.")
    else:
        st.info("No active jobs recorded yet. Go to 'Run Outreach' to fetch live jobs!")

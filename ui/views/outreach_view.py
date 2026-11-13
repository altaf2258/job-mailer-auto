import streamlit as st
import threading
import time
from core.fetcher import fetch_and_store_jobs
from core.mailer import send_scheduled_emails, send_followup_emails
from core.db import get_due_followups_count

# Process controller module tracking active background jobs across threads
class ProcessManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProcessManager, cls).__new__(cls)
                cls._instance.tasks = {}
            return cls._instance

    def start_fetch(self, user_id, user_obj, max_days_old=7, job_board="All Platforms"):
        key = f"fetch_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            return False, "Fetch already running."

        stop_evt = threading.Event()
        state = {
            "thread": None,
            "stop_event": stop_evt,
            "status": "Starting job discovery...",
            "progress": 0.0,
            "count": 0,
            "done": False,
            "stopped": False,
            "error": None
        }

        def worker():
            try:
                def on_progress(msg, frac):
                    state["status"] = msg
                    state["progress"] = max(0.0, min(1.0, float(frac)))

                count = fetch_and_store_jobs(
                    progress_callback=on_progress,
                    profile_override=user_obj,
                    stop_event=stop_evt,
                    max_days_old=max_days_old,
                    job_board=job_board
                )
                state["count"] = count
                state["done"] = True
                if stop_evt.is_set():
                    state["stopped"] = True
                    state["status"] = f"Pipeline terminated. Recorded {count} jobs before stop."
                else:
                    state["status"] = f"Complete! Recorded {count} jobs in database."
            except Exception as e:
                state["error"] = str(e)
                state["done"] = True
                state["status"] = f"Error: {e}"

        t = threading.Thread(target=worker, daemon=True)
        state["thread"] = t
        self.tasks[key] = state
        t.start()
        return True, "Fetch started."

    def stop_fetch(self, user_id):
        key = f"fetch_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            self.tasks[key]["stop_event"].set()
            self.tasks[key]["status"] = "Termination requested... stopping gracefully."
            return True
        return False

    def get_fetch_state(self, user_id):
        key = f"fetch_{user_id}"
        task = self.tasks.get(key)
        if not task:
            return {"running": False, "status": "Idle", "progress": 0.0, "done": False, "count": 0, "stopped": False}
        running = task["thread"].is_alive()
        return {
            "running": running,
            "status": task["status"],
            "progress": task["progress"],
            "done": task["done"],
            "count": task.get("count", 0),
            "stopped": task.get("stopped", False),
            "error": task.get("error")
        }

    def clear_fetch(self, user_id):
        key = f"fetch_{user_id}"
        if key in self.tasks:
            del self.tasks[key]

    def start_send(self, user_id, user_obj, force=True, limit=5, max_days_old=7):
        key = f"send_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            return False, "Batch send already running."

        stop_evt = threading.Event()
        state = {
            "thread": None,
            "stop_event": stop_evt,
            "status": "Initializing outreach batch...",
            "progress": 0.0,
            "sent": 0,
            "done": False,
            "stopped": False,
            "summary": "",
            "error": None
        }

        def worker():
            try:
                def on_progress(msg, frac):
                    state["status"] = msg
                    state["progress"] = max(0.0, min(1.0, float(frac)))

                sent, summary = send_scheduled_emails(
                    force=force,
                    custom_limit=limit,
                    progress_callback=on_progress,
                    profile_override=user_obj,
                    stop_event=stop_evt,
                    max_days_old=max_days_old
                )
                state["sent"] = sent
                state["summary"] = summary
                state["done"] = True
                if stop_evt.is_set():
                    state["stopped"] = True
                    state["status"] = f"Dispatch terminated. Sent {sent} emails before stop."
                else:
                    state["status"] = summary
            except Exception as e:
                state["error"] = str(e)
                state["done"] = True
                state["status"] = f"Error: {e}"

        t = threading.Thread(target=worker, daemon=True)
        state["thread"] = t
        self.tasks[key] = state
        t.start()
        return True, "Send started."

    def stop_send(self, user_id):
        key = f"send_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            self.tasks[key]["stop_event"].set()
            self.tasks[key]["status"] = "Termination requested... stopping immediately."
            return True
        return False

    def get_send_state(self, user_id):
        key = f"send_{user_id}"
        task = self.tasks.get(key)
        if not task:
            return {"running": False, "status": "Idle", "progress": 0.0, "done": False, "sent": 0, "stopped": False}
        running = task["thread"].is_alive()
        return {
            "running": running,
            "status": task["status"],
            "progress": task["progress"],
            "done": task["done"],
            "sent": task.get("sent", 0),
            "stopped": task.get("stopped", False),
            "error": task.get("error")
        }

    def clear_send(self, user_id):
        key = f"send_{user_id}"
        if key in self.tasks:
            del self.tasks[key]

    def start_followup(self, user_id, user_obj, days=3, limit=10):
        key = f"followup_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            return False, "Follow-up batch already running."

        stop_evt = threading.Event()
        state = {
            "thread": None,
            "stop_event": stop_evt,
            "status": "Initializing follow-up sequence...",
            "progress": 0.0,
            "sent": 0,
            "done": False,
            "stopped": False,
            "summary": "",
            "error": None
        }

        def worker():
            try:
                def on_progress(msg, frac):
                    state["status"] = msg
                    state["progress"] = max(0.0, min(1.0, float(frac)))

                sent, summary = send_followup_emails(
                    days=days,
                    custom_limit=limit,
                    progress_callback=on_progress,
                    profile_override=user_obj,
                    stop_event=stop_evt
                )
                state["sent"] = sent
                state["summary"] = summary
                state["done"] = True
                if stop_evt.is_set():
                    state["stopped"] = True
                    state["status"] = f"Follow-up terminated. Sent {sent} emails before stop."
                else:
                    state["status"] = summary
            except Exception as e:
                state["error"] = str(e)
                state["done"] = True
                state["status"] = f"Error: {e}"

        t = threading.Thread(target=worker, daemon=True)
        state["thread"] = t
        self.tasks[key] = state
        t.start()
        return True, "Followup started."

    def stop_followup(self, user_id):
        key = f"followup_{user_id}"
        if key in self.tasks and self.tasks[key]["thread"].is_alive():
            self.tasks[key]["stop_event"].set()
            self.tasks[key]["status"] = "Termination requested... stopping immediately."
            return True
        return False

    def get_followup_state(self, user_id):
        key = f"followup_{user_id}"
        task = self.tasks.get(key)
        if not task:
            return {"running": False, "status": "Idle", "progress": 0.0, "done": False, "sent": 0, "stopped": False}
        running = task["thread"].is_alive()
        return {
            "running": running,
            "status": task["status"],
            "progress": task["progress"],
            "done": task["done"],
            "sent": task.get("sent", 0),
            "stopped": task.get("stopped", False),
            "error": task.get("error")
        }

    def clear_followup(self, user_id):
        key = f"followup_{user_id}"
        if key in self.tasks:
            del self.tasks[key]

mgr = ProcessManager()

@st.fragment
def render_fetch_section(user):
    user_id = user["id"]
    state = mgr.get_fetch_state(user_id)
    is_running = state["running"]

    active_roles_count = len(user.get("target_roles") or [])
    cities_list = user.get("target_cities") or []
    loc_display = f"{len(cities_list)} cities" if cities_list else "All over India"
    user_key_status = "Personal Key Configured" if user.get("rapidapi_key") else "No RapidAPI Key Configured"
    st.caption(f"Queries JSearch for **{user['full_name']}**'s criteria (**{active_roles_count} roles** in **{loc_display}** | {user_key_status}).")

    btn_fetch_col1, btn_fetch_col2, btn_fetch_col3 = st.columns([1.2, 1.2, 1])
    with btn_fetch_col1:
        selected_job_board = st.selectbox(
            "🌐 Target Job Board / Platform:",
            options=[
                "🌐 All Platforms (Naukri, LinkedIn, Indeed...)",
                "🇮🇳 Naukri.com Only",
                "💼 LinkedIn Only",
                "🔍 Indeed Only",
                "🏢 Glassdoor Only"
            ],
            index=0,
            key="fetch_job_board_select",
            disabled=is_running
        )
    with btn_fetch_col2:
        fetch_days_option = st.selectbox(
            "📅 Job Recency (Posted Within):",
            options=["Past 24 Hours (Today)", "Past 3 Days", "Past 7 Days (1 Week)", "Past 14 Days (2 Weeks)", "Past 30 Days (1 Month)", "Custom Number of Days"],
            index=2,
            key="fetch_days_preset",
            disabled=is_running
        )
    with btn_fetch_col3:
        if fetch_days_option == "Custom Number of Days":
            custom_days = st.number_input("Enter Max Days:", min_value=1, max_value=90, value=7, key="custom_fetch_days", disabled=is_running)
            selected_fetch_days = int(custom_days)
        elif "24 Hours" in fetch_days_option:
            selected_fetch_days = 1
        elif "3 Days" in fetch_days_option:
            selected_fetch_days = 3
        elif "7 Days" in fetch_days_option:
            selected_fetch_days = 7
        elif "14 Days" in fetch_days_option:
            selected_fetch_days = 14
        else:
            selected_fetch_days = 30

        st.caption(f"Targeting: **{selected_job_board}** (Past **{selected_fetch_days} days**)")

    btn_fetch_action1, btn_fetch_action2 = st.columns([1.5, 1])
    with btn_fetch_action1:
        start_fetch = st.button("▶️ Start Fetching Jobs", key="btn_start_fetch", type="primary", disabled=is_running, use_container_width=True)
    with btn_fetch_action2:
        stop_fetch = st.button("⏹️ Terminate Fetch", key="btn_stop_fetch", type="secondary", disabled=(not is_running), use_container_width=True)

    if start_fetch and not is_running:
        mgr.clear_fetch(user_id)
        mgr.start_fetch(user_id, user, max_days_old=selected_fetch_days, job_board=selected_job_board)
        st.rerun()

    if stop_fetch and is_running:
        mgr.stop_fetch(user_id)
        st.warning("⚠️ Termination signal sent! Stopping job search...")
        st.rerun()

    if is_running:
        st.progress(state["progress"])
        st.info(f"⏳ {state['status']}")
        time.sleep(2)
        st.rerun()
    elif state["done"]:
        if state["stopped"]:
            st.warning(f"⏹️ {state['status']}")
        elif state["error"]:
            st.error(f"❌ {state['status']}")
        else:
            st.success(f"✅ {state['status']}")

@st.fragment
def render_send_section(user):
    user_id = user["id"]
    state = mgr.get_send_state(user_id)
    is_running = state["running"]

    st.caption(f"Dispatches emails via SMTP from **{user['email']}** attaching role-matched resumes.")
    force_send = st.checkbox("Bypass schedule slot (Force Send)", value=True, disabled=is_running, key="chk_force_send")
    
    send_col1, send_col2 = st.columns(2)
    with send_col1:
        batch_limit = st.number_input("Max emails to send in this batch", min_value=1, max_value=100, value=10, disabled=is_running, key="num_batch_limit")
    with send_col2:
        outreach_max_days = st.number_input("Target jobs posted within (days)", min_value=1, max_value=90, value=7, disabled=is_running, key="num_outreach_days", help="Only email jobs posted within this many days.")

    btn_mail_col1, btn_mail_col2 = st.columns([1.5, 1])
    with btn_mail_col1:
        start_mail = st.button("▶️ Start Sending Batch", key="btn_start_mail", type="primary", disabled=is_running, use_container_width=True)
    with btn_mail_col2:
        stop_mail = st.button("⏹️ Terminate Batch", key="btn_stop_mail", type="secondary", disabled=(not is_running), use_container_width=True)

    if start_mail and not is_running:
        mgr.clear_send(user_id)
        mgr.start_send(user_id, user, force=force_send, limit=batch_limit, max_days_old=int(outreach_max_days))
        st.rerun()

    if stop_mail and is_running:
        mgr.stop_send(user_id)
        st.warning("⚠️ Termination signal sent! Aborting email dispatch...")
        st.rerun()

    if is_running:
        st.progress(state["progress"])
        st.info(f"✉️ {state['status']}")
        time.sleep(2)
        st.rerun()
    elif state["done"]:
        if state["stopped"]:
            st.warning(f"⏹️ {state['status']}")
        elif state["error"]:
            st.error(f"❌ {state['status']}")
        else:
            st.success(f"✅ {state['status']}")

@st.fragment
def render_followup_section(user):
    user_id = user["id"]
    state = mgr.get_followup_state(user_id)
    is_running = state["running"]

    due_count = get_due_followups_count(user_id=user_id, days=3)

    st.caption(r"Sends polite threaded follow-up emails (`In-Reply-To` & `References`) for cold outreach sent >= 3 days ago without a reply.")
    
    col_metric, col_inputs = st.columns([1, 2])
    with col_metric:
        st.metric(label="Follow-ups Due (>= 3 Days)", value=due_count)
    with col_inputs:
        f_limit = st.number_input("Max follow-ups to send", min_value=1, max_value=50, value=min(10, max(1, due_count)) if due_count > 0 else 5, disabled=is_running, key="num_followup_limit")
        days_threshold = st.number_input("Days since cold email", min_value=1, max_value=30, value=3, disabled=is_running, key="num_followup_days")

    btn_f_col1, btn_f_col2 = st.columns([1.5, 1])
    with btn_f_col1:
        start_f = st.button("▶️ Start 3-Day Follow-Up Batch", key="btn_start_followup", type="primary", disabled=(is_running or due_count == 0), use_container_width=True)
    with btn_f_col2:
        stop_f = st.button("⏹️ Terminate Follow-Ups", key="btn_stop_followup", type="secondary", disabled=(not is_running), use_container_width=True)

    if start_f and not is_running:
        mgr.clear_followup(user_id)
        mgr.start_followup(user_id, user, days=days_threshold, limit=f_limit)
        st.rerun()

    if stop_f and is_running:
        mgr.stop_followup(user_id)
        st.warning("⚠️ Termination signal sent! Aborting follow-up dispatch...")
        st.rerun()

    if is_running:
        st.progress(state["progress"])
        st.info(f"📬 {state['status']}")
        time.sleep(2)
        st.rerun()
    elif state["done"]:
        if state["stopped"]:
            st.warning(f"⏹️ {state['status']}")
        elif state["error"]:
            st.error(f"❌ {state['status']}")
        else:
            st.success(f"✅ {state['status']}")

def render_outreach_view(user):
    st.subheader("Pipeline Execution")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 1. Fetch Live Jobs")
        render_fetch_section(user)

    with col2:
        st.markdown("### 2. Send Cold Outreach Batch")
        render_send_section(user)

    st.markdown("---")
    st.markdown("### 3. Automated Follow-up Drip Sequences (3-day follow-up)")
    render_followup_section(user)

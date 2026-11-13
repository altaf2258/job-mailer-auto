import time
import threading
from datetime import datetime
from core.fetcher import fetch_and_store_jobs
from core.mailer import send_scheduled_emails, send_followup_emails
from core.db import get_connection, get_profile_by_id, get_stats, get_due_followups_count

_scheduler_started = False
_scheduler_lock = threading.Lock()

def get_all_active_profiles():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM user_profiles")
        rows = cursor.fetchall()
        conn.close()
        profiles = []
        for r in rows:
            p = get_profile_by_id(r["id"])
            if p and p.get("email"):
                profiles.append(p)
        return profiles
    except Exception as e:
        print(f"[Scheduler] Error querying profiles: {e}")
        return []

def scheduler_worker():
    print("[Scheduler] ⏰ In-App Slot Dispatch Daemon started! Monitoring all user slots every 30 seconds.")
    last_dispatched = {}  # key: (user_id, hour) -> today's date str to avoid duplicate sends in the same hour

    while True:
        try:
            now = datetime.now()
            current_hour = now.hour
            today_str = now.strftime("%Y-%m-%d")

            profiles = get_all_active_profiles()
            for profile in profiles:
                pid = profile["id"]
                pname = profile.get("profile_name", f"User #{pid}")
                custom_slots = profile.get("custom_slots") or []

                for s in custom_slots:
                    slot_hour = int(s.get("hour", -1))
                    if slot_hour == current_hour:
                        dispatch_key = (pid, current_hour, today_str)
                        if dispatch_key not in last_dispatched:
                            slot_name = s.get("name", f"Slot {current_hour}:00")
                            slot_limit = int(s.get("limit", 10))
                            print(f"\n[Scheduler] 🚀 TRIGGERING SCHEDULED SLOT: '{slot_name}' for {pname} (Limit: {slot_limit} emails, Hour: {current_hour}:00)")
                            last_dispatched[dispatch_key] = True

                            try:
                                sent, summary = send_scheduled_emails(
                                    force=True,
                                    custom_limit=slot_limit,
                                    profile_override=profile
                                )
                                print(f"[Scheduler] Result for {pname}: {summary}")
                            except Exception as e:
                                print(f"[Scheduler] Error sending for {pname}: {e}")

                            # Check for 3-day follow-ups
                            try:
                                due = get_due_followups_count(user_id=pid, days=3)
                                if due > 0:
                                    print(f"[Scheduler] 📬 Found {due} due follow-ups for {pname}. Dispatching...")
                                    f_sent, f_summary = send_followup_emails(days=3, custom_limit=5, profile_override=profile)
                                    print(f"[Scheduler] Follow-up result: {f_summary}")
                            except Exception as e:
                                print(f"[Scheduler] Follow-up dispatch error: {e}")

        except Exception as e:
            print(f"[Scheduler Worker Error]: {e}")

        time.sleep(30)

def start_inapp_scheduler():
    global _scheduler_started
    with _scheduler_lock:
        if not _scheduler_started:
            t = threading.Thread(target=scheduler_worker, daemon=True, name="InAppTimingSlotScheduler")
            t.start()
            _scheduler_started = True
            return True
        return False


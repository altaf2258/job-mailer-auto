"""
Automated background dispatcher for candidate email outreach and morning job discovery.
Evaluates all active candidates' 3 custom slots continuously or per scheduled invocation.
"""
import time
import argparse
from datetime import datetime
from core.fetcher import fetch_and_store_jobs
from core.mailer import send_scheduled_emails, send_followup_emails
from core.db import get_connection, get_profile_by_id, get_stats, get_due_followups_count

def get_all_active_profiles():
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

def execute_slot_cycle():
    now = datetime.now()
    current_hour = now.hour
    time_str = now.strftime('%Y-%m-%d %H:%M:%S')

    profiles = get_all_active_profiles()
    if not profiles:
        print(f"[{time_str}] [Worker] No candidate profiles found in database.")
        return

    print(f"\n[{time_str}] ========== Starting Automated Slot Evaluation ({len(profiles)} candidates) ==========")

    for profile in profiles:
        pid = profile["id"]
        pname = profile.get("profile_name", f"User #{pid}")
        email = profile.get("email")
        custom_slots = profile.get("custom_slots") or [
            {"hour": 10, "limit": 10, "name": "Morning Window"},
            {"hour": 14, "limit": 10, "name": "Afternoon Window"},
            {"hour": 17, "limit": 5, "name": "Evening Window"}
        ]

        # 1. Early morning automated job discovery (08:00 AM)
        if current_hour == 8:
            print(f"[{time_str}] [User {pname}] Morning job discovery window. Searching fresh jobs...")
            try:
                added = fetch_and_store_jobs(profile_override=profile)
                print(f"[{time_str}] [User {pname}] Job discovery complete: added {added} records.")
            except Exception as e:
                print(f"[{time_str}] [User {pname}] Error during job fetch: {e}")

        # 2. Check candidate's custom slot hours
        matched_slot = None
        for s in custom_slots:
            if int(s.get("hour", -1)) == current_hour:
                matched_slot = s
                break

        if matched_slot:
            slot_name = matched_slot.get("name", f"Slot {current_hour}:00")
            slot_limit = int(matched_slot.get("limit", 10))
            print(f"[{time_str}] [User {pname}] ⏰ Current hour ({current_hour}:00) MATCHES '{slot_name}' (Limit: {slot_limit})! Dispatching outreach...")
            try:
                sent, summary = send_scheduled_emails(
                    force=True,
                    custom_limit=slot_limit,
                    profile_override=profile
                )
                print(f"[{time_str}] [User {pname}] {summary}")
            except Exception as e:
                print(f"[{time_str}] [User {pname}] Error during outreach dispatch: {e}")

            # Also check if candidate has any due 3-day follow-ups during scheduled slot
            try:
                due_f_count = get_due_followups_count(user_id=pid, days=3)
                if due_f_count > 0:
                    print(f"[{time_str}] [User {pname}] 📬 Found {due_f_count} due 3-day follow-up(s). Dispatching follow-up sequence...")
                    f_sent, f_summary = send_followup_emails(days=3, custom_limit=5, profile_override=profile)
                    print(f"[{time_str}] [User {pname}] {f_summary}")
            except Exception as e:
                print(f"[{time_str}] [User {pname}] Error during follow-up dispatch: {e}")
        else:
            configured_hours = [f"{int(s.get('hour', 0)):02d}:00" for s in custom_slots if "hour" in s]
            print(f"[{time_str}] [User {pname}] Standby. Current hour ({current_hour}:00) is outside configured windows ({', '.join(configured_hours)}).")

        stats = get_stats(user_id=pid)
        print(f"[{time_str}] [User {pname}] Status -> Total Leads: {stats['total']} | Pending: {stats['pending']} | Sent: {stats['sent']}")

    print(f"[{time_str}] ==================================================================================\n")

def run_continuous_daemon(check_interval_seconds=60):
    print("=" * 70)
    print("💼 AI Job Mailer Automated Timing Slot Daemon Active")
    print("Continuously monitors candidate custom slots every minute.")
    print("Press Ctrl+C to stop.")
    print("=" * 70)

    last_dispatched_hour = None
    today_date = None

    while True:
        now = datetime.now()
        current_hour = now.hour
        current_date = now.strftime("%Y-%m-%d")

        # Trigger once per hour upon transition
        if (current_date, current_hour) != (today_date, last_dispatched_hour):
            execute_slot_cycle()
            today_date = current_date
            last_dispatched_hour = current_hour

        time.sleep(check_interval_seconds)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Timing Slot Runner")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background checking slots every minute")
    args = parser.parse_args()

    if args.daemon:
        run_continuous_daemon()
    else:
        execute_slot_cycle()

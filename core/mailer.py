import os
import smtplib
import time
import random
import uuid
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid

from core.config import load_config
from core.db import (
    init_db, get_pending_leads, mark_lead_sent, 
    get_active_profile, get_resume_for_job,
    get_due_followups, is_lead_already_sent_outreach
)
from core.personalizer import render_pitch_for_profile, render_followup_pitch_for_profile, extract_text_from_pdf
from core.matcher import is_role_matching_targets
from core.resume_tailorer import extract_and_tailor_any_resume_with_gemini, build_dynamic_ats_pdf
from core.crypto import decrypt_secret
from core.tracker import get_tracking_base_url

def get_slot_info(cfg, profile=None):
    """
    Checks active profile's 3 custom timing slots, falling back to config.yaml slots.
    """
    current_hour = datetime.now().hour
    
    # 1. Check user profile's custom slots
    if profile and profile.get("custom_slots"):
        for slot in profile["custom_slots"]:
            if int(slot.get("hour", -1)) == current_hour:
                return slot.get("name", f"Slot {current_hour}:00"), int(slot.get("limit", 10))

    # 2. Fallback to global config slots
    slots = cfg.get("mailer", {}).get("slots", {})
    if current_hour in slots:
        slot_data = slots[current_hour]
        return slot_data.get("name", f"Slot {current_hour}:00"), slot_data.get("limit", 10)
    elif str(current_hour) in slots:
        slot_data = slots[str(current_hour)]
        return slot_data.get("name", f"Slot {current_hour}:00"), slot_data.get("limit", 10)
    return None, 0

def send_single_email(server, profile, lead, category):
    sender_email = profile.get("email")
    sender_name = profile.get("full_name") or profile.get("name") or "Job Applicant"
    profile_id = profile.get("id")
    role_name = lead.get("role", "")

    # Unique tracking ID for this outgoing message
    tracking_id = str(uuid.uuid4())
    base_track_url = get_tracking_base_url()

    # Retrieve base matching resume
    resume_path = get_resume_for_job(profile_id, job_role=role_name, category=category) if profile_id else None
    
    # 1. LIVE KEYWORD EXTRACTION & RESUME TAILORING PER JOB DESCRIPTION
    raw_gemini = profile.get("gemini_api_key") or ""
    gemini_key = decrypt_secret(raw_gemini).strip() if raw_gemini else ""
    job_desc = lead.get("job_description") or ""

    tailored_resume_path = None
    extracted_keywords = []

    if gemini_key and job_desc and len(job_desc.strip()) > 50:
        base_resume_text = extract_text_from_pdf(resume_path) if resume_path else ""
        tailored_data = extract_and_tailor_any_resume_with_gemini(profile, lead, base_resume_text, gemini_key)
        if tailored_data:
            extracted_keywords = [
                s.strip()
                for cat in tailored_data.get("skills_categories", [])
                for s in cat.get("skills", "").split(",") if s.strip()
            ][:8]
            print(f"    [JD Keyword Optimizer] Dynamic tailored skills extracted: {extracted_keywords}")
            
            # Generate a dynamic job-tailored PDF resume in a dedicated tailored folder
            clean_company = "".join(c for c in lead.get("company", "Company") if c.isalnum() or c in (' ', '_', '-')).strip()
            clean_role = "".join(c for c in role_name if c.isalnum() or c in (' ', '_', '-')).strip()
            cand_name_slug = (profile.get("full_name") or "Candidate").replace(" ", "_")
            tailored_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", f"user_{profile_id}", "tailored_resumes")
            tailored_pdf_name = f"{cand_name_slug}_{clean_company}_{clean_role}_Tailored.pdf".replace(" ", "_")
            out_pdf = os.path.join(tailored_dir, tailored_pdf_name)

            try:
                build_dynamic_ats_pdf(tailored_data, out_pdf)
                if os.path.exists(out_pdf):
                    tailored_resume_path = out_pdf
                    print(f"    [ATS Resume Generator] Created dynamic tailored PDF: '{tailored_pdf_name}'")
            except Exception as e:
                print(f"    [ATS Resume Generator] Fallback to base resume: {e}")

    # 2. Render email pitch (incorporates extracted JD keywords into the 200-300 word email body)
    subject, text_content = render_pitch_for_profile(profile, lead, category, extracted_keywords=extracted_keywords)

    # 3. Create Multi-Part Alternative: Plaintext + Tracked HTML with 1x1 Pixel & Tracked Links
    candidate_linkedin = profile.get("linkedin") or "https://linkedin.com"
    encoded_linkedin = urllib.parse.quote(candidate_linkedin)
    tracked_link_url = f"{base_track_url}/track/click?tid={tracking_id}&url={encoded_linkedin}"
    open_pixel_url = f"{base_track_url}/track/open?tid={tracking_id}"
    resume_view_url = f"{base_track_url}/track/resume?tid={tracking_id}"

    # Build clean HTML email wrapping plain text paragraphs and injecting invisible pixel
    paragraphs = [f"<p style='margin: 0 0 12px 0; line-height: 1.5;'>{p.strip()}</p>" for p in text_content.split("\n\n") if p.strip()]
    html_body_paragraphs = "\n".join(paragraphs)
    # Replace plain text LinkedIn with tracked link if present in text
    if candidate_linkedin in html_body_paragraphs:
        html_body_paragraphs = html_body_paragraphs.replace(
            candidate_linkedin,
            f"<a href='{tracked_link_url}' style='color: #0A66C2; text-decoration: underline;'>{candidate_linkedin}</a>"
        )
    else:
        # Append clean tracked LinkedIn link below signature
        html_body_paragraphs += f"<p style='margin-top: 10px;'><a href='{tracked_link_url}' style='color: #0A66C2; text-decoration: underline;'>🔗 View My LinkedIn / Portfolio</a></p>"

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14.5px; color: #222222; background-color: #ffffff;">
{html_body_paragraphs}
<!-- 1x1 Transparent Open Tracking Pixel -->
<img src="{open_pixel_url}" width="1" height="1" alt="" style="display:none !important; width:1px !important; height:1px !important; border:0 !important;" />
</body>
</html>"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14.5px; color: #222222; background-color: #ffffff;">
{html_body_paragraphs}
<!-- 1x1 Transparent Open Tracking Pixel -->
<img src="{open_pixel_url}" width="1" height="1" alt="" style="display:none !important; width:1px !important; height:1px !important; border:0 !important;" />
</body>
</html>"""

    msg = MIMEMultipart('mixed')
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = lead['email']
    msg['Subject'] = subject
    msg_id = make_msgid()
    msg['Message-ID'] = msg_id

    # Attach alternative body: text/plain + text/html
    alt_part = MIMEMultipart('alternative')
    alt_part.attach(MIMEText(text_content, 'plain'))
    alt_part.attach(MIMEText(html_content, 'html'))
    msg.attach(alt_part)

    # Select tailored resume first, fallback to standard sub-role resume
    final_resume_path = tailored_resume_path if (tailored_resume_path and os.path.exists(tailored_resume_path)) else resume_path
    attached_file_name = None

    if final_resume_path and os.path.exists(final_resume_path):
        with open(final_resume_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            attached_file_name = os.path.basename(final_resume_path)
            part.add_header("Content-Disposition", f"attachment; filename={attached_file_name}")
            msg.attach(part)
            print(f"    -> Attached {'JD-Tailored' if final_resume_path == tailored_resume_path else 'Standard'} resume: '{attached_file_name}' for [{category} | {role_name}]")
    else:
        print(f"    -> Warning: No resume found for [{category} | {role_name}]. Sending text pitch only.")

    server.sendmail(sender_email, lead['email'], msg.as_string())
    return msg_id, subject, attached_file_name, tracking_id

def send_scheduled_emails(force=False, custom_limit=None, progress_callback=None, profile_override=None, stop_event=None, max_days_old=7):
    init_db()
    cfg = load_config()

    profile = profile_override or get_active_profile()
    if not profile:
        return 0, "No active user profile found. Please create or activate one."

    sender_email = profile.get("email")
    
    # STRICT REQUIREMENT: Decrypt Gmail App Password directly from user's encrypted database record.
    # NEVER fall back to .env or system secrets.
    from core.crypto import decrypt_secret
    raw_app_pwd = profile.get("smtp_password") or ""
    app_password = decrypt_secret(raw_app_pwd).strip()

    if not sender_email or not app_password:
        return 0, f"Missing Gmail address or App Password in profile '{profile.get('profile_name')}'. Please configure it under '🔑 Credentials & API Keys'."

    slot_name, slot_limit = get_slot_info(cfg, profile=profile)
    if not slot_name and not force:
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] Outside scheduled windows for profile '{profile.get('profile_name')}'. Use force=True to bypass."
        print(msg)
        return 0, msg

    active_slot = slot_name if slot_name else "Manual Batch"
    limit = custom_limit or (slot_limit if slot_limit > 0 else 10)

    user_profile_id = profile.get("id") if profile else 1
    pending_leads = get_pending_leads(limit=limit * 2, user_id=user_profile_id, max_days_old=max_days_old)  # Fetch extra to account for role skips
    if not pending_leads:
        msg = "No pending leads with valid emails found to send."
        print(msg)
        return 0, msg

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, app_password)
    except Exception as e:
        return 0, f"SMTP Connection failed for {sender_email}: {e}"

    sent_count = 0
    min_delay = cfg.get("mailer", {}).get("min_delay_secs", 45)
    max_delay = cfg.get("mailer", {}).get("max_delay_secs", 80)

    print(f"\n--- Dispatching for Profile: {profile.get('profile_name')} ({sender_email}) ---")

    for i, lead in enumerate(pending_leads):
        if stop_event:
            is_stopped = stop_event.is_set() if hasattr(stop_event, "is_set") else bool(stop_event())
            if is_stopped:
                print("\n[Mailer] Dispatch terminated early by user request.")
                if progress_callback:
                    progress_callback("Outreach batch terminated by user.", sent_count / max(1, limit))
                break

        if sent_count >= limit:
            break

        to_email = (lead.get('email') or '').strip().lower()
        company = lead.get('company', '').strip()
        role = lead.get('role', '').strip()
        category = lead.get('category', 'FULLSTACK')

        if not to_email or '@' not in to_email or to_email in ['none', 'nan', 'null', '']:
            continue

        # SAFETY CHECK: Only skip if this company or email is in sent_logs from an ACTUAL sent email (not this lead itself)
        user_id = profile.get('id', 1)
        if is_lead_already_sent_outreach(company, to_email, user_id=user_id):
            print(f"Skipping {company} ({to_email}): Company or email already received outreach.")
            continue

        target_roles = profile.get("target_roles") or []
        if target_roles and not is_role_matching_targets(role, target_roles):
            print(f"Skipping {company} ({role}): Does not match target roles.")
            continue

        log_str = f"[{sent_count+1}/{limit}] Sending [{category}] -> {to_email} ({company})..."
        print(log_str)
        if progress_callback:
            progress_callback(log_str, (sent_count) / limit)

        try:
            msg_id, subject, attached_resume, tracking_id = send_single_email(
                server=server,
                profile=profile,
                lead=lead,
                category=category
            )
            mark_lead_sent(
                lead_id=lead['id'],
                profile_id=profile.get('id'),
                email=to_email,
                company=company,
                role=role,
                category=category,
                slot=active_slot,
                message_id=msg_id,
                subject=subject,
                resume_sent=attached_resume,
                tracking_id=tracking_id
            )
            sent_count += 1

            if sent_count < limit:
                delay = random.randint(min_delay, max_delay)
                print(f"Waiting {delay}s for inbox health...")
                time.sleep(delay)

        except Exception as e:
            print(f"Failed sending to {to_email}: {e}")

    server.quit()
    summary = f"Slot '{active_slot}' complete. Profile '{profile.get('profile_name')}' sent {sent_count} emails."
    print(summary)
    return sent_count, summary

def send_followup_emails(days=3, custom_limit=None, progress_callback=None, profile_override=None, stop_event=None):
    """
    Sends automated follow-up emails in the same thread (via In-Reply-To and References)
    for cold emails sent >= `days` ago (default 3 days).
    """
    init_db()
    cfg = load_config()

    profile = profile_override or get_active_profile()
    if not profile:
        return 0, "No active user profile found. Please create or activate one."

    sender_email = profile.get("email")
    from core.crypto import decrypt_secret
    raw_app_pwd = profile.get("smtp_password") or ""
    app_password = decrypt_secret(raw_app_pwd).strip()

    if not sender_email or not app_password:
        return 0, f"Missing Gmail credentials for profile '{profile.get('profile_name')}'."

    user_profile_id = profile.get("id") if profile else 1
    limit = custom_limit or 10
    due_leads = get_due_followups(user_id=user_profile_id, days=days, limit=limit)
    if not due_leads:
        msg = f"No cold emails sent >= {days} days ago are currently pending follow-up."
        print(msg)
        return 0, msg

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, app_password)
    except Exception as e:
        return 0, f"SMTP Connection failed for {sender_email}: {e}"

    sent_count = 0
    min_delay = cfg.get("mailer", {}).get("min_delay_secs", 45)
    max_delay = cfg.get("mailer", {}).get("max_delay_secs", 80)

    sender_name = profile.get("full_name") or profile.get("name") or "Job Applicant"
    print(f"\n--- Dispatching Follow-ups for: {profile.get('profile_name')} ({sender_email}) ---")

    for i, lead in enumerate(due_leads):
        if stop_event:
            is_stopped = stop_event.is_set() if hasattr(stop_event, "is_set") else bool(stop_event())
            if is_stopped:
                print("\n[Followup] Dispatch terminated early by user request.")
                if progress_callback:
                    progress_callback("Follow-up batch terminated by user.", sent_count / max(1, limit))
                break

        if sent_count >= limit:
            break

        to_email = (lead.get("email") or "").strip().lower()
        company = lead.get("company", "").strip()
        role = lead.get("role", "").strip()
        category = lead.get("category", "FULLSTACK")
        orig_msg_id = lead.get("original_message_id")

        log_str = f"[Followup {sent_count+1}/{limit}] Following up with {company} ({to_email})..."
        print(log_str)
        if progress_callback:
            progress_callback(log_str, sent_count / max(1, len(due_leads)))

        try:
            subject, text_content = render_followup_pitch_for_profile(profile, lead)

            msg = MIMEMultipart()
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            new_msg_id = make_msgid()
            msg['Message-ID'] = new_msg_id

            # Crucial: Threading headers for Gmail and standard email clients
            if orig_msg_id:
                msg['In-Reply-To'] = orig_msg_id
                msg['References'] = orig_msg_id

            msg.attach(MIMEText(text_content, 'plain'))

            # Attach tailored resume for follow-up
            resume_path = get_resume_for_job(user_profile_id, job_role=role, category=category)
            attached_file_name = None
            if resume_path and os.path.exists(resume_path):
                with open(resume_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    attached_file_name = os.path.basename(resume_path)
                    part.add_header("Content-Disposition", f"attachment; filename={attached_file_name}")
                    msg.attach(part)

            server.sendmail(sender_email, to_email, msg.as_string())

            # Mark sent as follow-up in database
            mark_lead_sent(
                lead_id=lead.get('lead_id'),
                profile_id=user_profile_id,
                email=to_email,
                company=company,
                role=role,
                category=category,
                slot="Follow-up Sequence",
                message_id=new_msg_id,
                resume_sent=attached_file_name,
                subject=subject,
                is_followup=1
            )
            sent_count += 1

            if sent_count < len(due_leads) and sent_count < limit:
                delay = random.randint(min_delay, max_delay)
                print(f"Waiting {delay}s for inbox health...")
                time.sleep(delay)

        except Exception as e:
            print(f"Failed sending follow-up to {to_email}: {e}")

    server.quit()
    summary = f"Follow-up drip sequence completed: Sent {sent_count} follow-ups for '{profile.get('profile_name')}'."
    print(summary)
    return sent_count, summary

if __name__ == "__main__":
    import sys
    force_run = "--force" in sys.argv
    send_scheduled_emails(force=force_run)

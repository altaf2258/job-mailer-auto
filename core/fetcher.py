import requests
import time
from datetime import datetime, timezone
from core.config import load_config
from core.db import init_db, add_lead, is_lead_existing_or_sent, get_active_profile
from core.verifier import verify_email
from core.personalizer import detect_role_category
from core.crawler import crawl_company_for_email, extract_valid_emails_from_text
from core.matcher import is_experience_matching, is_role_matching_targets

def is_company_excluded(company_name, excluded_list):
    clean = str(company_name).lower().strip()
    return any(ex.lower().strip() in clean for ex in excluded_list)

def fetch_and_store_jobs(progress_callback=None, profile_override=None, stop_event=None, max_days_old=7, job_board="All Platforms"):
    """
    Searches jobs via JSearch using active user profile's target roles, cities, and custom RapidAPI key.
    Supports a configurable max_days_old (1 to 30 days), portal-specific filtering (Naukri, Indeed, LinkedIn, Glassdoor),
    and early stop_event.
    """
    init_db()
    cfg = load_config()

    profile = profile_override or get_active_profile()
    
    # STRICT REQUIREMENT: Take RapidAPI key directly from user's encrypted database record.
    # NEVER fall back to .env or system secrets.
    from core.crypto import decrypt_secret
    raw_key = (profile.get("rapidapi_key") if profile else None) or ""
    rapidapi_key = decrypt_secret(raw_key).strip()

    if not rapidapi_key:
        err_msg = f"[Error] No RapidAPI Key found in profile '{profile.get('profile_name') if profile else 'Unknown'}'. Please enter your RapidAPI Key in the dashboard under '🔑 Credentials & API Keys'."
        print(err_msg)
        return 0

    if profile:
        roles = profile.get("target_roles") or ["Full Stack Developer", "Frontend Developer", "Backend Developer"]
        user_cities = profile.get("target_cities")
        # If user left target_cities empty or None, search across entire India
        cities = user_cities if (user_cities and len(user_cities) > 0) else ["India"]
        excluded = profile.get("excluded_companies") or []
        user_years = profile.get("years_experience", 3)
        loc_desc = ", ".join(cities) if cities != ["India"] else "All over India"
        print(f"[Fetcher] Using preferences & RapidAPI key for: '{profile.get('profile_name')}' ({user_years} YOE, Location: {loc_desc})")
    else:
        roles = cfg.get("search", {}).get("roles", ["Full Stack Developer"])
        user_cities = cfg.get("search", {}).get("cities", [])
        cities = user_cities if (user_cities and len(user_cities) > 0) else ["India"]
        excluded = cfg.get("rules", {}).get("excluded_companies", [])
        user_years = 3

    url = "https://jsearch.p.rapidapi.com/search-v2"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "jsearch.p.rapidapi.com"
    }

    total_jobs_added = 0
    total_with_email = 0
    total_searches = len(cities) * len(roles)
    completed_searches = 0

    for city in cities:
        for role in roles:
            # Check if user requested termination
            if stop_event:
                is_stopped = stop_event.is_set() if hasattr(stop_event, "is_set") else bool(stop_event())
                if is_stopped:
                    print("\n[Fetcher] Terminated by user request.")
                    if progress_callback:
                        progress_callback("Fetch terminated by user.", completed_searches / max(1, total_searches))
                    return total_jobs_added

            completed_searches += 1
            # Incorporate experience query refinement: e.g. "Frontend Developer 3-5 years in India" or "... in Bangalore, India"
            exp_min = max(0, int(user_years) - 1)
            exp_max = int(user_years) + 1
            
            # Platform modifier for JSearch
            board_modifier = ""
            clean_board = str(job_board).lower()
            if "naukri" in clean_board:
                board_modifier = " via naukri.com"
            elif "indeed" in clean_board:
                board_modifier = " via indeed.com"
            elif "linkedin" in clean_board:
                board_modifier = " via linkedin.com"
            elif "glassdoor" in clean_board:
                board_modifier = " via glassdoor.com"

            if city.strip().lower() in ["india", "all", "pan india", "remote"]:
                query = f"{role} {exp_min}-{exp_max} years in India{board_modifier}"
            else:
                query = f"{role} {exp_min}-{exp_max} years in {city}, India{board_modifier}"
            msg = f"[{completed_searches}/{total_searches}] Querying JSearch for: {query}..."
            print(msg)
            if progress_callback:
                progress_callback(msg, completed_searches / total_searches)

            # Map max_days_old to JSearch date_posted filter
            if max_days_old <= 1:
                jsearch_date_posted = "today"
            elif max_days_old <= 3:
                jsearch_date_posted = "3days"
            elif max_days_old <= 7:
                jsearch_date_posted = "week"
            else:
                jsearch_date_posted = "month"

            params = {
                "query": query,
                "num_pages": 1,
                "date_posted": jsearch_date_posted
            }

            max_retries = 3
            res = None
            for attempt in range(1, max_retries + 1):
                try:
                    res = requests.get(url, headers=headers, params=params, timeout=30)
                    if res.status_code == 200:
                        break
                    elif res.status_code == 429:
                        print(f"  [API Warning] Rate limit hit (429). Retrying in 3s (attempt {attempt}/{max_retries})...")
                        time.sleep(3)
                except requests.exceptions.RequestException as req_err:
                    print(f"  [Network Warning] Attempt {attempt}/{max_retries} failed ({req_err}). Retrying in 2s...")
                    time.sleep(2)

            if not res or res.status_code != 200:
                print(f"  [Fetch Failed] Could not retrieve jobs for query: '{query}'")
                continue

            try:
                res_json = res.json()
                raw_data = res_json.get("data", {})
                if isinstance(raw_data, dict):
                    jobs = raw_data.get("jobs", [])
                elif isinstance(raw_data, list):
                    jobs = raw_data
                else:
                    jobs = []

                for item in jobs:
                    company = (item.get("employer_name") or "").strip()
                    job_title = (item.get("job_title") or "").strip()
                    desc = item.get("job_description") or ""
                    website = item.get("employer_website") or ""
                    job_url = item.get("job_apply_link") or item.get("job_google_link") or ""

                    if not company or is_company_excluded(company, excluded):
                        continue

                    # STRICT USER-CONFIGURABLE RECENCY CHECK (USING UTC TIME):
                    # Discard if job is older than max_days_old days
                    posted_at_iso = item.get("job_posted_at_datetime_utc")
                    posted_at_ts = item.get("job_posted_at_timestamp")
                    posted_dt_utc = None

                    if posted_at_iso:
                        try:
                            # Parse e.g. 2026-11-10T14:30:00.000Z to UTC
                            clean_iso = posted_at_iso.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(clean_iso)
                            posted_dt_utc = dt.astimezone(timezone.utc)
                        except Exception:
                            pass
                    elif posted_at_ts:
                        try:
                            posted_dt_utc = datetime.fromtimestamp(float(posted_at_ts), tz=timezone.utc)
                        except Exception:
                            pass

                    # Fallback to current UTC time if posted date is unspecified by API
                    now_utc = datetime.now(timezone.utc)
                    if not posted_dt_utc:
                        posted_dt_utc = now_utc

                    # Calculate age in days using pure UTC timestamps
                    age_seconds = (now_utc - posted_dt_utc).total_seconds()
                    if age_seconds > max_days_old * 86400:
                        age_days = int(age_seconds // 86400)
                        print(f"  [Skipped - Too Old] {job_title} at {company} (Posted {age_days} days ago > {max_days_old} days in UTC)")
                        continue

                    # Standardize storage format: YYYY-MM-DD HH:MM:SS in UTC
                    posted_at_str = posted_dt_utc.strftime("%Y-%m-%d %H:%M:%S")

                    # STRICT ROLE MATCH CHECK:
                    # Guarantees returned jobs strictly align with the user's selected roles (e.g. Reject Java/PHP if user chose Angular)
                    if roles and not is_role_matching_targets(job_title, roles):
                        print(f"  [Skipped - Role Mismatch] '{job_title}' at {company} (Does not match selected target roles: {roles})")
                        continue

                    # STRICT EXPERIENCE MATCH CHECK:
                    # e.g., if user has 4 years, match jobs within [3, 5] years range.
                    full_job_context = f"{job_title} {desc}"
                    if not is_experience_matching(full_job_context, user_years):
                        print(f"  [Skipped - Exp Mismatch] {job_title} at {company} (Outside {exp_min}-{exp_max} years for {user_years} YOE)")
                        continue

                    user_profile_id = profile.get("id") if profile else 1
                    if is_lead_existing_or_sent(company, job_title, user_id=user_profile_id):
                        continue

                    email = None
                    email_source = "none"

                    # 1. Search description text for published emails
                    desc_emails = extract_valid_emails_from_text(desc)
                    if desc_emails:
                        email = desc_emails[0]
                        email_source = "job_description"

                    # 2. Crawl company's real website (/careers, /jobs, /contact)
                    if not email and website:
                        crawled_email, page_source = crawl_company_for_email(website)
                        if crawled_email:
                            email = crawled_email
                            email_source = f"crawled:{page_source}"

                    # Verify MX DNS records to prevent bounces
                    if email:
                        is_valid, reason = verify_email(email)
                        if not is_valid:
                            email = None
                            email_source = "none"

                    category = detect_role_category(job_title)
                    inserted = add_lead(
                        company=company,
                        role=job_title,
                        city=city,
                        email=email,
                        contact_name="Hiring Team",
                        category=category,
                        email_source=email_source,
                        job_url=job_url,
                        user_id=user_profile_id,
                        website=website if website else None,
                        job_description=desc if desc else None,
                        posted_at=posted_at_str
                    )

                    if inserted:
                        total_jobs_added += 1
                        if email:
                            total_with_email += 1
                            print(f"  [Has Email] {company} -> {email}")

            except Exception as e:
                print(f"Error querying {query}: {e}")

    print(f"\n[Fetch Done] Recorded {total_jobs_added} total jobs in database ({total_with_email} with verified emails).")
    return total_jobs_added

if __name__ == "__main__":
    fetch_and_store_jobs()

import sqlite3
import os
import json
import hashlib
import uuid
import time
from datetime import datetime
from core.crypto import encrypt_secret, decrypt_secret

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "job_mailer.db")

def hash_password(password: str) -> str:
    if not password:
        return ""
    salt = "job_mailer_secure_salt_2026"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    return hash_password(plain_password) == hashed_password

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            smtp_password TEXT,
            rapidapi_key TEXT,
            custom_slots TEXT,          -- JSON list of 3 slots: [{"hour": 10, "limit": 10}, ...]
            phone TEXT,
            linkedin TEXT,
            years_experience INTEGER DEFAULT 3,
            primary_title TEXT DEFAULT 'Software Engineer',
            is_active INTEGER DEFAULT 0,
            target_roles TEXT,
            target_cities TEXT,
            excluded_companies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES user_profiles(id) ON DELETE CASCADE,
            UNIQUE(profile_id, category)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            subject_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES user_profiles(id) ON DELETE CASCADE,
            UNIQUE(profile_id, category)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            city TEXT,
            email TEXT,
            contact_name TEXT DEFAULT 'Hiring Team',
            category TEXT DEFAULT 'FULLSTACK',
            status TEXT DEFAULT 'NEW',
            email_source TEXT DEFAULT 'none',
            job_url TEXT,
            website TEXT,
            job_description TEXT,
            posted_at TIMESTAMP,
            match_score INTEGER DEFAULT 0,
            custom_note TEXT,
            is_deleted INTEGER DEFAULT 0,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE,
            UNIQUE(user_id, company, role, city)
        );
    """)

    # Ensure columns exist for existing databases
    cursor.execute("PRAGMA table_info(user_profiles)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if "custom_slots" not in user_cols:
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN custom_slots TEXT;")
    if "gemini_api_key" not in user_cols:
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN gemini_api_key TEXT;")

    cursor.execute("PRAGMA table_info(leads)")
    columns = [col[1] for col in cursor.fetchall()]
    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN is_deleted INTEGER DEFAULT 0;")
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN user_id INTEGER DEFAULT 1;")
    if "website" not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN website TEXT;")
    if "job_description" not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN job_description TEXT;")
    if "posted_at" not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN posted_at TIMESTAMP;")

    cursor.execute("PRAGMA table_info(sent_logs)")
    sent_cols = [col[1] for col in cursor.fetchall()]
    if "profile_id" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN profile_id INTEGER DEFAULT 1;")
    if "is_followup" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN is_followup INTEGER DEFAULT 0;")
    if "subject" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN subject TEXT;")
    if "resume_sent" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN resume_sent TEXT;")
    if "tracking_id" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN tracking_id TEXT;")
    if "opened_at" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN opened_at TIMESTAMP;")
    if "open_count" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN open_count INTEGER DEFAULT 0;")
    if "link_clicked_at" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN link_clicked_at TIMESTAMP;")
    if "click_count" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN click_count INTEGER DEFAULT 0;")
    if "resume_viewed_at" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN resume_viewed_at TIMESTAMP;")
    if "resume_view_count" not in sent_cols:
        cursor.execute("ALTER TABLE sent_logs ADD COLUMN resume_view_count INTEGER DEFAULT 0;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            profile_id INTEGER,
            email TEXT NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            category TEXT,
            slot TEXT,
            status TEXT DEFAULT 'SUCCESS',
            message_id TEXT,
            subject TEXT,
            is_followup INTEGER DEFAULT 0,
            resume_sent TEXT,
            error_message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id),
            FOREIGN KEY (profile_id) REFERENCES user_profiles (id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()

# ----------------- Auth & Account Management -----------------

def register_user(username, full_name, email, password, phone="", linkedin="", years_exp=3, primary_title="Software Engineer"):
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    roles_json = json.dumps([])
    cities_json = json.dumps([])
    excluded_json = json.dumps([])
    default_slots = json.dumps([
        {"hour": 10, "limit": 10, "name": "Morning Slot"},
        {"hour": 14, "limit": 10, "name": "Afternoon Slot"},
        {"hour": 17, "limit": 5, "name": "Evening Slot"}
    ])

    try:
        cursor.execute("""
            INSERT INTO user_profiles (
                profile_name, full_name, email, password_hash, phone, linkedin,
                years_experience, primary_title, is_active, target_roles, target_cities, 
                excluded_companies, custom_slots
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """, (
            username.strip(), full_name.strip(), email.strip().lower(), pwd_hash,
            phone.strip(), linkedin.strip(), years_exp, primary_title.strip(),
            roles_json, cities_json, excluded_json, default_slots
        ))
        conn.commit()
        user_id = cursor.lastrowid
        return True, "Registration successful!", user_id
    except sqlite3.IntegrityError as e:
        err = str(e).lower()
        if "profile_name" in err:
            return False, f"Username '{username}' is already taken.", None
        elif "email" in err:
            return False, f"Email '{email}' is already registered.", None
        return False, "An account with these details already exists.", None
    finally:
        conn.close()

def authenticate_user(identifier, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM user_profiles 
        WHERE LOWER(profile_name) = ? OR LOWER(email) = ?
        LIMIT 1
    """, (identifier.strip().lower(), identifier.strip().lower()))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "User not found. Please sign up first.", None

    user = dict(row)
    stored_hash = user.get("password_hash")
    
    if not stored_hash:
        new_hash = hash_password(password)
        conn = get_connection()
        conn.execute("UPDATE user_profiles SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
        conn.close()
        user["password_hash"] = new_hash
    elif not verify_password(password, stored_hash):
        return False, "Incorrect password. Please try again.", None

    user["target_roles"] = json.loads(user.get("target_roles") or "[]")
    user["target_cities"] = json.loads(user.get("target_cities") or "[]")
    user["excluded_companies"] = json.loads(user.get("excluded_companies") or "[]")
    user["custom_slots"] = json.loads(user.get("custom_slots") or "[]")
    return True, "Login successful!", user

# ----------------- Persistent Session Management -----------------

SESSION_TIMEOUT_SECONDS = 3600  # 1 Hour

def create_session(user_id: int) -> str:
    token = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_sessions (token, user_id, last_activity)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    """, (token, user_id))
    conn.commit()
    conn.close()
    return token

def validate_and_refresh_session(token: str):
    """
    Checks if token is valid and last activity is within 1 hour.
    If valid, updates last_activity to now and returns user_id.
    If expired, deletes the session and returns None.
    """
    if not token:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, last_activity,
               (strftime('%s', 'now') - strftime('%s', last_activity)) AS elapsed_seconds
        FROM user_sessions
        WHERE token = ?
    """, (token,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    elapsed = row["elapsed_seconds"]
    if elapsed is not None and elapsed > SESSION_TIMEOUT_SECONDS:
        cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    # Refresh activity timestamp
    cursor.execute("UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP WHERE token = ?", (token,))
    conn.commit()
    user_id = row["user_id"]
    conn.close()
    return user_id

def destroy_session(token: str):
    if not token:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_profile_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["target_roles"] = json.loads(d.get("target_roles") or "[]")
        d["target_cities"] = json.loads(d.get("target_cities") or "[]")
        d["excluded_companies"] = json.loads(d.get("excluded_companies") or "[]")
        default_slots = [
            {"hour": 10, "limit": 10, "name": "Morning Slot"},
            {"hour": 14, "limit": 10, "name": "Afternoon Slot"},
            {"hour": 17, "limit": 5, "name": "Evening Slot"}
        ]
        d["custom_slots"] = json.loads(d.get("custom_slots") or json.dumps(default_slots))
        return d
    return None

def update_user_profile(user_id, full_name, email, smtp_password=None, rapidapi_key=None,
                        gemini_api_key=None,
                        phone=None, linkedin=None, years_exp=None, primary_title=None,
                        target_roles=None, target_cities=None, excluded_companies=None, custom_slots=None):
    conn = get_connection()
    cursor = conn.cursor()

    roles_json = json.dumps(target_roles) if target_roles is not None else None
    cities_json = json.dumps(target_cities) if target_cities is not None else None
    excluded_json = json.dumps(excluded_companies) if excluded_companies is not None else None
    slots_json = json.dumps(custom_slots) if custom_slots is not None else None

    # Encrypt sensitive credentials before persisting to database
    enc_smtp_pwd = encrypt_secret(smtp_password.strip()) if smtp_password and smtp_password.strip() else None
    enc_rapid_key = encrypt_secret(rapidapi_key.strip()) if rapidapi_key and rapidapi_key.strip() else None
    enc_gemini_key = encrypt_secret(gemini_api_key.strip()) if gemini_api_key and gemini_api_key.strip() else None

    # Handle explicit updates vs retaining existing when parameter is None
    cursor.execute("""
        UPDATE user_profiles SET
            full_name = COALESCE(?, full_name),
            email = COALESCE(?, email),
            smtp_password = CASE WHEN ? IS NOT NULL THEN ? ELSE smtp_password END,
            rapidapi_key = CASE WHEN ? IS NOT NULL THEN ? ELSE rapidapi_key END,
            gemini_api_key = CASE WHEN ? IS NOT NULL THEN ? ELSE gemini_api_key END,
            phone = COALESCE(?, phone),
            linkedin = COALESCE(?, linkedin),
            years_experience = COALESCE(?, years_experience),
            primary_title = COALESCE(?, primary_title),
            target_roles = COALESCE(?, target_roles),
            target_cities = COALESCE(?, target_cities),
            excluded_companies = COALESCE(?, excluded_companies),
            custom_slots = COALESCE(?, custom_slots)
        WHERE id = ?
    """, (
        full_name.strip() if full_name else None,
        email.strip().lower() if email else None,
        enc_smtp_pwd, enc_smtp_pwd,
        enc_rapid_key, enc_rapid_key,
        enc_gemini_key, enc_gemini_key,
        phone, linkedin, years_exp, primary_title,
        roles_json, cities_json, excluded_json, slots_json, user_id
    ))
    conn.commit()
    conn.close()

def get_active_profile():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM user_profiles ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["target_roles"] = json.loads(d.get("target_roles") or "[]")
        d["target_cities"] = json.loads(d.get("target_cities") or "[]")
        d["excluded_companies"] = json.loads(d.get("excluded_companies") or "[]")
        default_slots = [
            {"hour": 10, "limit": 10, "name": "Morning Slot"},
            {"hour": 14, "limit": 10, "name": "Afternoon Slot"},
            {"hour": 17, "limit": 5, "name": "Evening Slot"}
        ]
        d["custom_slots"] = json.loads(d.get("custom_slots") or json.dumps(default_slots))
        return d
    return None

def set_active_profile(profile_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_profiles SET is_active = 0")
    cursor.execute("UPDATE user_profiles SET is_active = 1 WHERE id = ?", (profile_id,))
    conn.commit()
    conn.close()

# ----------------- Resume Management -----------------

def save_user_resume(profile_id, category, file_name, file_path):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_resumes (profile_id, category, file_name, file_path)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(profile_id, category) DO UPDATE SET
            file_name = excluded.file_name,
            file_path = excluded.file_path,
            uploaded_at = CURRENT_TIMESTAMP
    """, (profile_id, category.upper(), file_name, file_path))
    conn.commit()
    conn.close()

def get_user_resumes(profile_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT category, file_name, file_path FROM user_resumes WHERE profile_id = ?", (profile_id,))
    rows = cursor.fetchall()
    conn.close()
    return {r["category"]: {"file_name": r["file_name"], "file_path": r["file_path"]} for r in rows}

def delete_user_resume(profile_id, category):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_resumes WHERE profile_id = ? AND category = ?", (profile_id, category.upper()))
    conn.commit()
    conn.close()

def get_resume_for_job(profile_id, job_role: str = "", category: str = "FULLSTACK"):
    """
    Intelligently retrieves the best matching tailored resume:
    1. Checks exact matching sub-roles (e.g. ANGULAR, REACT, NEXTJS, NODEJS, MERN, MEAN, VUE).
    2. Falls back to parent category (FRONTEND, BACKEND, FULLSTACK, DEVOPS).
    3. Falls back to DEFAULT resume or any uploaded resume.
    """
    resumes = get_user_resumes(profile_id)
    if not resumes:
        return None

    role_lower = str(job_role).lower().strip()

    # Priority 1: Check sub-technologies in job role
    sub_tech_keys = [
        ("angular", "ANGULAR"),
        ("react", "REACT"),
        ("next", "NEXTJS"),
        ("vue", "VUE"),
        ("node", "NODEJS"),
        ("python", "PYTHON"),
        ("java", "JAVA"),
        (".net", "DOTNET"),
        ("mern", "MERN"),
        ("mean", "MEAN"),
        ("devops", "DEVOPS"),
        ("flutter", "FLUTTER"),
        ("android", "ANDROID"),
        ("ios", "IOS"),
    ]

    for keyword, key in sub_tech_keys:
        if keyword in role_lower and key in resumes:
            path = resumes[key]["file_path"]
            if os.path.exists(path):
                return path

    # Priority 2: Check matching category directly
    cat_upper = category.upper()
    if cat_upper in resumes and os.path.exists(resumes[cat_upper]["file_path"]):
        return resumes[cat_upper]["file_path"]

    # Priority 3: Fallback hierarchy
    for fb in ["DEFAULT", "FULLSTACK", "FRONTEND", "BACKEND", "DEVOPS"]:
        if fb in resumes and os.path.exists(resumes[fb]["file_path"]):
            return resumes[fb]["file_path"]

    # Priority 4: Return any existing resume file
    for r in resumes.values():
        if os.path.exists(r["file_path"]):
            return r["file_path"]

    return None

def get_resume_for_category(profile_id, category, job_role: str = ""):
    return get_resume_for_job(profile_id, job_role=job_role, category=category)

# ----------------- Custom Template Management -----------------

def save_user_template(profile_id, category, subject_template, body_template):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_templates (profile_id, category, subject_template, body_template)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(profile_id, category) DO UPDATE SET
            subject_template = excluded.subject_template,
            body_template = excluded.body_template,
            updated_at = CURRENT_TIMESTAMP
    """, (profile_id, category.upper(), subject_template.strip(), body_template.strip()))
    conn.commit()
    conn.close()

def get_user_template(profile_id, category):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT subject_template, body_template FROM user_templates WHERE profile_id = ? AND category = ?", (profile_id, category.upper()))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["subject_template"], row["body_template"]
    return None, None

# ----------------- Lead & Sent Management -----------------

def add_lead(company, role, city, email=None, contact_name="Hiring Team", category="FULLSTACK", email_source="none", job_url=None, match_score=0, user_id=None, website=None, job_description=None, posted_at=None):
    conn = get_connection()
    cursor = conn.cursor()
    clean_email = email.lower().strip() if email and isinstance(email, str) and "@" in email else None
    status = "NEW" if clean_email else "NO_EMAIL"
    clean_source = email_source if clean_email else "none"

    # Default to user_id 1 if not passed
    uid = user_id or 1

    inserted = False
    try:
        # Check if lead already exists for THIS user
        cursor.execute("""
            SELECT id FROM leads 
            WHERE user_id = ? AND company = ? AND role = ? AND (city = ? OR (city IS NULL AND ? IS NULL))
        """, (uid, company.strip(), role.strip(), city.strip() if city else None, city.strip() if city else None))
        existing_row = cursor.fetchone()

        if existing_row:
            cursor.execute("""
                UPDATE leads SET
                    email = COALESCE(?, email),
                    status = CASE WHEN ? IS NOT NULL THEN 'NEW' ELSE status END,
                    email_source = CASE WHEN ? IS NOT NULL THEN ? ELSE email_source END,
                    job_url = COALESCE(?, job_url),
                    website = COALESCE(?, website),
                    job_description = COALESCE(?, job_description),
                    posted_at = COALESCE(?, posted_at)
                WHERE id = ?
            """, (clean_email, clean_email, clean_email, clean_source, job_url, website, job_description, posted_at, existing_row["id"]))
        else:
            cursor.execute("""
                INSERT INTO leads (user_id, company, role, city, email, contact_name, category, status, email_source, job_url, website, job_description, posted_at, match_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid, company.strip(), role.strip(), city.strip() if city else None,
                clean_email, contact_name.strip() if contact_name else "Hiring Team",
                category, status, clean_source, job_url, website, job_description, posted_at, match_score
            ))
        conn.commit()
        inserted = cursor.rowcount > 0
    finally:
        conn.close()
    return inserted

def is_lead_existing_or_sent(company, role, email=None, user_id=None):
    """
    Checks if this candidate has already reached out to this company/email,
    or if this exact job is already recorded in leads.
    Guarantees no company or email already contacted is added back to the stack or re-sent.
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    clean_company = company.strip().lower()

    # 1. Check if email was already sent
    if email and isinstance(email, str) and "@" in email:
        clean_email = email.lower().strip()
        cursor.execute("SELECT 1 FROM sent_logs WHERE profile_id = ? AND LOWER(email) = ? LIMIT 1", (uid, clean_email))
        if cursor.fetchone():
            conn.close()
            return True
        cursor.execute("SELECT 1 FROM leads WHERE user_id = ? AND LOWER(email) = ? AND status = 'SENT' LIMIT 1", (uid, clean_email))
        if cursor.fetchone():
            conn.close()
            return True

    # 2. Check if this company was already contacted by this candidate
    cursor.execute("SELECT 1 FROM sent_logs WHERE profile_id = ? AND LOWER(company) = ? LIMIT 1", (uid, clean_company))
    if cursor.fetchone():
        conn.close()
        return True
    cursor.execute("SELECT 1 FROM leads WHERE user_id = ? AND LOWER(company) = ? AND status = 'SENT' LIMIT 1", (uid, clean_company))
    if cursor.fetchone():
        conn.close()
        return True

    # 3. Check if lead already exists in active leads table
    cursor.execute("SELECT 1 FROM leads WHERE user_id = ? AND LOWER(company) = ? AND LOWER(role) = ? AND is_deleted = 0 LIMIT 1", (uid, clean_company, role.strip().lower()))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def is_lead_already_sent_outreach(company, email=None, user_id=None):
    """
    Checks exclusively if this company or email has received an ACTUAL sent email in sent_logs.
    Only checks actual successful deliveries (ignoring skip tags or leads table status).
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    clean_company = company.strip().lower()

    if email and isinstance(email, str) and "@" in email:
        clean_email = email.lower().strip()
        cursor.execute("SELECT 1 FROM sent_logs WHERE profile_id = ? AND LOWER(email) = ? AND status = 'SUCCESS' AND slot != 'Duplicate Check Skip' LIMIT 1", (uid, clean_email))
        if cursor.fetchone():
            conn.close()
            return True

    cursor.execute("SELECT 1 FROM sent_logs WHERE profile_id = ? AND LOWER(company) = ? AND status = 'SUCCESS' AND slot != 'Duplicate Check Skip' LIMIT 1", (uid, clean_company))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_pending_leads(limit=None, user_id=None, max_days_old=7):
    """
    Retrieves pending leads for outreach with strict priority ordering:
    1. Highest priority to the freshest extracted jobs (ordered by id DESC, created_at DESC).
    2. Only jobs posted within `max_days_old` days (or jobs extracted within `max_days_old` days).
    3. Excludes companies or emails that already received successful outreach.
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    days_float = float(max_days_old) if max_days_old else 7.0
    query = """
        SELECT *, 
               COALESCE(posted_at, created_at) AS effective_date
        FROM leads 
        WHERE user_id = ?
          AND status IN ('NEW', 'APPROVED') 
          AND email IS NOT NULL 
          AND email != ''
          AND is_deleted = 0
          AND (
              (julianday(datetime('now', 'utc')) - julianday(COALESCE(posted_at, created_at))) <= ?
          )
          AND LOWER(company) NOT IN (
              SELECT LOWER(company) FROM sent_logs WHERE profile_id = ? AND status = 'SUCCESS'
          )
          AND LOWER(email) NOT IN (
              SELECT LOWER(email) FROM sent_logs WHERE profile_id = ? AND status = 'SUCCESS'
          )
        ORDER BY id DESC, created_at DESC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    cursor.execute(query, (uid, days_float, uid, uid))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_lead_sent(lead_id, profile_id, email, company, role, category, slot, message_id=None, resume_sent=None, subject=None, is_followup=0, tracking_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    new_status = 'FOLLOWED_UP' if is_followup else 'SENT'
    if lead_id:
        cursor.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
    else:
        cursor.execute("UPDATE leads SET status = ? WHERE email = ? AND user_id = ?", (new_status, email.lower().strip(), profile_id))
    cursor.execute("""
        INSERT INTO sent_logs (lead_id, profile_id, email, company, role, category, slot, message_id, subject, is_followup, resume_sent, status, tracking_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS', ?)
    """, (lead_id, profile_id, email, company, role, category, slot, message_id, subject, is_followup, resume_sent, tracking_id))
    conn.commit()
    conn.close()

def record_email_open(tracking_id: str):
    """Records an email open event from the 1x1 tracking pixel."""
    if not tracking_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sent_logs 
        SET opened_at = COALESCE(opened_at, CURRENT_TIMESTAMP),
            open_count = COALESCE(open_count, 0) + 1
        WHERE tracking_id = ?
    """, (tracking_id.strip(),))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    return affected

def record_link_click(tracking_id: str):
    """Records a portfolio/LinkedIn link click event from tracked link redirect."""
    if not tracking_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sent_logs 
        SET link_clicked_at = COALESCE(link_clicked_at, CURRENT_TIMESTAMP),
            click_count = COALESCE(click_count, 0) + 1
        WHERE tracking_id = ?
    """, (tracking_id.strip(),))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    return affected

def record_resume_view(tracking_id: str):
    """Records a resume PDF view/download click event."""
    if not tracking_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sent_logs 
        SET resume_viewed_at = COALESCE(resume_viewed_at, CURRENT_TIMESTAMP),
            resume_view_count = COALESCE(resume_view_count, 0) + 1
        WHERE tracking_id = ?
    """, (tracking_id.strip(),))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    return affected

def get_sent_resume_path_by_tracking_id(tracking_id: str):
    """Fetches the resume file path that was sent with this tracking ID."""
    if not tracking_id:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT profile_id, resume_sent FROM sent_logs WHERE tracking_id = ? LIMIT 1
    """, (tracking_id.strip(),))
    row = cursor.fetchone()
    conn.close()
    if row and row["resume_sent"]:
        import os
        pid = row["profile_id"]
        fname = row["resume_sent"]
        # Check tailored folder first
        tailored_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", f"user_{pid}", "tailored_resumes", fname)
        if os.path.exists(tailored_p):
            return tailored_p
        # Check standard upload folder
        std_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", f"user_{pid}", fname)
        if os.path.exists(std_p):
            return std_p
        # Check root
        root_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), fname)
        if os.path.exists(root_p):
            return root_p
    return None

def get_due_followups(user_id=None, days=3, limit=None):
    """
    Retrieves sent cold outreach emails that are due for follow-up:
    1. Sent >= `days` days ago in UTC (default 3 days).
    2. Sent originally as cold email (is_followup = 0) with status = 'SUCCESS'.
    3. No subsequent follow-up has been sent to this company or email yet.
    4. Lead is not soft-deleted.
    """
    conn = get_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    
    query = """
        SELECT 
            s.id AS sent_log_id,
            s.lead_id,
            s.profile_id,
            s.email,
            s.company,
            s.role,
            s.category,
            s.message_id AS original_message_id,
            s.subject AS original_subject,
            s.sent_at,
            l.contact_name,
            l.city,
            l.job_url,
            l.website,
            l.job_description
        FROM sent_logs s
        LEFT JOIN leads l ON s.lead_id = l.id
        WHERE s.profile_id = ?
          AND s.is_followup = 0
          AND s.status = 'SUCCESS'
          AND s.email IS NOT NULL AND s.email != ''
          AND (julianday(datetime('now', 'utc')) - julianday(s.sent_at)) >= ?
          AND (l.is_deleted IS NULL OR l.is_deleted = 0)
          AND LOWER(s.email) NOT IN (
              SELECT LOWER(email) FROM sent_logs WHERE profile_id = ? AND is_followup = 1
          )
          AND LOWER(s.company) NOT IN (
              SELECT LOWER(company) FROM sent_logs WHERE profile_id = ? AND is_followup = 1
          )
        ORDER BY s.sent_at ASC
    """
    params = [uid, float(days), uid, uid]
    if limit:
        query += f" LIMIT {int(limit)}"
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_due_followups_count(user_id=None, days=3):
    """Returns the total number of due follow-ups for a user"""
    due = get_due_followups(user_id=user_id, days=days)
    return len(due)

def soft_delete_leads(lead_ids: list, user_id=None):
    """Soft deletes leads by setting is_deleted = 1 for the specific user"""
    if not lead_ids:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(lead_ids))
    if user_id:
        cursor.execute(f"UPDATE leads SET is_deleted = 1 WHERE id IN ({placeholders}) AND user_id = ?", lead_ids + [user_id])
    else:
        cursor.execute(f"UPDATE leads SET is_deleted = 1 WHERE id IN ({placeholders})", lead_ids)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

def restore_leads(lead_ids: list, user_id=None):
    """Restores soft-deleted leads by setting is_deleted = 0"""
    if not lead_ids:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(lead_ids))
    if user_id:
        cursor.execute(f"UPDATE leads SET is_deleted = 0 WHERE id IN ({placeholders}) AND user_id = ?", lead_ids + [user_id])
    else:
        cursor.execute(f"UPDATE leads SET is_deleted = 0 WHERE id IN ({placeholders})", lead_ids)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

def permanent_delete_leads(lead_ids: list, user_id=None):
    """Permanently deletes leads from the database"""
    if not lead_ids:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(lead_ids))
    if user_id:
        cursor.execute(f"DELETE FROM leads WHERE id IN ({placeholders}) AND user_id = ?", lead_ids + [user_id])
    else:
        cursor.execute(f"DELETE FROM leads WHERE id IN ({placeholders})", lead_ids)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected

def get_stats(user_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    cursor.execute("SELECT COUNT(*) FROM leads WHERE user_id = ? AND is_deleted = 0", (uid,))
    total_leads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leads WHERE user_id = ? AND status IN ('NEW', 'APPROVED') AND email IS NOT NULL AND email != '' AND is_deleted = 0", (uid,))
    pending = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leads WHERE user_id = ? AND (status = 'NO_EMAIL' OR email IS NULL OR email = '') AND is_deleted = 0", (uid,))
    no_email = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sent_logs WHERE profile_id = ? AND status = 'SUCCESS'", (uid,))
    sent = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM leads WHERE user_id = ? AND is_deleted = 1", (uid,))
    deleted = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sent_logs WHERE profile_id = ? AND opened_at IS NOT NULL", (uid,))
    opened = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sent_logs WHERE profile_id = ? AND link_clicked_at IS NOT NULL", (uid,))
    clicked = cursor.fetchone()[0]
    conn.close()
    return {
        "total": total_leads, 
        "pending": pending, 
        "no_email": no_email, 
        "sent": sent, 
        "deleted": deleted,
        "opened": opened,
        "clicked": clicked
    }

if __name__ == "__main__":
    init_db()
    print("Database schema initialized with custom timing slots and RapidAPI key support.")

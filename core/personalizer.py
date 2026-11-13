import os
import re
import json
import requests
from jinja2 import Template, Environment, FileSystemLoader
from core.db import get_user_template, get_resume_for_job
from core.crypto import decrypt_secret

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
_jinja_env = None

def extract_text_from_pdf(pdf_path: str, max_chars: int = 5000) -> str:
    """
    Extracts text from a candidate's resume PDF to feed into the AI prompt.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        extracted = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted.append(t)
        full_text = "\n".join(extracted).strip()
        return full_text[:max_chars]
    except Exception as e:
        print(f"[Resume Extractor] Could not parse PDF ({pdf_path}): {e}")
        return ""

def get_jinja_env():
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)
    return _jinja_env

def detect_role_category(role_name: str) -> str:
    clean_role = str(role_name).lower()
    devops_keywords = ["devops", "cloud", "aws", "infrastructure", "sre", "kubernetes", "docker"]
    frontend_keywords = ["frontend", "front-end", "react", "angular", "ui", "web developer"]
    backend_keywords = ["backend", "back-end", "node", "nodejs", "api", "server", "database", "python", "golang"]
    fullstack_keywords = ["full stack", "fullstack", "full-stack", "software engineer", "sde"]

    if any(k in clean_role for k in devops_keywords):
        return "DEVOPS"
    is_fe = any(k in clean_role for k in frontend_keywords)
    is_be = any(k in clean_role for k in backend_keywords)
    is_fs = any(k in clean_role for k in fullstack_keywords)

    if is_fs and not (is_fe and not is_be):
        return "FULLSTACK"
    if is_be and not is_fe:
        return "BACKEND"
    if is_fe and not is_be:
        return "FRONTEND"
    return "FULLSTACK"

def generate_ai_pitch_with_gemini(profile: dict, lead: dict, gemini_api_key: str, resume_text: str = "", extracted_keywords: list = None) -> tuple[str, str]:
    """
    Generates a comprehensive, highly persuasive 200-300 word AI pitch using Google Gemini.
    Directly aligns the candidate's actual resume accomplishments with the hiring company's job description
    and seamlessly weaves in target JD keywords.
    """
    clean_key = gemini_api_key.strip()
    if not clean_key:
        return None, None

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={clean_key}"
    
    candidate_name = profile.get("full_name") or "Software Engineer"
    candidate_yoe = profile.get("years_experience", 4)
    candidate_phone = profile.get("phone", "") or ""
    candidate_linkedin = profile.get("linkedin", "") or ""
    candidate_roles = ", ".join(profile.get("target_roles") or ["Full Stack Developer", "Angular Developer"])
    
    company = lead.get("company", "Company")
    role = lead.get("role", "Open Role")
    contact = lead.get("contact_name") or "Team"
    city = lead.get("city") or "India"
    job_desc = (lead.get("job_description") or "")[:4000]

    kw_clause = f"\n- Priority High-Impact Keywords extracted from JD: {', '.join(extracted_keywords)}" if extracted_keywords else ""

    resume_context = f"\n\nCandidate's Actual Resume Details:\n\"\"\"{resume_text[:4500]}\"\"\"" if resume_text else ""

    system_prompt = (
        "You are an elite executive talent agent writing a deeply persuasive, crisp, professional cold outreach letter "
        "(strictly 200 to 300 words maximum). You must directly synthesize the candidate's real-world resume accomplishments "
        "with the exact requirements, tech stack, and engineering challenges stated in the employer's Job Description. "
        "Naturally incorporate the extracted JD technical keywords so ATS and recruiters recognize an immediate match. "
        "Avoid shallow buzzwords. Provide concrete engineering context, architecture patterns, and genuine enthusiasm."
    )

    user_prompt = f"""
Candidate Background:
- Name: {candidate_name}
- Years of Experience: {candidate_yoe} years
- Target Specialization: {candidate_roles}
- Phone: {candidate_phone}
- LinkedIn: {candidate_linkedin}{resume_context}

Target Opportunity:
- Hiring Company: {company}
- Open Position: {role}
- Hiring Manager / Contact: {contact}
- Office / Work Location: {city}{kw_clause}
- Full Job Description:
\"\"\"{job_desc}\"\"\"

Pitch Requirements (Strictly 200-300 Words Total):
1. Subject Line: High-converting, professional on the very first line starting with 'Subject: ' (e.g. 'Subject: {candidate_name} – Application for {role} ({candidate_yoe} YOE | Key Tech Stack)').
2. Salutation: Professional greeting to 'Hi {contact},'.
3. Introduction: Express direct, authentic interest for the {role} at {company}. Summarize {candidate_name}'s {candidate_yoe} years building scalable web applications.
4. Core Alignment & Technical Fit (1-2 tight, impactful paragraphs):
   - Highlight 2-3 specific technical requirements from their Job Description and naturally weave in the extracted tech keywords.
   - Connect them directly to proven accomplishments from the candidate's resume (e.g. enterprise platforms, state management RxJS/NgRx, REST API contracts, fintech/payment modules, scalable frontend architecture).
5. Strong Closing Call-to-Action: Politely request a brief 10-minute introductory call this week, mentioning the attached customized resume.
6. Sign-off:
Best regards,
{candidate_name}
{candidate_phone}
{candidate_linkedin}

Strict Rules:
- Total body word count must strictly be between 200 and 300 words.
- Return ONLY plain email text. Do not include word count stats, notes, labels, preamble, or markdown asterisks.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n{user_prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024
        }
    }

    # Send request with automatic retry on temporary Gemini 503 capacity spikes
    for attempt in range(1, 4):
        try:
            resp = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
            if resp.status_code == 200:
                res_json = resp.json()
                candidates = res_json.get("candidates", [])
                if candidates:
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    lines = raw_text.split("\n")
                    if lines[0].startswith("Subject:"):
                        subject = lines[0].replace("Subject:", "").strip()
                        body = "\n".join(lines[1:]).strip()
                    else:
                        subject = f"{candidate_name} – {role} Application ({candidate_yoe} YOE)"
                        body = raw_text
                    return subject, body
            elif resp.status_code in [503, 429] and attempt < 3:
                print(f"[Gemini Temporary Spike {resp.status_code}] Retrying in 2s (attempt {attempt}/3)...")
                import time
                time.sleep(2)
            else:
                print(f"[Gemini API Error] Status {resp.status_code}: {resp.text[:200]}")
                break
        except Exception as e:
            if attempt < 3:
                import time
                time.sleep(2)
            else:
                print(f"[Gemini Pitch Generation Failed]: {e}")

    return None, None

def render_pitch_for_profile(profile: dict, lead: dict, category: str, extracted_keywords: list = None) -> tuple[str, str]:
    """
    Renders (subject, body) for a given profile and lead.
    Priority sequence:
    1. If user configured Gemini API key and job description exists -> Generate Hyper-Personalized AI pitch.
    2. If user saved a customized template in DB for this category -> Render DB template.
    3. Fallback to tailored category Jinja2 template on disk.
    """
    profile_id = profile.get("id")
    raw_gemini = profile.get("gemini_api_key") or ""
    gemini_key = decrypt_secret(raw_gemini).strip() if raw_gemini else ""
    job_desc = lead.get("job_description")

    # 1. AI Hyper-Personalized Generation via Gemini
    if gemini_key and job_desc and len(job_desc.strip()) > 40:
        # Extract real resume text for this specific job sub-role/category
        role_name = lead.get("role", "")
        resume_path = get_resume_for_job(profile_id, job_role=role_name, category=category) if profile_id else None
        resume_text = extract_text_from_pdf(resume_path) if resume_path else ""

        ai_sub, ai_body = generate_ai_pitch_with_gemini(
            profile, lead, gemini_key, 
            resume_text=resume_text, 
            extracted_keywords=extracted_keywords
        )
        if ai_sub and ai_body:
            print(f"  [AI Personalizer] Generated 200-300 word tailored pitch with Gemini for {lead.get('company')} ({lead.get('role')})")
            return ai_sub, ai_body

    context = {
        "candidate": profile,
        "contact_name": lead.get("contact_name") or "Team",
        "company": lead.get("company"),
        "role": lead.get("role"),
        "city": lead.get("city")
    }

    # 2. Check custom template from DB
    if profile_id:
        custom_sub, custom_body = get_user_template(profile_id, category)
        if custom_sub and custom_body:
            rendered_sub = Template(custom_sub).render(**context).strip()
            rendered_body = Template(custom_body).render(**context).strip()
            return rendered_sub, rendered_body

    # 3. Disk fallback template
    env = get_jinja_env()
    template_name = f"{category.lower()}.j2"
    if template_name not in env.list_templates():
        template_name = "fullstack.j2"

    template = env.get_template(template_name)
    rendered = template.render(**context)

    lines = rendered.strip().split("\n")
    if lines[0].startswith("Subject:"):
        subject = lines[0].replace("Subject:", "").strip()
        body = "\n".join(lines[1:]).strip()
    else:
        subject = f"{profile.get('full_name', 'Software Engineer')} – Application for {lead.get('role', 'Open Position')}"
        body = rendered.strip()

    return subject, body

def render_followup_pitch_for_profile(profile: dict, lead: dict) -> tuple[str, str]:
    """
    Renders the 3-day follow-up pitch for a candidate.
    Uses templates/follow_up.j2 or customized user follow-up template.
    """
    profile_id = profile.get("id")
    context = {
        "candidate": profile,
        "contact_name": lead.get("contact_name") or "Team",
        "company": lead.get("company", ""),
        "role": lead.get("role", ""),
        "city": lead.get("city", "")
    }

    # 1. Check custom follow-up template from DB if configured
    if profile_id:
        custom_sub, custom_body = get_user_template(profile_id, "FOLLOWUP")
        if custom_body:
            rendered_body = Template(custom_body).render(**context).strip()
            orig_sub = lead.get("original_subject") or f"{profile.get('full_name', 'Software Engineer')} – Application for {lead.get('role', 'Open Position')}"
            rendered_sub = Template(custom_sub).render(**context).strip() if custom_sub else (
                orig_sub if orig_sub.lower().startswith("re:") else f"Re: {orig_sub}"
            )
            return rendered_sub, rendered_body

    # 2. Disk fallback template
    env = get_jinja_env()
    template = env.get_template("follow_up.j2")
    rendered = template.render(**context).strip()

    orig_sub = lead.get("original_subject") or f"{profile.get('full_name', 'Software Engineer')} – Application for {lead.get('role', 'Open Position')}"
    subject = orig_sub if orig_sub.lower().startswith("re:") else f"Re: {orig_sub}"
    return subject, rendered

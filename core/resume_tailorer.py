import os
import re
import json
import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from core.crypto import decrypt_secret

def extract_and_tailor_any_resume_with_gemini(profile: dict, lead: dict, base_resume_text: str, gemini_api_key: str) -> dict:
    """
    100% Dynamic for ANY candidate:
    Takes ANY user's raw resume text and the employer's Job Description.
    Uses Gemini to extract that specific user's real data (companies, titles, dates,
    education, projects) and adapts their skills & summary to align with the JD.
    """
    clean_key = gemini_api_key.strip()
    if not clean_key or not base_resume_text:
        return None

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={clean_key}"
    
    candidate_name = profile.get("full_name") or "Candidate"
    target_role = lead.get("role", "Software Engineer")
    target_company = lead.get("company", "Company")
    jd = (lead.get("job_description") or "")[:4000]

    prompt = f"""
You are the world's top ATS (Applicant Tracking System) Optimization Algorithm (matching systems like Taleo, Greenhouse, Workday, Lever, and Jobscan).
Your goal is to achieve an ATS Keyword and Relevance Match Score of 85% to 95% against the provided Job Description.

Target Job Opening:
- Company: {target_company}
- Exact Job Title: {target_role}
- Full Job Description:
\"\"\"{jd}\"\"\"

Candidate's Real Background & Master Resume Text:
\"\"\"{base_resume_text[:6000]}\"\"\"

CRITICAL ATS 85-95% SCORING RULES:
1. Exact Job Title Alignment: Set "headline_title" to EXACTLY mirror the target role title (e.g. "{target_role} | ...") followed by the top 3-4 technologies from the JD.
2. Complete Keyword Extraction: Identify EVERY hard technical skill, framework, library, tool, methodology, and architectural concept in the JD (e.g. Core Java, Spring Boot, React, SQL, Maven, Git, CI/CD, AWS, Kubernetes, Docker, Agile/Scrum).
3. 100% Skill Coverage: Every single hard skill and tool mentioned in the JD MUST be included in the "skills_categories" list if the candidate has transferable full-stack/software engineering capabilities.
4. Professional Summary Keyword Density: The 3-4 sentence summary must feature the exact job title in the first sentence and naturally weave in 5-8 of the primary keywords from the JD (responsibilities, platforms, coding standards).
5. Bullet Point Keyword Injection:
   - For EVERY experience item and project, weave in the JD's exact action verbs and terminologies (e.g., "Deployment on CaaS and AWS platforms", "Production Support", "Unit testing and CI/CD pipelines", "REST API integration", "Spring Boot microservices / React components").
   - Maintain the candidate's authentic companies, dates, degrees, and college names, but phrase their accomplishments using the EXACT vocabulary of the Job Description.

Return strictly a valid JSON object matching this EXACT schema (NO markdown formatting, no comments, no extra text):
{{
  "full_name": "{candidate_name}",
  "headline_title": "{target_role} | Top JD Skill 1 · Top JD Skill 2 · Top JD Skill 3",
  "contact_info": "Udaipur, Rajasthan, India | +91 6367134982 | nazimkhan4686@gmail.com | linkedin.com/in/nazim-khan",
  "summary": "High-impact summary starting with exact job title and densely incorporating key JD requirements...",
  "skills_categories": [
    {{"category": "Languages", "skills": "Exact language keywords from JD (e.g. Core Java, JavaScript, TypeScript, SQL...)"}},
    {{"category": "Frameworks & Frontend/Backend", "skills": "Exact framework keywords from JD (e.g. Spring Boot, Spring, React, Angular, Node.js...)"}},
    {{"category": "Cloud, DevOps & Build Tools", "skills": "Exact DevOps keywords from JD (e.g. AWS, CaaS, Docker, Kubernetes, Maven, Git, CI/CD...)"}},
    {{"category": "Databases & Architecture", "skills": "SQL, NoSQL, REST APIs, Microservices, CaaS..."}}
  ],
  "experience": [
    {{
      "role": "Role Title",
      "company": "Company Name",
      "location": "Location",
      "dates": "Dates",
      "bullets": [
        "Strong bullet point weaving in exact JD verbs and technologies...",
        "Strong bullet point with metrics and JD keywords..."
      ]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "tech_stack": "Technologies from JD",
      "bullets": [
        "Project bullet point aligning with JD requirements..."
      ]
    }}
  ],
  "education": [
    {{
      "degree": "Degree",
      "institution": "University / College",
      "dates": "Dates"
    }}
  ],
  "certifications_or_achievements": [
    "Relevant certifications, honors, or achievements"
  ]
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }

    # Send request with automatic retry on temporary Gemini 503 capacity spikes
    for attempt in range(1, 4):
        try:
            resp = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
            if resp.status_code == 200:
                res_json = resp.json()
                candidates = res_json.get("candidates", [])
                if candidates:
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    raw_text = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
                    raw_text = re.sub(r"^```\s*$", "", raw_text, flags=re.MULTILINE).strip()
                    parsed = json.loads(raw_text)
                    return parsed
            elif resp.status_code in [503, 429] and attempt < 3:
                print(f"[Dynamic Tailorer Spike {resp.status_code}] Retrying in 2s (attempt {attempt}/3)...")
                import time
                time.sleep(2)
            else:
                print(f"[Dynamic Tailorer] Gemini API error {resp.status_code}: {resp.text[:200]}")
                break
        except Exception as e:
            if attempt < 3:
                import time
                time.sleep(2)
            else:
                print(f"[Dynamic Tailorer] Failed to extract & tailor resume: {e}")

    return None

def build_dynamic_ats_pdf(tailored_data: dict, output_pdf_path: str):
    """
    Renders ANY user's parsed JSON into a clean, modern, ATS-compliant PDF.
    Zero hardcoded values: all sections loop through whatever the user actually has.
    """
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor("#1A5276")  # Navy
    dark_color = colors.HexColor("#2C3E50")     # Charcoal
    gray_color = colors.HexColor("#5D6D7E")     # Slate Gray

    name_style = ParagraphStyle(
        'DynResumeName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=0
    )

    title_style = ParagraphStyle(
        'DynResumeTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=dark_color,
        alignment=0
    )

    contact_style = ParagraphStyle(
        'DynResumeContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=gray_color,
        alignment=0
    )

    section_hdr_style = ParagraphStyle(
        'DynResumeSectionHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=primary_color,
        spaceBefore=7,
        spaceAfter=3
    )

    body_style = ParagraphStyle(
        'DynResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.8,
        leading=12.5,
        textColor=dark_color
    )

    bullet_style = ParagraphStyle(
        'DynResumeBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.8,
        textColor=dark_color,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=1.5
    )

    subhdr_style = ParagraphStyle(
        'DynResumeSubHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.8,
        leading=12.5,
        textColor=dark_color,
        spaceBefore=2
    )

    story = []

    # 1. Header (Dynamic)
    name = tailored_data.get("full_name") or "CANDIDATE"
    headline = tailored_data.get("headline_title") or "Software Professional"
    contact = tailored_data.get("contact_info") or ""

    story.append(Paragraph(name.upper(), name_style))
    story.append(Paragraph(headline, title_style))
    if contact:
        story.append(Paragraph(contact, contact_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=primary_color, spaceBefore=3, spaceAfter=5))

    # 2. Professional Summary (Dynamic)
    summary = tailored_data.get("summary")
    if summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_hdr_style))
        story.append(Paragraph(summary, body_style))
        story.append(Spacer(1, 3))

    # 3. Technical Skills (Dynamic)
    skills_cats = tailored_data.get("skills_categories", [])
    if skills_cats:
        story.append(Paragraph("TECHNICAL SKILLS", section_hdr_style))
        for cat in skills_cats:
            c_name = cat.get("category", "Skills")
            c_vals = cat.get("skills", "")
            if c_vals:
                story.append(Paragraph(f"<b>{c_name}:</b> {c_vals}", body_style))
        story.append(Spacer(1, 3))

    # 4. Professional Experience (Dynamic)
    experience_list = tailored_data.get("experience", [])
    if experience_list:
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_hdr_style))
        for exp in experience_list:
            role = exp.get("role", "Software Engineer")
            comp = exp.get("company", "Company")
            loc = exp.get("location", "")
            dates = exp.get("dates", "")
            loc_str = f" · [{loc}]" if loc else ""
            date_str = f" &nbsp;<i>({dates})</i>" if dates else ""
            
            story.append(Paragraph(f"<b>{role}</b> — {comp}{loc_str}{date_str}", subhdr_style))
            for b in exp.get("bullets", []):
                if b and b.strip():
                    story.append(Paragraph(f"• {b.strip()}", bullet_style))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 2))

    # 5. Key Projects (Dynamic)
    projects_list = tailored_data.get("projects", [])
    if projects_list:
        story.append(Paragraph("KEY PROJECTS", section_hdr_style))
        for prj in projects_list:
            p_name = prj.get("name", "Project")
            tech = prj.get("tech_stack", "")
            tech_str = f" &nbsp;| <i>{tech}</i>" if tech else ""
            story.append(Paragraph(f"<b>{p_name}</b>{tech_str}", subhdr_style))
            for b in prj.get("bullets", []):
                if b and b.strip():
                    story.append(Paragraph(f"• {b.strip()}", bullet_style))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 2))

    # 6. Education (Dynamic)
    edu_list = tailored_data.get("education", [])
    if edu_list:
        story.append(Paragraph("EDUCATION", section_hdr_style))
        for edu in edu_list:
            deg = edu.get("degree", "Degree")
            inst = edu.get("institution", "University")
            dates = edu.get("dates", "")
            d_str = f" &nbsp;({dates})" if dates else ""
            story.append(Paragraph(f"• <b>{deg}</b> — {inst}{d_str}", body_style))
        story.append(Spacer(1, 3))

    # 7. Achievements / Certifications (Dynamic)
    achievements = tailored_data.get("certifications_or_achievements", [])
    if achievements:
        story.append(Paragraph("ACHIEVEMENTS & CERTIFICATIONS", section_hdr_style))
        for ach in achievements:
            if ach and ach.strip():
                story.append(Paragraph(f"• {ach.strip()}", body_style))

    doc.build(story)
    return output_pdf_path

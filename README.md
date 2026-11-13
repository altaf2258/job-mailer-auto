# Job Mailer Pro 💼 – Multi-User Outreach Platform

An automated cold outreach and job application platform. It discovers fresh job postings, crawls company websites for verified HR and recruitment emails, matches candidate profiles, and dispatches role-tailored pitches with category-specific resume attachments.

---

## ✨ Features

1. **Multi-User Profiles**:
   - Manage multiple candidate profiles from the UI.
   - Each candidate has their own credentials, target roles, preferred cities, and excluded companies blacklist.
   - Switch active profiles with a single click.

2. **Role-Tailored Resumes**:
   - Upload separate resumes per role category (Frontend, Backend, Full-Stack, DevOps, Default).
   - The mailer detects the role type and attaches the corresponding resume automatically.

3. **Dynamic Template Studio**:
   - Write and edit custom subject lines and pitches per category directly in the web dashboard.
   - Live rendering previews test how variables like `{{ contact_name }}`, `{{ role }}`, `{{ company }}`, and `{{ city }}` appear before sending.

4. **Web Crawler & Verification Engine**:
   - Crawls company websites (`/careers`, `/jobs`, `/contact`) to extract genuine public inboxes.
   - Live DNS MX record checking verifies mail server validity and filters out non-human ATS notifications (`notification@...`).
   - Strict guardrails: jobs without an authentic email address are marked `NO_EMAIL` and never sent to.

5. **Safety Throttling & Cron Scheduling**:
   - Dispatches batches safely across daily windows (10 AM, 2 PM, 5 PM) with 45–80 second delays to maintain sender reputation.

---

## 🚀 Quick Start

### 1. Launch the Web Dashboard
```powershell
python -m streamlit run dashboard.py
```
Open `http://localhost:8501` to:
- Switch or create candidate profiles under **👤 Candidate Profiles & Resumes**.
- Upload role-specific resumes.
- Edit pitches in the **📝 Custom Template Studio**.
- Ingest jobs and send email batches under **🚀 Run Outreach**.

---

### 2. CLI Usage
* **Check database metrics**:
  ```powershell
  python run.py --stats
  ```

* **Fetch live jobs using active profile preferences**:
  ```powershell
  python run.py --fetch
  ```

* **Dispatch email batch**:
  ```powershell
  python run.py --send --force --limit 5
  ```

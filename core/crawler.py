import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Standard browser headers to avoid basic bot blocks
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Avoid image/asset/tracking false positives in regex
IGNORED_EMAIL_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js')
IGNORED_EMAIL_PREFIXES = ('example', 'test', 'demo', 'noreply', 'no-reply', 'mailer-daemon', 'notification', 'notifications', 'donotreply', 'privacy')
IGNORED_EMAIL_DOMAINS = ('smartrecruiters.com', 'greenhouse.io', 'lever.co', 'workday.com', 'myworkday.com', 'icims.com', 'ashbyhq.com')

def extract_valid_emails_from_text(text: str) -> list[str]:
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    clean_emails = []
    for m in matches:
        m_lower = m.lower().strip().rstrip('.')
        if any(m_lower.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
            continue
        if any(m_lower.startswith(prefix) for prefix in IGNORED_EMAIL_PREFIXES):
            continue
        domain_part = m_lower.split('@')[-1]
        if any(ignored_dom in domain_part for ignored_dom in IGNORED_EMAIL_DOMAINS):
            continue
        if len(m_lower.split('@')[0]) > 40:
            continue
        clean_emails.append(m_lower)
    return list(dict.fromkeys(clean_emails))  # Deduplicate while preserving order

def score_email_relevance(email: str) -> int:
    """Prioritize hiring/hr/career contacts over generic ones."""
    lower = email.lower()
    if any(k in lower for k in ["career", "careers", "jobs", "job", "hiring", "talent", "recruit"]):
        return 10
    if any(k in lower for k in ["hr", "people", "team"]):
        return 8
    if any(k in lower for k in ["contact", "info", "hello", "support"]):
        return 5
    return 3

def crawl_company_for_email(base_url: str, timeout: int = 8) -> tuple[str | None, str]:
    """
    Crawls company homepage, /careers, /jobs, and /contact pages.
    Extracts real, published emails from HTML text and 'mailto:' links.
    Returns: (found_email, source_page) or (None, "")
    """
    if not base_url or not isinstance(base_url, str):
        return None, ""

    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    parsed = urlparse(base_url)
    root_domain = parsed.netloc

    candidate_subpaths = [
        "",  # homepage
        "/careers",
        "/career",
        "/jobs",
        "/join-us",
        "/contact",
        "/contact-us",
        "/about-us",
        "/about"
    ]

    session = requests.Session()
    session.headers.update(HTTP_HEADERS)

    discovered_emails = []

    for path in candidate_subpaths:
        target_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", path)
        try:
            resp = session.get(target_url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200 or not resp.text:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Search mailto: links (highest reliability)
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href.lower().startswith("mailto:"):
                    clean = href.split("mailto:")[-1].split("?")[0].strip().lower()
                    if "@" in clean and clean not in [e[0] for e in discovered_emails]:
                        discovered_emails.append((clean, target_url, score_email_relevance(clean) + 5))

            # 2. Search visible page text
            page_text = soup.get_text(separator=" ")
            text_emails = extract_valid_emails_from_text(page_text)
            for email in text_emails:
                # Match against company domain when possible
                email_domain = email.split('@')[-1]
                bonus = 3 if root_domain in email_domain or email_domain in root_domain else 0
                score = score_email_relevance(email) + bonus
                discovered_emails.append((email, target_url, score))

            # Stop early if a high-confidence recruitment email is found
            recruitment_hits = [e for e in discovered_emails if e[2] >= 10]
            if recruitment_hits:
                break

        except Exception:
            continue

    if not discovered_emails:
        return None, ""

    # Sort discovered emails by relevance score
    discovered_emails.sort(key=lambda x: x[2], reverse=True)
    best_email, source_url, _ = discovered_emails[0]
    return best_email, source_url


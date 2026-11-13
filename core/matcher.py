import re

# Negative technology keywords to guard against unselected stacks
TECH_DISQUALIFIERS = {
    "java": ["java", "spring boot", "springboot", "j2ee", "hibernate"],
    ".net": [".net", "dotnet", "c#", "asp.net"],
    "python": ["python", "django", "fastapi", "flask"],
    "php": ["php", "laravel", "codeigniter", "wordpress"],
    "ruby": ["ruby", "rails"],
    "golang": ["golang", "go developer"]
}

# Synonym mapping for general role categories to cover related frontend/fullstack/backend titles
ROLE_SYNONYMS = {
    "frontend": ["frontend", "front-end", "front end", "react", "react.js", "angular", "vue", "next.js", "ui developer", "ui engineer", "web developer"],
    "backend": ["backend", "back-end", "back end", "node", "node.js", "nodejs", "api developer", "server engineer"],
    "fullstack": ["full stack", "fullstack", "full-stack", "mern", "mean", "software engineer", "sde", "web developer"]
}

def is_role_matching_targets(job_role: str, user_target_roles: list[str]) -> bool:
    """
    Strictly verifies whether a job title matches the user's selected target roles.
    Allows related modern frameworks (e.g. React/Angular when Frontend is targeted).
    Rejects completely unselected tech stacks (e.g. PHP/Java when not selected).
    """
    if not job_role or not user_target_roles:
        return True

    job_lower = job_role.lower().strip()
    user_targets_lower = [t.lower().strip() for t in user_target_roles]

    # 1. Direct or partial positive match with any selected target role
    matched_target = False
    for target in user_targets_lower:
        if target in job_lower:
            matched_target = True
            break
        target_words = [w for w in target.split() if w not in ["developer", "engineer", "stack", "development", ".js", "/"]]
        if target_words and all(w in job_lower for w in target_words if len(w) > 2):
            matched_target = True
            break
        for cat_key, syns in ROLE_SYNONYMS.items():
            if cat_key in target and any(s in job_lower for s in syns):
                matched_target = True
                break
        if matched_target:
            break

    # 2. Check for conflicting technologies the user DID NOT select
    for tech, keywords in TECH_DISQUALIFIERS.items():
        if any(kw in job_lower for kw in keywords):
            user_wants_this_tech = any(kw in t for t in user_targets_lower for kw in keywords)
            if not user_wants_this_tech:
                return False

    return matched_target

def is_experience_matching(job_text: str, user_years: int) -> bool:
    """
    Evaluates whether the job's stated experience requirements match the candidate's years of experience.
    Allows a flexible range: user_years +/- 1 (e.g. 4 years candidate matches 3-5 years).
    If no explicit experience requirement is mentioned in the job text, it allows it.
    """
    if not job_text or user_years is None:
        return True

    min_acceptable = max(0, int(user_years) - 1)
    max_acceptable = int(user_years) + 1

    # 1. Check for range: e.g. "3-5 years", "3 to 5 yrs", "2 - 4 years"
    range_matches = re.findall(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)', job_text, re.IGNORECASE)
    for low_str, high_str in range_matches:
        low = int(low_str)
        high = int(high_str)
        # Disqualify if the job is too senior (e.g. 6-10 years when user is 4)
        if low > max_acceptable:
            return False
        # Disqualify if the job is strictly for freshers / interns when user is experienced (e.g. 0-1 year)
        if high < min_acceptable and high <= 1 and int(user_years) >= 3:
            return False
        # If there is overlap with [min_acceptable, max_acceptable]
        if max(low, min_acceptable) <= min(high, max_acceptable):
            return True

    # 2. Check for minimum required: e.g. "5+ years", "minimum 5 years", "at least 6 yrs"
    min_matches = re.findall(r'(?:min(?:imum)?|at\s*least|\b)\s*(\d+)\+?\s*(?:years?|yrs?)', job_text, re.IGNORECASE)
    for m in min_matches:
        req_years = int(m)
        if req_years > max_acceptable:
            # Job requires e.g. 6+ or 7+ years -> Disqualify for a 4 YOE candidate
            return False

    return True


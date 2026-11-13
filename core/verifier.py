import re
import dns.resolver

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "throwawaymail.com", "trashmail.com", "yopmail.com"
}

_mx_cache = {}

def is_valid_syntax(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))

def has_mx_records(domain: str) -> bool:
    clean_domain = domain.lower().strip()
    if clean_domain in _mx_cache:
        return _mx_cache[clean_domain]

    if clean_domain in DISPOSABLE_DOMAINS:
        _mx_cache[clean_domain] = False
        return False

    try:
        answers = dns.resolver.resolve(clean_domain, 'MX', lifetime=4.0)
        has_mx = len(answers) > 0
        _mx_cache[clean_domain] = has_mx
        return has_mx
    except Exception:
        # Fallback to checking A record
        try:
            answers_a = dns.resolver.resolve(clean_domain, 'A', lifetime=3.0)
            has_a = len(answers_a) > 0
            _mx_cache[clean_domain] = has_a
            return has_a
        except Exception:
            _mx_cache[clean_domain] = False
            return False

def verify_email(email: str) -> tuple[bool, str]:
    if not is_valid_syntax(email):
        return False, "invalid_format"
    domain = email.split('@')[-1].lower().strip()
    if domain in DISPOSABLE_DOMAINS:
        return False, "disposable_domain"
    if not has_mx_records(domain):
        return False, "no_mx_or_a_record"
    return True, "valid"


import re

SENSITIVE_PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), '[API_KEY_REDACTED]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{20,}'), '[TOKEN_REDACTED]'),
    (re.compile(r'token[=:]\s*["\']?[a-zA-Z0-9_\-]{20,}["\']?', re.IGNORECASE), 'token=[REDACTED]'),
    (re.compile(r'password[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'password=[REDACTED]'),
    (re.compile(r'secret[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'secret=[REDACTED]'),
    (re.compile(r'Authorization[=:]\s*["\']?[^\s"\']+["\']?', re.IGNORECASE), 'Authorization=[REDACTED]'),
]


def filter_sensitive(text: str) -> str:
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
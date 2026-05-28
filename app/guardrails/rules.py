DEFAULT_MAX_INPUT_LENGTH = 4000
MAX_EXTERNAL_CONTEXT_LENGTH = 3000
MAX_OUTPUT_CHARS = 32000

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a",
    r"forget\s+(everything|your|all)",
    r"reveal\s+(your|the)\s+system\s+prompt",
    r"print\s+(your|the)\s+(system\s+)?prompt",
    r"act\s+as\s+(if|a|an)",
    r"new\s+instruction[s]?:",
    r"system\s*:",
    r"developer\s*:",
    r"bypass\s+(the\s+)?guardrails",
    r"jailbreak",
]

HARMFUL_INPUT_PATTERNS = [
    r";\s*rm\s+-rf",
    r"\$\([^)]*\)",
    r"`[^`]*`",
    r"\bunion\s+select\b",
    r"\bdrop\s+table\b",
    r"\binsert\s+into\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\bdelete\s+from\b",
]

BLOCKED_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback"}

BLOCKED_IP_RANGES = [
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/4",
    "240.0.0.0/4",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
}

FABRICATION_RISK_PATTERNS = [
    r"\$[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:million|billion|m|bn)?",
    r"\b[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:million|billion)\b",
    r"\b(?:revenue|funding|valuation|arr|mrr|market share)\b",
    r'"[^"\n]{30,}"',
]

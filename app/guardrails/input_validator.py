import ipaddress
import re
import socket
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from app.guardrails import rules


class GuardrailViolation(ValueError):
    """Raised when hardcoded input guardrails reject a value."""


@dataclass(frozen=True)
class InputValidationResult:
    is_valid: bool
    rejection_reason: str | None
    sanitized_input: str


BLOCKED_NETWORKS = [ipaddress.ip_network(item) for item in rules.BLOCKED_IP_RANGES]


def normalize_text(value: str) -> str:
    if value is None:
        raise GuardrailViolation("Input is required.")

    normalized = unicodedata.normalize("NFC", value.replace("\x00", ""))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    bad_chars = [
        char
        for char in normalized
        if unicodedata.category(char)[0] == "C" and char not in {"\n", "\t"}
    ]
    if bad_chars:
        raise GuardrailViolation("Input contains unsupported control characters.")
    return normalized.strip()


def validate_user_input(value: str, max_length: int = rules.DEFAULT_MAX_INPUT_LENGTH) -> str:
    sanitized = normalize_text(value)
    if not sanitized:
        raise GuardrailViolation("Input cannot be empty.")
    if len(sanitized) > max_length:
        raise GuardrailViolation(f"Input exceeds {max_length} characters.")

    lowered = sanitized.lower()
    for pattern in rules.INJECTION_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            raise GuardrailViolation("Input rejected by prompt-injection guardrails.")

    for pattern in rules.HARMFUL_INPUT_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            raise GuardrailViolation("Input rejected by abuse-pattern guardrails.")

    return sanitized


def sanitize_external_context(
    value: str,
    max_length: int = rules.MAX_EXTERNAL_CONTEXT_LENGTH,
) -> str:
    sanitized = normalize_text(value)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()

    lowered = sanitized.lower()
    for pattern in rules.INJECTION_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return "[External context removed: prompt-injection pattern detected.]"
    return sanitized


def sanitize_trusted_llm_input(value: str, max_length: int | None = None) -> str:
    sanitized = normalize_text(value)
    if max_length is not None and len(sanitized) > max_length:
        return sanitized[:max_length].rstrip()
    return sanitized


def validate_url_syntax(url: str) -> str:
    sanitized = normalize_text(url)
    if not sanitized:
        return ""
    if len(sanitized) > 2048:
        raise GuardrailViolation("URL exceeds 2048 characters.")

    parsed = urlparse(sanitized)
    if parsed.scheme not in {"http", "https"}:
        raise GuardrailViolation("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise GuardrailViolation("URL hostname is required.")
    if parsed.username or parsed.password:
        raise GuardrailViolation("URLs with embedded credentials are not allowed.")
    return sanitized


def validate_url_for_fetch(url: str) -> str:
    sanitized = validate_url_syntax(url)
    parsed = urlparse(sanitized)
    hostname = parsed.hostname
    if not hostname:
        raise GuardrailViolation("URL hostname is required.")
    if hostname.lower().rstrip(".") in rules.BLOCKED_HOSTNAMES:
        raise GuardrailViolation("Localhost URLs are not allowed.")

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or _default_port(parsed.scheme))
    except socket.gaierror as exc:
        raise GuardrailViolation("URL hostname could not be resolved.") from exc

    resolved_ips = {ipaddress.ip_address(item[4][0]) for item in addr_info}
    for ip_addr in resolved_ips:
        if _is_blocked_ip(ip_addr):
            raise GuardrailViolation("URL resolves to a blocked network range.")

    return sanitized


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _is_blocked_ip(ip_addr: ipaddress._BaseAddress) -> bool:
    if (
        ip_addr.is_private
        or ip_addr.is_loopback
        or ip_addr.is_link_local
        or ip_addr.is_multicast
        or ip_addr.is_reserved
        or ip_addr.is_unspecified
    ):
        return True
    return any(ip_addr in network for network in BLOCKED_NETWORKS)

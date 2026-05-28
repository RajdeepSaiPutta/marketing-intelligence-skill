import re
from dataclasses import dataclass

from app.guardrails import rules
from app.guardrails.input_validator import sanitize_trusted_llm_input


@dataclass(frozen=True)
class OutputValidationResult:
    sanitized_output: str
    warnings: list[str]


def sanitize_llm_output(
    value: str,
    stage: str = "chat",
    grounding_context: str = "",
    system_prompt: str = "",
) -> OutputValidationResult:
    sanitized = sanitize_trusted_llm_input(value, max_length=rules.MAX_OUTPUT_CHARS)
    warnings: list[str] = []

    for pattern in rules.PII_PATTERNS.values():
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)

    sanitized = _strip_system_prompt_leaks(sanitized, system_prompt)

    if stage == "seo_generation" and not sanitized.lstrip().startswith("OUTPUT:"):
        sanitized = "OUTPUT: " + sanitized.lstrip()

    if _has_fabrication_risk(sanitized) and not _has_supporting_context(sanitized, grounding_context):
        warning = "[WARNING] Some data points could not be verified against real-time sources."
        if warning not in sanitized:
            sanitized = sanitized.rstrip() + "\n\n" + warning
        warnings.append("fabrication_risk")

    return OutputValidationResult(sanitized_output=sanitized, warnings=warnings)


def _strip_system_prompt_leaks(output: str, system_prompt: str) -> str:
    if not system_prompt:
        return output

    protected = output
    marker_patterns = [
        r"IDENTITY\s*&\s*ROLE",
        r"CORE\s+PARAMETER\s+WORKFLOW\s+PIPELINES",
        r"MANDATORY\s+RE-RUN\s+TEMPLATE",
        r"TECHNICAL\s+SEO\s*&\s*PSYCHOLOGY\s+MATRIX",
    ]
    for pattern in marker_patterns:
        protected = re.sub(pattern, "[REDACTED SYSTEM INSTRUCTIONS]", protected, flags=re.IGNORECASE)

    significant_lines = [
        line.strip()
        for line in system_prompt.splitlines()
        if len(line.strip()) >= 80
    ]
    for line in significant_lines:
        protected = protected.replace(line, "[REDACTED SYSTEM INSTRUCTIONS]")
    return protected


def _has_fabrication_risk(output: str) -> bool:
    return any(re.search(pattern, output, flags=re.IGNORECASE) for pattern in rules.FABRICATION_RISK_PATTERNS)


def _has_supporting_context(output: str, grounding_context: str) -> bool:
    if not grounding_context.strip():
        return False

    grounding = grounding_context.lower()
    risk_fragments = re.findall(
        r"(?:\$[0-9][0-9,]*(?:\.[0-9]+)?|[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:million|billion))",
        output,
        flags=re.IGNORECASE,
    )
    if not risk_fragments:
        return True
    return all(fragment.lower() in grounding for fragment in risk_fragments[:10])

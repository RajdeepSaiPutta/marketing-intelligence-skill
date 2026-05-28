import logging

from google.genai import types

from app.config import get_settings
from app.dependencies import get_google_client
from app.guardrails.input_validator import sanitize_external_context, validate_user_input
from app.guardrails.output_validator import sanitize_llm_output

logger = logging.getLogger(__name__)


def fetch_live_google_grounding(query: str) -> str:
    settings = get_settings()
    safe_query = validate_user_input(query, max_length=settings.max_input_length)
    try:
        response = get_google_client().models.generate_content(
            model=settings.gemini_model,
            contents=(
                "Extract the active real-world facts, product tiers, capabilities, "
                "and market competitors for this query. Return concise bullets only, "
                f"with no boilerplate: {safe_query}"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                max_output_tokens=500,
                temperature=0.2,
            ),
        )
    except Exception:
        logger.error("Gemini grounding failed")
        return "Google web search grounding temporarily unavailable."

    raw_text = response.text if response.text else ""
    sanitized = sanitize_llm_output(raw_text, stage="chat").sanitized_output
    return sanitize_external_context(_dedupe_lines(sanitized), max_length=1800)


def _dedupe_lines(value: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for line in value.splitlines():
        cleaned = line.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            lines.append(cleaned)
    return "\n".join(lines)

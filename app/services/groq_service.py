import logging

from app.config import get_settings
from app.dependencies import get_groq_client
from app.guardrails.input_validator import sanitize_external_context, validate_user_input
from app.guardrails.output_validator import sanitize_llm_output

logger = logging.getLogger(__name__)


def create_completion(messages: list[dict[str, str]], temperature: float, max_tokens: int):
    settings = get_settings()
    return get_groq_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def create_completion_stream(messages: list[dict[str, str]], temperature: float, max_tokens: int):
    settings = get_settings()
    return get_groq_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )


def analyze_writing_style(article_text: str) -> str:
    safe_article = sanitize_external_context(article_text, max_length=3000)
    if not safe_article.strip():
        return ""

    prompt = validate_user_input(
        "Analyze this article's writing style. Return a concise style profile covering: "
        "tone, average sentence length, vocabulary level, rhetorical devices used, "
        "structural patterns, and any distinctive voice characteristics. Keep it under "
        f"300 words.\n\nArticle: {safe_article}",
        max_length=3800,
    )
    try:
        completion = create_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400,
        )
    except Exception:
        logger.error("Style analysis failed")
        return "Style analysis failed."

    raw_text = completion.choices[0].message.content or ""
    return sanitize_llm_output(raw_text, stage="chat").sanitized_output

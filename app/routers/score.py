import logging
import re

from fastapi import APIRouter, HTTPException

from app.models import ScoreRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["score"])


@router.post("/score-article")
async def score_article(request: ScoreRequest):
    try:
        return calculate_article_score(request.article_text, request.target_keyword)
    except Exception:
        logger.error("Unhandled error in score_article")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        ) from None


def calculate_article_score(text: str, target_keyword: str = "") -> dict[str, int | float]:
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    reading_time = max(1, word_count // 200)
    headings = len(re.findall(r"^#{2,3}\s+", text, re.MULTILINE))

    kw_density = 0.0
    if target_keyword and word_count > 0:
        kw_count = len(re.findall(r"\b" + re.escape(target_keyword.lower()) + r"\b", text.lower()))
        kw_density = (kw_count / word_count) * 100

    sentences = max(1, len(re.split(r"[.!?]+", text)) - 1)
    syllables = sum(count_syllables(word) for word in words)

    fk_score = 0.0
    if word_count > 0:
        fk_score = 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)

    score = 50
    if word_count > 500:
        score += 10
    if word_count > 1000:
        score += 10
    if headings > 3:
        score += 10
    if 0.5 <= kw_density <= 2.5:
        score += 10
    if fk_score > 40:
        score += 10

    return {
        "word_count": word_count,
        "reading_time": reading_time,
        "headings": headings,
        "keyword_density": round(kw_density, 2),
        "readability_score": round(fk_score, 1),
        "overall_score": min(100, max(0, score)),
    }


def count_syllables(word: str) -> int:
    if not word:
        return 0

    lowered = word.lower()
    count = 1 if lowered[0] in "aeiouy" else 0
    for index in range(1, len(lowered)):
        if lowered[index] in "aeiouy" and lowered[index - 1] not in "aeiouy":
            count += 1
    if lowered.endswith("e"):
        count -= 1
    return max(1, count)

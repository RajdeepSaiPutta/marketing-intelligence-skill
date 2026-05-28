import json
import logging
import re

from app.guardrails.input_validator import validate_user_input
from app.services.gemini_service import fetch_live_google_grounding
from app.services.groq_service import analyze_writing_style
from app.services.scraper import scrape_website
from app.routers.score import calculate_article_score

logger = logging.getLogger(__name__)


async def handle_tool_call(name: str, args: dict) -> str:
    try:
        if name == "web_search":
            query = args.get("query", "")
            if not query:
                return "Error: query is required."
            result = fetch_live_google_grounding(query)
            return result

        if name == "scrape_url":
            url = args.get("url", "")
            if not url:
                return "Error: url is required."
            result = await scrape_website(url)
            return result

        if name == "analyze_style":
            text = args.get("text", "")
            if not text:
                return "Error: text is required."
            result = analyze_writing_style(text)
            return result

        if name == "score_article":
            article_text = args.get("article_text", "")
            target_keyword = args.get("target_keyword", "")
            if not article_text:
                return "Error: article_text is required."
            result = calculate_article_score(article_text, target_keyword)
            return json.dumps(result)

        return f"Error: unknown tool '{name}'."
    except Exception:
        logger.error("Tool call failed: %s", name)
        return f"Tool '{name}' execution failed."

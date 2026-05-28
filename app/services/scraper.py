import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.guardrails.input_validator import GuardrailViolation, sanitize_external_context, validate_url_for_fetch

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 1_048_576
MAX_REDIRECTS = 3
USER_AGENT = "Mozilla/5.0 (compatible; skill-api/1.0; +https://localhost)"


async def scrape_website(url: str) -> str:
    try:
        current_url = validate_url_for_fetch(url)
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0), follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                async with client.stream("GET", current_url, headers={"User-Agent": USER_AGENT}) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise GuardrailViolation("Redirect response did not include a location.")
                        current_url = validate_url_for_fetch(urljoin(current_url, location))
                        continue

                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
                        raise GuardrailViolation("Remote response is too large.")

                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise GuardrailViolation("Remote response is too large.")
                    return _extract_summary(bytes(content), response.encoding)

            raise GuardrailViolation("Too many redirects.")
    except GuardrailViolation:
        logger.warning("Scrape blocked by guardrails")
        return "[Scraping blocked by URL safety guardrails.]"
    except Exception:
        logger.error("Scraping failed")
        return "[Scraping failed.]"


def _extract_summary(content: bytes, encoding: str | None) -> str:
    html = content.decode(encoding or "utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
        tag.extract()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = str(meta_tag["content"]).strip()

    headings: list[str] = []
    for level in range(1, 4):
        for tag in soup.find_all(f"h{level}"):
            heading = tag.get_text(" ", strip=True)
            if heading:
                headings.append(heading)

    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    summary = (
        f"TITLE: {title}\n"
        f"DESC: {meta_desc}\n"
        f"HEADINGS: {', '.join(headings[:8])}\n"
        f"BODY: {body[:500]}"
    )
    return sanitize_external_context(summary, max_length=800)

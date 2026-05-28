TOOL_REGISTRY = {
    "web_search": {
        "name": "web_search",
        "description": "Search the web for real-time information about a company, product, topic, or person. Uses Google grounding for fresh results.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    "scrape_url": {
        "name": "scrape_url",
        "description": "Extract readable text content from a URL. Returns title, description, headings, and body text.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL to scrape"}},
            "required": ["url"],
        },
    },
    "analyze_style": {
        "name": "analyze_style",
        "description": "Analyze the writing style of a piece of text. Returns tone, sentence length, vocabulary level, and structural patterns.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to analyze"}},
            "required": ["text"],
        },
    },
    "score_article": {
        "name": "score_article",
        "description": "Score an article for SEO quality, readability, keyword density, and structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "article_text": {"type": "string", "description": "Full article text"},
                "target_keyword": {"type": "string", "description": "Optional target keyword"},
            },
            "required": ["article_text"],
        },
    },
}


def get_tool_manifest() -> str:
    lines = ["Available tools:"]
    for name, tool in TOOL_REGISTRY.items():
        params = tool["parameters"]
        param_desc = ", ".join(
            f'{pname}: {pinfo.get("description", "")}'
            for pname, pinfo in params.get("properties", {}).items()
        )
        lines.append(f'- {name}: {tool["description"]} Parameters: {param_desc}')
    return "\n".join(lines)

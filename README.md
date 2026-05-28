# Marketing and Journaling Pipeline

a content generation workspace with persistent memory, security, and mcp tools.

## features

- **3-step pipeline**: paste a url or upload a pdf -> ai researches -> generates article -> seo score
- **chat with tools**: talk to the ai and it can search the web, scrape urls, analyze style, or score articles on its own
- **persistent sessions**: every chat and article saves to sqlite. switch between projects, resume where you left off
- **real-time google grounding**: groq + gemini work together for fresh, factual content
- **document upload**: upload pdf, txt, or md files. content is extracted and fed into the ai context
- **api key auth + rate limiting**: protect your api quota. anonymous users get 2 requests/day by default
- **input/output guardrails**: blocks prompt injection, redacts pii, flags fabricated data. all at the code level, not just instructions

## quick start

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with your groq_api_key, gemini_api_key, admin_api_key
python run.py
# open http://localhost:8000
```

## how it works

there are 4 tabs:

1. **links** -- paste a company url + optional style reference url, or upload a pdf. click start research.
2. **research** -- see the ai's analysis of your target. click create prompts.
3. **results** -- pick a prompt, generate an article, see its seo score, revise, copy, or download as .md.
4. **chat** -- freeform conversation with tools enabled. the ai can search the web, scrape, analyze, or score things for you.

everything saves automatically. switch sessions from the header dropdown to go back to previous work.

## project structure

see `project_structure.md` for the full file tree and explanations.

## security notes

- api keys go in `.env`, never in code
- browser users are anonymous with strict rate limits (2 req/min, 2 req/day default)
- authenticated users get higher limits via api keys created at post /api/admin/keys
- cors allows only your configured origins (no wildcard)
- ssrf blocking on all url fetches
- all llm output is sanitized before reaching the browser
- no stack traces or internal paths are ever returned to the client

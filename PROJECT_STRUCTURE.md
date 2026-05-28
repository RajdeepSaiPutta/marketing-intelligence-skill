# skill+api — project structure

```
skill+api/
│
├── run.py                     start command: python run.py
├── .env                       your api keys (not uploaded to github)
├── .env.example               template showing what keys you need
├── requirements.txt           dependencies to install
├── .gitignore                 files git should ignore
│
├── index.html                 the web app -- open http://localhost:8000
│
├── app/
│   ├── main.py                app factory -- wires everything together
│   ├── config.py              all settings from .env
│   ├── models.py              request/response formats
│   ├── dependencies.py        groq + gemini client connections
│   │
│   ├── routers/               api endpoints (what you call)
│   │   ├── generate.py        post /api/generate-content -- write articles
│   │   ├── chat.py            post /api/chat -- talk with ai + tools
│   │   ├── score.py           post /api/score-article -- grade seo quality
│   │   ├── sessions.py        get/post/delete /api/sessions -- save/load chats
│   │   ├── admin.py           post/get/delete /api/admin/keys -- manage api keys
│   │   └── documents.py       post/get/delete /api/documents -- upload pdfs
│   │
│   ├── services/              brain -- actual work happens here
│   │   ├── groq_service.py    talks to groq ai (llama model)
│   │   ├── gemini_service.py  talks to google gemini (web search)
│   │   ├── scraper.py         reads website content safely
│   │   ├── chat_service.py    chat logic + mcp tool loop
│   │   ├── document_service.py extracts text from pdf/txt/md files
│   │   ├── session_service.py saves/loads your chat history
│   │   └── prompt_optimizer.py picks the right instructions for each task
│   │
│   ├── guardrails/            safety checks
│   │   ├── input_validator.py blocks prompt injection, bad urls, control chars
│   │   ├── output_validator.py redacts pii, flags made-up data
│   │   └── rules.py           all the regex patterns (blocklists)
│   │
│   ├── security/              auth + rate limits
│   │   ├── auth.py            checks api keys (bearer tokens)
│   │   ├── rate_limiter.py    stops abuse (2 req/min anonymous default)
│   │   └── cors.py            only your domain can call the api
│   │
│   ├── memory/                database
│   │   └── store.py           sqlite -- stores sessions, messages, keys, docs
│   │
│   └── tools/                 mcp tools (ai can use these)
│       ├── registry.py        lists available tools for the ai
│       └── handlers.py        runs the tools when ai asks
│
├── test_all.py                28 automated tests
├── skill.md                   instructions the ai follows for writing
├── scaling_plan.md            development roadmap
└── project_structure.md       this file
```

## what everything does

**run.py** -> **main.py** -- starts the web server. all requests flow through here.

**routers/** -- waiters. they take your request and pass it to the right kitchen.

**services/** -- the kitchen. groq bakes articles, gemini fetches web facts, scraper reads websites.

**guardrails/** -- health inspector. blocks bad inputs before they reach the ai, cleans outputs before they reach you.

**security/** -- security guard. checks your api key, rate-limits, locks cors.

**memory/store.py** -- filing cabinet. every chat, every upload, every api key gets saved to a sqlite file on disk.

**tools/** -- the ai's toolbox. when you chat with tools enabled, the ai can search the web, scrape urls, analyze writing style, or score articles on its own.

## what happens when you click "start research"

1. browser sends your urls + pdfs to post /api/generate-content-stream
2. generate.py receives it
3. input_validator.py checks for hacks
4. scraper.py reads your urls safely (blocks localhost/private ips)
5. gemini_service.py searches google for real-time facts
6. document_service.py pulls text from your uploaded pdfs
7. everything gets bundled into instructions for groq ai
8. groq writes the analysis, output_validator.py cleans it
9. response streams back to your browser
10. store.py saves the conversation to sqlite

## what happens when you chat with tools

same flow, but groq can decide to call web_search, scrape_url, analyze_style, or score_article mid-conversation. the chat service loops: ai request -> tool result -> ai final answer.

## setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in your groq_api_key, gemini_api_key, admin_api_key in .env
python run.py
# open http://localhost:8000
```

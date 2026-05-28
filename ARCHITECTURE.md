# architecture diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │              browser (index.html)                │
                    │  tab1: links  tab2: research  tab3: article     │
                    │  tab4: chat   session dropdown  doc upload      │
                    └──────────┬──────────────────────────────────────┘
                               │ http://localhost:8000
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        fastapi app (app/main.py)                         │
│                                                                          │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────────┐   │
│  │ bodysize     │   │ ratelimiter      │   │ cors                   │   │
│  │ middleware    │──▶│ middleware        │──▶│ middleware              │   │
│  │ (max 1mb)    │   │ (checks quota)   │   │ (allows your origins)   │   │
│  └──────────────┘   └──────────────────┘   └────────────────────────┘   │
│                               │                                          │
│                               ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │                     route dispatcher                          │       │
│  │  ┌──────────┐  ┌──────┐  ┌──────┐  ┌────────┐  ┌──────────┐  │       │
│  │  │ generate │  │ chat │  │score │  │sessions│  │ admin    │  │       │
│  │  │ router   │  │router│  │router│  │router  │  │ router   │  │       │
│  │  └────┬─────┘  └──┬───┘  └──┬───┘  └───┬────┘  └────┬─────┘  │       │
│  │       │           │         │          │            │        │       │
│  │       │           │         │          │            │        │       │
│  │       │    ┌──────┘         │          │            │        │       │
│  │       │    │  documents     │          │            │        │       │
│  │       │    │  router        │          │            │        │       │
│  │       │    └──┬─────────────┘          │            │        │       │
│  └───────┼────────┼───────────────────────┼────────────┼────────┘       │
└──────────┼────────┼───────────────────────┼────────────┼────────────────┘
           │        │                       │            │
           ▼        ▼                       ▼            ▼
    ┌──────────────┐  ┌──────────────┐  ┌────────┐  ┌──────────┐
    │ generate     │  │ chat_service │  │ score  │  │ session  │
    │ pipeline     │  │ + tools loop │  │ (local)│  │ crud     │
    └──────┬───────┘  └──────┬───────┘  └────────┘  └────┬─────┘
           │                 │                            │
           ▼                 ▼                            ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    input guardrails                          │
    │  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
    │  │ normalize│  │ validate │  │ injection │  │ url/ssrf  │  │
    │  │ unicode  │  │ max len  │  │ detection  │  │ check     │  │
    │  └──────────┘  └──────────┘  └───────────┘  └───────────┘  │
    └──────────────────────┬───────────────────────────────────────┘
                           │ passes
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    context builder                            │
    │  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
    │  │ session  │  │ document │  │ scraper   │  │ gemini    │  │
    │  │ history  │  │ text     │  │ (url)     │  │ web search│  │
    │  └──────────┘  └──────────┘  └───────────┘  └───────────┘  │
    │                                                              │
    │  all bundled into system prompt + messages array             │
    └──────────────────────┬───────────────────────────────────────┘
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                       groq ai (llama)                        │
    │  - writes analysis                                           │
    │  - generates article                                         │
    │  - answers chat                                              │
    │  - may request tool calls (if tools_enabled)                 │
    └──────────┬───────────────────────────────────────────────────┘
               │ raw response
               ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    output guardrails                          │
    │  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
    │  │ pii      │  │ system   │  │ fabrication│  │ format    │  │
    │  │ redact   │  │ prompt   │  │ flag      │  │ enforce   │  │
    │  │          │  │ leak     │  │           │  │ (output:) │  │
    │  └──────────┘  └──────────┘  └───────────┘  └───────────┘  │
    └──────────────────────┬───────────────────────────────────────┘
                           │ clean response
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                     persist to sqlite                         │
    │  - append_exchange(session_id, user_msg, assistant_msg)      │
    │  - updates session timestamp                                 │
    └──────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                  stream back to browser                       │
    │  sse events: {"token": "..."}  {"done": true}                │
    │  or with tools: {"tool_call": {...}}  {"token": "..."}       │
    └──────────────────────────────────────────────────────────────┘


                     ===== tool call flow (in chat) =====

    ┌─────────┐    ┌──────────────┐    ┌───────────────┐
    │ groq    │───▶│ detect       │───▶│ execute tool  │
    │ returns │    │ {"tool":..., │    │ via handlers  │
    │ tool    │    │ "args":...}  │    │               │
    │ request │    │              │    │               │
    └─────────┘    └──────────────┘    └───────┬───────┘
         ▲                                    │ result
         │                                    ▼
         │                          ┌──────────────────┐
         └──────────────────────────│ feed result back │
            send again with         │ to groq + repeat │
            tool result as context  │ (max 5 rounds)   │
                                    └──────────────────┘


                     ===== session restore flow =====

    ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐
    │ user clicks  │───▶│ get          │───▶│ parse messages  │
    │ session in   │    │ /api/sessions│    │ by content:     │
    │ dropdown     │    │ /{id}        │    │ - "output:" →   │
    │              │    │              │    │   article       │
    │              │    │              │    │ - "[prompt]" →  │
    │              │    │              │    │   prompt cards  │
    │              │    │              │    │ - other →       │
    │              │    │              │    │   matrix/chat   │
    └──────────────┘    └──────────────┘    └────────┬────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────────┐
                                          │ restore ui panels   │
                                          │ switch to correct   │
                                          │ tab                 │
                                          └─────────────────────┘


                     ===== file upload flow =====

    ┌──────────┐    ┌──────────────┐    ┌──────────────────┐
    │ user     │───▶│ post         │───▶│ detect type:     │
    │ picks    │    │ /api/        │    │ .pdf → pymupdf   │
    │ file     │    │ documents    │    │ .txt → utf-8     │
    │          │    │ (multipart)  │    │ .md → utf-8      │
    └──────────┘    └──────────────┘    └────────┬─────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │ store text in sqlite │
                                       │ documents table      │
                                       └──────────────────────┘
```

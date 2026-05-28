import json
import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.guardrails.input_validator import sanitize_external_context, sanitize_trusted_llm_input
from app.guardrails.output_validator import sanitize_llm_output
from app.models import ContentRequest
from app.services.document_service import get_document_text
from app.services.gemini_service import fetch_live_google_grounding
from app.services.groq_service import analyze_writing_style, create_completion, create_completion_stream
from app.services.prompt_optimizer import get_prompt_for_stage
from app.services.scraper import scrape_website
from app.services.session_service import session_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate-content")
async def generate_content(request: ContentRequest):
    try:
        runtime_system_instruction, grounding_context = await build_runtime_instruction(request)
        history = session_service.get_history(request.session_id)

        current_user_message = {"role": "user", "content": request.user_prompt}
        messages = [{"role": "system", "content": runtime_system_instruction}] + history + [current_user_message]

        completion = create_completion(messages=messages, temperature=0.7, max_tokens=3000)
        raw_response = completion.choices[0].message.content
        if not raw_response:
            raise HTTPException(status_code=502, detail="Upstream model returned an empty response.")

        ai_response = sanitize_llm_output(
            raw_response,
            stage=request.stage,
            grounding_context=grounding_context,
            system_prompt=runtime_system_instruction,
        ).sanitized_output
        session_service.append_exchange(request.session_id, request.user_prompt, ai_response)
        return {"success": True, "data": ai_response}
    except HTTPException:
        raise
    except Exception:
        logger.error("Unhandled error in generate_content")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        ) from None


@router.post("/generate-content-stream")
async def generate_content_stream(request: ContentRequest):
    try:
        runtime_system_instruction, grounding_context = await build_runtime_instruction(request)
        history = session_service.get_history(request.session_id)
        current_user_message = {"role": "user", "content": request.user_prompt}
        messages = [{"role": "system", "content": runtime_system_instruction}] + history + [current_user_message]
    except Exception:
        logger.error("Failed to prepare streaming generation")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        ) from None

    def event_generator():
        try:
            full_response = ""
            stream = create_completion_stream(messages=messages, temperature=0.7, max_tokens=3000)
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content

            safe_response = sanitize_llm_output(
                full_response,
                stage=request.stage,
                grounding_context=grounding_context,
                system_prompt=runtime_system_instruction,
            ).sanitized_output
            session_service.append_exchange(request.session_id, request.user_prompt, safe_response)

            for index in range(0, len(safe_response), 512):
                yield f"data: {json.dumps({'token': safe_response[index:index + 512]})}\n\n"
            yield f"data: {json.dumps({'done': True, 'full_text': safe_response})}\n\n"
        except Exception:
            logger.error("Unhandled error in generate_content_stream")
            payload = {
                "error": "internal_error",
                "detail": "An internal error occurred. Please try again.",
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def build_runtime_instruction(request: ContentRequest) -> tuple[str, str]:
    base_prompt = get_prompt_for_stage(request.stage)
    google_search_context = fetch_live_google_grounding(request.user_prompt)
    grounding_context = sanitize_external_context(google_search_context, max_length=3000)

    urls = re.findall(r"(https?://\S+)", request.user_prompt)
    scraped_data = ""
    if urls:
        scraped_data = await scrape_website(urls[0])

    style_profile = ""
    if request.reference_url:
        ref_text = await scrape_website(request.reference_url)
        if ref_text and not ref_text.startswith("[Scraping"):
            style_profile = sanitize_external_context(analyze_writing_style(ref_text), max_length=1200)

    document_texts: list[str] = []
    for doc_id in request.documents:
        text = get_document_text(doc_id)
        if text:
            safe_text = sanitize_external_context(text, max_length=2000)
            document_texts.append(f"[Document {doc_id}]:\n{safe_text}")

    instruction = (
        f"{base_prompt}\n\n"
        "CURRENT WORKSPACE RUNTIME SETTINGS:\n"
        f"- TARGET PIPELINE STATE EXECUTION REQUIRED: {request.stage.upper()}\n"
        "- REAL-TIME GOOGLE GROUNDING CONTEXT:\n"
        f"{grounding_context}"
    )

    if scraped_data:
        safe_scraped_data = sanitize_external_context(scraped_data, max_length=2000)
        instruction += f"\n- SCRAPED WEBSITE CONTENT:\n{safe_scraped_data}"

    if style_profile:
        instruction += f"\n- REFERENCE VOICE STYLE PROFILE:\n{style_profile}"

    if document_texts:
        instruction += "\n- UPLOADED DOCUMENTS:\n" + "\n\n".join(document_texts)

    return sanitize_trusted_llm_input(instruction, max_length=9000), grounding_context

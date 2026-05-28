import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.guardrails.input_validator import validate_url_syntax, validate_user_input


class ContentRequest(BaseModel):
    user_prompt: str = Field(..., max_length=4000)
    stage: Literal["ideation", "seo_generation", "chat"]
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=36)
    reference_url: str = Field(default="", max_length=2048)
    documents: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("user_prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return validate_user_input(value)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError("session_id must be a valid UUID.") from exc

    @field_validator("reference_url")
    @classmethod
    def validate_reference_url(cls, value: str) -> str:
        if not value or not value.strip():
            return ""
        return validate_url_syntax(value)

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, value: list[str]) -> list[str]:
        clean_ids: list[str] = []
        for document_id in value:
            try:
                clean_ids.append(str(uuid.UUID(document_id)))
            except ValueError as exc:
                raise ValueError("document IDs must be valid UUIDs.") from exc
        return clean_ids


class ScoreRequest(BaseModel):
    article_text: str = Field(..., min_length=1, max_length=50000)
    target_keyword: str = Field(default="", max_length=200)

    @field_validator("article_text")
    @classmethod
    def validate_article_text(cls, value: str) -> str:
        cleaned = value.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("article_text cannot be empty.")
        return cleaned

    @field_validator("target_keyword")
    @classmethod
    def validate_target_keyword(cls, value: str) -> str:
        return value.replace("\x00", "").strip()


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=36)
    tools_enabled: bool = False
    documents: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return validate_user_input(value)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError("session_id must be a valid UUID.") from exc

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, value: list[str]) -> list[str]:
        clean_ids: list[str] = []
        for document_id in value:
            try:
                clean_ids.append(str(uuid.UUID(document_id)))
            except ValueError as exc:
                raise ValueError("document IDs must be valid UUIDs.") from exc
        return clean_ids

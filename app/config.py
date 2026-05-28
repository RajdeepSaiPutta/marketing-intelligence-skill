from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    gemini_api_key: str
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:8000"])
    max_input_length: int = 4000
    max_history_messages: int = 20
    max_sessions_per_ip: int = 10
    db_path: str = "data/sessions.db"
    upload_dir: str = "data/documents"
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.5-flash"
    max_request_body_bytes: int = 1_048_576
    admin_api_key: str = ""
    anonymous_requests_per_minute: int = 2
    anonymous_requests_per_day: int = 2
    authenticated_requests_per_minute: int = 5
    authenticated_requests_per_day: int = 50
    global_requests_per_minute: int = 20
    global_requests_per_day: int = 800

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        else:
            origins = value

        if not origins:
            raise ValueError("At least one allowed origin is required.")
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed.")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()

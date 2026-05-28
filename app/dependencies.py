from functools import lru_cache
from pathlib import Path

from google import genai
from groq import Groq

from app.config import Settings, get_settings


@lru_cache
def get_groq_client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)


@lru_cache
def get_google_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


@lru_cache
def get_base_system_prompt() -> str:
    skill_path = Path("SKILL.md")
    if not skill_path.exists():
        return "Act as an expert strategist. Follow structured workspace parameters."
    return skill_path.read_text(encoding="utf-8")


def settings_dependency() -> Settings:
    return get_settings()

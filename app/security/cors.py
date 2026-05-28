from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings


def configure_cors(app: FastAPI, settings: Settings) -> None:
    if "*" in settings.allowed_origins:
        raise RuntimeError("Wildcard CORS origins are not allowed.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

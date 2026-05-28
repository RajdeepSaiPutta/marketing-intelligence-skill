from typing import Any

from app.memory.store import store


class SQLiteSessionService:
    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return store.get_history(session_id)

    def append_exchange(self, session_id: str, user_message: str, assistant_message: str) -> None:
        store.append_exchange(session_id, user_message, assistant_message)

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return store.list_sessions(limit=limit, offset=offset)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return store.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        return store.delete_session(session_id)


session_service = SQLiteSessionService()

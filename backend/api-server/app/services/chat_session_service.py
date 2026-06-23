from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.chat import ChatSession


class ChatSessionService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(
        self,
        project_id: int,
        session_code: str | None = None,
        source: str = "portal",
        selected_kb_ids: list[int] | None = None,
        switches: dict | None = None,
    ) -> ChatSession:
        session = None
        if session_code:
            session = (
                self.db.query(ChatSession)
                .filter(ChatSession.project_id == project_id, ChatSession.session_code == session_code)
                .first()
            )
        if session:
            return session

        session = ChatSession(
            session_code=session_code or self._build_session_code(),
            project_id=project_id,
            source=source,
            title="新對話",
            selected_kb_ids=selected_kb_ids or [],
            switches_json=switches or {},
            last_active_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.flush()
        return session

    def sync_scene_state(self, session: ChatSession, scene_payload: dict[str, object]) -> None:
        next_state = dict(session.state_json or {})
        next_state["scene"] = {
            "scene_key": scene_payload["scene_key"],
            "case_id": scene_payload["case_id"],
            "route_key": scene_payload.get("route_key"),
            "state": scene_payload["state"],
            "missing_fields": scene_payload.get("missing_fields", []),
            "updated_at": datetime.utcnow().isoformat(),
        }
        session.state_json = next_state
        session.summary = str(scene_payload.get("summary") or "") or session.summary
        session.last_active_at = datetime.utcnow()
        if scene_payload.get("summary"):
            session.title = str(scene_payload["summary"])[:24]

    def clear_scene_state(self, session: ChatSession) -> None:
        next_state = dict(session.state_json or {})
        next_state.pop("scene", None)
        session.state_json = next_state or None
        session.last_active_at = datetime.utcnow()

    def _build_session_code(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"sess_{timestamp}"

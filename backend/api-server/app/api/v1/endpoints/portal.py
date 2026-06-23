from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.chat_service import ChatService
from app.services.project_service import ProjectService
from app.services.scenes.service import SceneService

router = APIRouter()


class PortalChatAskRequest(BaseModel):
    session_id: str | None = None
    query: str
    use_memory: bool = True
    source: str = "portal"
    selected_kb_ids: list[int] = Field(default_factory=list)
    switches: dict = Field(default_factory=dict)


class PortalSceneActionRequest(BaseModel):
    confirmation_token: str | None = None


def _ensure_public_project(project_id: int, db: Session) -> dict:
    project = ProjectService(db).get_public_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


@router.get("/projects", response_model=ApiResponse[list[dict]])
def list_projects(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ProjectService(db).list_public_projects())


@router.get("/projects/{project_id}/opening", response_model=ApiResponse[dict])
def get_opening(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _ensure_public_project(project_id, db)
    return ApiResponse(data=ProjectService(db).get_opening_settings(project_id))


@router.post("/projects/{project_id}/chat/ask", response_model=ApiResponse[dict])
def ask(project_id: int, payload: PortalChatAskRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _ensure_public_project(project_id, db)
    data = ChatService(db).ask(
        project_id=project_id,
        session_id=payload.session_id,
        query=payload.query,
        use_memory=payload.use_memory,
        source=payload.source,
        selected_kb_ids=payload.selected_kb_ids,
        switches=payload.switches,
    )
    return ApiResponse(data=data)


@router.post("/projects/{project_id}/chat/stream")
async def stream_ask(project_id: int, payload: PortalChatAskRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    _ensure_public_project(project_id, db)
    service = ChatService(db)

    async def event_stream():
        try:
            async for chunk in service.stream_ask(
                project_id=project_id,
                session_id=payload.session_id,
                query=payload.query,
                use_memory=payload.use_memory,
                source=payload.source,
                selected_kb_ids=payload.selected_kb_ids,
                switches=payload.switches,
            ):
                yield chunk
        except ValueError as exc:
            yield service._sse_event("error", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            yield service._sse_event("error", {"message": str(exc) or "stream_failed"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/projects/{project_id}/chat/sessions", response_model=ApiResponse[list[dict]])
def list_sessions(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    _ensure_public_project(project_id, db)
    return ApiResponse(data=ChatService(db).list_sessions(project_id))


@router.get("/projects/{project_id}/chat/sessions/{session_id}", response_model=ApiResponse[dict])
def get_session_detail(project_id: int, session_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    _ensure_public_project(project_id, db)
    data = ChatService(db).get_session_detail(project_id, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ApiResponse(data=data)


@router.get("/projects/{project_id}/scenes/{case_id}", response_model=ApiResponse[dict])
def get_scene(project_id: int, case_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    if not project_context["project"] or project_context["project"].get("status") != "active":
        raise HTTPException(status_code=404, detail="project_not_found")
    return ApiResponse(data=SceneService(db).get_case_detail(project_id, case_id, project_context))


@router.post("/projects/{project_id}/scenes/{case_id}/actions/{action_name}", response_model=ApiResponse[dict])
def execute_action(
    project_id: int,
    case_id: str,
    action_name: str,
    payload: PortalSceneActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    if not project_context["project"] or project_context["project"].get("status") != "active":
        raise HTTPException(status_code=404, detail="project_not_found")
    return ApiResponse(
        data=SceneService(db).execute_action(
            project_id,
            case_id,
            action_name,
            project_context,
            confirmation_token=payload.confirmation_token if payload else None,
        )
    )


@router.get("/projects/{project_id}/scenes/{case_id}/artifacts/{artifact_key}")
def get_artifact(project_id: int, case_id: str, artifact_key: str, db: Session = Depends(get_db)):
    _ensure_public_project(project_id, db)
    return SceneService(db).serve_artifact(project_id, case_id, artifact_key)

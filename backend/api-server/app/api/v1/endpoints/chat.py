from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.database import get_db
from app.schemas.common import ApiResponse, SimpleMessage
from app.services.chat_service import ChatService

router = APIRouter()


class ChatAskRequest(BaseModel):
    session_id: str | None = None
    query: str
    use_memory: bool = True
    source: str = "portal"
    selected_kb_ids: list[int] = Field(default_factory=list)
    switches: dict = Field(default_factory=dict)


@router.post("/ask", response_model=ApiResponse[dict])
def ask(project_id: int, payload: ChatAskRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    try:
        data = ChatService(db).ask(
            project_id=project_id,
            session_id=payload.session_id,
            query=payload.query,
            use_memory=payload.use_memory,
            source=payload.source,
            selected_kb_ids=payload.selected_kb_ids,
            switches=payload.switches,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.post("/stream")
async def stream_ask(project_id: int, payload: ChatAskRequest, db: Session = Depends(get_db)) -> StreamingResponse:
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


@router.get("/sessions", response_model=ApiResponse[list[dict]])
def list_sessions(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ChatService(db).list_sessions(project_id))


@router.get("/sessions/{session_id}", response_model=ApiResponse[dict])
def get_session_detail(project_id: int, session_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = ChatService(db).get_session_detail(project_id, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ApiResponse(data=data)


@router.delete("/sessions/{session_id}/memory", response_model=ApiResponse[SimpleMessage])
def clear_session_memory(project_id: int, session_id: str, db: Session = Depends(get_db)) -> ApiResponse[SimpleMessage]:
    cleared = ChatService(db).clear_session_memory(project_id, session_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="memory_cleared"))

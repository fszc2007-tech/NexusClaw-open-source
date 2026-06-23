from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("", response_model=ApiResponse[list[dict]])
def list_logs(
    project_id: int,
    session_id: str | None = Query(default=None),
    query_keyword: str | None = Query(default=None),
    answer_keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    data = ChatService(db).list_logs(
        project_id=project_id,
        session_id=session_id,
        query_keyword=query_keyword,
        answer_keyword=answer_keyword,
    )
    return ApiResponse(data=data)


@router.get("/{session_id}", response_model=ApiResponse[dict])
def get_log_detail(project_id: int, session_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = ChatService(db).get_log_detail(project_id, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="session_not_found")
    return ApiResponse(data=data)

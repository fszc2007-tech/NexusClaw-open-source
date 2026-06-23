from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


class KnowledgeCreateRequest(BaseModel):
    kb_id: int
    title: str
    keywords: list[str] = Field(default_factory=list)
    content: str
    document_name: str | None = None
    check_duplicate: bool = True


@router.get("", response_model=ApiResponse[list[dict]])
def list_knowledge(
    project_id: int,
    kb_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    service = KnowledgeService(db)
    target_kb_id = kb_id
    if target_kb_id is None:
        bases = service.list_bases(project_id)
        if not bases:
            return ApiResponse(data=[])
        target_kb_id = bases[0]["id"]
    return ApiResponse(data=service.list_items(project_id=project_id, kb_id=target_kb_id, status=status))


@router.post("", response_model=ApiResponse[dict])
def create_knowledge(
    project_id: int,
    payload: KnowledgeCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=KnowledgeService(db).create_item(project_id=project_id, kb_id=payload.kb_id, payload=payload.model_dump()))


@router.post("/{knowledge_id}/publish", response_model=ApiResponse[dict])
def publish_knowledge(
    project_id: int,
    knowledge_id: int,
    kb_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).publish_item(project_id=project_id, kb_id=kb_id, knowledge_id=knowledge_id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return ApiResponse(data=data)

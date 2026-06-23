from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


class KnowledgeCreateRequest(BaseModel):
    kb_id: int
    title: str
    keywords: list[str] = []
    content: str
    check_duplicate: bool = True


@router.get("", response_model=ApiResponse[list[dict]])
def list_knowledge(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    service = KnowledgeService(db)
    return ApiResponse(data=service.list_knowledge(project_id))


@router.post("", response_model=ApiResponse[dict])
def create_knowledge(project_id: int, payload: KnowledgeCreateRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    service = KnowledgeService(db)
    result = service.preview_create(
        project_id=project_id,
        kb_id=payload.kb_id,
        title=payload.title,
        keywords=payload.keywords,
        content=payload.content,
        check_duplicate=payload.check_duplicate,
    )
    return ApiResponse(data=result)

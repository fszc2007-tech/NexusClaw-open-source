from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


class KnowledgeBaseRequest(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False


class KnowledgeItemRequest(BaseModel):
    document_name: str | None = None
    title: str
    keywords: list[str] = Field(default_factory=list)
    content: str
    source_url: str | None = None
    source_org: str | None = None
    review_due_at: str | None = None
    review_sla_days: int | None = None
    owner_user_id: int | None = None
    source_type: str = "manual"
    source_file_id: int | None = None
    status: str = "editing"
    check_duplicate: bool = True


@router.get("", response_model=ApiResponse[list[dict]])
def list_bases(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeService(db).list_bases(project_id))


@router.post("", response_model=ApiResponse[dict])
def create_base(
    project_id: int,
    payload: KnowledgeBaseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=KnowledgeService(db).create_base(project_id, payload.model_dump()))


@router.put("/{kb_id}", response_model=ApiResponse[dict])
def update_base(
    project_id: int,
    kb_id: int,
    payload: KnowledgeBaseRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).update_base(project_id, kb_id, payload.model_dump())
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_base_not_found")
    return ApiResponse(data=data)


@router.delete("/{kb_id}", response_model=ApiResponse[dict])
def delete_base(
    project_id: int,
    kb_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).delete_base(project_id, kb_id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_base_not_found")
    return ApiResponse(data=data)


@router.get("/{kb_id}/dashboard", response_model=ApiResponse[dict])
def dashboard(project_id: int, kb_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=KnowledgeService(db).dashboard(project_id, kb_id))


@router.get("/{kb_id}/items", response_model=ApiResponse[list[dict]])
def list_items(
    project_id: int,
    kb_id: int,
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeService(db).list_items(project_id, kb_id, status))


@router.post("/{kb_id}/items", response_model=ApiResponse[dict])
def create_item(
    project_id: int,
    kb_id: int,
    payload: KnowledgeItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=KnowledgeService(db).create_item(
            project_id,
            kb_id,
            payload.model_dump(),
            acting_user_id=current_user.id,
        )
    )


@router.get("/{kb_id}/items/{knowledge_id}", response_model=ApiResponse[dict])
def get_item(project_id: int, kb_id: int, knowledge_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = KnowledgeService(db).get_item(project_id, kb_id, knowledge_id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return ApiResponse(data=data)


@router.put("/{kb_id}/items/{knowledge_id}", response_model=ApiResponse[dict])
def update_item(
    project_id: int,
    kb_id: int,
    knowledge_id: int,
    payload: KnowledgeItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).update_item(project_id, kb_id, knowledge_id, payload.model_dump(), acting_user_id=current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return ApiResponse(data=data)


@router.post("/{kb_id}/items/{knowledge_id}/publish", response_model=ApiResponse[dict])
def publish_item(
    project_id: int,
    kb_id: int,
    knowledge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).publish_item(project_id, kb_id, knowledge_id, acting_user_id=current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return ApiResponse(data=data)


@router.delete("/{kb_id}/items/{knowledge_id}", response_model=ApiResponse[dict])
def delete_item(
    project_id: int,
    kb_id: int,
    knowledge_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeService(db).delete_item(project_id, kb_id, knowledge_id)
    if not data:
        raise HTTPException(status_code=404, detail="knowledge_not_found")
    return ApiResponse(data=data)

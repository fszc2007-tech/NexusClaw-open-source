from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.dedup_service import DedupService

router = APIRouter()


class DedupCheckRequest(BaseModel):
    title: str
    keywords: list[str] = Field(default_factory=list)
    content: str


class DedupResolveRequest(BaseModel):
    record_id: int
    action: str
    comment: str | None = None


class DedupBulkResolveRequest(BaseModel):
    record_ids: list[int] = Field(default_factory=list)
    action: str
    comment: str | None = None


class DedupRefreshRequest(BaseModel):
    kb_id: int | None = None


@router.post("/check", response_model=ApiResponse[dict])
def check_dedup(
    project_id: int,
    payload: DedupCheckRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = DedupService(db).check(
        project_id=project_id,
        title=payload.title,
        keywords=payload.keywords,
        content=payload.content,
    )
    return ApiResponse(data=data)


@router.get("/candidates", response_model=ApiResponse[list[dict]])
def list_dedup_candidates(
    project_id: int,
    action: str | None = Query(default="pending"),
    kb_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=DedupService(db).list_records(project_id=project_id, action=action, kb_id=kb_id))


@router.post("/refresh", response_model=ApiResponse[dict])
def refresh_dedup_candidates(
    project_id: int,
    payload: DedupRefreshRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=DedupService(db).rebuild_project_records(project_id=project_id, kb_id=payload.kb_id))


@router.post("/resolve", response_model=ApiResponse[dict])
def resolve_dedup(
    project_id: int,
    payload: DedupResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    try:
        data = DedupService(db).resolve_record(
            project_id=project_id,
            record_id=payload.record_id,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail="dedup_record_not_found")
    return ApiResponse(data=data)


@router.post("/bulk-resolve", response_model=ApiResponse[dict])
def bulk_resolve_dedup(
    project_id: int,
    payload: DedupBulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=DedupService(db).bulk_resolve_records(
            project_id=project_id,
            record_ids=payload.record_ids,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
        )
    )

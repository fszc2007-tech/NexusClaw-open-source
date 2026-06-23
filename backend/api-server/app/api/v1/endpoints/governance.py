from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.conflict_service import ConflictService
from app.services.freshness_service import FreshnessService
from app.services.governance_summary_service import GovernanceSummaryService

router = APIRouter()


class StaleScanRequest(BaseModel):
    kb_id: int | None = None
    stale_after_days: int | None = None


class StaleResolveRequest(BaseModel):
    task_id: int
    action: str
    comment: str | None = None
    next_review_days: int | None = None


class StaleBulkResolveRequest(BaseModel):
    task_ids: list[int] = Field(default_factory=list)
    action: str
    comment: str | None = None
    next_review_days: int | None = None


class ConflictScanRequest(BaseModel):
    kb_id: int | None = None


class ConflictResolveRequest(BaseModel):
    task_id: int
    action: str
    comment: str | None = None


class ConflictBulkResolveRequest(BaseModel):
    task_ids: list[int] = Field(default_factory=list)
    action: str
    comment: str | None = None


@router.get("/summary", response_model=ApiResponse[dict])
def get_governance_summary(
    project_id: int,
    kb_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=GovernanceSummaryService(db).build_summary(project_id=project_id, kb_id=kb_id))


@router.get("/stale/tasks", response_model=ApiResponse[list[dict]])
def list_stale_tasks(
    project_id: int,
    status: str | None = Query(default="pending"),
    kb_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=FreshnessService(db).list_stale_tasks(project_id=project_id, status=status, kb_id=kb_id))


@router.post("/stale/scan", response_model=ApiResponse[dict])
def scan_stale_tasks(
    project_id: int,
    payload: StaleScanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=FreshnessService(db).scan_stale_items(
            project_id=project_id,
            kb_id=payload.kb_id,
            stale_after_days=payload.stale_after_days,
        )
    )


@router.post("/stale/resolve", response_model=ApiResponse[dict])
def resolve_stale_task(
    project_id: int,
    payload: StaleResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    try:
        data = FreshnessService(db).resolve_stale_task(
            project_id=project_id,
            task_id=payload.task_id,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
            next_review_days=payload.next_review_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail="governance_task_not_found")
    return ApiResponse(data=data)


@router.post("/stale/bulk-resolve", response_model=ApiResponse[dict])
def bulk_resolve_stale_tasks(
    project_id: int,
    payload: StaleBulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=FreshnessService(db).bulk_resolve_stale_tasks(
            project_id=project_id,
            task_ids=payload.task_ids,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
            next_review_days=payload.next_review_days,
        )
    )


@router.get("/conflict/tasks", response_model=ApiResponse[list[dict]])
def list_conflict_tasks(
    project_id: int,
    status: str | None = Query(default="pending"),
    kb_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ConflictService(db).list_conflict_tasks(project_id=project_id, status=status, kb_id=kb_id))


@router.post("/conflict/scan", response_model=ApiResponse[dict])
def scan_conflict_tasks(
    project_id: int,
    payload: ConflictScanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=ConflictService(db).scan_conflicts(project_id=project_id, kb_id=payload.kb_id))


@router.post("/conflict/resolve", response_model=ApiResponse[dict])
def resolve_conflict_task(
    project_id: int,
    payload: ConflictResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    try:
        data = ConflictService(db).resolve_conflict_task(
            project_id=project_id,
            task_id=payload.task_id,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail="governance_task_not_found")
    return ApiResponse(data=data)


@router.post("/conflict/bulk-resolve", response_model=ApiResponse[dict])
def bulk_resolve_conflict_tasks(
    project_id: int,
    payload: ConflictBulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=ConflictService(db).bulk_resolve_conflict_tasks(
            project_id=project_id,
            task_ids=payload.task_ids,
            action=payload.action,
            reviewer_id=current_user.id,
            comment=payload.comment,
        )
    )

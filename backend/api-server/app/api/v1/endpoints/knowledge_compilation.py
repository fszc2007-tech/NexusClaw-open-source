from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse, SimpleMessage
from app.services.knowledge_compilation_service import KnowledgeCompilationService

router = APIRouter()


class CompilationPageCreateRequest(BaseModel):
    page_type: str = "topic"
    topic_key: str | None = None
    canonical_title: str | None = None
    title: str
    summary: str | None = None
    content_markdown: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tree_node_ids: list[int] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "draft"
    change_summary: str | None = None


class CompilationPageUpdateRequest(CompilationPageCreateRequest):
    pass


class CompilationSourceRequest(BaseModel):
    source_type: str
    source_id: str
    source_ref_id: str | None = None
    source_title: str | None = None
    source_locator: dict[str, Any] = Field(default_factory=dict)
    quote: str | None = None
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    claim_text: str | None = None
    support_type: str = "supports"
    weight: float = 1.0
    order_no: int = 0


class CompilationLinkRequest(BaseModel):
    to_page_id: int
    link_type: str = "related"
    anchor_text: str | None = None


class CompilationRunRequest(BaseModel):
    idempotency_key: str | None = None
    run_type: str = "recompile"
    trigger_type: str = "manual"
    strategy: Literal["compiled_first", "raw_first", "hybrid", "disabled"] = "compiled_first"
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class CompilationHealthRunRequest(BaseModel):
    idempotency_key: str | None = None
    run_type: str = "full_scan"
    page_ids: list[int] = Field(default_factory=list)


class CompilationHealthFindingUpdateRequest(BaseModel):
    status: Literal["open", "resolved", "ignored", "superseded"]


class CompilationWritebackCandidateRequest(BaseModel):
    chat_session_id: str | int
    chat_message_id: int
    suggested_page_id: int | None = None
    suggested_page_type: str = "answer_writeback"
    suggested_title: str | None = None
    review_note: str | None = None


@router.get("/pages", response_model=ApiResponse[list[dict]])
def list_pages(
    project_id: int,
    kb_id: int,
    keyword: str | None = None,
    page_type: str | None = None,
    status: str | None = None,
    health_status: str | None = None,
    topic_key: str | None = None,
    tree_node_id: int | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    data = KnowledgeCompilationService(db).list_pages(
        project_id=project_id,
        kb_id=kb_id,
        keyword=keyword,
        page_type=page_type,
        status=status,
        health_status=health_status,
        topic_key=topic_key,
        tree_node_id=tree_node_id,
    )
    return ApiResponse(data=data)


@router.post("/pages", response_model=ApiResponse[dict])
def create_page(
    project_id: int,
    kb_id: int,
    payload: CompilationPageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).create_page(
        project_id=project_id,
        kb_id=kb_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    return ApiResponse(data=data)


@router.get("/pages/{page_id}", response_model=ApiResponse[dict])
def get_page_detail(project_id: int, kb_id: int, page_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).get_page_detail(project_id, kb_id, page_id)
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_not_found")
    return ApiResponse(data=data)


@router.put("/pages/{page_id}", response_model=ApiResponse[dict])
def update_page(
    project_id: int,
    kb_id: int,
    page_id: int,
    payload: CompilationPageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).update_page(
        project_id=project_id,
        kb_id=kb_id,
        page_id=page_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_not_found")
    return ApiResponse(data=data)


@router.delete("/pages/{page_id}", response_model=ApiResponse[SimpleMessage])
def archive_page(
    project_id: int,
    kb_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[SimpleMessage]:
    ok = KnowledgeCompilationService(db).archive_page(project_id, kb_id, page_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="compilation_page_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="archived"))


@router.get("/pages/{page_id}/versions", response_model=ApiResponse[list[dict]])
def list_versions(project_id: int, kb_id: int, page_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeCompilationService(db).list_versions(project_id, kb_id, page_id))


@router.get("/pages/{page_id}/versions/{version_id}", response_model=ApiResponse[dict])
def get_version_detail(
    project_id: int,
    kb_id: int,
    page_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).get_version_detail(project_id, kb_id, page_id, version_id)
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_version_not_found")
    return ApiResponse(data=data)


@router.post("/pages/{page_id}/versions/{version_id}/publish", response_model=ApiResponse[dict])
def publish_version(
    project_id: int,
    kb_id: int,
    page_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).publish_version(project_id, kb_id, page_id, version_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_version_not_found")
    return ApiResponse(data=data)


@router.get("/pages/{page_id}/sources", response_model=ApiResponse[list[dict]])
def list_sources(project_id: int, kb_id: int, page_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeCompilationService(db).list_sources(project_id, kb_id, page_id))


@router.post("/pages/{page_id}/sources", response_model=ApiResponse[dict])
def add_source(
    project_id: int,
    kb_id: int,
    page_id: int,
    payload: CompilationSourceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).add_source(
        project_id,
        kb_id,
        page_id,
        payload.model_dump(),
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_not_found")
    return ApiResponse(data=data)


@router.delete("/pages/{page_id}/sources/{source_link_id}", response_model=ApiResponse[SimpleMessage])
def delete_source(
    project_id: int,
    kb_id: int,
    page_id: int,
    source_link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[SimpleMessage]:
    ok = KnowledgeCompilationService(db).delete_source(
        project_id,
        kb_id,
        page_id,
        source_link_id,
        current_user_id=current_user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="compilation_source_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="deleted"))


@router.get("/pages/{page_id}/links", response_model=ApiResponse[list[dict]])
def list_links(project_id: int, kb_id: int, page_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeCompilationService(db).list_links(project_id, kb_id, page_id))


@router.post("/pages/{page_id}/links", response_model=ApiResponse[dict])
def add_link(
    project_id: int,
    kb_id: int,
    page_id: int,
    payload: CompilationLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).add_link(
        project_id,
        kb_id,
        page_id,
        payload.model_dump(),
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="compilation_page_not_found")
    return ApiResponse(data=data)


@router.delete("/pages/{page_id}/links/{link_id}", response_model=ApiResponse[SimpleMessage])
def delete_link(
    project_id: int,
    kb_id: int,
    page_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[SimpleMessage]:
    ok = KnowledgeCompilationService(db).delete_link(
        project_id,
        kb_id,
        page_id,
        link_id,
        current_user_id=current_user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="compilation_link_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="deleted"))


@router.post("/pages/{page_id}/runs", response_model=ApiResponse[dict])
def create_run(
    project_id: int,
    kb_id: int,
    page_id: int,
    payload: CompilationRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).create_run(
        project_id=project_id,
        kb_id=kb_id,
        page_id=page_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    return ApiResponse(data=data)


@router.get("/pages/{page_id}/runs", response_model=ApiResponse[list[dict]])
def list_runs(project_id: int, kb_id: int, page_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=KnowledgeCompilationService(db).list_runs(project_id, kb_id, page_id))


@router.get("/runs/{run_id}", response_model=ApiResponse[dict])
def get_run_detail(project_id: int, kb_id: int, run_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).get_run_detail(project_id, kb_id, run_id)
    if not data:
        raise HTTPException(status_code=404, detail="compilation_run_not_found")
    return ApiResponse(data=data)


@router.post("/health-runs", response_model=ApiResponse[dict])
def create_health_run(
    project_id: int,
    kb_id: int,
    payload: CompilationHealthRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).create_health_run(
        project_id=project_id,
        kb_id=kb_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    return ApiResponse(data=data)


@router.get("/health-runs/{run_id}", response_model=ApiResponse[dict])
def get_health_run_detail(project_id: int, kb_id: int, run_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).get_health_run_detail(project_id, kb_id, run_id)
    if not data:
        raise HTTPException(status_code=404, detail="compilation_health_run_not_found")
    return ApiResponse(data=data)


@router.get("/health-findings", response_model=ApiResponse[list[dict]])
def list_health_findings(
    project_id: int,
    kb_id: int,
    page_id: int | None = None,
    check_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    data = KnowledgeCompilationService(db).list_health_findings(
        project_id=project_id,
        kb_id=kb_id,
        page_id=page_id,
        check_type=check_type,
        severity=severity,
        status=status,
    )
    return ApiResponse(data=data)


@router.put("/health-findings/{finding_id}", response_model=ApiResponse[dict])
def update_health_finding(
    project_id: int,
    kb_id: int,
    finding_id: int,
    payload: CompilationHealthFindingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).update_health_finding(
        project_id=project_id,
        kb_id=kb_id,
        finding_id=finding_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="compilation_health_finding_not_found")
    return ApiResponse(data=data)


@router.post("/writeback-candidates", response_model=ApiResponse[dict])
def create_writeback_candidate(
    project_id: int,
    kb_id: int,
    payload: CompilationWritebackCandidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).create_writeback_candidate(
        project_id=project_id,
        kb_id=kb_id,
        payload=payload.model_dump(),
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="writeback_source_not_found")
    return ApiResponse(data=data)


@router.get("/writeback-candidates", response_model=ApiResponse[list[dict]])
def list_writeback_candidates(
    project_id: int,
    kb_id: int,
    status: str | None = None,
    suggested_page_id: int | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    data = KnowledgeCompilationService(db).list_writeback_candidates(
        project_id=project_id,
        kb_id=kb_id,
        status=status,
        suggested_page_id=suggested_page_id,
    )
    return ApiResponse(data=data)


@router.post("/writeback-candidates/{candidate_id}/merge", response_model=ApiResponse[dict])
def merge_writeback_candidate(
    project_id: int,
    kb_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).merge_writeback_candidate(
        project_id=project_id,
        kb_id=kb_id,
        candidate_id=candidate_id,
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="writeback_candidate_not_found")
    return ApiResponse(data=data)


@router.post("/writeback-candidates/{candidate_id}/reject", response_model=ApiResponse[dict])
def reject_writeback_candidate(
    project_id: int,
    kb_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = KnowledgeCompilationService(db).reject_writeback_candidate(
        project_id=project_id,
        kb_id=kb_id,
        candidate_id=candidate_id,
        current_user_id=current_user.id,
    )
    if not data:
        raise HTTPException(status_code=404, detail="writeback_candidate_not_found")
    return ApiResponse(data=data)

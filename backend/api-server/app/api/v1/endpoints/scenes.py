from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.project_service import ProjectService
from app.services.scenes.service import SceneService

router = APIRouter()


class SceneStartRequest(BaseModel):
    scene_key: str = "hk_tax_address_change"
    route_key: str | None = None
    session_id: str | None = None
    source: str = "openclaw"
    initial_query: str | None = None
    selected_kb_ids: list[int] = Field(default_factory=list)
    switches: dict[str, Any] = Field(default_factory=dict)
    resume_if_exists: bool = True


class ScenePayloadPatchRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "openclaw"
    merge_mode: str = "merge"


class SceneFieldUpdateRequest(BaseModel):
    value: Any = None
    source: str = "openclaw"


class SceneActionRequest(BaseModel):
    confirmation_token: str | None = None


class SceneRecoverRequest(BaseModel):
    strategy: str | None = "auto"
    source: str = "openclaw"


@router.post("/start", response_model=ApiResponse[dict])
def start_scene(project_id: int, payload: SceneStartRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    data = SceneService(db).start_case(
        project_id=project_id,
        project_context=project_context,
        scene_key=payload.scene_key,
        route_key=payload.route_key,
        session_code=payload.session_id,
        source=payload.source,
        initial_query=payload.initial_query,
        selected_kb_ids=payload.selected_kb_ids,
        switches=payload.switches,
        resume_if_exists=payload.resume_if_exists,
    )
    return ApiResponse(data=data)


@router.get("/{case_id}", response_model=ApiResponse[dict])
def get_scene(project_id: int, case_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(data=SceneService(db).get_case_detail(project_id, case_id, project_context))


@router.get("/{case_id}/fields", response_model=ApiResponse[dict])
def get_scene_fields(project_id: int, case_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=SceneService(db).get_field_status(project_id, case_id))


@router.get("/{case_id}/next-actions", response_model=ApiResponse[dict])
def get_scene_next_actions(project_id: int, case_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(data=SceneService(db).get_next_actions(project_id, case_id, project_context))


@router.patch("/{case_id}/payload", response_model=ApiResponse[dict])
def patch_scene_payload(
    project_id: int,
    case_id: str,
    payload: ScenePayloadPatchRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(
        data=SceneService(db).merge_payload(
            project_id=project_id,
            case_id=case_id,
            payload_patch=payload.payload,
            project_context=project_context,
            source=payload.source,
        )
    )


@router.patch("/{case_id}/fields/{field_name}", response_model=ApiResponse[dict])
def update_scene_field(
    project_id: int,
    case_id: str,
    field_name: str,
    payload: SceneFieldUpdateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(
        data=SceneService(db).update_field(
            project_id=project_id,
            case_id=case_id,
            field_name=field_name,
            value=payload.value,
            project_context=project_context,
            source=payload.source,
        )
    )


@router.post("/{case_id}/actions/{action_name}", response_model=ApiResponse[dict])
def execute_action(
    project_id: int,
    case_id: str,
    action_name: str,
    payload: SceneActionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(
        data=SceneService(db).execute_action(
            project_id,
            case_id,
            action_name,
            project_context,
            confirmation_token=payload.confirmation_token if payload else None,
        )
    )


@router.post("/{case_id}/recover", response_model=ApiResponse[dict])
def recover_scene(
    project_id: int,
    case_id: str,
    payload: SceneRecoverRequest | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    project_context = ProjectService(db).get_active_project_context(project_id)
    return ApiResponse(
        data=SceneService(db).recover_case(
            project_id=project_id,
            case_id=case_id,
            project_context=project_context,
            strategy=payload.strategy if payload else "auto",
            source=payload.source if payload else "openclaw",
        )
    )


@router.get("/{case_id}/artifacts/{artifact_key}")
def get_artifact(project_id: int, case_id: str, artifact_key: str, db: Session = Depends(get_db)):
    return SceneService(db).serve_artifact(project_id, case_id, artifact_key)

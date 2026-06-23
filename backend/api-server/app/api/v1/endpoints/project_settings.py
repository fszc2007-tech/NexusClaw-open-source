from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.project_service import ProjectService

router = APIRouter()


class OpeningSettingsRequest(BaseModel):
    mode: str = "card"
    opening_text: str | None = None
    recommended_questions: list[str] = Field(default_factory=list)
    hot_questions: list[str] = Field(default_factory=list)
    hot_policies: list[str] = Field(default_factory=list)
    enabled: bool = True


class PromptSettingsRequest(BaseModel):
    prompt_template: str


class MemorySettingsRequest(BaseModel):
    capability_memory: bool = True
    memory_scope: Literal["off", "session_only"] = "session_only"
    memory_ttl_days: int = Field(default=7, ge=1, le=365)
    preference_memory_enabled: bool = False
    enabled_scene_keys_json: list[str] = Field(default_factory=list)
    scene_entry_mode: str = "chat"
    scene_runtime_config_json: dict = Field(default_factory=dict)


class KnowledgeCompilationSettingsRequest(BaseModel):
    capability_knowledge_compilation: bool = False
    compilation_strategy: Literal["compiled_first", "raw_first", "hybrid", "disabled"] = "compiled_first"
    compilation_min_score: float = Field(default=0.82, ge=0.0, le=1.0)
    compilation_min_supporting_source_count: int = Field(default=2, ge=1, le=20)
    compilation_allow_with_warning: bool = False


@router.get("/opening", response_model=ApiResponse[dict])
def get_opening(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).get_opening_settings(project_id))


@router.put("/opening", response_model=ApiResponse[dict])
def update_opening(
    project_id: int,
    payload: OpeningSettingsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).update_opening_settings(project_id, payload.model_dump()))


@router.get("/prompt", response_model=ApiResponse[dict])
def get_prompt(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).get_prompt_settings(project_id))


@router.put("/prompt", response_model=ApiResponse[dict])
def update_prompt(
    project_id: int,
    payload: PromptSettingsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).update_prompt_settings(project_id, payload.model_dump()))


@router.get("/memory", response_model=ApiResponse[dict])
def get_memory(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).get_memory_settings(project_id))


@router.put("/memory", response_model=ApiResponse[dict])
def update_memory(
    project_id: int,
    payload: MemorySettingsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).update_memory_settings(project_id, payload.model_dump()))


@router.get("/knowledge-compilation", response_model=ApiResponse[dict])
def get_knowledge_compilation(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).get_knowledge_compilation_settings(project_id))


@router.put("/knowledge-compilation", response_model=ApiResponse[dict])
def update_knowledge_compilation(
    project_id: int,
    payload: KnowledgeCompilationSettingsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=ProjectService(db).update_knowledge_compilation_settings(project_id, payload.model_dump()))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_project_admin, require_project_member, require_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.project_service import ProjectService

router = APIRouter()


class ProjectCapabilityPayload(BaseModel):
    multi_turn: bool = True
    memory: bool = True
    sensitive_detection: bool = True
    gov_domain_check: bool = True
    knowledge_tree: bool = False


class ProjectUpsertRequest(BaseModel):
    project_key: str | None = None
    company_name: str
    description: str | None = None
    logo_url: str | None = None
    status: str = "active"
    capabilities: ProjectCapabilityPayload = Field(default_factory=ProjectCapabilityPayload)


@router.get("", response_model=ApiResponse[list[dict]])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ProjectService(db).list_projects(current_user=current_user))


@router.post("", response_model=ApiResponse[dict])
def create_project(
    payload: ProjectUpsertRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> ApiResponse[dict]:
    if not payload.project_key:
        raise HTTPException(status_code=400, detail="project_key_required")
    return ApiResponse(data=ProjectService(db).create_project(payload.model_dump()))


@router.get("/{project_id}", response_model=ApiResponse[dict])
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_member),
) -> ApiResponse[dict]:
    data = ProjectService(db).get_project(project_id)
    if not data:
        raise HTTPException(status_code=404, detail="project_not_found")
    return ApiResponse(data=data)


@router.put("/{project_id}", response_model=ApiResponse[dict])
def update_project(
    project_id: int,
    payload: ProjectUpsertRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = ProjectService(db).update_project(project_id, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail="project_not_found")
    return ApiResponse(data=data)

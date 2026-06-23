from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse, SimpleMessage
from app.services.project_member_service import ProjectMemberService

router = APIRouter()


class ProjectMembersCreateRequest(BaseModel):
    user_ids: list[int] = Field(default_factory=list)
    usernames: list[str] = Field(default_factory=list)
    project_role: str = "project_member"


class ProjectMemberUpdateRequest(BaseModel):
    project_role: str


@router.get("", response_model=ApiResponse[list[dict]])
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ProjectMemberService(db).list_members(project_id))


@router.post("", response_model=ApiResponse[list[dict]])
def create_members(
    project_id: int,
    payload: ProjectMembersCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=ProjectMemberService(db).add_members(project_id, payload.model_dump()))


@router.put("/{member_id}", response_model=ApiResponse[dict])
def update_member(
    project_id: int,
    member_id: int,
    payload: ProjectMemberUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = ProjectMemberService(db).update_member(project_id, member_id, payload.model_dump())
    if not data:
        raise HTTPException(status_code=404, detail="project_member_not_found")
    return ApiResponse(data=data)


@router.delete("/{member_id}", response_model=ApiResponse[SimpleMessage])
def delete_member(
    project_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[SimpleMessage]:
    deleted = ProjectMemberService(db).delete_member(project_id, member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="project_member_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="project_member_deleted"))

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_super_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse, SimpleMessage
from app.services.user_service import UserService

router = APIRouter()


class UserCreateRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    nickname: str | None = None
    profile: str | None = None
    system_role: str = "normal_user"
    status: str = "active"


class UserUpdateRequest(BaseModel):
    username: str | None = None
    password: str | None = Field(default=None, min_length=8)
    nickname: str | None = None
    profile: str | None = None
    system_role: str | None = None
    status: str | None = None


@router.get("", response_model=ApiResponse[list[dict]])
def list_users(
    username: str | None = Query(default=None),
    system_role: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> ApiResponse[list[dict]]:
    return ApiResponse(data=UserService(db).list_users(username=username, system_role=system_role))


@router.post("", response_model=ApiResponse[dict])
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> ApiResponse[dict]:
    return ApiResponse(data=UserService(db).create_user(payload.model_dump()))


@router.get("/{user_id}", response_model=ApiResponse[dict])
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)) -> ApiResponse[dict]:
    data = UserService(db).get_user(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="user_not_found")
    return ApiResponse(data=data)


@router.put("/{user_id}", response_model=ApiResponse[dict])
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> ApiResponse[dict]:
    data = UserService(db).update_user(user_id, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail="user_not_found")
    return ApiResponse(data=data)


@router.delete("/{user_id}", response_model=ApiResponse[SimpleMessage])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_super_admin),
) -> ApiResponse[SimpleMessage]:
    deleted = UserService(db).delete_user(user_id, acting_user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="user_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="user_deleted"))

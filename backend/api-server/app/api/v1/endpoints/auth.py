from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=ApiResponse[dict])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=AuthService(db).login(payload.username, payload.password))


@router.get("/me", response_model=ApiResponse[dict])
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=AuthService(db).get_current_user_payload(current_user))


@router.post("/logout", response_model=ApiResponse[dict])
def logout(
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    token = authorization.partition(" ")[2].strip() if authorization else ""
    AuthService(db).logout(current_user.id, token)
    return ApiResponse(data={"success": True})

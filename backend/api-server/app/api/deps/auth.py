from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.access_service import AccessService
from app.services.auth_service import AuthService


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authorization")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    return AuthService(db).get_user_by_access_token(token)


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.system_role != "super_admin":
        raise HTTPException(status_code=403, detail="forbidden")
    return current_user


def require_project_member(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if AccessService(db).can_access_project(current_user, project_id):
        return current_user
    raise HTTPException(status_code=403, detail="forbidden")


def require_project_admin(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if AccessService(db).can_manage_project(current_user, project_id):
        return current_user
    raise HTTPException(status_code=403, detail="forbidden")

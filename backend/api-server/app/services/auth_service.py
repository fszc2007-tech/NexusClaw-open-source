from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_session_token, digest_token, hash_password, verify_password
from app.models.project import ProjectMember
from app.models.user import User, UserSession


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, username: str, password: str) -> dict:
        self.ensure_seed_admin()
        user = self.db.query(User).filter(User.username == username).first()
        if not user or user.status != "active" or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid_credentials")

        token = create_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=settings.AUTH_TOKEN_EXPIRE_HOURS)
        session = UserSession(
            user_id=user.id,
            access_token=digest_token(token),
            expires_at=expires_at,
            status="active",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.AUTH_TOKEN_EXPIRE_HOURS * 3600,
            "user": self.serialize_user(user),
        }

    def logout(self, user_id: int, token: str) -> None:
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.access_token == digest_token(token),
                UserSession.status == "active",
            )
            .first()
        )
        if not session:
            return
        session.status = "revoked"
        self.db.commit()

    def get_user_by_access_token(self, token: str) -> User:
        now = datetime.utcnow()
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.access_token == digest_token(token),
                UserSession.status == "active",
                UserSession.expires_at > now,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=401, detail="invalid_or_expired_token")

        user = self.db.query(User).filter(User.id == session.user_id).first()
        if not user or user.status != "active":
            raise HTTPException(status_code=401, detail="invalid_or_expired_token")
        return user

    def get_current_user_payload(self, user: User) -> dict:
        memberships = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.user_id == user.id)
            .order_by(ProjectMember.project_id.asc(), ProjectMember.id.asc())
            .all()
        )
        return {
            **self.serialize_user(user),
            "project_memberships": [
                {
                    "id": item.id,
                    "project_id": item.project_id,
                    "project_role": item.project_role,
                }
                for item in memberships
            ],
        }

    def ensure_seed_admin(self) -> None:
        has_any_user = self.db.query(User.id).first()
        if has_any_user:
            return

        admin = User(
            username=settings.AUTH_SEED_ADMIN_USERNAME,
            password_hash=hash_password(settings.AUTH_SEED_ADMIN_PASSWORD),
            nickname=settings.AUTH_SEED_ADMIN_NICKNAME,
            profile="系统初始化管理员",
            system_role="super_admin",
            status="active",
        )
        self.db.add(admin)
        self.db.commit()

    def serialize_user(self, user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "profile": user.profile,
            "system_role": user.system_role,
            "status": user.status,
        }

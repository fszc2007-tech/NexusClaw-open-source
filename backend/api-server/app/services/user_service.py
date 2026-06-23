from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.project import ProjectMember
from app.models.user import User, UserSession


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self, username: str | None = None, system_role: str | None = None) -> list[dict]:
        query = self.db.query(User)
        if username:
            query = query.filter(User.username.like(f"%{username}%"))
        if system_role:
            query = query.filter(User.system_role == system_role)
        return [self.serialize_user(item) for item in query.order_by(User.id.desc()).all()]

    def get_user(self, user_id: int) -> dict | None:
        user = self.db.query(User).filter(User.id == user_id).first()
        return self.serialize_user(user) if user else None

    def create_user(self, payload: dict) -> dict:
        existing = self.db.query(User).filter(User.username == payload["username"]).first()
        if existing:
            raise HTTPException(status_code=409, detail="username_already_exists")

        user = User(
            username=payload["username"],
            password_hash=hash_password(payload["password"]),
            nickname=payload.get("nickname") or payload["username"],
            profile=payload.get("profile"),
            system_role=payload.get("system_role", "normal_user"),
            status=payload.get("status", "active"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self.serialize_user(user)

    def update_user(self, user_id: int, payload: dict) -> dict | None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        next_username = payload.get("username", user.username)
        if next_username != user.username:
            duplicate = self.db.query(User).filter(User.username == next_username, User.id != user_id).first()
            if duplicate:
                raise HTTPException(status_code=409, detail="username_already_exists")
            user.username = next_username

        if payload.get("password"):
            user.password_hash = hash_password(payload["password"])

        user.nickname = payload.get("nickname", user.nickname)
        user.profile = payload.get("profile", user.profile)
        user.system_role = payload.get("system_role", user.system_role)
        user.status = payload.get("status", user.status)
        self.db.commit()
        self.db.refresh(user)
        return self.serialize_user(user)

    def delete_user(self, user_id: int, acting_user_id: int) -> bool:
        if user_id == acting_user_id:
            raise HTTPException(status_code=400, detail="cannot_delete_self")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        self.db.query(UserSession).filter(UserSession.user_id == user_id).delete()
        self.db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()
        self.db.delete(user)
        self.db.commit()
        return True

    def serialize_user(self, user: User | None) -> dict | None:
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "profile": user.profile,
            "system_role": user.system_role,
            "status": user.status,
        }

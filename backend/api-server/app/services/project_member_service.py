from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project import ProjectMember
from app.models.user import User


class ProjectMemberService:
    MAX_PROJECT_ADMINS = 5

    def __init__(self, db: Session):
        self.db = db

    def list_members(self, project_id: int) -> list[dict]:
        rows = (
            self.db.query(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .filter(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.id.asc())
            .all()
        )
        return [self._serialize_member(member, user) for member, user in rows]

    def add_members(self, project_id: int, payload: dict) -> list[dict]:
        user_ids = list(payload.get("user_ids") or [])
        usernames = [item.strip() for item in payload.get("usernames") or [] if item and item.strip()]
        project_role = payload.get("project_role", "project_member")

        if usernames:
            matched_users = self.db.query(User).filter(User.username.in_(usernames)).all()
            missing = sorted(set(usernames) - {item.username for item in matched_users})
            if missing:
                raise HTTPException(status_code=404, detail=f"user_not_found:{','.join(missing)}")
            user_ids.extend(item.id for item in matched_users)

        unique_user_ids = sorted({int(item) for item in user_ids})
        if not unique_user_ids:
            raise HTTPException(status_code=400, detail="member_targets_required")

        existing_members = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id.in_(unique_user_ids))
            .all()
        )
        if existing_members:
            raise HTTPException(status_code=409, detail="project_member_already_exists")

        users = self.db.query(User).filter(User.id.in_(unique_user_ids)).all()
        if len(users) != len(unique_user_ids):
            raise HTTPException(status_code=404, detail="user_not_found")

        if project_role == "project_admin":
            self._ensure_project_admin_capacity(project_id, len(unique_user_ids))

        created: list[ProjectMember] = []
        for user in users:
            member = ProjectMember(project_id=project_id, user_id=user.id, project_role=project_role)
            self.db.add(member)
            created.append(member)

        self.db.commit()
        return self.list_members(project_id)

    def update_member(self, project_id: int, member_id: int, payload: dict) -> dict | None:
        member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.id == member_id, ProjectMember.project_id == project_id)
            .first()
        )
        if not member:
            return None

        next_role = payload.get("project_role", member.project_role)
        if next_role == "project_admin" and member.project_role != "project_admin":
            self._ensure_project_admin_capacity(project_id, 1)
        member.project_role = next_role
        self.db.commit()

        user = self.db.query(User).filter(User.id == member.user_id).first()
        return self._serialize_member(member, user) if user else None

    def delete_member(self, project_id: int, member_id: int) -> bool:
        member = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.id == member_id, ProjectMember.project_id == project_id)
            .first()
        )
        if not member:
            return False
        self.db.delete(member)
        self.db.commit()
        return True

    def _ensure_project_admin_capacity(self, project_id: int, incoming_count: int) -> None:
        current_admins = (
            self.db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.project_role == "project_admin")
            .count()
        )
        if current_admins + incoming_count > self.MAX_PROJECT_ADMINS:
            raise HTTPException(status_code=400, detail="project_admin_limit_exceeded")

    def _serialize_member(self, member: ProjectMember, user: User) -> dict:
        return {
            "id": member.id,
            "project_id": member.project_id,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "status": user.status,
            "project_role": member.project_role,
            "system_role": user.system_role,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        }

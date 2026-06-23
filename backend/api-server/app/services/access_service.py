from sqlalchemy.orm import Session

from app.models.project import ProjectMember
from app.models.user import User


class AccessService:
    def __init__(self, db: Session):
        self.db = db

    def is_super_admin(self, user: User) -> bool:
        return user.system_role == "super_admin"

    def get_project_membership(self, user_id: int, project_id: int) -> ProjectMember | None:
        return (
            self.db.query(ProjectMember)
            .filter(ProjectMember.user_id == user_id, ProjectMember.project_id == project_id)
            .first()
        )

    def can_access_project(self, user: User, project_id: int) -> bool:
        if self.is_super_admin(user):
            return True
        return self.get_project_membership(user.id, project_id) is not None

    def can_manage_project(self, user: User, project_id: int) -> bool:
        if self.is_super_admin(user):
            return True
        membership = self.get_project_membership(user.id, project_id)
        return membership is not None and membership.project_role == "project_admin"

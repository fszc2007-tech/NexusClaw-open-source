from sqlalchemy.orm import Session

from app.models.project import Project, ProjectPersona


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_projects(self) -> list[Project]:
        return self.db.query(Project).order_by(Project.id.desc()).all()

    def get_project(self, project_id: int) -> Project | None:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_persona(self, project_id: int) -> ProjectPersona | None:
        return self.db.query(ProjectPersona).filter(ProjectPersona.project_id == project_id).first()

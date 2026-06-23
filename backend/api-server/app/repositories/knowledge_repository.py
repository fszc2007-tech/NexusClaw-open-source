from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge, KnowledgeDedupRecord


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_project(self, project_id: int) -> list[Knowledge]:
        return self.db.query(Knowledge).filter(Knowledge.project_id == project_id).order_by(Knowledge.id.desc()).all()

    def get(self, knowledge_id: int) -> Knowledge | None:
        return self.db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()

    def list_dedup_records(self, project_id: int) -> list[KnowledgeDedupRecord]:
        return (
            self.db.query(KnowledgeDedupRecord)
            .filter(KnowledgeDedupRecord.project_id == project_id)
            .order_by(KnowledgeDedupRecord.id.desc())
            .all()
        )

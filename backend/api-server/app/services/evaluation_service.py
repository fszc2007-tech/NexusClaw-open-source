from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationDataset, EvaluationDatasetItem


class EvaluationService:
    def __init__(self, db: Session):
        self.db = db

    def list_datasets(self, project_id: int) -> list[dict]:
        rows = (
            self.db.query(
                EvaluationDataset,
                func.count(EvaluationDatasetItem.id).label("item_count"),
            )
            .outerjoin(EvaluationDatasetItem, EvaluationDatasetItem.dataset_id == EvaluationDataset.id)
            .filter(EvaluationDataset.project_id == project_id)
            .group_by(EvaluationDataset.id)
            .order_by(EvaluationDataset.id.desc())
            .all()
        )
        return [self._serialize_dataset(dataset, int(item_count or 0)) for dataset, item_count in rows]

    def create_dataset(self, project_id: int, payload: dict) -> dict:
        dataset = EvaluationDataset(
            project_id=project_id,
            name=payload["name"],
            description=payload.get("description"),
            status=payload.get("status", "active"),
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return self._serialize_dataset(dataset, 0)

    def update_dataset(self, project_id: int, dataset_id: int, payload: dict) -> dict | None:
        dataset = (
            self.db.query(EvaluationDataset)
            .filter(EvaluationDataset.project_id == project_id, EvaluationDataset.id == dataset_id)
            .first()
        )
        if not dataset:
            return None
        dataset.name = payload.get("name", dataset.name)
        dataset.description = payload.get("description", dataset.description)
        dataset.status = payload.get("status", dataset.status)
        self.db.commit()
        self.db.refresh(dataset)
        item_count = (
            self.db.query(func.count(EvaluationDatasetItem.id))
            .filter(EvaluationDatasetItem.dataset_id == dataset.id)
            .scalar()
        )
        return self._serialize_dataset(dataset, int(item_count or 0))

    def delete_dataset(self, project_id: int, dataset_id: int) -> bool:
        dataset = (
            self.db.query(EvaluationDataset)
            .filter(EvaluationDataset.project_id == project_id, EvaluationDataset.id == dataset_id)
            .first()
        )
        if not dataset:
            return False
        (
            self.db.query(EvaluationDatasetItem)
            .filter(EvaluationDatasetItem.dataset_id == dataset.id)
            .delete(synchronize_session=False)
        )
        self.db.delete(dataset)
        self.db.commit()
        return True

    def list_dataset_items(self, project_id: int, dataset_id: int) -> list[dict]:
        dataset = (
            self.db.query(EvaluationDataset)
            .filter(EvaluationDataset.project_id == project_id, EvaluationDataset.id == dataset_id)
            .first()
        )
        if not dataset:
            return []
        items = (
            self.db.query(EvaluationDatasetItem)
            .filter(EvaluationDatasetItem.dataset_id == dataset_id)
            .order_by(EvaluationDatasetItem.id.desc())
            .all()
        )
        return [self._serialize_item(item) for item in items]

    def create_dataset_item(self, project_id: int, dataset_id: int, payload: dict) -> dict | None:
        dataset = (
            self.db.query(EvaluationDataset)
            .filter(EvaluationDataset.project_id == project_id, EvaluationDataset.id == dataset_id)
            .first()
        )
        if not dataset:
            return None
        item = EvaluationDatasetItem(
            dataset_id=dataset_id,
            query=payload["query"],
            ref_answer=payload.get("ref_answer"),
            expected_knowledge_ids=payload.get("expected_knowledge_ids"),
            tags=payload.get("tags"),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_item(item)

    def _serialize_dataset(self, dataset: EvaluationDataset, item_count: int) -> dict:
        return {
            "id": dataset.id,
            "project_id": dataset.project_id,
            "name": dataset.name,
            "description": dataset.description,
            "status": dataset.status,
            "item_count": item_count,
            "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
        }

    def _serialize_item(self, item: EvaluationDatasetItem) -> dict:
        return {
            "id": item.id,
            "dataset_id": item.dataset_id,
            "query": item.query,
            "ref_answer": item.ref_answer,
            "expected_knowledge_ids": item.expected_knowledge_ids,
            "tags": item.tags,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

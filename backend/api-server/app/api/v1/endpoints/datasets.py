from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, SimpleMessage
from app.services.evaluation_service import EvaluationService

router = APIRouter()


class DatasetRequest(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"


class DatasetItemRequest(BaseModel):
    query: str
    ref_answer: str | None = None
    expected_knowledge_ids: str | None = None
    tags: str | None = None


@router.get("", response_model=ApiResponse[list[dict]])
def list_datasets(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=EvaluationService(db).list_datasets(project_id))


@router.post("", response_model=ApiResponse[dict])
def create_dataset(project_id: int, payload: DatasetRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    return ApiResponse(data=EvaluationService(db).create_dataset(project_id, payload.model_dump()))


@router.put("/{dataset_id}", response_model=ApiResponse[dict])
def update_dataset(project_id: int, dataset_id: int, payload: DatasetRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = EvaluationService(db).update_dataset(project_id, dataset_id, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    return ApiResponse(data=data)


@router.delete("/{dataset_id}", response_model=ApiResponse[SimpleMessage])
def delete_dataset(project_id: int, dataset_id: int, db: Session = Depends(get_db)) -> ApiResponse[SimpleMessage]:
    deleted = EvaluationService(db).delete_dataset(project_id, dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    return ApiResponse(data=SimpleMessage(success=True, detail="dataset_deleted"))


@router.get("/{dataset_id}/items", response_model=ApiResponse[list[dict]])
def list_dataset_items(project_id: int, dataset_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=EvaluationService(db).list_dataset_items(project_id, dataset_id))


@router.post("/{dataset_id}/items", response_model=ApiResponse[dict])
def create_dataset_item(
    project_id: int,
    dataset_id: int,
    payload: DatasetItemRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    data = EvaluationService(db).create_dataset_item(project_id, dataset_id, payload.model_dump())
    if not data:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    return ApiResponse(data=data)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.project_service import ProjectService

router = APIRouter()


@router.get("", response_model=ApiResponse[list[dict]])
def list_projects(db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    service = ProjectService(db)
    return ApiResponse(data=service.list_projects())


@router.get("/{project_id}", response_model=ApiResponse[dict])
def get_project(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    service = ProjectService(db)
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ApiResponse(data=project)


@router.get("/{project_id}/persona", response_model=ApiResponse[dict])
def get_project_persona(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    service = ProjectService(db)
    persona = service.get_persona(project_id)
    if not persona:
        raise HTTPException(status_code=404, detail="project persona not found")
    return ApiResponse(data=persona)

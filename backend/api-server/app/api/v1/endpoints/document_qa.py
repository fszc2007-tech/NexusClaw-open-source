from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.document_qa_service import DocumentQaService

router = APIRouter()


class DocumentQaAskRequest(BaseModel):
    file_id: int
    query: str


@router.get("/files", response_model=ApiResponse[list[dict]])
def list_files(project_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    try:
        data = DocumentQaService(db).list_files(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.post("/files/upload", response_model=ApiResponse[dict])
async def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    overwrite_same_name: bool = Form(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    try:
        data = await DocumentQaService(db).upload_file(project_id, file, overwrite_same_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.get("/files/{file_id}/preview", response_model=ApiResponse[dict])
def get_preview(project_id: int, file_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    try:
        data = DocumentQaService(db).get_preview(project_id, file_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not data:
        raise HTTPException(status_code=404, detail="file_not_found")
    return ApiResponse(data=data)


@router.post("/ask", response_model=ApiResponse[dict])
def ask(project_id: int, payload: DocumentQaAskRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    try:
        data = DocumentQaService(db).ask(project_id, payload.file_id, payload.query)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"project_not_found", "file_not_found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return ApiResponse(data=data)

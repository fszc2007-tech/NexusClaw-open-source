from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth import require_project_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.file_service import FileService

router = APIRouter()


class FileImportRequest(BaseModel):
    chunk_size: int = 500
    generate_qa: bool = False
    import_mode: str = "default"
    table_schema_hint: str | None = None


class FileQaGenerateRequest(BaseModel):
    chunk_size: int = 700
    max_pairs: int = 12


@router.get("", response_model=ApiResponse[list[dict]])
def list_files(project_id: int, kb_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    return ApiResponse(data=FileService(db).list_files(project_id, kb_id))


@router.post("", response_model=ApiResponse[dict])
async def upload_file(
    project_id: int,
    kb_id: int,
    background_tasks: BackgroundTasks,
    upload: UploadFile = File(...),
    overwrite_same_name: bool = Form(default=False),
    auto_process: bool = Form(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    service = FileService(db)
    data = await service.upload_file(
        project_id=project_id,
        kb_id=kb_id,
        upload=upload,
        overwrite_same_name=overwrite_same_name,
        created_by=current_user.id,
    )
    if auto_process and data.get("parse_status") == "success":
        prepared = service.prepare_auto_process(
            project_id=project_id,
            kb_id=kb_id,
            file_id=int(data["id"]),
            created_by=current_user.id,
        )
        if prepared:
            data = prepared
        background_tasks.add_task(
            FileService.run_auto_process_in_background,
            project_id=project_id,
            kb_id=kb_id,
            file_id=int(data["id"]),
            created_by=current_user.id,
        )
    return ApiResponse(data=data)


@router.get("/{file_id}/preview", response_model=ApiResponse[dict])
def get_preview(project_id: int, kb_id: int, file_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    data = FileService(db).get_file_preview(project_id, kb_id, file_id)
    if not data:
        raise HTTPException(status_code=404, detail="file_not_found")
    return ApiResponse(data=data)


@router.post("/{file_id}/import", response_model=ApiResponse[dict])
def import_file(
    project_id: int,
    kb_id: int,
    file_id: int,
    payload: FileImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = FileService(db).import_file(
        project_id,
        kb_id,
        file_id,
        chunk_size=payload.chunk_size,
        generate_qa=payload.generate_qa,
        import_mode=payload.import_mode,
        table_schema_hint=payload.table_schema_hint,
    )
    if not data:
        raise HTTPException(status_code=404, detail="file_not_found")
    return ApiResponse(data=data)


@router.post("/{file_id}/generate-qa", response_model=ApiResponse[dict])
def generate_qa(
    project_id: int,
    kb_id: int,
    file_id: int,
    payload: FileQaGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = FileService(db).generate_qa(project_id, kb_id, file_id, chunk_size=payload.chunk_size, max_pairs=payload.max_pairs)
    if not data:
        raise HTTPException(status_code=404, detail="file_not_found")
    return ApiResponse(data=data)


@router.delete("/{file_id}", response_model=ApiResponse[dict])
def delete_file(
    project_id: int,
    kb_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_project_admin),
) -> ApiResponse[dict]:
    data = FileService(db).delete_file(project_id, kb_id, file_id)
    if not data:
        raise HTTPException(status_code=404, detail="file_not_found")
    return ApiResponse(data=data)

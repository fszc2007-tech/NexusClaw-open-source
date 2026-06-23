from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.services.deepseek_service import DeepSeekService
from app.services.knowledge_compilation_service import KnowledgeCompilationService
from app.services.project_service import ProjectService
from app.services.retrieval_service import RetrievalService

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    selected_kb_ids: list[int] = Field(default_factory=list)


@router.post("", response_model=ApiResponse[dict])
def search(project_id: int, payload: SearchRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    deepseek_service = DeepSeekService()
    rewritten_query = deepseek_service.rewrite_query(payload.query, [])
    project_context = ProjectService(db).get_active_project_context(project_id)
    hits = RetrievalService(db).retrieve(
        project_id=project_id,
        query=rewritten_query,
        selected_kb_ids=payload.selected_kb_ids,
    )
    compilation = KnowledgeCompilationService(db).build_chat_compilation_context(
        project_id=project_id,
        kb_ids=payload.selected_kb_ids or None,
        query=rewritten_query,
        settings=project_context.get("settings") or {},
        switches={
            "knowledge_compilation": True,
            "compilation_strategy": (project_context.get("settings") or {}).get("compilation_strategy", "compiled_first"),
        },
    )
    return ApiResponse(
        data={
            "query": payload.query,
            "rewritten_query": rewritten_query,
            "hits": hits,
            "total": len(hits),
            "compilation": {
                "enabled": bool(compilation.get("enabled")),
                "usable": bool(compilation.get("usable")),
                "strategy": compilation.get("strategy"),
                "selected_mode": compilation.get("selected_mode"),
                "fallback_reason": compilation.get("fallback_reason"),
                "page_hits": compilation.get("page_hits") or [],
                "reference_items": compilation.get("reference_items") or [],
                "raw_sources": compilation.get("raw_sources") or [],
            },
        }
    )

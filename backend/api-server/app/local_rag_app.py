from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.services.local_rag_service import LocalRagService, LocalVectorDocument


class VectorDocumentPayload(BaseModel):
    document_id: str | None = None
    document_kind: str = "knowledge_item"
    knowledge_id: int | None = None
    chunk_id: int | None = None
    project_id: int
    kb_id: int
    title: str
    content: str
    document_name: str | None = None
    source_type: str | None = None
    metadata: dict = Field(default_factory=dict)


class VectorUpsertRequest(BaseModel):
    documents: list[VectorDocumentPayload] = Field(default_factory=list)


class VectorDeleteRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[int] = Field(default_factory=list)


class VectorSearchRequest(BaseModel):
    query: str
    project_id: int
    kb_ids: list[int] = Field(default_factory=list)
    top_k: int = 10
    document_kind: str | None = None


class RerankDocumentPayload(BaseModel):
    document_id: str | None = None
    knowledge_id: int | None = None
    chunk_id: int | None = None
    title: str = ""
    content: str = ""
    score: float | None = None


class RerankRequest(BaseModel):
    query: str
    documents: list[RerankDocumentPayload] = Field(default_factory=list)


def create_app() -> FastAPI:
    app = FastAPI(
        title="nexusclaw-local-rag",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    service = LocalRagService()

    @app.get("/health")
    def healthcheck() -> dict:
        runtime = service.runtime_status()
        return {
            "status": "ok",
            "service": "nexusclaw-local-rag",
            "embedding_provider": runtime["embedding_provider"],
            "embedding_device": runtime["embedding_device_resolved"],
            "embedding_model": runtime["embedding_model"],
            "rerank_provider": runtime["rerank_provider"],
            "rerank_device": runtime["rerank_device_resolved"],
            "rerank_model": runtime["rerank_model"],
            "runtime": runtime,
        }

    @app.post("/warmup")
    def warmup() -> dict:
        return {"code": 0, "message": "ok", "data": service.warmup()}

    @app.post("/vector/upsert")
    def upsert_vectors(payload: VectorUpsertRequest) -> dict:
        data = service.upsert_documents(
            [
                LocalVectorDocument(
                    document_id=document.document_id,
                    document_kind=document.document_kind,
                    knowledge_id=document.knowledge_id,
                    chunk_id=document.chunk_id,
                    project_id=document.project_id,
                    kb_id=document.kb_id,
                    title=document.title,
                    content=document.content,
                    document_name=document.document_name,
                    source_type=document.source_type,
                    metadata=document.metadata,
                )
                for document in payload.documents
            ]
        )
        return {"code": 0, "message": "ok", "data": data}

    @app.post("/vector/delete")
    def delete_vectors(payload: VectorDeleteRequest) -> dict:
        return {
            "code": 0,
            "message": "ok",
            "data": service.delete_documents(
                document_ids=payload.document_ids,
                knowledge_ids=payload.knowledge_ids,
            ),
        }

    @app.post("/vector/search")
    def search_vectors(payload: VectorSearchRequest) -> dict:
        return {
            "code": 0,
            "message": "ok",
            "data": service.search(
                query=payload.query,
                project_id=payload.project_id,
                kb_ids=payload.kb_ids,
                top_k=payload.top_k,
                document_kind=payload.document_kind,
            ),
        }

    @app.post("/rerank")
    def rerank(payload: RerankRequest) -> dict:
        return {
            "code": 0,
            "message": "ok",
            "data": service.rerank(
                payload.query,
                [document.model_dump() for document in payload.documents],
            ),
        }

    return app


app = create_app()

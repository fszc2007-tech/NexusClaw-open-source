import logging
import hashlib
import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import ensure_storage_root, settings
from app.core.text_locale import to_traditional_data
from app.models.file import FileRecord, FileTask
from app.models.knowledge import KnowledgeChunk, KnowledgeItem
from app.services.chunk_sync_service import ChunkSyncService
from app.services.conflict_service import ConflictService
from app.services.dedup_service import DedupService
from app.services.deepseek_service import DeepSeekService
from app.services.document_parser import DocumentParser, ParsedBlock, ParsedDocument
from app.services.freshness_service import FreshnessService
from app.services.retrieval_service import RetrievalService
from app.services.search_sync_service import SearchSyncService
from app.services.table_aware_ingestion_service import TableAwareIngestionService, TableKnowledgeDraft


logger = logging.getLogger(__name__)


class FileService:
    AUTO_IMPORT_CHUNK_SIZE = 500
    AUTO_IMPORT_GENERATE_QA = True

    def __init__(self, db: Session):
        self.db = db
        self.storage_root = ensure_storage_root()
        self.document_parser = DocumentParser()
        self.deepseek_service = DeepSeekService()
        self.dedup_service = DedupService(db)
        self.conflict_service = ConflictService(db)
        self.freshness_service = FreshnessService(db)
        self.search_sync_service = SearchSyncService()
        self.chunk_sync_service = ChunkSyncService(db)
        self.table_aware_ingestion_service = TableAwareIngestionService()

    def list_files(self, project_id: int, kb_id: int) -> list[dict]:
        items = (
            self.db.query(FileRecord)
            .filter(FileRecord.project_id == project_id, FileRecord.kb_id == kb_id)
            .order_by(FileRecord.id.desc())
            .all()
        )
        return [self._serialize_file(item) for item in items]

    async def upload_file(
        self,
        project_id: int,
        kb_id: int,
        upload: UploadFile,
        overwrite_same_name: bool = False,
        created_by: int | None = None,
    ) -> dict:
        original_name = upload.filename or f"upload_{uuid4().hex[:8]}.txt"
        target_relative = self._prepare_target_path(project_id, kb_id, original_name, overwrite_same_name)
        target_absolute = self.storage_root / target_relative
        target_absolute.parent.mkdir(parents=True, exist_ok=True)

        content = await upload.read()
        target_absolute.write_bytes(content)

        file_ext = Path(original_name).suffix.lower().lstrip(".") or None
        mime_type = upload.content_type or mimetypes.guess_type(original_name)[0]
        content_hash = hashlib.sha256(content).hexdigest()
        parsed_document, parse_error = self.document_parser.parse(target_absolute, file_ext=file_ext, mime_type=mime_type)
        preview_path = None
        parsed_document_path = None
        parser_name = None
        parse_meta_json: dict[str, Any] = {}
        parse_status = "success"
        if parse_error:
            parse_status = "failed"
        elif parsed_document:
            parser_name = parsed_document.parser_name
            parsed_document.metadata = {
                **parsed_document.metadata,
                "document_name": original_name,
                "mime_type": mime_type,
                "file_ext": file_ext,
            }
            parse_meta_json = {
                **parsed_document.metadata,
                "block_count": len(parsed_document.blocks),
                "text_length": len(parsed_document.text or ""),
            }
            preview_text = self._build_preview_text(parsed_document)
            preview_relative = target_relative.with_suffix(target_relative.suffix + ".preview.txt")
            preview_absolute = self.storage_root / preview_relative
            preview_absolute.write_text(preview_text, encoding="utf-8")
            preview_path = str(preview_relative)
            parsed_relative = target_relative.with_suffix(target_relative.suffix + ".parsed.json")
            parsed_absolute = self.storage_root / parsed_relative
            parsed_absolute.write_text(json.dumps(parsed_document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            parsed_document_path = str(parsed_relative)

        record = FileRecord(
            project_id=project_id,
            kb_id=kb_id,
            file_name=original_name,
            file_ext=file_ext,
            mime_type=mime_type,
            file_size=len(content),
            content_hash=content_hash,
            storage_path=str(target_relative),
            preview_path=preview_path,
            parsed_document_path=parsed_document_path,
            parser_name=parser_name,
            parse_meta_json=parse_meta_json,
            overwrite_same_name=overwrite_same_name,
            parse_status=parse_status,
            chunk_status="pending",
            qa_status="pending",
            parse_error=parse_error,
            created_by=created_by,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._serialize_file(record)

    def prepare_auto_process(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        created_by: int | None = None,
    ) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None
        if item.parse_status != "success":
            return self._serialize_file(item)

        task = self._get_or_create_file_task(
            project_id=project_id,
            kb_id=kb_id,
            file_id=file_id,
            task_type="auto_process",
            created_by=created_by,
        )
        task.status = "processing"
        task.error_message = None
        task.request_payload = {
            **(task.request_payload or {}),
            "trigger": "upload",
            "generate_qa": self.AUTO_IMPORT_GENERATE_QA,
            "chunk_size": self.AUTO_IMPORT_CHUNK_SIZE,
        }
        task.result_payload = {}
        item.chunk_status = "processing"
        item.qa_status = "processing"
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_file(item)

    def run_auto_process(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        created_by: int | None = None,
    ) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None

        task = self._get_or_create_file_task(
            project_id=project_id,
            kb_id=kb_id,
            file_id=file_id,
            task_type="auto_process",
            created_by=created_by,
        )

        try:
            parsed_document = self._read_parsed_document(item)
            if not parsed_document:
                raise ValueError("该文件暂无可入库的解析结果，请先确认解析是否成功。")

            import_mode = self._resolve_auto_import_mode(
                item=item,
                parsed_document=parsed_document,
            )
            result = self.import_file(
                project_id=project_id,
                kb_id=kb_id,
                file_id=file_id,
                chunk_size=self.AUTO_IMPORT_CHUNK_SIZE,
                generate_qa=self.AUTO_IMPORT_GENERATE_QA,
                import_mode=import_mode,
            )
            refreshed_task = self._get_or_create_file_task(
                project_id=project_id,
                kb_id=kb_id,
                file_id=file_id,
                task_type="auto_process",
                created_by=created_by,
            )
            refreshed_task.status = "completed"
            refreshed_task.error_message = None
            refreshed_task.result_payload = {
                "import_mode": import_mode,
                "generate_qa": self.AUTO_IMPORT_GENERATE_QA,
                "knowledge_count": (result or {}).get("knowledge_count"),
                "qa_count": (result or {}).get("qa_count"),
                "qa_generator": (result or {}).get("qa_generator"),
                "table_aware": (result or {}).get("table_aware"),
            }
            self.db.commit()
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("auto process file failed", extra={"project_id": project_id, "kb_id": kb_id, "file_id": file_id})
            self.db.rollback()
            failed_item = self._find_file(project_id, kb_id, file_id)
            failed_task = self._get_or_create_file_task(
                project_id=project_id,
                kb_id=kb_id,
                file_id=file_id,
                task_type="auto_process",
                created_by=created_by,
            )
            if failed_item:
                failed_item.chunk_status = "failed"
                failed_item.qa_status = "failed"
            failed_task.status = "failed"
            failed_task.error_message = str(exc)[:255]
            failed_task.result_payload = {
                **(failed_task.result_payload or {}),
                "failed_at": datetime.utcnow().isoformat(),
            }
            self.db.commit()
            if failed_item:
                self.db.refresh(failed_item)
                return self._serialize_file(failed_item)
            raise

    @classmethod
    def run_auto_process_in_background(
        cls,
        project_id: int,
        kb_id: int,
        file_id: int,
        created_by: int | None = None,
    ) -> None:
        db = SessionLocal()
        try:
            cls(db).run_auto_process(project_id=project_id, kb_id=kb_id, file_id=file_id, created_by=created_by)
        finally:
            db.close()

    def get_file_preview(self, project_id: int, kb_id: int, file_id: int) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None
        preview_text = self._read_preview_text(item)
        return {
            "id": item.id,
            "file_name": item.file_name,
            "content": preview_text,
            "parser_name": item.parser_name,
            "mime_type": item.mime_type,
            "parse_meta": item.parse_meta_json or {},
            "parse_error": item.parse_error,
        }

    def import_file(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        chunk_size: int = 500,
        generate_qa: bool = False,
        import_mode: str = "default",
        table_schema_hint: str | None = None,
    ) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None

        parsed_document = self._read_parsed_document(item)
        if not parsed_document:
            item.chunk_status = "failed"
            item.parse_status = "failed"
            item.parse_error = item.parse_error or "该文件暂无可入库的解析结果，请先确认解析是否成功。"
            self.db.commit()
            return self._serialize_file(item)

        chunks = self._chunk_document(parsed_document, chunk_size=chunk_size)
        stale_file_chunks = self._list_chunk_records_by_file(project_id, kb_id, item.id, source_kind="file")
        self._delete_knowledge_by_file(project_id, kb_id, item.id, source_type="file")
        self.search_sync_service.delete_chunks(stale_file_chunks)
        created_count = 0
        created_items: list[KnowledgeItem] = []
        for chunk in chunks:
            normalized_chunk = to_traditional_data(chunk)
            knowledge = KnowledgeItem(
                project_id=project_id,
                kb_id=kb_id,
                document_name=item.file_name,
                title=normalized_chunk["title"],
                content=normalized_chunk["content"],
                keywords_json=[],
                source_type="file",
                source_file_id=item.id,
                source_meta_json=normalized_chunk["source_meta"],
                status="active",
                version_no=1,
                published_at=datetime.utcnow(),
            )
            self.db.add(knowledge)
            created_items.append(knowledge)
            created_count += 1

        task = FileTask(
            project_id=project_id,
            kb_id=kb_id,
            file_id=item.id,
            task_type="chunk_import",
            status="completed",
            request_payload={
                "chunk_size": chunk_size,
                "generate_qa": generate_qa,
                "import_mode": import_mode,
                "table_schema_hint": table_schema_hint,
            },
            result_payload={"knowledge_count": created_count, "parser_name": item.parser_name},
        )
        self.db.add(task)

        item.chunk_status = "completed"
        qa_count = 0
        qa_pairs: list[dict[str, Any]] = []
        qa_created_items: list[KnowledgeItem] = []
        qa_generator = "disabled"
        stale_generated_qa_chunks = self._list_chunk_records_by_file(project_id, kb_id, item.id, source_kind="file_qa")
        if generate_qa:
            qa_pairs, qa_created_items, qa_generator = self._replace_generated_qa_items(project_id, kb_id, item, chunks)
            qa_count = len(qa_created_items)
            item.qa_status = "generated" if qa_count else "skipped"
        else:
            item.qa_status = "skipped"

        table_aware_summary: dict[str, Any] | None = None
        table_aware_created_items: list[KnowledgeItem] = []
        normalized_import_mode = " ".join(str(import_mode or "default").split()).strip().lower() or "default"
        if normalized_import_mode == "table_aware":
            table_aware_summary, table_aware_created_items = self._replace_table_aware_items(
                project_id=project_id,
                kb_id=kb_id,
                item=item,
                parsed_document=parsed_document,
                table_schema_hint=table_schema_hint,
            )

        item.parse_status = "success"
        self.db.commit()
        self.db.refresh(item)
        for knowledge in created_items:
            self.db.refresh(knowledge)
            self.dedup_service.sync_item_records(knowledge)
            self.freshness_service.refresh_item_metadata(knowledge)
            self.conflict_service.sync_item_task(knowledge)
            self.search_sync_service.upsert_knowledge(knowledge)
        for knowledge in qa_created_items:
            self.db.refresh(knowledge)
            self.dedup_service.sync_item_records(knowledge)
            self.freshness_service.refresh_item_metadata(knowledge)
            self.conflict_service.sync_item_task(knowledge)
            self.search_sync_service.upsert_knowledge(knowledge)
        for knowledge in table_aware_created_items:
            self.db.refresh(knowledge)
            self.dedup_service.sync_item_records(knowledge)
            self.freshness_service.refresh_item_metadata(knowledge)
            self.conflict_service.sync_item_task(knowledge)
            self.search_sync_service.upsert_knowledge(knowledge)
        created_file_chunks = self.chunk_sync_service.rebuild_file_chunks(
            project_id=project_id,
            kb_id=kb_id,
            file_id=item.id,
            document_name=item.file_name,
            chunks=chunks,
            source_items=created_items,
            source_kind="file",
        )
        self.search_sync_service.upsert_chunks(created_file_chunks)
        if generate_qa and qa_created_items:
            self.search_sync_service.delete_chunks(stale_generated_qa_chunks)
            qa_chunks = [
                {
                    "title": pair["question"],
                    "content": pair["answer"],
                    "source_meta": pair["source_meta"],
                }
                for pair in qa_pairs
            ]
            created_qa_chunks = self.chunk_sync_service.rebuild_file_chunks(
                project_id=project_id,
                kb_id=kb_id,
                file_id=item.id,
                document_name=item.file_name,
                chunks=qa_chunks,
                source_items=qa_created_items,
                source_kind="file_qa",
            )
            self.search_sync_service.upsert_chunks(created_qa_chunks)

        if table_aware_created_items:
            for knowledge in table_aware_created_items:
                chunks_for_item = self.chunk_sync_service.sync_manual_item(knowledge)
                self.search_sync_service.upsert_chunks(chunks_for_item)
            validation_summary = self._validate_table_aware_queries(
                project_id=project_id,
                kb_id=kb_id,
                created_items=table_aware_created_items,
                validation_queries=(table_aware_summary or {}).get("validation_queries") or [],
            )
            if table_aware_summary is not None:
                table_aware_summary["validation_summary"] = validation_summary
                task.result_payload = {
                    **(task.result_payload or {}),
                    "table_aware": {
                        key: value
                        for key, value in table_aware_summary.items()
                        if key != "validation_queries"
                    },
                }
        self.db.commit()
        result = {
            **self._serialize_file(item),
            "knowledge_count": created_count,
            "qa_count": qa_count,
            "qa_generator": qa_generator,
        }
        if table_aware_summary is not None:
            result["table_aware"] = {
                key: value
                for key, value in table_aware_summary.items()
                if key != "validation_queries"
            }
        return result

    def generate_qa(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        chunk_size: int = 700,
        max_pairs: int = 12,
    ) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None

        parsed_document = self._read_parsed_document(item)
        if not parsed_document:
            item.qa_status = "failed"
            item.parse_status = "failed"
            item.parse_error = item.parse_error or "该文件暂无可用于 QA 生成的解析结果，请先确认解析是否成功。"
            self.db.commit()
            return self._serialize_file(item)

        chunks = self._chunk_document(parsed_document, chunk_size=max(200, chunk_size))
        stale_qa_chunks = self._list_chunk_records_by_file(project_id, kb_id, item.id, source_kind="file_qa")
        qa_pairs, created_items, qa_generator = self._replace_generated_qa_items(
            project_id,
            kb_id,
            item,
            chunks,
            max_pairs=max_pairs,
        )
        task = FileTask(
            project_id=project_id,
            kb_id=kb_id,
            file_id=item.id,
            task_type="generate_qa",
            status="completed",
            request_payload={"chunk_size": chunk_size, "max_pairs": max_pairs},
            result_payload={
                "knowledge_count": len(created_items),
                "parser_name": item.parser_name,
                "qa_generator": qa_generator,
            },
        )
        self.db.add(task)
        item.qa_status = "generated" if created_items else "skipped"
        item.parse_status = "success"
        self.db.commit()
        self.db.refresh(item)
        for knowledge in created_items:
            self.db.refresh(knowledge)
            self.dedup_service.sync_item_records(knowledge)
            self.freshness_service.refresh_item_metadata(knowledge)
            self.conflict_service.sync_item_task(knowledge)
            self.search_sync_service.upsert_knowledge(knowledge)
        qa_chunks = [
            {
                "title": pair["question"],
                "content": pair["answer"],
                "source_meta": pair["source_meta"],
            }
            for pair in qa_pairs
        ]
        self.search_sync_service.delete_chunks(stale_qa_chunks)
        created_qa_chunks = self.chunk_sync_service.rebuild_file_chunks(
            project_id=project_id,
            kb_id=kb_id,
            file_id=item.id,
            document_name=item.file_name,
            chunks=qa_chunks,
            source_items=created_items,
            source_kind="file_qa",
        )
        self.search_sync_service.upsert_chunks(created_qa_chunks)
        self.db.commit()
        return {
            **self._serialize_file(item),
            "knowledge_count": len(created_items),
            "generated_questions": [pair["question"] for pair in qa_pairs],
            "qa_generator": qa_generator,
        }

    def delete_file(self, project_id: int, kb_id: int, file_id: int) -> dict | None:
        item = self._find_file(project_id, kb_id, file_id)
        if not item:
            return None

        serialized = self._serialize_file(item)
        stale_chunks = self._list_chunk_records_by_file(project_id, kb_id, item.id)
        self._delete_knowledge_by_file(project_id, kb_id, item.id)
        self.search_sync_service.delete_chunks(stale_chunks)
        self.chunk_sync_service.delete_by_file(project_id, kb_id, item.id)
        file_tasks = (
            self.db.query(FileTask)
            .filter(
                FileTask.project_id == project_id,
                FileTask.kb_id == kb_id,
                FileTask.file_id == item.id,
            )
            .all()
        )
        for task in file_tasks:
            self.db.delete(task)

        self._remove_storage_artifacts(item)
        self.db.delete(item)
        self.db.commit()
        return serialized

    def _find_file(self, project_id: int, kb_id: int, file_id: int) -> FileRecord | None:
        return (
            self.db.query(FileRecord)
            .filter(FileRecord.project_id == project_id, FileRecord.kb_id == kb_id, FileRecord.id == file_id)
            .first()
        )

    def _resolve_auto_import_mode(
        self,
        item: FileRecord,
        parsed_document: ParsedDocument,
    ) -> str:
        if self.table_aware_ingestion_service.supports(parsed_document, item.file_name, item.file_ext):
            return "table_aware"
        return "default"

    def _get_or_create_file_task(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        task_type: str,
        created_by: int | None = None,
    ) -> FileTask:
        task = (
            self.db.query(FileTask)
            .filter(
                FileTask.project_id == project_id,
                FileTask.kb_id == kb_id,
                FileTask.file_id == file_id,
                FileTask.task_type == task_type,
            )
            .order_by(FileTask.id.desc())
            .first()
        )
        if task:
            return task
        task = FileTask(
            project_id=project_id,
            kb_id=kb_id,
            file_id=file_id,
            task_type=task_type,
            status="pending",
            request_payload={},
            result_payload={},
            created_by=created_by,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _get_latest_file_task(self, project_id: int, kb_id: int, file_id: int, task_type: str) -> FileTask | None:
        return (
            self.db.query(FileTask)
            .filter(
                FileTask.project_id == project_id,
                FileTask.kb_id == kb_id,
                FileTask.file_id == file_id,
                FileTask.task_type == task_type,
            )
            .order_by(FileTask.id.desc())
            .first()
        )

    def _serialize_file_task(self, task: FileTask | None) -> dict[str, Any] | None:
        if not task:
            return None
        return {
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "request_payload": task.request_payload or {},
            "result_payload": task.result_payload or {},
            "error_message": task.error_message,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }

    def _prepare_target_path(
        self,
        project_id: int,
        kb_id: int,
        file_name: str,
        overwrite_same_name: bool,
    ) -> Path:
        clean_name = Path(file_name).name
        relative_path = Path(f"project_{project_id}") / f"kb_{kb_id}" / clean_name
        if overwrite_same_name or not (self.storage_root / relative_path).exists():
            return relative_path
        suffix = uuid4().hex[:6]
        stem = Path(clean_name).stem
        ext = Path(clean_name).suffix
        return Path(f"project_{project_id}") / f"kb_{kb_id}" / f"{stem}_{suffix}{ext}"

    def _read_preview_text(self, item: FileRecord) -> str:
        if item.preview_path:
            preview_absolute = self.storage_root / item.preview_path
            if preview_absolute.exists():
                return preview_absolute.read_text(encoding="utf-8")
        return ""

    def _delete_knowledge_by_file(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        source_type: str | None = None,
    ) -> None:
        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.kb_id == kb_id,
            KnowledgeItem.source_file_id == file_id,
        )
        if source_type is not None:
            query = query.filter(KnowledgeItem.source_type == source_type)

        for knowledge in query.all():
            self.search_sync_service.delete_knowledge(knowledge.id)
            self.search_sync_service.delete_chunks(self._list_chunk_records_by_source_item(knowledge.id))
            self.chunk_sync_service.delete_by_source_item(knowledge.id)
            self.db.delete(knowledge)

    def _list_chunk_records_by_file(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        source_kind: str | None = None,
    ) -> list[KnowledgeChunk]:
        query = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.project_id == project_id,
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.file_id == file_id,
        )
        if source_kind is not None:
            query = query.filter(KnowledgeChunk.source_kind == source_kind)
        return query.order_by(KnowledgeChunk.id.asc()).all()

    def _list_chunk_records_by_source_item(self, source_item_id: int) -> list[KnowledgeChunk]:
        return (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_item_id == source_item_id)
            .order_by(KnowledgeChunk.id.asc())
            .all()
        )

    def _replace_generated_qa_items(
        self,
        project_id: int,
        kb_id: int,
        item: FileRecord,
        chunks: list[dict[str, Any]],
        max_pairs: int = 12,
    ) -> tuple[list[dict[str, Any]], list[KnowledgeItem], str]:
        self._delete_knowledge_by_file(project_id, kb_id, item.id, source_type="file_qa")
        qa_pairs, qa_generator = self._build_generated_qa_pairs(item.file_name, chunks, max_pairs=max_pairs)
        created_items: list[KnowledgeItem] = []
        for qa in qa_pairs:
            normalized_qa = to_traditional_data(qa)
            knowledge = KnowledgeItem(
                project_id=project_id,
                kb_id=kb_id,
                document_name=item.file_name,
                title=normalized_qa["question"],
                content=normalized_qa["answer"],
                keywords_json=normalized_qa["keywords"],
                source_type="file_qa",
                source_file_id=item.id,
                source_meta_json=normalized_qa["source_meta"],
                status="active",
                version_no=1,
                published_at=datetime.utcnow(),
            )
            self.db.add(knowledge)
            created_items.append(knowledge)
        return qa_pairs, created_items, qa_generator

    def _replace_table_aware_items(
        self,
        project_id: int,
        kb_id: int,
        item: FileRecord,
        parsed_document: ParsedDocument,
        table_schema_hint: str | None = None,
    ) -> tuple[dict[str, Any] | None, list[KnowledgeItem]]:
        if not self.table_aware_ingestion_service.supports(parsed_document, item.file_name, item.file_ext):
            self._delete_table_aware_manual_items(project_id, kb_id, item.id)
            return {
                "enabled": False,
                "reason": "document_not_eligible",
                "table_count": 0,
                "row_item_count": 0,
                "meta_item_count": 0,
                "validation_queries": [],
            }, []

        extraction = self.table_aware_ingestion_service.extract(
            document=parsed_document,
            file_name=item.file_name,
            schema_hint=table_schema_hint,
        )
        self._delete_table_aware_manual_items(project_id, kb_id, item.id)
        created_items = self._create_table_aware_manual_items(
            project_id=project_id,
            kb_id=kb_id,
            item=item,
            drafts=[*extraction.meta_drafts, *extraction.row_drafts],
        )
        summary = {
            "enabled": True,
            **extraction.summary(),
            "created_item_count": len(created_items),
            "validation_queries": extraction.validation_queries,
        }
        return summary, created_items

    def _delete_table_aware_manual_items(self, project_id: int, kb_id: int, file_id: int) -> int:
        items = (
            self.db.query(KnowledgeItem)
            .filter(
                KnowledgeItem.project_id == project_id,
                KnowledgeItem.kb_id == kb_id,
                KnowledgeItem.source_file_id == file_id,
                KnowledgeItem.source_type == "manual",
            )
            .all()
        )
        deleted = 0
        for knowledge in items:
            ingest_kind = str((knowledge.source_meta_json or {}).get("ingest_kind") or "").strip().lower()
            if not ingest_kind.startswith("structured_table"):
                continue
            self.search_sync_service.delete_knowledge(knowledge.id)
            self.search_sync_service.delete_chunks(self._list_chunk_records_by_source_item(knowledge.id))
            self.chunk_sync_service.delete_by_source_item(knowledge.id)
            self.db.delete(knowledge)
            deleted += 1
        if deleted:
            self.db.commit()
        return deleted

    def _create_table_aware_manual_items(
        self,
        project_id: int,
        kb_id: int,
        item: FileRecord,
        drafts: list[TableKnowledgeDraft],
    ) -> list[KnowledgeItem]:
        created_items: list[KnowledgeItem] = []
        for draft in drafts:
            normalized_title = " ".join(str(draft.title or "").split()).strip()
            normalized_content = str(draft.content or "").strip()
            if not normalized_title or not normalized_content:
                continue
            normalized_meta = to_traditional_data(
                {
                    **(draft.source_meta or {}),
                    "file_name": item.file_name,
                    "parser_name": item.parser_name,
                }
            )
            knowledge = KnowledgeItem(
                project_id=project_id,
                kb_id=kb_id,
                document_name=item.file_name,
                title=to_traditional_data(normalized_title),
                content=to_traditional_data(normalized_content),
                keywords_json=to_traditional_data(draft.keywords or []),
                source_type="manual",
                source_file_id=item.id,
                source_meta_json=normalized_meta,
                status="active",
                version_no=1,
                published_at=datetime.utcnow(),
            )
            self.db.add(knowledge)
            created_items.append(knowledge)
        self.db.commit()
        return created_items

    def _validate_table_aware_queries(
        self,
        project_id: int,
        kb_id: int,
        created_items: list[KnowledgeItem],
        validation_queries: list[str],
    ) -> dict[str, Any]:
        if not created_items or not validation_queries:
            return {"total": 0, "passed": 0, "cases": []}
        created_ids = {item.id for item in created_items}
        retrieval_service = RetrievalService(self.db)
        cases: list[dict[str, Any]] = []
        passed = 0
        for query in validation_queries:
            hits = retrieval_service.retrieve(project_id=project_id, query=query, selected_kb_ids=[kb_id])
            top_hit = hits[0] if hits else None
            top_hit_id = int(top_hit.get("knowledge_id") or 0) if isinstance(top_hit, dict) else 0
            is_pass = top_hit_id in created_ids
            if is_pass:
                passed += 1
            cases.append(
                {
                    "query": query,
                    "top_hit_knowledge_id": top_hit_id or None,
                    "top_hit_title": top_hit.get("title") if isinstance(top_hit, dict) else None,
                    "passed": is_pass,
                }
            )
        return {
            "total": len(validation_queries),
            "passed": passed,
            "pass_rate": round(passed / max(len(validation_queries), 1), 4),
            "cases": cases,
        }

    def _build_generated_qa_pairs(
        self,
        file_name: str,
        chunks: list[dict[str, Any]],
        max_pairs: int = 12,
    ) -> tuple[list[dict[str, Any]], str]:
        llm_pairs = self.deepseek_service.generate_document_qa_pairs(file_name, chunks, max_pairs=max_pairs)
        normalized_llm_pairs = self._normalize_llm_generated_qa_pairs(file_name, chunks, llm_pairs, max_pairs=max_pairs)
        if normalized_llm_pairs:
            return normalized_llm_pairs, "deepseek"

        qa_pairs: list[dict[str, Any]] = []
        file_stem = Path(file_name).stem
        for chunk in chunks:
            content = str(chunk.get("content") or "").strip()
            if len(content) < 30:
                continue
            source_meta = dict(chunk.get("source_meta") or {})
            topic = self._resolve_chunk_topic(file_stem, source_meta)
            question = f"{file_stem}中「{topic}」的主要內容是什麼？" if topic else f"{file_stem}的主要內容是什麼？"
            keywords = [value for value in [file_stem, topic] if value]
            qa_pairs.append(
                {
                    "question": question,
                    "answer": content,
                    "keywords": keywords[:6],
                    "source_meta": {
                        **source_meta,
                        "qa_kind": "generated",
                        "qa_question": question,
                        "qa_generator": "fallback_rule",
                    },
                }
            )
            if len(qa_pairs) >= max_pairs:
                break
        return qa_pairs, "fallback_rule"

    def _normalize_llm_generated_qa_pairs(
        self,
        file_name: str,
        chunks: list[dict[str, Any]],
        llm_pairs: list[dict[str, Any]],
        max_pairs: int = 12,
    ) -> list[dict[str, Any]]:
        if not llm_pairs:
            return []

        chunk_map = {
            int(((chunk.get("source_meta") or {}).get("chunk_index")) or index): chunk
            for index, chunk in enumerate(chunks, start=1)
        }
        file_stem = Path(file_name).stem
        normalized: list[dict[str, Any]] = []
        for pair in llm_pairs:
            question = " ".join(str(pair.get("question") or "").split()).strip()
            answer = str(pair.get("answer") or "").strip()
            if not question or not answer:
                continue
            chunk_index = int(pair.get("chunk_index") or 0)
            source_chunk = chunk_map.get(chunk_index)
            if source_chunk is None:
                continue
            source_meta = dict(source_chunk.get("source_meta") or {})
            keywords = [
                str(keyword).strip()
                for keyword in (pair.get("keywords") or [])
                if str(keyword).strip()
            ]
            topic = self._resolve_chunk_topic(file_stem, source_meta)
            normalized.append(
                {
                    "question": question,
                    "answer": answer,
                    "keywords": (keywords or [file_stem, topic])[:6],
                    "source_meta": {
                        **source_meta,
                        "qa_kind": "generated",
                        "qa_question": question,
                        "qa_generator": "deepseek",
                        "qa_chunk_index": chunk_index,
                    },
                }
            )
            if len(normalized) >= max_pairs:
                break
        return normalized

    def _resolve_chunk_topic(self, file_stem: str, source_meta: dict[str, Any]) -> str:
        heading_path = [str(item).strip() for item in source_meta.get("heading_path") or [] if str(item).strip()]
        if heading_path:
            return heading_path[-1]

        page_numbers = [str(item) for item in source_meta.get("page_numbers") or [] if item]
        if page_numbers:
            return f"第{page_numbers[0]}頁"

        row_range = source_meta.get("row_range")
        sheet_names = [str(item).strip() for item in source_meta.get("sheet_names") or [] if str(item).strip()]
        if row_range and len(row_range) == 2:
            sheet_name = sheet_names[0] if sheet_names else "表格"
            return f"{sheet_name} 第{row_range[0]}-{row_range[1]}行"

        section_title = str(source_meta.get("section_title") or "").strip()
        if section_title and section_title != file_stem:
            return section_title
        return ""

    def _remove_storage_artifacts(self, item: FileRecord) -> None:
        for relative_path in [item.storage_path, item.preview_path, item.parsed_document_path]:
            if not relative_path:
                continue
            absolute_path = self.storage_root / relative_path
            if absolute_path.exists():
                absolute_path.unlink()

    def _read_parsed_document(self, item: FileRecord) -> ParsedDocument | None:
        if not item.parsed_document_path:
            return None
        parsed_absolute = self.storage_root / item.parsed_document_path
        if not parsed_absolute.exists():
            return None
        payload = json.loads(parsed_absolute.read_text(encoding="utf-8"))
        blocks = [
            ParsedBlock(
                block_type=str(block.get("block_type") or "paragraph"),
                text=str(block.get("text") or ""),
                order_no=int(block.get("order_no") or index),
                page_no=block.get("page_no"),
                sheet_name=block.get("sheet_name"),
                slide_no=block.get("slide_no"),
                section_title=block.get("section_title"),
                metadata=block.get("metadata") or {},
            )
            for index, block in enumerate(payload.get("blocks") or [], start=1)
            if str(block.get("text") or "").strip()
        ]
        return ParsedDocument(
            parser_name=str(payload.get("parser_name") or item.parser_name or "unknown"),
            text=str(payload.get("text") or ""),
            blocks=blocks,
            metadata=payload.get("metadata") or {},
        )

    def _build_preview_text(self, document: ParsedDocument) -> str:
        preview_text = document.text.strip() or "\n".join(block.text for block in document.blocks)
        return preview_text[: settings.FILE_PREVIEW_MAX_CHARS]

    def _chunk_document(self, document: ParsedDocument, chunk_size: int = 500) -> list[dict[str, Any]]:
        strategy = str(document.metadata.get("chunk_strategy") or "structured_text")
        if strategy == "spreadsheet":
            return self._chunk_spreadsheet_document(document, chunk_size)
        if strategy == "slide":
            return self._chunk_slide_document(document, chunk_size)
        if strategy in {"ocr_document", "paged_document"}:
            return self._chunk_paged_document(document, chunk_size)
        return self._chunk_structured_text_document(document, chunk_size)

    def _chunk_structured_text_document(self, document: ParsedDocument, chunk_size: int) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        heading_stack: list[tuple[int, str]] = []
        pending_heading: ParsedBlock | None = None
        current_lines: list[str] = []
        current_blocks: list[ParsedBlock] = []
        current_heading_path: list[str] = []

        def flush_chunk() -> None:
            nonlocal current_lines, current_blocks
            if not current_lines:
                return
            if current_blocks and all(block.block_type == "title" for block in current_blocks):
                current_lines = []
                current_blocks = []
                return
            chunks.append(
                self._create_chunk(
                    document=document,
                    blocks=current_blocks,
                    content="\n".join(current_lines).strip(),
                    chunk_index=len(chunks) + 1,
                    title=current_heading_path[-1] if current_heading_path else self._build_chunk_title(document, len(chunks) + 1),
                    heading_path=current_heading_path,
                )
            )
            current_lines = []
            current_blocks = []

        def ensure_heading_prefix() -> None:
            nonlocal pending_heading
            if pending_heading is None or current_lines:
                return
            heading_level = max(1, min(3, int(pending_heading.metadata.get("heading_level") or 1)))
            current_lines.append(f"{'#' * heading_level} {pending_heading.text}")
            current_blocks.append(pending_heading)
            pending_heading = None

        for block in document.blocks:
            text = block.text.strip()
            if not text:
                continue
            if block.block_type == "title":
                flush_chunk()
                heading_level = int(block.metadata.get("heading_level") or 1)
                while heading_stack and heading_stack[-1][0] >= heading_level:
                    heading_stack.pop()
                heading_stack.append((heading_level, text))
                current_heading_path = [title for _, title in heading_stack]
                pending_heading = block
                continue

            ensure_heading_prefix()

            if block.block_type == "table":
                flush_chunk()
                table_lines = []
                table_blocks = []
                if pending_heading is not None:
                    current_heading_path = current_heading_path or [pending_heading.text]
                    heading_level = max(1, min(3, int(pending_heading.metadata.get("heading_level") or 1)))
                    table_lines.append(f"{'#' * heading_level} {pending_heading.text}")
                    table_blocks.append(pending_heading)
                    pending_heading = None
                table_lines.append(text)
                table_blocks.append(block)
                chunks.append(
                    self._create_chunk(
                        document=document,
                        blocks=table_blocks,
                        content="\n".join(table_lines).strip(),
                        chunk_index=len(chunks) + 1,
                        title=current_heading_path[-1] if current_heading_path else self._build_chunk_title(document, len(chunks) + 1),
                        heading_path=current_heading_path,
                    )
                )
                continue

            candidate = "\n".join([*current_lines, text]).strip()
            if current_lines and len(candidate) > chunk_size:
                flush_chunk()
                ensure_heading_prefix()

            if len(text) > chunk_size:
                for fragment in self._split_long_text(text, chunk_size):
                    if current_lines:
                        flush_chunk()
                        ensure_heading_prefix()
                    current_lines.append(fragment)
                    current_blocks.append(
                        ParsedBlock(
                            block_type=block.block_type,
                            text=fragment,
                            order_no=block.order_no,
                            page_no=block.page_no,
                            sheet_name=block.sheet_name,
                            slide_no=block.slide_no,
                            section_title=block.section_title,
                            metadata=block.metadata,
                        )
                    )
                    flush_chunk()
                continue

            current_lines.append(text)
            current_blocks.append(block)

        flush_chunk()
        return chunks

    def _chunk_spreadsheet_document(self, document: ParsedDocument, chunk_size: int) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        blocks_by_sheet: dict[str, list[ParsedBlock]] = {}
        for block in document.blocks:
            sheet_name = block.sheet_name or ("CSV" if document.parser_name == "native_csv" else "Sheet")
            blocks_by_sheet.setdefault(sheet_name, []).append(block)

        for sheet_name, sheet_blocks in blocks_by_sheet.items():
            title_blocks = [block for block in sheet_blocks if block.block_type == "title"]
            row_blocks = [block for block in sheet_blocks if block.block_type == "table_row"]
            if not row_blocks:
                if title_blocks:
                    chunks.append(
                        self._create_chunk(
                            document=document,
                            blocks=title_blocks,
                            content="\n".join(block.text for block in title_blocks),
                            chunk_index=len(chunks) + 1,
                            title=sheet_name,
                            heading_path=[sheet_name],
                            extra_meta={"sheet_name": sheet_name},
                        )
                    )
                continue

            header_fields = list(row_blocks[0].metadata.get("header_fields") or []) or [cell.strip() for cell in row_blocks[0].text.split("|") if cell.strip()]
            data_rows = row_blocks[1:] if len(row_blocks) > 1 else row_blocks
            window_blocks: list[ParsedBlock] = []
            window_lines: list[str] = []
            window_start_row: int | None = None

            def flush_sheet_window() -> None:
                nonlocal window_blocks, window_lines, window_start_row
                if not window_blocks:
                    return
                row_indexes = [int(block.metadata.get("row_index") or 0) for block in window_blocks]
                row_range = [min(row_indexes), max(row_indexes)] if row_indexes else None
                content_lines = [f"# Sheet: {sheet_name}"]
                if header_fields:
                    content_lines.append(f"表头: {' | '.join(header_fields)}")
                content_lines.extend(window_lines)
                chunks.append(
                    self._create_chunk(
                        document=document,
                        blocks=[*title_blocks, *window_blocks] if title_blocks else window_blocks,
                        content="\n".join(content_lines).strip(),
                        chunk_index=len(chunks) + 1,
                        title=f"{sheet_name} {row_range[0]}-{row_range[1]}行" if row_range else sheet_name,
                        heading_path=[sheet_name],
                        extra_meta={
                            "sheet_name": sheet_name,
                            "row_range": row_range,
                            "header_fields": header_fields,
                        },
                    )
                )
                window_blocks = []
                window_lines = []
                window_start_row = None

            for block in data_rows:
                row_index = int(block.metadata.get("row_index") or 0)
                candidate_lines = [*window_lines, block.text]
                candidate_len = len("\n".join(candidate_lines))
                if window_blocks and (candidate_len > chunk_size * 2 or len(window_blocks) >= 20):
                    flush_sheet_window()
                if window_start_row is None:
                    window_start_row = row_index
                window_blocks.append(block)
                window_lines.append(block.text)

            flush_sheet_window()

        return chunks

    def _chunk_slide_document(self, document: ParsedDocument, chunk_size: int) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        slide_numbers = sorted({block.slide_no for block in document.blocks if block.slide_no})
        for slide_no in slide_numbers:
            slide_blocks = [block for block in document.blocks if block.slide_no == slide_no]
            title_block = next((block for block in slide_blocks if block.block_type == "title"), None)
            slide_title = title_block.text if title_block else f"第{slide_no}页幻灯片"
            text_blocks = [block for block in slide_blocks if block.block_type not in {"title", "table"}]
            table_blocks = [block for block in slide_blocks if block.block_type == "table"]

            if text_blocks or title_block:
                content_lines = [f"# {slide_title}"]
                current_blocks = [title_block] if title_block else []
                for block in text_blocks:
                    candidate = "\n".join([*content_lines, block.text]).strip()
                    if len(candidate) > chunk_size and len(content_lines) > 1:
                        chunks.append(
                            self._create_chunk(
                                document=document,
                                blocks=current_blocks,
                                content="\n".join(content_lines).strip(),
                                chunk_index=len(chunks) + 1,
                                title=slide_title,
                                heading_path=[slide_title],
                                extra_meta={"slide_title": slide_title},
                            )
                        )
                        content_lines = [f"# {slide_title}"]
                        current_blocks = [title_block] if title_block else []
                    content_lines.append(block.text)
                    current_blocks.append(block)
                if len(content_lines) > 1 or title_block:
                    chunks.append(
                        self._create_chunk(
                            document=document,
                            blocks=current_blocks,
                            content="\n".join(content_lines).strip(),
                            chunk_index=len(chunks) + 1,
                            title=slide_title,
                            heading_path=[slide_title],
                            extra_meta={"slide_title": slide_title},
                        )
                    )

            for block in table_blocks:
                table_lines = [f"# {slide_title}", block.text]
                chunks.append(
                    self._create_chunk(
                        document=document,
                        blocks=[title_block, block] if title_block else [block],
                        content="\n".join(table_lines).strip(),
                        chunk_index=len(chunks) + 1,
                        title=f"{slide_title} 表格",
                        heading_path=[slide_title],
                        extra_meta={"slide_title": slide_title},
                    )
                )

        return chunks

    def _chunk_paged_document(self, document: ParsedDocument, chunk_size: int) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        page_numbers = sorted({block.page_no for block in document.blocks if block.page_no}) or [1]
        for page_no in page_numbers:
            page_blocks = [block for block in document.blocks if (block.page_no or 1) == page_no]
            page_title = f"第{page_no}页"
            current_lines = [f"# {page_title}"]
            current_blocks: list[ParsedBlock] = []
            for block in page_blocks:
                candidate = "\n".join([*current_lines, block.text]).strip()
                if current_blocks and len(candidate) > chunk_size:
                    chunks.append(
                        self._create_chunk(
                            document=document,
                            blocks=current_blocks,
                            content="\n".join(current_lines).strip(),
                            chunk_index=len(chunks) + 1,
                            title=page_title,
                            heading_path=[page_title],
                        )
                    )
                    current_lines = [f"# {page_title}"]
                    current_blocks = []
                current_lines.append(block.text)
                current_blocks.append(block)
            if current_blocks:
                chunks.append(
                    self._create_chunk(
                        document=document,
                        blocks=current_blocks,
                        content="\n".join(current_lines).strip(),
                        chunk_index=len(chunks) + 1,
                        title=page_title,
                        heading_path=[page_title],
                    )
                )
        return chunks

    def _create_chunk(
        self,
        document: ParsedDocument,
        blocks: list[ParsedBlock | None],
        content: str,
        chunk_index: int,
        title: str,
        heading_path: list[str] | None = None,
        extra_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_blocks = [block for block in blocks if block is not None]
        return {
            "title": title,
            "content": content.strip(),
            "source_meta": self._build_chunk_source_meta(
                document=document,
                blocks=normalized_blocks,
                chunk_index=chunk_index,
                heading_path=heading_path or [],
                extra_meta=extra_meta or {},
            ),
        }

    def _split_long_text(self, text: str, chunk_size: int) -> list[str]:
        fragments: list[str] = []
        current = ""
        for paragraph in [part.strip() for part in text.splitlines() if part.strip()] or [text]:
            if len(current) + len(paragraph) + 1 <= chunk_size:
                current = f"{current}\n{paragraph}".strip()
                continue
            if current:
                fragments.append(current)
            while len(paragraph) > chunk_size:
                fragments.append(paragraph[:chunk_size])
                paragraph = paragraph[chunk_size:]
            current = paragraph
        if current:
            fragments.append(current)
        return fragments

    def _build_chunk_title(self, document: ParsedDocument, index: int) -> str:
        base_name = Path(document.metadata.get("document_name") or "").stem if document.metadata.get("document_name") else None
        return base_name or f"文档分块 {index}"

    def _build_chunk_source_meta(
        self,
        document: ParsedDocument,
        blocks: list[ParsedBlock],
        chunk_index: int,
        heading_path: list[str],
        extra_meta: dict[str, Any],
    ) -> dict[str, Any]:
        page_numbers = sorted({block.page_no for block in blocks if block.page_no})
        slide_numbers = sorted({block.slide_no for block in blocks if block.slide_no})
        sheet_names = [block.sheet_name for block in blocks if block.sheet_name]
        section_titles = [block.section_title for block in blocks if block.section_title]
        row_indexes = sorted({int(block.metadata.get("row_index")) for block in blocks if block.metadata.get("row_index") is not None})
        header_fields = extra_meta.get("header_fields") or next(
            (block.metadata.get("header_fields") for block in blocks if block.metadata.get("header_fields")),
            [],
        )
        bbox_list = [block.metadata.get("bbox") for block in blocks if block.metadata.get("bbox")]
        ocr_scores = [float(block.metadata.get("score") or block.metadata.get("ocr_score")) for block in blocks if block.metadata.get("score") is not None or block.metadata.get("ocr_score") is not None]
        table_index = extra_meta.get("table_index") or next((block.metadata.get("table_index") for block in blocks if block.metadata.get("table_index") is not None), None)
        derived_row_range = extra_meta.get("row_range")
        if derived_row_range is None and row_indexes:
            derived_row_range = [min(row_indexes), max(row_indexes)]
        file_name = str(document.metadata.get("document_name") or "")
        file_type = str(document.metadata.get("file_ext") or "")
        return {
            "file_name": file_name,
            "file_type": file_type,
            "chunk_index": chunk_index,
            "parser_name": document.parser_name,
            "route_kind": document.metadata.get("route_kind"),
            "chunk_strategy": document.metadata.get("chunk_strategy"),
            "heading_path": heading_path,
            "section_title": heading_path[-1] if heading_path else (list(dict.fromkeys(section_titles))[-1] if section_titles else None),
            "block_types": sorted({block.block_type for block in blocks}),
            "page_numbers": page_numbers,
            "slide_numbers": slide_numbers,
            "sheet_names": list(dict.fromkeys(sheet_names)),
            "section_titles": list(dict.fromkeys(section_titles)),
            "row_range": derived_row_range,
            "header_fields": header_fields,
            "table_index": table_index,
            "bbox_list": bbox_list,
            "ocr_score_avg": round(sum(ocr_scores) / len(ocr_scores), 4) if ocr_scores else None,
            "order_range": [min((block.order_no for block in blocks), default=chunk_index), max((block.order_no for block in blocks), default=chunk_index)],
            **extra_meta,
        }

    def _serialize_file(self, item: FileRecord) -> dict:
        auto_process_task = self._get_latest_file_task(item.project_id, item.kb_id, item.id, task_type="auto_process")
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "file_name": item.file_name,
            "file_ext": item.file_ext,
            "mime_type": item.mime_type,
            "file_size": item.file_size,
            "content_hash": item.content_hash,
            "storage_path": item.storage_path,
            "preview_path": item.preview_path,
            "parsed_document_path": item.parsed_document_path,
            "parser_name": item.parser_name,
            "parse_meta": item.parse_meta_json or {},
            "parse_status": item.parse_status,
            "chunk_status": item.chunk_status,
            "qa_status": item.qa_status,
            "parse_error": item.parse_error,
            "auto_process_task": self._serialize_file_task(auto_process_task),
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.file import FileRecord
from app.models.knowledge import KnowledgeBase
from app.services.deepseek_service import DeepSeekService
from app.services.document_parser import ParsedBlock
from app.services.file_service import FileService
from app.services.project_service import ProjectService


class DocumentQaService:
    def __init__(self, db: Session):
        self.db = db
        self.file_service = FileService(db)
        self.deepseek_service = DeepSeekService()
        self.project_service = ProjectService(db)

    def list_files(self, project_id: int) -> list[dict]:
        self._ensure_project_exists(project_id)
        items = (
            self.db.query(FileRecord)
            .filter(FileRecord.project_id == project_id)
            .order_by(FileRecord.updated_at.desc(), FileRecord.id.desc())
            .all()
        )
        return [self.file_service._serialize_file(item) for item in items]

    async def upload_file(self, project_id: int, upload: UploadFile, overwrite_same_name: bool = False) -> dict:
        kb_id = self._resolve_document_kb_id(project_id)
        return await self.file_service.upload_file(project_id, kb_id, upload, overwrite_same_name)

    def get_preview(self, project_id: int, file_id: int) -> dict | None:
        item = self._find_project_file(project_id, file_id)
        if not item:
            return None

        preview = self.file_service.get_file_preview(project_id, item.kb_id, item.id)
        if not preview:
            return None

        parsed_document = self.file_service._read_parsed_document(item)
        blocks = parsed_document.blocks if parsed_document and parsed_document.blocks else self._build_blocks_from_text(preview.get("content") or "")
        return {
            **preview,
            "blocks": [self._serialize_block(block) for block in blocks],
        }

    def ask(self, project_id: int, file_id: int, query: str) -> dict:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            raise ValueError("query_empty")

        item = self._find_project_file(project_id, file_id)
        if not item:
            raise ValueError("file_not_found")
        if item.parse_status == "failed":
            raise ValueError(item.parse_error or "file_parse_failed")

        preview = self.get_preview(project_id, file_id)
        if not preview:
            raise ValueError("file_preview_not_found")

        blocks = preview.get("blocks") or []
        ranked_blocks = self._rank_blocks(normalized_query, blocks)
        citations = [self._build_citation(entry["block"], entry["score"]) for entry in ranked_blocks[:3]]

        answer, model_name = self._generate_answer(
            file_name=item.file_name,
            query=normalized_query,
            citations=citations,
            preview_content=str(preview.get("content") or ""),
        )
        return {
            "file_id": file_id,
            "query": normalized_query,
            "answer": answer,
            "citations": citations,
            "trace_id": uuid4().hex[:16],
            "model_name": model_name,
        }

    def _ensure_project_exists(self, project_id: int) -> None:
        if not self.project_service.get_project(project_id):
            raise ValueError("project_not_found")

    def _resolve_document_kb_id(self, project_id: int) -> int:
        self._ensure_project_exists(project_id)
        kb = (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.project_id == project_id)
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.id.asc())
            .first()
        )
        if kb:
            return kb.id

        project = self.project_service.get_project(project_id)
        project_key = project["project_key"] if project else f"project_{project_id}"
        kb = KnowledgeBase(
            project_id=project_id,
            name=f"kb_{project_key}",
            description="项目默认知识库",
            is_default=True,
        )
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb.id

    def _find_project_file(self, project_id: int, file_id: int) -> FileRecord | None:
        self._ensure_project_exists(project_id)
        return (
            self.db.query(FileRecord)
            .filter(FileRecord.project_id == project_id, FileRecord.id == file_id)
            .first()
        )

    def _serialize_block(self, block: ParsedBlock) -> dict:
        return {
            "block_id": f"block-{block.order_no}",
            "block_type": block.block_type,
            "text": block.text,
            "order_no": block.order_no,
            "page_no": block.page_no,
            "sheet_name": block.sheet_name,
            "slide_no": block.slide_no,
            "section_title": block.section_title,
            "metadata": block.metadata or {},
        }

    def _build_blocks_from_text(self, content: str) -> list[ParsedBlock]:
        blocks: list[ParsedBlock] = []
        for index, paragraph in enumerate([item.strip() for item in content.split("\n") if item.strip()], start=1):
            blocks.append(
                ParsedBlock(
                    block_type="paragraph",
                    text=paragraph,
                    order_no=index,
                )
            )
        return blocks

    def _rank_blocks(self, query: str, blocks: list[dict]) -> list[dict]:
        terms = self._extract_terms(query)
        ranked: list[dict] = []
        for index, block in enumerate(blocks):
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            score = self._score_block(query, terms, text)
            ranked.append(
                {
                    "index": index,
                    "score": score,
                    "block": block,
                }
            )
        ranked.sort(key=lambda item: (item["score"], -item["index"]), reverse=True)
        positives = [item for item in ranked if item["score"] > 0]
        if positives:
            return positives
        return ranked[:3]

    def _extract_terms(self, query: str) -> list[str]:
        english_terms = [item.lower() for item in re.findall(r"[A-Za-z0-9]{2,}", query)]
        chinese_terms: list[str] = []
        for segment in re.findall(r"[\u4e00-\u9fff]{2,}", query):
            if len(segment) <= 4:
                chinese_terms.append(segment)
            chinese_terms.extend(segment[index : index + 2] for index in range(max(len(segment) - 1, 0)))
            chinese_terms.extend(segment[index : index + 3] for index in range(max(len(segment) - 2, 0)))
        seen: set[str] = set()
        ordered: list[str] = []
        for term in [*english_terms, *chinese_terms]:
            clean_term = term.strip()
            if len(clean_term) < 2 or clean_term in seen:
                continue
            seen.add(clean_term)
            ordered.append(clean_term)
        return ordered

    def _score_block(self, query: str, terms: list[str], text: str) -> int:
        score = 0
        lowered_text = text.lower()
        lowered_query = query.lower()
        if lowered_query and lowered_query in lowered_text:
            score += len(lowered_query) * 3
        for term in terms:
            if re.fullmatch(r"[A-Za-z0-9]+", term):
                score += lowered_text.count(term) * max(2, len(term))
            else:
                score += text.count(term) * len(term)
        return score

    def _build_citation(self, block: dict, score: int) -> dict:
        quote = str(block.get("text") or "").strip()
        snippet = quote[:220]
        if len(quote) > 220:
            snippet = f"{snippet}..."
        return {
            "block_id": block.get("block_id"),
            "quote": snippet,
            "page_no": block.get("page_no"),
            "sheet_name": block.get("sheet_name"),
            "slide_no": block.get("slide_no"),
            "score": score,
        }

    def _generate_answer(self, file_name: str, query: str, citations: list[dict], preview_content: str) -> tuple[str, str]:
        if not citations:
            return "当前文档中没有检索到与该问题直接相关的内容，请换一种问法或检查文档是否已解析完整。", "document-extractive"

        if self.deepseek_service.is_enabled():
            try:
                answer, model_name = self.deepseek_service.answer(
                    system_prompt=(
                        "你是一个文档问答助手。"
                        "只能依据提供的文档片段回答，不要补充片段之外的事实。"
                        "如果依据不足，请明确说明文档中未找到。"
                    ),
                    runtime_prompt=self._build_runtime_prompt(file_name, query, citations),
                )
                cleaned = answer.strip()
                if cleaned:
                    return cleaned, model_name
            except Exception:  # noqa: BLE001
                pass

        snippets = [f"{index}. {item['quote']}" for index, item in enumerate(citations, start=1) if item.get("quote")]
        if snippets:
            summary = "\n".join(snippets)
            return f"根据《{file_name}》中命中的原文片段，和问题“{query}”最相关的内容如下：\n{summary}", "document-extractive"

        short_preview = preview_content[:240]
        if len(preview_content) > 240:
            short_preview = f"{short_preview}..."
        return f"当前基于文档原文做回答，先提供最接近的问题上下文：\n{short_preview}", "document-extractive"

    def _build_runtime_prompt(self, file_name: str, query: str, citations: list[dict]) -> str:
        references = "\n\n".join(
            f"[{index}] {item.get('quote')}"
            for index, item in enumerate(citations, start=1)
            if item.get("quote")
        )
        return (
            f"文档名称：{Path(file_name).name}\n"
            f"用户问题：{query}\n\n"
            f"可用文档片段：\n{references}\n\n"
            "请直接回答用户问题，并尽量引用上面片段中的说法。"
        )

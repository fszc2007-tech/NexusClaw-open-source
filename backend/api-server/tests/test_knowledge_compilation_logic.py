from __future__ import annotations

from datetime import datetime
import unittest

from app.models.knowledge_compilation import KnowledgeCompilationPage
from app.services.chat_service import ChatService
from app.services.knowledge_compilation_service import KnowledgeCompilationService


def _build_page(**overrides) -> KnowledgeCompilationPage:
    now = datetime.utcnow()
    payload = {
        "id": 1,
        "project_id": 1,
        "kb_id": 1,
        "page_type": "faq",
        "topic_key": "bno-materials",
        "canonical_title": "BNO 續簽材料",
        "title": "BNO 續簽材料",
        "summary": "整理 BNO 續簽所需材料與補充說明",
        "content_markdown": "BNO 續簽需要身份證明、住址證明與相關申請表。",
        "status": "published",
        "health_status": "healthy",
        "retrieval_priority": 50,
        "version_no": 3,
        "current_version_id": 3,
        "published_version_id": 3,
        "last_compiled_at": now,
        "published_at": now,
        "created_by": 1,
        "updated_by": 1,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "tags_json": [],
        "metadata_json": {},
    }
    payload.update(overrides)
    return KnowledgeCompilationPage(**payload)


class KnowledgeCompilationLogicTests(unittest.TestCase):
    def test_score_compilation_page_prefers_relevant_healthy_page(self) -> None:
        service = KnowledgeCompilationService(db=None)
        page = _build_page()
        score = service._score_compilation_page(
            query="BNO 續簽材料",
            query_tokens=service._tokenize_text("BNO 續簽材料"),
            page=page,
            sources=[],
        )
        self.assertGreaterEqual(score, 0.82)

    def test_score_compilation_page_rejects_irrelevant_page(self) -> None:
        service = KnowledgeCompilationService(db=None)
        page = _build_page(
            title="居住證辦理流程",
            canonical_title="居住證辦理流程",
            summary="整理居住證辦理步驟",
            content_markdown="這裡是居住證流程內容。",
        )
        score = service._score_compilation_page(
            query="BNO 續簽材料",
            query_tokens=service._tokenize_text("BNO 續簽材料"),
            page=page,
            sources=[],
        )
        self.assertEqual(score, 0.0)

    def test_merge_compilation_with_retrieval_hybrid_strategy(self) -> None:
        service = ChatService.__new__(ChatService)
        compilation_context = {
            "usable": True,
            "reference_items": [
                {
                    "title": "編譯頁/BNO 續簽材料",
                    "document_name": "編譯知識頁/faq",
                    "snippet": "整理過的材料清單",
                    "compilation_page_id": 11,
                }
            ],
            "raw_sources": [
                {
                    "source_type": "file_chunk",
                    "source_id": "chunk-1",
                    "title": "官方 PDF",
                }
            ],
        }
        ranked_items = [
            {
                "knowledge_id": 7,
                "title": "原始材料說明",
                "document_name": "官方文件",
                "snippet": "原始材料內容",
            }
        ]

        prompt_items, sources, compiled_used = service._merge_compilation_with_retrieval(
            compilation_context=compilation_context,
            ranked_items=ranked_items,
            strategy="hybrid",
        )

        self.assertTrue(compiled_used)
        self.assertEqual(len(prompt_items), 2)
        self.assertEqual(prompt_items[0]["compilation_page_id"], 11)
        self.assertTrue(any(item.get("knowledge_id") == 7 for item in prompt_items))
        self.assertEqual(sources[0]["source_id"], "chunk-1")

    def test_build_writeback_source_refs_falls_back_to_chat_message_source(self) -> None:
        service = KnowledgeCompilationService(db=None)

        class Candidate:
            source_docs_snapshot = []
            chat_message_id = 99
            chat_session_id = 88
            suggested_title = "測試回流"
            question = "BNO 續簽和永居材料有何差異？"
            answer = "需要更多住址與居留證明。"

        refs = service._build_writeback_source_refs(Candidate())
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["source_type"], "chat_message")
        self.assertEqual(refs[0]["source_id"], "99")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.services.chat_service import ChatService


class SearchCompilationResponseTests(unittest.TestCase):
    def test_merge_source_items_dedupes_compilation_and_raw_sources(self) -> None:
        service = ChatService.__new__(ChatService)
        merged = service._merge_source_items(
            [
                {"source_type": "file_chunk", "source_id": "chunk-1", "source_ref_id": "ref-a"},
                {"source_type": "file_chunk", "source_id": "chunk-2", "source_ref_id": "ref-b"},
            ],
            [
                {"source_type": "file_chunk", "source_id": "chunk-1", "source_ref_id": "ref-a"},
                {"knowledge_id": 9, "title": "raw-hit"},
            ],
        )
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["source_id"], "chunk-1")
        self.assertEqual(merged[1]["source_id"], "chunk-2")
        self.assertEqual(merged[2]["knowledge_id"], 9)


if __name__ == "__main__":
    unittest.main()

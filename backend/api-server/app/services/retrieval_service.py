from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeItem
from app.services.chunk_retrieval_service import ChunkRetrievalService


@dataclass
class RetrievalHit:
    knowledge_id: int
    kb_id: int
    title: str
    document_name: str | None
    snippet: str
    source_url: str | None = None
    source_org: str | None = None
    source_meta: dict[str, Any] | None = None
    term_score: float = 0.0
    vector_score: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "kb_id": self.kb_id,
            "title": self.title,
            "document_name": self.document_name,
            "source_url": self.source_url,
            "source_org": self.source_org,
            "score": round(self.score, 4),
            "term_score": round(self.term_score, 4),
            "vector_score": round(self.vector_score, 4),
            "snippet": self.snippet,
        }

    def clone(self) -> "RetrievalHit":
        return RetrievalHit(
            knowledge_id=self.knowledge_id,
            kb_id=self.kb_id,
            title=self.title,
            document_name=self.document_name,
            snippet=self.snippet,
            source_url=self.source_url,
            source_org=self.source_org,
            source_meta=dict(self.source_meta or {}),
            term_score=self.term_score,
            vector_score=self.vector_score,
            score=self.score,
        )


class RetrievalService:
    SNIPPET_MAX_CHARS = 900

    DEFINITION_QUERY_PATTERNS = (
        "是什麼意思",
        "是什么意思",
        "代表什麼",
        "代表什么",
        "是什麼",
        "是甚麼",
    )
    DEFINITION_STOP_PATTERNS = (
        "在這個表裏",
        "在这个表里",
        "這個表裏",
        "这个表里",
        "在這個表中",
        "在这个表中",
        "這個表中",
        "这个表中",
        "在表裏",
        "在表里",
        "在表中",
        "這個表",
        "这个表",
        "該表",
        "该表",
        "表中的",
        "表中",
        "裏",
        "里",
    )

    def __init__(self, db: Session):
        self.db = db
        self.chunk_retrieval_service = ChunkRetrievalService(db)

    def retrieve(
        self,
        project_id: int,
        query: str,
        selected_kb_ids: list[int] | None = None,
        rewritten_query: str | None = None,
        scene_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if settings.USE_CHUNK_RETRIEVAL:
            chunk_hits = self.chunk_retrieval_service.retrieve(
                query=query,
                rewritten_query=rewritten_query,
                project_id=project_id,
                selected_kb_ids=selected_kb_ids,
                scene_state=scene_state,
                top_k=settings.CHUNK_RETRIEVAL_TOP_K,
            )
            if chunk_hits:
                return chunk_hits
        fusion_top_k = max(settings.RETRIEVAL_FUSION_TOP_K, settings.RETRIEVAL_TOP_K)
        term_hits = self._filter_governance_hits(self._term_search(project_id, query, selected_kb_ids, fusion_top_k))
        vector_hits = self._filter_governance_hits(self._vector_search(project_id, query, selected_kb_ids, fusion_top_k))

        merged_hits = self._merge_hits(term_hits, vector_hits)
        reranked_hits = self._rerank(query, merged_hits)
        if reranked_hits:
            return [item.to_dict() for item in reranked_hits[: settings.RETRIEVAL_TOP_K]]

        fallback_hits = self._filter_governance_hits(
            self._local_lexical_search(project_id, query, selected_kb_ids, settings.RETRIEVAL_TOP_K)
        )
        return [item.to_dict() for item in fallback_hits]

    def _term_search(
        self,
        project_id: int,
        query: str,
        selected_kb_ids: list[int] | None,
        top_k: int,
    ) -> list[RetrievalHit]:
        if settings.ELASTICSEARCH_URL:
            try:
                return self._elasticsearch_search(project_id, query, selected_kb_ids, top_k)
            except Exception:  # noqa: BLE001
                pass
        return self._local_lexical_search(project_id, query, selected_kb_ids, top_k)

    def _vector_search(
        self,
        project_id: int,
        query: str,
        selected_kb_ids: list[int] | None,
        top_k: int,
    ) -> list[RetrievalHit]:
        if not settings.VECTOR_SEARCH_URL:
            return []

        payload = {
            "query": query,
            "project_id": project_id,
            "kb_ids": selected_kb_ids or [],
            "top_k": top_k,
            "document_kind": "knowledge_item",
        }
        try:
            with httpx.Client(timeout=settings.VECTOR_TIMEOUT_SECONDS) as client:
                response = client.post(settings.VECTOR_SEARCH_URL, json=payload)
                response.raise_for_status()
                result = response.json()
        except Exception:  # noqa: BLE001
            return []

        records = result.get("data") if isinstance(result, dict) else result
        if not isinstance(records, list):
            return []

        hits: list[RetrievalHit] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            knowledge_id = record.get("knowledge_id")
            if not isinstance(knowledge_id, int):
                continue
            hits.append(
                RetrievalHit(
                    knowledge_id=knowledge_id,
                    kb_id=int(record.get("kb_id") or 0),
                    title=str(record.get("title") or ""),
                    document_name=str(record.get("document_name")) if record.get("document_name") else None,
                    snippet=str(record.get("snippet") or record.get("content") or "")[: self.SNIPPET_MAX_CHARS],
                    source_url=str(record.get("source_url")) if record.get("source_url") else None,
                    source_org=str(record.get("source_org")) if record.get("source_org") else None,
                    vector_score=float(record.get("score") or 0.0),
                )
            )
        return hits

    def _merge_hits(self, term_hits: list[RetrievalHit], vector_hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not term_hits and not vector_hits:
            return []

        merged: dict[int, RetrievalHit] = {}

        for rank, hit in enumerate(term_hits, start=1):
            existing = merged.get(hit.knowledge_id) or hit
            existing.term_score = max(existing.term_score, hit.term_score)
            existing.score += self._rrf(rank) + hit.term_score * 0.65
            merged[hit.knowledge_id] = existing

        for rank, hit in enumerate(vector_hits, start=1):
            existing = merged.get(hit.knowledge_id) or hit
            existing.vector_score = max(existing.vector_score, hit.vector_score)
            existing.score += self._rrf(rank) + hit.vector_score * 0.55
            if not existing.title:
                existing.title = hit.title
            if not existing.document_name:
                existing.document_name = hit.document_name
            if not existing.source_url:
                existing.source_url = hit.source_url
            if not existing.source_org:
                existing.source_org = hit.source_org
            if not existing.snippet:
                existing.snippet = hit.snippet
            merged[hit.knowledge_id] = existing

        return sorted(merged.values(), key=lambda item: item.score, reverse=True)

    def _rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []
        if settings.RERANK_URL:
            original_hits = [hit.clone() for hit in hits]
            reranked = self._remote_rerank(query, hits)
            if reranked:
                return self._protect_high_confidence_top1(original_hits, reranked)

        query_tokens = self._tokenize(query)
        for hit in hits:
            title_tokens = self._tokenize(hit.title)
            snippet_tokens = self._tokenize(hit.snippet)
            overlap = len(query_tokens & (title_tokens | snippet_tokens))
            density = overlap / max(len(query_tokens), 1)
            hit.score = (
                hit.score
                + density * 0.4
                + hit.term_score * 0.15
                + hit.vector_score * 0.1
                + self._definition_focus_boost(query=query, hit=hit)
            )
        return sorted(hits, key=lambda item: item.score, reverse=True)

    def _remote_rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        payload = {
            "query": query,
            "documents": [
                {
                    "knowledge_id": hit.knowledge_id,
                    "title": hit.title,
                    "content": hit.snippet,
                    "score": hit.score,
                }
                for hit in hits
            ],
        }
        try:
            with httpx.Client(timeout=settings.RERANK_TIMEOUT_SECONDS) as client:
                response = client.post(settings.RERANK_URL, json=payload)
                response.raise_for_status()
                result = response.json()
        except Exception:  # noqa: BLE001
            return []

        records = result.get("data") if isinstance(result, dict) else result
        if not isinstance(records, list):
            return []

        scored_hits: dict[int, float] = {}
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("knowledge_id"), int):
                scored_hits[int(record["knowledge_id"])] = float(record.get("score") or 0.0)

        if not scored_hits:
            return []

        for hit in hits:
            if hit.knowledge_id in scored_hits:
                hit.score = scored_hits[hit.knowledge_id]
        return sorted(hits, key=lambda item: item.score, reverse=True)

    def _protect_high_confidence_top1(
        self,
        original_hits: list[RetrievalHit],
        reranked_hits: list[RetrievalHit],
    ) -> list[RetrievalHit]:
        if not settings.RERANK_PROTECT_RAW_TOP1:
            return reranked_hits
        if len(original_hits) < 2 or len(reranked_hits) < 2:
            return reranked_hits

        original_top1 = original_hits[0]
        original_top2 = original_hits[1]
        reranked_top1 = reranked_hits[0]
        if reranked_top1.knowledge_id == original_top1.knowledge_id:
            return reranked_hits

        original_margin = original_top1.score - original_top2.score
        if original_top1.score < settings.RERANK_PROTECT_MIN_SCORE:
            return reranked_hits
        if original_margin < settings.RERANK_PROTECT_MIN_MARGIN:
            return reranked_hits

        protected_hit = next((hit for hit in reranked_hits if hit.knowledge_id == original_top1.knowledge_id), None)
        if protected_hit is None:
            return reranked_hits

        protected_hit.score = max(
            reranked_top1.score,
            protected_hit.score,
            original_top1.score,
        ) + settings.RERANK_PROTECT_SCORE_EPSILON
        return sorted(reranked_hits, key=lambda item: item.score, reverse=True)

    def _elasticsearch_search(
        self,
        project_id: int,
        query: str,
        selected_kb_ids: list[int] | None,
        top_k: int,
    ) -> list[RetrievalHit]:
        filters: list[dict[str, Any]] = [
            {"term": {"project_id": project_id}},
            {"term": {"status": "active"}},
            {
                "bool": {
                    "should": [
                        {"term": {"document_kind": "knowledge_item"}},
                        {"bool": {"must_not": {"exists": {"field": "document_kind"}}}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        ]
        if selected_kb_ids:
            filters.append({"terms": {"kb_id": selected_kb_ids}})

        payload = {
            "size": top_k,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^4", "keywords^2", "content"],
                            "type": "best_fields",
                        }
                    },
                }
            },
            "_source": ["knowledge_id", "kb_id", "title", "document_name", "content", "source_url", "source_org"],
        }
        auth = None
        if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
            auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

        url = f"{settings.ELASTICSEARCH_URL.rstrip('/')}/{settings.ELASTICSEARCH_INDEX}/_search"
        with httpx.Client(timeout=settings.ELASTICSEARCH_TIMEOUT_SECONDS, auth=auth) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        hits = result.get("hits", {}).get("hits", [])
        score_max = max((float(item.get("_score") or 0.0) for item in hits), default=1.0)
        return [
            RetrievalHit(
                knowledge_id=int(item.get("_source", {}).get("knowledge_id") or 0),
                kb_id=int(item.get("_source", {}).get("kb_id") or 0),
                title=str(item.get("_source", {}).get("title") or ""),
                document_name=(
                    str(item.get("_source", {}).get("document_name"))
                    if item.get("_source", {}).get("document_name")
                    else None
                ),
                source_url=(
                    str(item.get("_source", {}).get("source_url"))
                    if item.get("_source", {}).get("source_url")
                    else None
                ),
                source_org=(
                    str(item.get("_source", {}).get("source_org"))
                    if item.get("_source", {}).get("source_org")
                    else None
                ),
                snippet=str(item.get("_source", {}).get("content") or "")[: self.SNIPPET_MAX_CHARS],
                term_score=round(float(item.get("_score") or 0.0) / max(score_max, 1e-6), 4),
            )
            for item in hits
            if int(item.get("_source", {}).get("knowledge_id") or 0) > 0
        ]

    def _local_lexical_search(
        self,
        project_id: int,
        query: str,
        selected_kb_ids: list[int] | None,
        top_k: int,
    ) -> list[RetrievalHit]:
        db_query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.status == "active",
            KnowledgeItem.governance_status == "active",
        )
        if selected_kb_ids:
            db_query = db_query.filter(KnowledgeItem.kb_id.in_(selected_kb_ids))
        items = db_query.order_by(KnowledgeItem.updated_at.desc()).all()

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        hits: list[RetrievalHit] = []
        for item in items:
            haystack = " ".join(
                [
                    item.title or "",
                    item.content or "",
                    " ".join(item.keywords_json or []),
                ]
            ).lower()
            overlap = sum(1 for token in query_tokens if token in haystack)
            if overlap <= 0 and query.lower() not in haystack:
                continue
            normalized_score = min(overlap / max(len(query_tokens), 1) + 0.25, 0.99)
            if normalized_score < settings.RETRIEVAL_MIN_SCORE:
                continue
            hits.append(
                RetrievalHit(
                    knowledge_id=item.id,
                    kb_id=item.kb_id,
                    title=item.title,
                    document_name=item.document_name,
                    snippet=item.content[: self.SNIPPET_MAX_CHARS],
                    source_url=item.source_url,
                    source_org=item.source_org,
                    source_meta=item.source_meta_json or {},
                    term_score=round(normalized_score + self._definition_focus_boost_for_item(query, item), 4),
                    score=round(normalized_score + self._definition_focus_boost_for_item(query, item), 4),
                )
            )
        return sorted(hits, key=lambda item: item.score, reverse=True)[:top_k]

    def _rrf(self, rank: int) -> float:
        return 1.0 / (60 + rank)

    def _filter_governance_hits(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []
        allowed_ids = {
            item_id
            for item_id, in self.db.query(KnowledgeItem.id)
            .filter(
                KnowledgeItem.id.in_([hit.knowledge_id for hit in hits]),
                KnowledgeItem.governance_status == "active",
            )
            .all()
        }
        return [hit for hit in hits if hit.knowledge_id in allowed_ids]

    def _tokenize(self, text: str) -> set[str]:
        normalized = text.lower().strip()
        if not normalized:
            return set()

        tokens = {token for token in re.split(r"[\s,，。！？；：、/()（）]+", normalized) if token}
        for token in list(tokens):
            if len(token) <= 1:
                continue
            if re.search(r"[\u4e00-\u9fff]", token):
                tokens.update(token[index : index + 2] for index in range(len(token) - 1))
        return {token for token in tokens if token}

    def _definition_focus_boost_for_item(self, query: str, item: KnowledgeItem) -> float:
        hit = RetrievalHit(
            knowledge_id=item.id,
            kb_id=item.kb_id,
            title=item.title,
            document_name=item.document_name,
            snippet=item.content[: self.SNIPPET_MAX_CHARS],
            source_url=item.source_url,
            source_org=item.source_org,
            source_meta=item.source_meta_json or {},
        )
        return self._definition_focus_boost(query=query, hit=hit)

    def _definition_focus_boost(self, query: str, hit: RetrievalHit) -> float:
        if not self._is_definition_query(query):
            return 0.0
        focus_candidates = self._extract_definition_focus_candidates(query)
        if not focus_candidates:
            return 0.0

        meta = hit.source_meta or {}
        ingest_kind = str(meta.get("ingest_kind") or "").strip().lower()
        meta_kind = str(meta.get("meta_kind") or "").strip().lower()
        searchable_candidates = [
            hit.title,
            hit.snippet,
            meta.get("column_label"),
            meta.get("column_label_en"),
            meta.get("footnote_marker"),
            meta.get("row_label"),
            meta.get("definition"),
            meta.get("meaning"),
        ]
        normalized_candidates = [
            self._normalize_focus_text(str(candidate))
            for candidate in searchable_candidates
            if str(candidate or "").strip()
        ]
        if not normalized_candidates:
            return 0.0
        context_tokens = self._extract_definition_context_tokens(query, focus_candidates)
        context_haystack = self._normalize_focus_text(
            " ".join(
                str(value or "")
                for value in [
                    hit.title,
                    hit.document_name,
                    hit.snippet,
                    meta.get("table_title"),
                    meta.get("definition"),
                    meta.get("meaning"),
                ]
            )
        )

        boost = 0.0
        for focus in focus_candidates:
            exact_match = any(focus == candidate for candidate in normalized_candidates)
            partial_match = any(focus in candidate or candidate in focus for candidate in normalized_candidates)
            if exact_match:
                if ingest_kind == "structured_table_meta":
                    boost = max(boost, 1.1)
                elif ingest_kind.startswith("structured_table"):
                    boost = max(boost, 0.7)
                else:
                    boost = max(boost, 0.35)
                continue
            if partial_match:
                if ingest_kind == "structured_table_meta":
                    boost = max(boost, 0.62)
                elif meta_kind in {"column_definition", "footnote_definition"}:
                    boost = max(boost, 0.45)
                else:
                    boost = max(boost, 0.2)
        if context_tokens:
            context_overlap = sum(1 for token in context_tokens if token in context_haystack)
            if context_overlap > 0:
                boost += min(0.75, context_overlap / max(len(context_tokens), 1) * 0.75)
            else:
                boost -= 0.3
        return boost

    def _is_definition_query(self, query: str) -> bool:
        normalized = self._normalize_focus_text(query)
        return any(pattern in normalized for pattern in self.DEFINITION_QUERY_PATTERNS)

    def _extract_definition_focus_candidates(self, query: str) -> list[str]:
        normalized_query = query.strip()
        focus_candidates: list[str] = []

        quoted_candidates = re.findall(r"[「“\"']([^」”\"']{1,40})[」”\"']", normalized_query)
        focus_candidates.extend(quoted_candidates)

        definition_pattern = "|".join(re.escape(pattern) for pattern in self.DEFINITION_QUERY_PATTERNS)
        symbolic_matches = re.findall(
            rf"([A-Za-z0-9][A-Za-z0-9+*/%._-]{{0,30}})\s*(?:{definition_pattern})",
            normalized_query,
            flags=re.IGNORECASE,
        )
        focus_candidates.extend(symbolic_matches)
        focus_candidates.extend(re.findall(r"\*{1,4}", normalized_query))
        focus_candidates.extend(
            re.findall(r"[A-Za-z0-9]+(?:[+*/%._-][A-Za-z0-9*%._-]+)+", normalized_query, flags=re.IGNORECASE)
        )

        cleaned = normalized_query
        for pattern in [*self.DEFINITION_QUERY_PATTERNS, *self.DEFINITION_STOP_PATTERNS]:
            cleaned = re.sub(re.escape(pattern), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[「」“”\"'：:？?（）()\[\],，。!！/\\]+", " ", cleaned)
        cleaned = " ".join(cleaned.split()).strip()
        if cleaned and len(cleaned) <= 20:
            focus_candidates.append(cleaned)

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in focus_candidates:
            normalized_candidate = self._normalize_focus_text(candidate)
            if not normalized_candidate or normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            deduped.append(normalized_candidate)
        return sorted(deduped, key=len, reverse=True)

    def _normalize_focus_text(self, text: str) -> str:
        normalized = " ".join(str(text or "").strip().lower().split())
        if not normalized:
            return ""
        normalized = normalized.replace("“", "").replace("”", "").replace("「", "").replace("」", "")
        return normalized

    def _extract_definition_context_tokens(self, query: str, focus_candidates: list[str]) -> list[str]:
        cleaned = query
        for pattern in [*self.DEFINITION_QUERY_PATTERNS, *self.DEFINITION_STOP_PATTERNS]:
            cleaned = re.sub(re.escape(pattern), " ", cleaned, flags=re.IGNORECASE)
        for focus in focus_candidates:
            if focus:
                cleaned = re.sub(re.escape(focus), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[「」“”\"'：:？?（）()\[\],，。!！/\\]+", " ", cleaned)
        tokens = [token for token in self._tokenize(cleaned) if len(token.strip()) >= 2]
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped[:8]

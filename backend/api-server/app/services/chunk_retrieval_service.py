from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import ChunkRelation, KnowledgeChunk, KnowledgeItem


@dataclass
class RetrievalFilters:
    project_id: int
    kb_ids: list[int]
    status: str = "active"
    region: str | None = None
    route_kind: str | None = None
    subject_type: str | None = None


@dataclass
class ChunkHit:
    chunk_id: int
    knowledge_id: int
    kb_id: int
    source_kind: str
    source_item_id: int | None
    file_id: int | None
    title: str
    document_name: str | None
    snippet: str
    lexical_text: str
    contextual_text: str
    citation_text: str | None
    chunk_meta: dict[str, Any]
    authority_level: int
    source_rank: float
    source_url: str | None = None
    source_org: str | None = None
    term_score: float = 0.0
    vector_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "knowledge_id": self.knowledge_id,
            "kb_id": self.kb_id,
            "source_kind": self.source_kind,
            "source_item_id": self.source_item_id,
            "file_id": self.file_id,
            "title": self.title,
            "document_name": self.document_name,
            "snippet": self.snippet,
            "source_url": self.source_url,
            "source_org": self.source_org,
            "citation_text": self.citation_text,
            "contextual_text": self.contextual_text,
            "chunk_meta": self.chunk_meta,
            "authority_level": self.authority_level,
            "score": round(self.final_score or self.rerank_score or self.fused_score, 4),
            "term_score": round(self.term_score, 4),
            "vector_score": round(self.vector_score, 4),
        }


class ChunkRetrievalService:
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

    def retrieve(
        self,
        *,
        query: str,
        rewritten_query: str | None,
        project_id: int,
        selected_kb_ids: list[int] | None = None,
        scene_state: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = self._infer_filters(
            query=query,
            scene_state=scene_state or {},
            selected_kb_ids=selected_kb_ids or [],
            project_id=project_id,
        )
        term_hits = self._term_search(query, filters, top_k=max(settings.CHUNK_RERANK_TOP_K * 2, 12))
        vector_hits = self._vector_search(rewritten_query or query, filters, top_k=max(settings.CHUNK_RERANK_TOP_K * 2, 12))
        fused = self._rrf_merge(term_hits, vector_hits)
        if not fused and (filters.route_kind or filters.subject_type):
            relaxed_filters = RetrievalFilters(
                project_id=filters.project_id,
                kb_ids=filters.kb_ids,
                status=filters.status,
                region=filters.region,
            )
            term_hits = self._term_search(query, relaxed_filters, top_k=max(settings.CHUNK_RERANK_TOP_K * 2, 12))
            vector_hits = self._vector_search(rewritten_query or query, relaxed_filters, top_k=max(settings.CHUNK_RERANK_TOP_K * 2, 12))
            fused = self._rrf_merge(term_hits, vector_hits)
        expanded = self._expand_neighbors(fused[: max(settings.CHUNK_RERANK_TOP_K, 8)], per_side=1)
        reranked = self._structured_rerank(query=query, hits=expanded)
        final_hits = self._pack_final_evidence(reranked, top_k=top_k or settings.CHUNK_RETRIEVAL_TOP_K)
        return [item.to_dict() for item in final_hits]

    def _infer_filters(
        self,
        query: str,
        scene_state: dict[str, Any],
        selected_kb_ids: list[int],
        project_id: int,
    ) -> RetrievalFilters:
        lowered = query.strip().lower()
        route_kind = scene_state.get("route_kind")
        subject_type = scene_state.get("subject_type")
        if not route_kind and "地址" in query and ("更改" in query or "變更" in query or "变更" in query):
            route_kind = "address_change"
        if not subject_type:
            if "公司" in query or "業務" in query or "业务" in query:
                subject_type = "company"
            elif "個人" in query or "个人" in query or "通訊地址" in query or "通讯地址" in query:
                subject_type = "individual"
        region = "HK"
        if "澳门" in lowered or "macau" in lowered:
            region = "MO"
        if "內地" in query or "内地" in query:
            region = "CN"
        return RetrievalFilters(
            project_id=project_id,
            kb_ids=selected_kb_ids,
            region=region,
            route_kind=route_kind,
            subject_type=subject_type,
        )

    def _base_query(self, filters: RetrievalFilters):
        query = (
            self.db.query(KnowledgeChunk)
            .outerjoin(KnowledgeItem, KnowledgeItem.id == KnowledgeChunk.source_item_id)
            .filter(
                KnowledgeChunk.project_id == filters.project_id,
                KnowledgeChunk.status == filters.status,
                KnowledgeChunk.is_active.is_(True),
                (KnowledgeChunk.source_item_id.is_(None)) | (KnowledgeItem.governance_status == "active"),
            )
        )
        if filters.kb_ids:
            query = query.filter(KnowledgeChunk.kb_id.in_(filters.kb_ids))
        if filters.region:
            query = query.filter((KnowledgeChunk.region == filters.region) | (KnowledgeChunk.region.is_(None)))
        if filters.route_kind:
            query = query.filter((KnowledgeChunk.route_kind == filters.route_kind) | (KnowledgeChunk.route_kind.is_(None)))
        if filters.subject_type:
            query = query.filter(
                (KnowledgeChunk.subject_type == filters.subject_type) | (KnowledgeChunk.subject_type.is_(None))
            )
        return query

    def _term_search(self, query: str, filters: RetrievalFilters, top_k: int) -> list[ChunkHit]:
        rows = self._base_query(filters).order_by(KnowledgeChunk.updated_at.desc()).all()
        tokens = self._tokenize(query)
        if not tokens:
            return []
        hits: list[ChunkHit] = []
        for row in rows:
            haystack = " ".join([row.title or "", row.lexical_text or ""]).lower()
            overlap = sum(1 for token in tokens if token in haystack)
            if overlap <= 0 and query.lower() not in haystack:
                continue
            hit = self._to_hit(row)
            term_score = min(overlap / max(len(tokens), 1) + 0.25, 0.99)
            term_score += self._definition_focus_boost(query=query, hit=hit)
            hit = self._to_hit(row)
            hit.term_score = round(term_score, 4)
            hit.fused_score = hit.term_score
            hits.append(hit)
        return sorted(hits, key=lambda item: item.term_score, reverse=True)[:top_k]

    def _vector_search(self, query: str, filters: RetrievalFilters, top_k: int) -> list[ChunkHit]:
        if settings.VECTOR_SEARCH_URL:
            remote_hits = self._remote_vector_search(query, filters, top_k)
            if remote_hits:
                return remote_hits
        rows = self._base_query(filters).order_by(KnowledgeChunk.updated_at.desc()).all()
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        hits: list[ChunkHit] = []
        for row in rows:
            contextual_tokens = self._tokenize(f"{row.title} {row.contextual_text}")
            overlap = len(query_tokens & contextual_tokens)
            if overlap <= 0:
                continue
            hit = self._to_hit(row)
            semantic_score = min(overlap / max(len(query_tokens), 1) + 0.15, 0.95)
            semantic_score += self._definition_focus_boost(query=query, hit=hit)
            hit = self._to_hit(row)
            hit.vector_score = round(semantic_score, 4)
            hit.fused_score = hit.vector_score
            hits.append(hit)
        return sorted(hits, key=lambda item: item.vector_score, reverse=True)[:top_k]

    def _remote_vector_search(self, query: str, filters: RetrievalFilters, top_k: int) -> list[ChunkHit]:
        payload = {
            "query": query,
            "project_id": filters.project_id,
            "kb_ids": filters.kb_ids or [],
            "top_k": max(top_k * 2, 12),
            "document_kind": "knowledge_chunk",
        }
        try:
            with httpx.Client(timeout=settings.VECTOR_TIMEOUT_SECONDS) as client:
                response = client.post(settings.VECTOR_SEARCH_URL, json=payload)
                response.raise_for_status()
                result = response.json()
        except Exception:
            return []

        records = result.get("data") if isinstance(result, dict) else result
        if not isinstance(records, list):
            return []

        chunk_ids: list[int] = []
        score_map: dict[int, float] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            chunk_id = record.get("chunk_id")
            metadata = record.get("metadata") or {}
            if not isinstance(chunk_id, int):
                chunk_id = metadata.get("chunk_id")
            if not isinstance(chunk_id, int) or chunk_id <= 0:
                continue
            chunk_ids.append(chunk_id)
            score_map[chunk_id] = max(score_map.get(chunk_id, 0.0), float(record.get("score") or 0.0))

        if not chunk_ids:
            return []

        rows = (
            self._base_query(filters)
            .filter(KnowledgeChunk.id.in_(sorted(set(chunk_ids))))
            .all()
        )
        row_map = {int(row.id): row for row in rows}
        hits: list[ChunkHit] = []
        for chunk_id in chunk_ids:
            row = row_map.get(chunk_id)
            if row is None:
                continue
            hit = self._to_hit(row)
            hit.vector_score = round(score_map.get(chunk_id, 0.0), 4)
            hit.fused_score = hit.vector_score
            hits.append(hit)
        return sorted(hits, key=lambda item: item.vector_score, reverse=True)[:top_k]

    def _rrf_merge(self, term_hits: list[ChunkHit], vector_hits: list[ChunkHit], k: int = 60) -> list[ChunkHit]:
        score_map: dict[int, ChunkHit] = {}

        def upsert(hit: ChunkHit) -> ChunkHit:
            existing = score_map.get(hit.chunk_id)
            if existing is not None:
                existing.term_score = max(existing.term_score, hit.term_score)
                existing.vector_score = max(existing.vector_score, hit.vector_score)
                return existing
            score_map[hit.chunk_id] = hit
            return hit

        for rank, hit in enumerate(term_hits, start=1):
            item = upsert(hit)
            item.fused_score += 1.0 / (k + rank)

        for rank, hit in enumerate(vector_hits, start=1):
            item = upsert(hit)
            item.fused_score += 1.0 / (k + rank)

        for item in score_map.values():
            item.final_score = item.fused_score + self._authority_boost(item) + self._source_kind_bias(item)
        return sorted(score_map.values(), key=lambda item: item.final_score, reverse=True)

    def _expand_neighbors(self, hits: list[ChunkHit], per_side: int = 1) -> list[ChunkHit]:
        if not hits:
            return []
        expanded: dict[int, ChunkHit] = {item.chunk_id: item for item in hits}
        for hit in hits:
            relations = (
                self.db.query(ChunkRelation)
                .filter(
                    ChunkRelation.from_chunk_id == hit.chunk_id,
                    ChunkRelation.relation_type.in_(["prev", "next", "same_section"]),
                )
                .limit(max(3, per_side * 3))
                .all()
            )
            for relation in relations:
                if relation.to_chunk_id in expanded:
                    continue
                neighbor = self.db.query(KnowledgeChunk).filter(KnowledgeChunk.id == relation.to_chunk_id).first()
                if not neighbor or neighbor.status != "active" or not neighbor.is_active:
                    continue
                expanded[neighbor.id] = self._to_hit(neighbor)
        return list(expanded.values())

    def _structured_rerank(self, query: str, hits: list[ChunkHit]) -> list[ChunkHit]:
        if not hits:
            return []
        if settings.RERANK_URL:
            reranked = self._remote_rerank(query, hits)
            if reranked:
                return self._promote_primary_file_evidence(reranked)

        query_tokens = self._tokenize(query)
        for hit in hits:
            content_tokens = self._tokenize(self._format_for_rerank(hit))
            overlap = len(query_tokens & content_tokens)
            hit.rerank_score = round(
                hit.final_score
                + overlap / max(len(query_tokens), 1)
                + self._definition_focus_boost(query=query, hit=hit),
                4,
            )
        ranked = sorted(hits, key=lambda item: (item.rerank_score, item.final_score), reverse=True)
        return self._promote_primary_file_evidence(ranked)

    def _remote_rerank(self, query: str, hits: list[ChunkHit]) -> list[ChunkHit]:
        payload = {
            "query": query,
            "documents": [
                {
                    "chunk_id": hit.chunk_id,
                    "content": self._format_for_rerank(hit),
                    "score": hit.final_score,
                }
                for hit in hits
            ],
        }
        try:
            with httpx.Client(timeout=settings.RERANK_TIMEOUT_SECONDS) as client:
                response = client.post(settings.RERANK_URL, json=payload)
                response.raise_for_status()
                result = response.json()
        except Exception:
            return []

        records = result.get("data") if isinstance(result, dict) else result
        if not isinstance(records, list):
            return []
        scores = {
            int(record["chunk_id"]): float(record.get("score") or 0.0)
            for record in records
            if isinstance(record, dict) and record.get("chunk_id") is not None
        }
        if not scores:
            return []
        for hit in hits:
            if hit.chunk_id in scores:
                hit.rerank_score = scores[hit.chunk_id]
        return sorted(hits, key=lambda item: (item.rerank_score, item.final_score), reverse=True)

    def _pack_final_evidence(self, hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
        final_hits: list[ChunkHit] = []
        seen_signatures: set[tuple[Any, ...]] = set()
        for hit in hits:
            signature = self._build_evidence_signature(hit)
            if signature in seen_signatures:
                continue
            if (
                hit.source_kind == "file_qa"
                and not settings.FILE_QA_ALLOWED_AS_SOLO_EVIDENCE
                and len([item for item in final_hits if item.source_kind != "file_qa"]) >= 2
            ):
                continue
            final_hits.append(hit)
            seen_signatures.add(signature)
            if len(final_hits) >= top_k:
                break
        return final_hits

    def _build_evidence_signature(self, hit: ChunkHit) -> tuple[Any, ...]:
        meta = hit.chunk_meta or {}
        ingest_kind = str(meta.get("ingest_kind") or "").strip().lower()
        if ingest_kind.startswith("structured_table"):
            semantic_key = (
                meta.get("meta_kind")
                or meta.get("column_key")
                or meta.get("column_label")
                or meta.get("footnote_marker")
                or meta.get("row_label")
                or meta.get("row_index")
                or hit.source_item_id
                or hit.chunk_id
            )
            return (
                hit.file_id if hit.file_id is not None else (hit.source_item_id or hit.chunk_id),
                hit.source_kind,
                ingest_kind,
                meta.get("table_kind"),
                semantic_key,
            )
        primary_anchor = hit.file_id if hit.file_id is not None else (hit.source_item_id or hit.chunk_id)
        return (
            primary_anchor,
            tuple(meta.get("page_numbers") or []),
            tuple(meta.get("heading_path") or []),
            hit.source_kind,
        )

    def _promote_primary_file_evidence(self, hits: list[ChunkHit]) -> list[ChunkHit]:
        if not hits:
            return []
        top = hits[0]
        if top.source_kind != "file_qa" or top.file_id is None:
            return hits
        replacement = next(
            (item for item in hits[1:] if item.file_id == top.file_id and item.source_kind in {"file", "manual"}),
            None,
        )
        if replacement is None:
            return hits
        replacement.rerank_score = max(replacement.rerank_score, top.rerank_score) + 0.0001
        return sorted(hits, key=lambda item: (item.rerank_score, item.final_score), reverse=True)

    def _format_for_rerank(self, hit: ChunkHit) -> str:
        meta = hit.chunk_meta or {}
        section = " > ".join(meta.get("heading_path") or [])
        pages = meta.get("page_numbers") or []
        row_range = meta.get("row_range") or []
        return "\n".join(
            [
                f"title: {hit.title}",
                f"source_kind: {hit.source_kind}",
                f"document_name: {hit.document_name or ''}",
                f"section: {section}",
                f"page_numbers: {pages}",
                f"row_range: {row_range}",
                f"ingest_kind: {meta.get('ingest_kind') or ''}",
                f"meta_kind: {meta.get('meta_kind') or ''}",
                f"table_title: {meta.get('table_title') or ''}",
                f"column_label: {meta.get('column_label') or ''}",
                f"column_label_en: {meta.get('column_label_en') or ''}",
                f"footnote_marker: {meta.get('footnote_marker') or ''}",
                f"row_label: {meta.get('row_label') or ''}",
                f"group_path: {' > '.join(meta.get('group_path') or [])}",
                f"row_aliases: {' '.join(meta.get('row_aliases') or [])}",
                f"authority_level: {hit.authority_level}",
                f"text: {hit.contextual_text}",
            ]
        )

    def _definition_focus_boost(self, query: str, hit: ChunkHit) -> float:
        if not self._is_definition_query(query):
            return 0.0
        focus_candidates = self._extract_definition_focus_candidates(query)
        if not focus_candidates:
            return 0.0

        meta = hit.chunk_meta or {}
        ingest_kind = str(meta.get("ingest_kind") or "").strip().lower()
        meta_kind = str(meta.get("meta_kind") or "").strip().lower()
        searchable_candidates = [
            hit.title,
            hit.lexical_text,
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
                    hit.lexical_text,
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
                    boost = max(boost, 1.25)
                elif ingest_kind.startswith("structured_table"):
                    boost = max(boost, 0.8)
                else:
                    boost = max(boost, 0.45)
                continue
            if partial_match:
                if ingest_kind == "structured_table_meta":
                    boost = max(boost, 0.72)
                elif meta_kind in {"column_definition", "footnote_definition"}:
                    boost = max(boost, 0.5)
                else:
                    boost = max(boost, 0.25)
        if context_tokens:
            context_overlap = sum(1 for token in context_tokens if token in context_haystack)
            if context_overlap > 0:
                boost += min(0.85, context_overlap / max(len(context_tokens), 1) * 0.85)
            else:
                boost -= 0.35
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

    def _authority_boost(self, hit: ChunkHit) -> float:
        if hit.authority_level >= 100:
            return 0.2
        if hit.authority_level >= 80:
            return 0.12
        if hit.authority_level <= 30:
            return -0.18
        return 0.0

    def _source_kind_bias(self, hit: ChunkHit) -> float:
        if hit.source_kind == "official_web":
            return 0.12
        if hit.source_kind == "file":
            return 0.08
        if hit.source_kind == "manual":
            return 0.04
        if hit.source_kind == "file_qa":
            return -0.12
        return 0.0

    def _to_hit(self, row: KnowledgeChunk) -> ChunkHit:
        snippet = (row.citation_text or row.contextual_text or "")[:220]
        meta = row.chunk_meta_json or {}
        return ChunkHit(
            chunk_id=row.id,
            knowledge_id=int(row.source_item_id or row.id),
            kb_id=row.kb_id,
            source_kind=row.source_kind,
            source_item_id=row.source_item_id,
            file_id=row.file_id,
            title=row.title,
            document_name=row.document_name,
            snippet=snippet,
            source_url=str(meta.get("source_url")) if meta.get("source_url") else None,
            source_org=str(meta.get("source_org")) if meta.get("source_org") else None,
            lexical_text=row.lexical_text,
            contextual_text=row.contextual_text,
            citation_text=row.citation_text,
            chunk_meta=meta,
            authority_level=int(row.authority_level or 0),
            source_rank=float(row.source_rank or 1.0),
        )

    def _tokenize(self, text: str) -> set[str]:
        normalized = text.lower().strip()
        if not normalized:
            return set()
        tokens = {token for token in re.split(r"[\s,，。！？；：、/()（）\[\]\n:]+", normalized) if token}
        for token in list(tokens):
            if len(token) <= 1:
                continue
            if re.search(r"[\u4e00-\u9fff]", token):
                tokens.update(token[index : index + 2] for index in range(len(token) - 1))
        return {token for token in tokens if token}

from __future__ import annotations

import re
from typing import Any

from app.services.address.parsers.local_address_parser import LocalAddressParser
from app.services.address.schemas import LocalParseResult
from app.services.address.providers.als_client import AlsClient
from app.services.address.schemas import AddressResolveResult, AlsCandidate


class AddressResolverService:
    def __init__(
        self,
        local_parser: LocalAddressParser | None = None,
        als_client: AlsClient | None = None,
        enable_als: bool = True,
    ) -> None:
        self.local_parser = local_parser or LocalAddressParser()
        self.als_client = als_client or AlsClient()
        self.enable_als = enable_als

    def resolve(
        self,
        raw_address: str,
        structured_hint: dict[str, Any] | None = None,
    ) -> AddressResolveResult:
        local = self.local_parser.parse(raw_address, structured_hint)
        normalized_hint = self.local_parser.normalize_structured(structured_hint)
        partial_structured = local.heuristic_structured or normalized_hint
        is_actual_address = self.local_parser.looks_like_actual_address_text(local.normalized_address)
        is_partial_address = self.local_parser.looks_like_partial_address_text(local.normalized_address)

        if not local.normalized_address:
            return self._empty_result()
        if not is_actual_address:
            partial_score = self._structured_score(partial_structured)
            return AddressResolveResult(
                normalized_address=local.normalized_address,
                address_structured=partial_structured,
                confidence="low" if partial_score >= 1 else "",
                source="heuristic_partial" if is_partial_address and partial_structured else ("provided" if normalized_hint else "none"),
                is_complete=False,
                pdf_parts=self._build_pdf_parts(partial_structured, local.pdf_parts),
                structured_count=partial_score,
                source_chain=["heuristic"] if is_partial_address and partial_structured else [],
            )

        candidates = self.als_client.search(local.official_query) if self.enable_als and local.official_query else []
        best_candidate = self._pick_best_als_candidate(local, candidates)
        merged_structured = self._merge_structured(local.heuristic_structured, normalized_hint, best_candidate)
        pdf_parts = self._build_pdf_parts(merged_structured, local.pdf_parts)
        confidence = self._compute_confidence(best_candidate, candidates, merged_structured)
        needs_confirmation, confirmation_reason = self._compute_confirmation(best_candidate, candidates, local.unit_parts)

        geo = self._build_geo(best_candidate)
        official = self._build_official(best_candidate, candidates)
        normalized_address = best_candidate.full_address_zh if best_candidate and best_candidate.full_address_zh else local.normalized_address
        source_chain = ["heuristic"]
        if best_candidate:
            source_chain.append("als")

        return AddressResolveResult(
            normalized_address=normalized_address,
            address_structured=merged_structured,
            pdf_parts=pdf_parts,
            confidence=confidence,
            source="official_merged" if best_candidate else "heuristic",
            is_complete=self._estimate_completeness(normalized_address, merged_structured, pdf_parts),
            structured_count=self._structured_score(merged_structured),
            official=official,
            geo=geo,
            needs_confirmation=needs_confirmation,
            confirmation_reason=confirmation_reason,
            candidate_options=self._build_candidate_options(candidates),
            source_chain=source_chain,
        )

    def _empty_result(self) -> AddressResolveResult:
        return AddressResolveResult(
            normalized_address="",
            address_structured=None,
            pdf_parts=self._empty_pdf_parts(),
            confidence="",
            source="none",
            is_complete=False,
            structured_count=0,
        )

    def _pick_best_als_candidate(
        self,
        local: LocalParseResult,
        candidates: list[AlsCandidate],
    ) -> AlsCandidate | None:
        if not candidates:
            return None

        target_block = str(local.unit_parts.get("block") or "").strip()
        scored: list[tuple[float, AlsCandidate]] = []
        for candidate in candidates:
            score = candidate.score
            score += self._query_alignment_score(local, candidate)
            if target_block:
                if candidate.block == target_block:
                    score += 20
                elif candidate.block and candidate.block != target_block:
                    score -= 15
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] < 35:
            return None
        return scored[0][1]

    def _merge_structured(
        self,
        heuristic_structured: dict[str, str] | None,
        structured_hint: dict[str, str] | None,
        candidate: AlsCandidate | None,
    ) -> dict[str, str] | None:
        merged: dict[str, str] = {}
        for source in [structured_hint or {}, heuristic_structured or {}]:
            for key, value in source.items():
                if value and key not in merged:
                    merged[key] = value

        if candidate:
            official_values = {
                "area": candidate.area,
                "district": candidate.district,
                "street": candidate.street,
                "building": candidate.building,
            }
            for key, value in official_values.items():
                if value:
                    merged[key] = value
            if not merged.get("block") and candidate.block:
                merged["block"] = candidate.block

        return merged or None

    def _build_pdf_parts(
        self,
        structured: dict[str, str] | None,
        fallback_pdf_parts: dict[str, str],
    ) -> dict[str, str]:
        if not structured:
            return fallback_pdf_parts
        merged = self._empty_pdf_parts()
        mapping = {
            "area": "area",
            "flat_room": "flat_room",
            "block": "block",
            "floor": "floor",
            "building": "line1",
            "street": "line2",
            "district": "line3",
        }
        for source_key, target_key in mapping.items():
            raw = structured.get(source_key)
            if raw:
                merged[target_key] = raw[:80]
        for key, value in fallback_pdf_parts.items():
            if not merged.get(key):
                merged[key] = value
        return merged

    def _build_official(self, candidate: AlsCandidate | None, candidates: list[AlsCandidate]) -> dict[str, Any]:
        if not candidate:
            return {
                "als_matched": False,
                "candidate_count": len(candidates),
                "match_quality": "none",
                "standardized_address_zh": "",
                "standardized_address_en": "",
            }
        return {
            "als_matched": True,
            "candidate_count": len(candidates),
            "match_quality": self._official_match_quality(candidate, candidates),
            "standardized_address_zh": candidate.full_address_zh,
            "standardized_address_en": candidate.full_address_en,
            "selected_score": candidate.score,
        }

    def _build_geo(self, candidate: AlsCandidate | None) -> dict[str, Any]:
        if not candidate or candidate.latitude is None or candidate.longitude is None:
            return {"matched": False, "provider": "als"}
        return {
            "matched": True,
            "provider": "als",
            "lat": candidate.latitude,
            "lng": candidate.longitude,
            "place_name": candidate.building or candidate.full_address_zh,
        }

    def _build_candidate_options(self, candidates: list[AlsCandidate]) -> list[dict[str, Any]]:
        return [
            {
                "label": candidate.full_address_zh or candidate.building or candidate.street,
                "building": candidate.building,
                "street": candidate.street,
                "district": candidate.district,
                "block": candidate.block,
                "score": candidate.score,
            }
            for candidate in candidates[:3]
        ]

    def _compute_confidence(
        self,
        best_candidate: AlsCandidate | None,
        candidates: list[AlsCandidate],
        structured: dict[str, str] | None,
    ) -> str:
        if not best_candidate:
            score = self._structured_score(structured)
            if score >= 3:
                return "medium"
            if score >= 1:
                return "low"
            return ""

        if len(candidates) == 1 and best_candidate.score >= 60:
            return "high"
        if len(candidates) >= 2:
            sorted_scores = sorted((candidate.score for candidate in candidates), reverse=True)
            if sorted_scores[0] - sorted_scores[1] >= 8 and sorted_scores[0] >= 60:
                return "high"
        if best_candidate.score >= 50:
            return "medium"
        return "low"

    def _compute_confirmation(
        self,
        best_candidate: AlsCandidate | None,
        candidates: list[AlsCandidate],
        unit_parts: dict[str, str],
    ) -> tuple[bool, str]:
        if not best_candidate:
            return False, ""
        target_block = str(unit_parts.get("block") or "").strip()
        if target_block and best_candidate.block and best_candidate.block != target_block:
            return True, "block_conflict"
        if len(candidates) >= 2:
            sorted_scores = sorted((candidate.score for candidate in candidates), reverse=True)
            if sorted_scores[0] - sorted_scores[1] < 5:
                if target_block and best_candidate.block == target_block:
                    return False, ""
                return True, "multiple_close_candidates"
        return False, ""

    def _official_match_quality(self, best_candidate: AlsCandidate, candidates: list[AlsCandidate]) -> str:
        if len(candidates) == 1 and best_candidate.score >= 60:
            return "high"
        if len(candidates) >= 2:
            sorted_scores = sorted((candidate.score for candidate in candidates), reverse=True)
            if sorted_scores[0] - sorted_scores[1] >= 8 and sorted_scores[0] >= 60:
                return "high"
        if best_candidate.score >= 50:
            return "medium"
        return "low"

    def _estimate_completeness(
        self,
        normalized_address: str,
        structured: dict[str, str] | None,
        pdf_parts: dict[str, str],
    ) -> bool:
        if not self.local_parser.looks_like_partial_address_text(normalized_address):
            return False
        if structured:
            has_location = bool(structured.get("district") or structured.get("street"))
            has_building_anchor = bool(structured.get("building") or structured.get("block"))
            has_unit = bool(structured.get("floor") and structured.get("flat_room"))
            if has_location and (has_building_anchor or has_unit):
                return True
            if self._structured_score(structured) >= 4 and bool(structured.get("building") or structured.get("street")):
                return True

        line1 = bool(pdf_parts.get("line1"))
        line2 = bool(pdf_parts.get("line2"))
        line3 = bool(pdf_parts.get("line3"))
        has_unit_parts = bool(pdf_parts.get("block") or (pdf_parts.get("floor") and pdf_parts.get("flat_room")))
        return (line1 and line2 and (line3 or has_unit_parts)) or (line2 and has_unit_parts)

    def _structured_score(self, structured: dict[str, str] | None) -> int:
        if not structured:
            return 0
        return len([key for key in ["area", "flat_room", "block", "floor", "building", "street", "district"] if structured.get(key)])

    def _empty_pdf_parts(self) -> dict[str, str]:
        return {
            "area": "",
            "flat_room": "",
            "block": "",
            "floor": "",
            "line1": "",
            "line2": "",
            "line3": "",
        }

    def _query_alignment_score(self, local: LocalParseResult, candidate: AlsCandidate) -> float:
        score = 0.0
        structured = local.heuristic_structured or {}
        building_query = self._compact(structured.get("building", ""))
        building_candidate = self._compact(candidate.building)

        street_query = self._compact(structured.get("street", ""))
        street_candidate = self._compact(candidate.street)
        if street_query:
            street_stem_query = self._extract_street_stem(street_query)
            street_stem_candidate = self._extract_street_stem(street_candidate)
            if (
                street_stem_query
                and street_stem_candidate
                and not building_query
                and street_stem_query != street_stem_candidate
            ):
                score -= 35
            if street_query in street_candidate or street_candidate in street_query:
                score += 30
            elif self._has_shared_substring(street_query, street_candidate, 3):
                score += 12
            else:
                score -= 30

        if building_query:
            if building_query in building_candidate or building_candidate in building_query:
                score += 25
            elif self._has_shared_substring(building_query, building_candidate, 3):
                score += 10
            else:
                score -= 18

        query_numbers = set(re.findall(r"\d+", local.official_query))
        candidate_text = " ".join([candidate.street, candidate.building, candidate.block])
        candidate_numbers = set(re.findall(r"\d+", candidate_text))
        if query_numbers and not query_numbers.issubset(candidate_numbers):
            score -= 20

        return score

    def _compact(self, value: str) -> str:
        return re.sub(r"[\s,，;；]+", "", value or "")

    def _has_shared_substring(self, left: str, right: str, min_length: int) -> bool:
        if len(left) < min_length or len(right) < min_length:
            return False
        seen = {left[index:index + min_length] for index in range(0, len(left) - min_length + 1)}
        return any(fragment in right for fragment in seen if fragment)

    def _extract_street_stem(self, compact_street: str) -> str:
        match = re.search(r"([\u4e00-\u9fffA-Za-z]+?)(?:道|街|路|里|坊|徑|巷|圍|围|臺|台)\d*", compact_street)
        if not match:
            return ""
        return match.group(1)

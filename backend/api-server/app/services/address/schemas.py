from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LocalParseResult:
    normalized_address: str
    official_query: str
    unit_parts: dict[str, str]
    heuristic_structured: dict[str, str] | None
    pdf_parts: dict[str, str]


@dataclass
class AlsCandidate:
    raw: dict[str, Any]
    building: str
    street: str
    district: str
    area: str
    block: str
    full_address_zh: str
    full_address_en: str
    latitude: float | None = None
    longitude: float | None = None
    score: float = 0.0


@dataclass
class AddressResolveResult:
    normalized_address: str
    address_structured: dict[str, str] | None
    pdf_parts: dict[str, str]
    confidence: str
    source: str
    is_complete: bool
    structured_count: int
    official: dict[str, Any] = field(default_factory=dict)
    geo: dict[str, Any] = field(default_factory=dict)
    needs_confirmation: bool = False
    confirmation_reason: str = ""
    candidate_options: list[dict[str, Any]] = field(default_factory=list)
    source_chain: list[str] = field(default_factory=list)


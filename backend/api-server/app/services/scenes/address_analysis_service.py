from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.address.parsers.local_address_parser import LocalAddressParser
from app.services.address.providers.als_client import AlsClient
from app.services.address.resolver_service import AddressResolverService


class AddressAnalysisService:
    ADDRESS_KEYS = ("area", "flat_room", "block", "floor", "building", "street", "district")

    def __init__(self) -> None:
        self.local_parser = LocalAddressParser()
        self.address_resolver = AddressResolverService(
            local_parser=self.local_parser,
            als_client=AlsClient(),
            enable_als=settings.ADDRESS_RESOLVER_ENABLE_ALS,
        )

    def analyze(
        self,
        raw_address: str,
        structured_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.address_resolver.resolve(raw_address, structured_hint)
        return {
            "normalized_address": result.normalized_address,
            "address_structured": result.address_structured,
            "confidence": result.confidence,
            "source": result.source,
            "is_complete": result.is_complete,
            "pdf_parts": result.pdf_parts,
            "structured_count": result.structured_count,
            "official": result.official,
            "geo": result.geo,
            "needs_confirmation": result.needs_confirmation,
            "confirmation_reason": result.confirmation_reason,
            "candidate_options": result.candidate_options,
            "source_chain": result.source_chain,
        }

    def looks_like_actual_address_text(self, text: str) -> bool:
        return self.local_parser.looks_like_actual_address_text(text)

    def looks_like_address_input_text(self, text: str) -> bool:
        return self.local_parser.looks_like_partial_address_text(text)

    def normalize_structured(self, value: dict[str, Any] | None) -> dict[str, str] | None:
        return self.local_parser.normalize_structured(value)

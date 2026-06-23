from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.services.address.schemas import AlsCandidate


class AlsClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ALS_BASE_URL).rstrip("/")

    def search(self, query: str, limit: int | None = None) -> list[AlsCandidate]:
        normalized_query = " ".join((query or "").split())
        if not normalized_query:
            return []

        count = limit or settings.ALS_RESULT_LIMIT
        try:
            with httpx.Client(timeout=settings.ALS_TIMEOUT_SECONDS) as client:
                response = client.get(
                    f"{self.base_url}/lookup",
                    params={"q": normalized_query, "n": count},
                    headers={
                        "Accept": "application/json",
                        "Accept-Language": "zh-Hant,en",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:  # noqa: BLE001
            return []

        suggested = payload.get("SuggestedAddress")
        if not isinstance(suggested, list):
            return []

        candidates: list[AlsCandidate] = []
        for item in suggested:
            candidate = self._to_candidate(item)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _to_candidate(self, item: dict[str, Any]) -> AlsCandidate | None:
        premises = ((((item or {}).get("Address") or {}).get("PremisesAddress")) or {})
        chi = premises.get("ChiPremisesAddress") or {}
        eng = premises.get("EngPremisesAddress") or {}
        geo = premises.get("GeospatialInformation") or {}
        validation = (item or {}).get("ValidationInformation") or {}

        building = self._build_chi_building(chi)
        street = self._build_chi_street(chi)
        district = self._clean(((chi.get("ChiDistrict") or {}).get("DcDistrict")) or "")
        block = self._build_chi_block(chi)
        area = self._map_region(chi.get("Region") or eng.get("Region") or "")

        try:
            latitude = float(geo.get("Latitude")) if geo.get("Latitude") else None
        except (TypeError, ValueError):
            latitude = None
        try:
            longitude = float(geo.get("Longitude")) if geo.get("Longitude") else None
        except (TypeError, ValueError):
            longitude = None

        return AlsCandidate(
            raw=item,
            building=building,
            street=street,
            district=district,
            area=area,
            block=block,
            full_address_zh=self._build_chi_full_address(chi),
            full_address_en=self._build_eng_full_address(eng),
            latitude=latitude,
            longitude=longitude,
            score=float(validation.get("Score") or 0.0),
        )

    def _build_chi_building(self, chi: dict[str, Any]) -> str:
        estate = chi.get("ChiEstate") or {}
        estate_name = self._clean(estate.get("EstateName"))
        phase_name = self._clean((estate.get("ChiPhase") or {}).get("PhaseName"))
        building = f"{estate_name}{phase_name}"
        return self._clean(building)

    def _build_chi_block(self, chi: dict[str, Any]) -> str:
        block = chi.get("ChiBlock") or {}
        block_no = self._clean(block.get("BlockNo"))
        block_descriptor = self._clean(block.get("BlockDescriptor"))
        return self._clean(f"{block_no}{block_descriptor}")

    def _build_chi_street(self, chi: dict[str, Any]) -> str:
        street = chi.get("ChiStreet") or {}
        location_name = self._clean(street.get("LocationName"))
        street_name = self._clean(street.get("StreetName"))
        building_from = self._clean(street.get("BuildingNoFrom"))
        building_to = self._clean(street.get("BuildingNoTo"))
        number = ""
        if building_from and building_to and building_from != building_to:
            number = f"{building_from}-{building_to}號"
        elif building_from:
            number = f"{building_from}號"
        return self._clean(f"{location_name}{street_name}{number}")

    def _build_chi_full_address(self, chi: dict[str, Any]) -> str:
        parts = [
            self._clean(chi.get("Region")),
            self._clean(((chi.get("ChiDistrict") or {}).get("DcDistrict"))),
            self._build_chi_street(chi),
            self._build_chi_building(chi),
            self._build_chi_block(chi),
        ]
        return self._clean("".join(part for part in parts if part))

    def _build_eng_full_address(self, eng: dict[str, Any]) -> str:
        block = eng.get("EngBlock") or {}
        estate = eng.get("EngEstate") or {}
        street = eng.get("EngStreet") or {}
        district = eng.get("EngDistrict") or {}

        block_name = self._clean(" ".join(part for part in [block.get("BlockDescriptor"), block.get("BlockNo")] if part))
        estate_name = self._clean(" ".join(part for part in [estate.get("EstateName"), (estate.get("EngPhase") or {}).get("PhaseName")] if part))
        street_name = self._clean(" ".join(part for part in [street.get("LocationName"), street.get("StreetName")] if part))
        if street.get("BuildingNoFrom"):
            street_name = self._clean(f"{street_name} {street.get('BuildingNoFrom')}")
        parts = [
            self._clean(eng.get("Region")),
            self._clean(district.get("DcDistrict")),
            street_name,
            estate_name,
            block_name,
        ]
        return self._clean(", ".join(part for part in parts if part))

    def _map_region(self, value: str) -> str:
        normalized = self._clean(value).lower()
        mapping = {
            "hk": "hk",
            "hong kong": "hk",
            "香港": "hk",
            "kln": "kln",
            "kowloon": "kln",
            "九龙": "kln",
            "九龍": "kln",
            "nt": "nt",
            "new territories": "nt",
            "新界": "nt",
        }
        return mapping.get(normalized, "others")

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").split()).strip(" ,，")


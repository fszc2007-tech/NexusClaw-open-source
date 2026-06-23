from __future__ import annotations

import re
from typing import Any

from app.services.address.schemas import LocalParseResult


class LocalAddressParser:
    ADDRESS_KEYS = ("area", "flat_room", "block", "floor", "building", "street", "district")
    GENERIC_PHRASES = [
        "我要改地址",
        "我要改收税单地址",
        "我要改收稅單地址",
        "我要改通訊地址",
        "我要改业务地址",
        "我要改業務地址",
        "帮我改地址",
        "幫我改地址",
        "修改地址",
        "更改地址",
        "地址变更",
        "地址變更",
        "business address change",
        "postal address change",
    ]

    def parse(
        self,
        raw_address: str,
        structured_hint: dict[str, Any] | None = None,
    ) -> LocalParseResult:
        normalized_address = self._cleanup_fragment(raw_address)
        normalized_hint = self.normalize_structured(structured_hint)
        if not normalized_address:
            return LocalParseResult(
                normalized_address="",
                official_query="",
                unit_parts={},
                heuristic_structured=normalized_hint,
                pdf_parts=self._empty_pdf_parts(),
            )

        heuristic = self._heuristic_parse(normalized_address)
        structured = heuristic["address_structured"]
        if normalized_hint and self._structured_score(normalized_hint) > self._structured_score(structured):
            structured = {**structured, **normalized_hint} if structured else normalized_hint

        official_query = self._build_official_query(normalized_address, structured, heuristic["official_parts"])
        unit_parts = {
            key: value
            for key, value in {
                "block": (structured or {}).get("block", ""),
                "floor": (structured or {}).get("floor", ""),
                "flat_room": (structured or {}).get("flat_room", ""),
            }.items()
            if value
        }

        return LocalParseResult(
            normalized_address=normalized_address,
            official_query=official_query,
            unit_parts=unit_parts,
            heuristic_structured=structured,
            pdf_parts=heuristic["pdf_parts"],
        )

    def normalize_structured(self, value: dict[str, Any] | None) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None
        normalized: dict[str, str] = {}
        for key in self.ADDRESS_KEYS:
            raw = value.get(key)
            if not isinstance(raw, str):
                continue
            cleaned = self._cleanup_fragment(raw)
            if not cleaned:
                continue
            if key == "area":
                mapped = self._normalize_area(cleaned)
                if mapped:
                    normalized[key] = mapped
                continue
            normalized[key] = cleaned
        return normalized or None

    def looks_like_actual_address_text(self, text: str) -> bool:
        normalized = self._cleanup_fragment(text)
        if len(normalized) < 6:
            return False

        if not self._passes_address_intent_filter(normalized):
            return False

        lowered = normalized.lower()
        strong_markers = [
            "號",
            "号",
            "街",
            "道",
            "樓",
            "楼",
            "室",
            "座",
            "大廈",
            "大厦",
            "廣場",
            "香港",
            "九龍",
            "九龙",
            "新界",
            "flat",
            "room",
            "block",
            "tower",
            "street",
            "road",
            "building",
            "floor",
        ]
        if any(marker in normalized or marker in lowered for marker in strong_markers):
            return True
        if any(char.isdigit() for char in normalized) and len(normalized) >= 10:
            return True
        if any(token in normalized for token in [",", "，", ";", "；", "\n"]):
            return True
        return False

    def looks_like_partial_address_text(self, text: str) -> bool:
        normalized = self._cleanup_fragment(text)
        if len(normalized) < 4:
            return False
        if not self._passes_address_intent_filter(normalized):
            return False
        if self.looks_like_actual_address_text(normalized):
            return True

        lowered = normalized.lower()
        partial_markers = [
            "大廈",
            "大厦",
            "中心",
            "廣場",
            "广场",
            "花園",
            "花园",
            "苑",
            "邨",
            "閣",
            "轩",
            "軒",
            "居",
            "城",
            "村",
            "estate",
            "building",
            "tower",
            "plaza",
            "center",
            "centre",
            "garden",
            "city",
        ]
        if any(marker in normalized or marker in lowered for marker in partial_markers):
            return True
        if re.search(r"[一二三四五六七八九十0-9]+期", normalized):
            return True
        return False

    def _heuristic_parse(self, normalized_address: str) -> dict[str, Any]:
        working = normalized_address
        area = self._detect_area_key(working)
        working = self._strip_area_prefix(working)

        compact_components, working = self._extract_hk_compact_unit(working)
        flat_room = compact_components.get("flat_room", "")
        block = compact_components.get("block", "")
        floor = compact_components.get("floor", "")

        if not flat_room:
            flat_room, working = self._extract_component(
                working,
                [
                    r"\b(?:FLAT|ROOM|UNIT)\s*[A-Z0-9/-]+\b",
                    r"[A-Z0-9/-]+\s*(?:室|房)\b",
                ],
            )
        if not floor:
            floor, working = self._extract_component(
                working,
                [
                    r"\b(?:G/F|LG/F|UG/F)\b",
                    r"\b\d+\s*(?:/F|FLOOR|F)\b",
                    r"\d+\s*(?:樓|楼)\b",
                ],
            )
        if not block:
            block, working = self._extract_component(
                working,
                [
                    r"\b(?:BLOCK|TOWER)\s*[A-Z0-9-]+\b",
                    r"[A-Z0-9-]+\s*(?:座|棟|栋)\b",
                ],
            )

        district, working = self._extract_district(working)
        street, building = self._split_inline_street_and_building(working)
        if not building:
            building, working = self._extract_building_name(working)
            street = self._cleanup_fragment(working)

        if not building and not district and street:
            segments = [item.strip() for item in re.split(r"[，,;；]+", street) if item.strip()]
            if len(segments) >= 2:
                building = self._cleanup_fragment(segments[0])
                street = self._cleanup_fragment(" ".join(segments[1:]))

        address_structured = {
            key: value
            for key, value in {
                "area": area,
                "flat_room": flat_room[:80],
                "block": block[:80],
                "floor": floor[:80],
                "building": building[:80],
                "street": street[:80],
                "district": district[:80],
            }.items()
            if value
        } or None

        return {
            "address_structured": address_structured,
            "pdf_parts": {
                "area": area,
                "flat_room": flat_room[:80],
                "block": block[:80],
                "floor": floor[:80],
                "line1": building[:80],
                "line2": street[:80],
                "line3": district[:80],
            },
            "official_parts": {
                "street": street[:80],
                "building": building[:80],
                "block": block[:80],
            },
        }

    def _build_official_query(
        self,
        normalized_address: str,
        structured: dict[str, str] | None,
        official_parts: dict[str, str],
    ) -> str:
        parts = [
            official_parts.get("street", ""),
            official_parts.get("building", ""),
            official_parts.get("block", ""),
        ]
        query = self._cleanup_fragment(" ".join(part for part in parts if part))
        if query:
            return query

        cleaned = self._strip_area_prefix(normalized_address)
        cleaned = re.sub(r"\b(?:FLAT|ROOM|UNIT)\s*[A-Z0-9/-]+\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[A-Z0-9/-]+\s*(?:室|房)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:G/F|LG/F|UG/F)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+\s*(?:/F|FLOOR|F)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\d+\s*(?:樓|楼)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = self._cleanup_fragment(cleaned)
        if structured and structured.get("block") and structured["block"] not in cleaned:
            cleaned = self._cleanup_fragment(f"{cleaned} {structured['block']}")
        return cleaned[:160]

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

    def _structured_score(self, structured: dict[str, str] | None) -> int:
        if not structured:
            return 0
        return len([key for key in self.ADDRESS_KEYS if structured.get(key)])

    def _extract_hk_compact_unit(self, text: str) -> tuple[dict[str, str], str]:
        compact_patterns = [
            re.compile(
                r"(?P<full>(?:第)?(?P<block>[A-Z]|\d{1,2})\s*座\s*(?P<floor>\d{1,2})\s*(?:樓|楼|F)?\s*(?P<flat>[A-Z]\d?)\s*(?:室|房)?)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?P<full>(?:TOWER|BLOCK)\s*(?P<block>\d{1,2}|[A-Z])[,\\s/-]*(?P<floor>\d{1,2})\s*(?:/F|FLOOR|F)[,\\s/-]*(?:FLAT|ROOM|UNIT)?\s*(?P<flat>[A-Z]\d?))",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?P<full>(?P<floor>\d{1,2})\s*(?:樓|楼|F)?\s*(?P<flat>[A-Z]\d?)\s*(?:室|房))",
                re.IGNORECASE,
            ),
        ]

        for pattern in compact_patterns:
            match = pattern.search(text)
            if not match:
                continue
            block = (match.groupdict().get("block") or "").strip()
            floor = (match.groupdict().get("floor") or "").strip()
            flat = (match.groupdict().get("flat") or "").strip().upper()
            components = {
                "flat_room": f"{flat}室" if flat else "",
                "block": f"{block}座" if block and "座" not in block.upper() and "TOWER" not in block.upper() and "BLOCK" not in block.upper() else block,
                "floor": floor,
            }
            remaining = self._cleanup_fragment(f"{text[:match.start('full')]} {text[match.end('full'):]}")
            return components, remaining
        return {}, self._cleanup_fragment(text)

    def _extract_component(self, text: str, patterns: list[str]) -> tuple[str, str]:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            component = self._cleanup_fragment(match.group(0))
            remaining = self._cleanup_fragment(f"{text[:match.start()]} {text[match.end():]}")
            return component, remaining
        return "", self._cleanup_fragment(text)

    def _extract_district(self, text: str) -> tuple[str, str]:
        districts = [
            "中西區", "灣仔", "东区", "東區", "南區", "油尖旺", "深水埗", "九龙城", "九龍城", "黄大仙", "黃大仙",
            "观塘", "觀塘", "荃湾", "荃灣", "屯门", "屯門", "元朗", "北區", "北区", "大埔", "西貢", "西贡",
            "沙田", "葵青", "离岛", "離島",
        ]
        segments = [item.strip() for item in re.split(r"[\n,，;；]+", text) if item.strip()]
        for segment in segments:
            compact_segment = re.sub(r"\s+", "", segment)
            for district in districts:
                if segment == district or segment.endswith(f" {district}") or segment.endswith(district):
                    remaining_segments = [item for item in segments if item != segment]
                    if segment != district:
                        leading = self._cleanup_fragment(segment.removesuffix(district))
                        if leading:
                            remaining_segments.append(leading)
                    return district, self._cleanup_fragment(" ".join(remaining_segments))
                if compact_segment.startswith(district):
                    remainder = self._cleanup_fragment(segment[len(district):])
                    if remainder.startswith(("道", "街", "路", "里", "坊", "徑", "巷", "圍", "围", "臺", "台")):
                        continue
                    if remainder or compact_segment != district:
                        remaining_segments = [item for item in segments if item != segment]
                        if remainder:
                            remaining_segments.append(remainder)
                        return district, self._cleanup_fragment(" ".join(remaining_segments))
        return "", self._cleanup_fragment(text)

    def _extract_building_name(self, text: str) -> tuple[str, str]:
        segments = [item.strip() for item in re.split(r"[\n,，;；]+", text) if item.strip()]
        building_markers = [
            "大厦", "大廈", "中心", "廣場", "广场", "商業大廈", "商业大厦", "花園", "花园", "城",
            "building", "tower", "centre", "center", "plaza", "city", "garden",
        ]
        for segment in segments:
            lowered = segment.lower()
            if any(marker in segment or marker in lowered for marker in building_markers):
                remaining_segments = [item for item in segments if item != segment]
                return self._cleanup_fragment(segment), self._cleanup_fragment(" ".join(remaining_segments))
        return "", self._cleanup_fragment(text)

    def _split_inline_street_and_building(self, text: str) -> tuple[str, str]:
        normalized = self._cleanup_fragment(text)
        if not normalized:
            return "", ""

        zh_match = re.match(
            r"^(?P<street>.*?(?:道|街|路|里|坊|徑|巷|圍|围|臺|台)\s*\d+[A-Z0-9/-]*號)(?P<building>.+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if zh_match:
            street = self._cleanup_fragment(zh_match.group("street"))
            building = self._cleanup_fragment(zh_match.group("building"))
            if street and building:
                return street, building

        return "", ""

    def _strip_area_prefix(self, text: str) -> str:
        stripped = text.strip()
        prefixes = [
            r"^(?:香港|Hong Kong|H\.?K\.?)",
            r"^(?:九龍|九龙|Kowloon|KLN\.?)",
            r"^(?:新界|New Territories|N\.?T\.?)",
        ]
        changed = True
        while changed:
            changed = False
            for pattern in prefixes:
                next_value = re.sub(pattern, "", stripped, count=1, flags=re.IGNORECASE).strip(" ,，")
                if next_value != stripped:
                    stripped = next_value
                    changed = True
        return self._cleanup_fragment(stripped)

    def _detect_area_key(self, address: str) -> str:
        lowered = (address or "").lower()
        if any(token in lowered for token in ["九龍", "九龙", "kln", "kowloon"]):
            return "kln"
        if any(token in lowered for token in ["新界", "n.t.", "new territories"]):
            return "nt"
        if any(token in lowered for token in ["香港", "h.k.", "hong kong"]):
            return "hk"
        return "others"

    def _normalize_area(self, value: str) -> str | None:
        normalized = value.strip().lower()
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
            "others": "others",
            "other": "others",
            "其他": "others",
        }
        return mapping.get(normalized)

    def _cleanup_fragment(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip(" ,，;；")

    def _passes_address_intent_filter(self, normalized: str) -> bool:
        lowered = normalized.lower()
        if any(phrase in normalized for phrase in self.GENERIC_PHRASES):
            return False
        if any(phrase in lowered for phrase in ["change address", "update address"]):
            return False
        if self._looks_like_scene_intent_phrase(normalized):
            return False
        return True

    def _looks_like_scene_intent_phrase(self, normalized: str) -> bool:
        lowered = normalized.lower()
        action_markers = [
            "搬家",
            "搬办公室",
            "搬辦公室",
            "改地址",
            "改通訊地址",
            "改通讯地址",
            "改收税单地址",
            "改收稅單地址",
            "更改地址",
            "地址变更",
            "地址變更",
            "填写",
            "填寫",
            "填表",
            "生成pdf",
            "生成 pdf",
            "開始辦理",
            "开始办理",
            "幫我",
            "帮我",
        ]
        address_subject_markers = [
            "地址",
            "通訊地址",
            "通讯地址",
            "收税单地址",
            "收稅單地址",
            "業務地址",
            "业务地址",
            "ir1249",
            "irc3111a",
        ]
        structural_markers = [
            "號",
            "号",
            "街",
            "道",
            "樓",
            "楼",
            "室",
            "座",
            "大廈",
            "大厦",
            "香港",
            "九龍",
            "九龙",
            "新界",
            "flat",
            "room",
            "block",
            "tower",
            "street",
            "road",
            "building",
            "floor",
        ]
        has_action = any(marker in normalized or marker in lowered for marker in action_markers)
        has_subject = any(marker in normalized or marker in lowered for marker in address_subject_markers)
        has_structure = any(marker in normalized or marker in lowered for marker in structural_markers) or any(char.isdigit() for char in normalized)
        return has_action and has_subject and not has_structure

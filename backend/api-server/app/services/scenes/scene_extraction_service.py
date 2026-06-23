from __future__ import annotations

import json
from typing import Any

from app.services.deepseek_service import DeepSeekService


class SceneExtractionService:
    EXTRACTION_META_FIELDS = {"address_structured"}
    EXTRACTION_HIDDEN_FIELDS = {"_field_confidence"}

    def __init__(self, deepseek_service: DeepSeekService | None = None) -> None:
        self.deepseek_service = deepseek_service or DeepSeekService()

    def extract_fields(
        self,
        route_rules: dict[str, Any],
        payload: dict[str, Any],
        query: str,
        missing_fields: list[str],
        visible_fields: list[str],
    ) -> dict[str, Any]:
        normalized = " ".join(query.strip().split())
        if not normalized or not self.deepseek_service.is_enabled():
            return {}
        if self._should_skip_llm_extraction(normalized):
            return {}

        field_labels = route_rules.get("field_labels", {})
        candidate_fields = list(dict.fromkeys([*missing_fields, *visible_fields, *field_labels.keys()]))
        if not candidate_fields:
            return {}

        system_prompt = (
            "你是政务表单信息抽取助手。"
            "你的任务是从用户当前这句话里抽取可以直接用于官方表格填写的字段。"
            "只允许抽取用户明确表达的信息，不能猜测、不能补全、不能改写事实。"
            "但对地址字段，允许你在不改变原文事实的前提下做语义拆分，把同一段地址原文归位到不同结构化槽位。"
            "若字段没有被用户明确说出，就不要输出。"
            "只输出合法 JSON，不要解释。"
        )
        runtime_prompt = (
            f"表格编号：{route_rules.get('form_no')}\n"
            f"表格标题：{route_rules.get('title')}\n"
            f"当前已填写字段：{json.dumps(payload, ensure_ascii=False)}\n"
            f"当前缺失字段：{json.dumps(missing_fields, ensure_ascii=False)}\n"
            f"当前展示字段：{json.dumps(visible_fields, ensure_ascii=False)}\n"
            f"候选字段及中文标签：{json.dumps({key: field_labels.get(key, key) for key in candidate_fields}, ensure_ascii=False)}\n"
            f"如需抽取申请人类别，只能使用这些值：{json.dumps(self._applicant_type_options(route_rules), ensure_ascii=False)}\n"
            "布尔字段只能输出 true 或 false。\n"
            "日期尽量输出 YYYY-MM-DD；如果用户只说“下个月1号”这类相对日期，也可以按原话输出。\n"
            "如果用户提供了完整地址，除了 `new_address` 原文外，你还可以额外输出 `address_structured`。\n"
            "address_structured 仅允许这些键：area, flat_room, block, floor, building, street, district。\n"
            "其中 area 只能用 hk / kln / nt / others。\n"
            "对地址请优先输出 `address_structured`，不要因为原文没有逗号或标准分隔符就放弃拆分。\n"
            "对地址结构化时，请尽量把用户原文中已经包含的信息完整归位到对应槽位；这属于信息整理，不算猜测。\n"
            "如果某个地址槽位无法从原文 reasonably 判断，可以留空；但不要因为个别槽位不确定，就整段不输出。\n"
            "香港地址结构化时请遵守这些规则：\n"
            "1. `flat_room` 放室 / 房 / Flat / Room，例如 A室、6H室。\n"
            "2. `block` 放座 / Block / Tower，例如 3座。\n"
            "3. `floor` 只放楼层值，例如 10、23、G/F。\n"
            "4. `building` 放楼宇 / 屋苑 / 大厦 / 期数名称，例如 新都城一期、海濱廣場。\n"
            "5. `street` 放街道或较小地段文本；如果没有明确街道门牌，但有地区性前缀，也可放例如 寶琳、將軍澳寶琳。\n"
            "6. `district` 只在用户明确提供行政区 / 区域时填写，例如 觀塘、灣仔、沙田；如果只是街道名前缀或你不确定，就留空。\n"
            "7. 不要把同一片文本同时重复放进 building / street / district。\n"
            "8. 如果地址只包含屋苑名、期数、座、楼、室，没有明确街道门牌，也允许输出 building + block + floor + flat_room，并把较大的地段前缀放进 street。\n"
            "地址示例：\n"
            "- 输入：香港九龍觀塘道 88 號 10 樓 A 室\n"
            "  输出：{\"new_address\":\"香港九龍觀塘道 88 號 10 樓 A 室\",\"address_structured\":{\"area\":\"kln\",\"flat_room\":\"A室\",\"floor\":\"10\",\"street\":\"觀塘道 88 號\",\"district\":\"觀塘\"}}\n"
            "- 输入：寶琳新都城一期 3 座6H\n"
            "  输出：{\"new_address\":\"寶琳新都城一期 3 座6H\",\"address_structured\":{\"flat_room\":\"H室\",\"block\":\"3座\",\"floor\":\"6\",\"building\":\"新都城一期\",\"street\":\"寶琳\"}}\n"
            "- 输入：將軍澳寶琳新都城一期3座6H室\n"
            "  输出：{\"new_address\":\"將軍澳寶琳新都城一期3座6H室\",\"address_structured\":{\"flat_room\":\"H室\",\"block\":\"3座\",\"floor\":\"6\",\"building\":\"新都城一期\",\"street\":\"將軍澳寶琳\"}}\n"
            "只有当整段地址几乎完全无法拆分时，才不要输出 `address_structured`。\n"
            "若用户这一句同时给了多个字段，请一次性全部抽取。\n"
            "同时请给每个已抽取字段一个置信度，只能是 high / medium / low。\n"
            "对 `address_structured`：能稳定拆出大部分地址槽位时用 high 或 medium；只有在存在多种合理拆法、你明显拿不准时才标记 low。\n"
            "输出格式：{\"fields\":{\"field_key\":\"value\"},\"field_confidence\":{\"field_key\":\"high|medium|low\"}}。\n"
            f"用户输入：{normalized}"
        )
        payload_json = self.deepseek_service.extract_structured_json(system_prompt, runtime_prompt)
        if not isinstance(payload_json, dict):
            return {}
        fields = payload_json.get("fields")
        if not isinstance(fields, dict):
            return {}
        result = {
            key: value
            for key, value in fields.items()
            if key in {*candidate_fields, *self.EXTRACTION_META_FIELDS} and value not in (None, "", [], {})
        }
        field_confidence = payload_json.get("field_confidence")
        if isinstance(field_confidence, dict):
            normalized_confidence = {
                key: str(value).strip().lower()
                for key, value in field_confidence.items()
                if key in result and str(value).strip().lower() in {"high", "medium", "low"}
            }
            if normalized_confidence:
                result["_field_confidence"] = normalized_confidence
        return result

    def _should_skip_llm_extraction(self, query: str) -> bool:
        normalized = query.lower()
        if len(query) < 6:
            return True
        generic_starts = [
            "帮我填写",
            "幫我填寫",
            "帮我填",
            "幫我填",
            "开始填写",
            "開始填寫",
            "开始填表",
            "開始填表",
            "生成 pdf",
            "生成pdf",
        ]
        has_rich_slot_signal = (
            len(query) >= 20
            or any(token in query for token in ["，", ",", "\n", "电话", "電話", "地址", "月", "日", "HKID", "身份证", "身分證"])
            or any(char.isdigit() for char in query)
        )
        if any(keyword in query for keyword in generic_starts) and not has_rich_slot_signal:
            return True
        if normalized in {
            "salary earner",
            "property owner",
            "sole proprietor",
            "business owner",
            "employer",
        }:
            return True
        if query.isdigit() and len(query) <= 10:
            return True
        return False

    def _applicant_type_options(self, route_rules: dict[str, Any]) -> list[str]:
        options = (route_rules.get("field_options") or {}).get("applicant_type") or []
        return [str(option.get("value")) for option in options if option.get("value")]

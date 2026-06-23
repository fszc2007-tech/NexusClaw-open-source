from __future__ import annotations

import re
from typing import Any

from app.services.scenes.registry import SceneRegistry


class SceneRouter:
    SCENE_INVITATION_MARKERS = (
        "需要我幫您完成表格的填寫嗎",
        "需要我帮您完成表格的填写吗",
        "開始填寫",
        "开始填写",
    )
    AFFIRMATIVE_FOLLOWUPS = {
        "是",
        "是的",
        "好的",
        "好",
        "好呀",
        "好啊",
        "可以",
        "可以的",
        "需要",
        "要",
        "是的需要",
        "係",
        "嗯",
        "嗯嗯",
        "yes",
        "ok",
    }
    AFFIRMATIVE_FOLLOWUP_PATTERN = re.compile(
        r"^(是|是的|好|好的|可以|可以的|需要|要|係|嗯|yes|ok)(啊|呀|啦|喇|呢|哦|喔|嘛|吧|唷|哇|诶|欸)*$"
    )
    ZH_VARIANT_PAIRS = (
        ("税", "稅"),
        ("变", "變"),
        ("讯", "訊"),
        ("业", "業"),
        ("单", "單"),
        ("帮", "幫"),
        ("写", "寫"),
        ("办", "辦"),
        ("广", "廣"),
        ("龙", "龍"),
        ("楼", "樓"),
        ("号", "號"),
    )
    DEFAULT_KNOWLEDGE_KEYWORDS = {
        "是什么",
        "是什麼",
        "什么是",
        "什麼是",
        "什么",
        "什麼",
        "什么意思",
        "什麼意思",
        "如何提交",
        "怎么提交",
        "怎麼提交",
        "提交方式",
        "区别",
        "區別",
        "有什么区别",
        "有什麼區別",
        "准备什么资料",
        "準備什麼資料",
        "要准备什么资料",
        "要準備什麼資料",
    }

    def __init__(self, registry: SceneRegistry | None = None) -> None:
        self.registry = registry or SceneRegistry()

    def classify(
        self,
        query: str,
        memory_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        scene_key = "hk_tax_address_change"
        if not self.registry.is_enabled(project_context, scene_key):
            return {
                "intent_mode": "knowledge_query",
                "should_route_scene": False,
                "scene_key": None,
                "route_key": None,
                "reason": "scene_disabled",
            }

        normalized = query.strip().lower()
        scene_state = (memory_context.get("state") or {}).get("scene") or {}
        scene_rules = self.registry.get_scene_definition(scene_key)
        routes = scene_rules.get("routes", {})

        form_tokens = self._collect_form_tokens(routes)
        knowledge_keywords = {
            *(keyword.lower() for keyword in scene_rules.get("entry", {}).get("knowledge_keywords", [])),
            *self.DEFAULT_KNOWLEDGE_KEYWORDS,
        }
        mentions_form = any(self._contains_keyword(normalized, token) for token in form_tokens)
        asks_for_knowledge = any(self._contains_keyword(normalized, keyword) for keyword in knowledge_keywords)
        action_keywords = scene_rules.get("entry", {}).get("action_keywords", [])
        mentions_action = any(self._contains_keyword(normalized, keyword) for keyword in action_keywords)
        if not mentions_action and self._looks_like_address_change_request(normalized):
            mentions_action = True
        recent_turns = memory_context.get("recent_turns") or []
        latest_turn = recent_turns[-1] if recent_turns else {}
        invited_to_start_scene = self._has_scene_invitation(latest_turn)

        route_scores: dict[str, int] = {}
        for route_key, route_rules in routes.items():
            score = sum(1 for keyword in route_rules.get("route_keywords", []) if self._contains_keyword(normalized, keyword))
            if score:
                route_scores[route_key] = score

        resolved_route_key = None
        ambiguous_route = False
        if route_scores:
            top_score = max(route_scores.values())
            top_routes = [route_key for route_key, score in route_scores.items() if score == top_score]
            if len(top_routes) == 1:
                resolved_route_key = top_routes[0]
            else:
                ambiguous_route = True

        has_active_scene = scene_state.get("scene_key") == scene_key and scene_state.get("state") not in {"DONE", "FAILED"}
        if has_active_scene and asks_for_knowledge:
            return {
                "intent_mode": "hybrid_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": scene_state.get("route_key") or resolved_route_key,
                "reason": "resume_active_scene_hybrid",
            }
        if has_active_scene:
            return {
                "intent_mode": "scene_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": scene_state.get("route_key") or resolved_route_key,
                "reason": "resume_active_scene",
            }
        if invited_to_start_scene and self._is_affirmative_followup(normalized):
            contextual_route_key = resolved_route_key or self._infer_route_from_recent_turn(routes, latest_turn)
            return {
                "intent_mode": "scene_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": contextual_route_key,
                "reason": "accept_previous_scene_invitation",
            }
        if mentions_form and asks_for_knowledge:
            return {
                "intent_mode": "hybrid_request",
                "should_route_scene": False,
                "scene_key": scene_key,
                "route_key": resolved_route_key,
                "reason": "knowledge_plus_form",
            }
        if ambiguous_route:
            return {
                "intent_mode": "scene_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": None,
                "reason": "ambiguous_route_keywords",
            }
        if resolved_route_key:
            return {
                "intent_mode": "scene_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": resolved_route_key,
                "reason": "keyword_route_match",
            }
        if mentions_action:
            return {
                "intent_mode": "scene_request",
                "should_route_scene": True,
                "scene_key": scene_key,
                "route_key": None,
                "reason": "generic_scene_action",
            }
        return {
            "intent_mode": "knowledge_query",
            "should_route_scene": False,
            "scene_key": scene_key,
            "route_key": None,
            "reason": "knowledge_only",
        }

    def route(
        self,
        query: str,
        memory_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        intent = self.classify(query, memory_context, project_context)
        if not intent.get("should_route_scene"):
            return None
        return {
            "scene_key": intent["scene_key"],
            "route_key": intent.get("route_key"),
            "reason": intent.get("reason"),
            "intent_mode": intent.get("intent_mode"),
        }

    def _collect_form_tokens(self, routes: dict[str, Any]) -> set[str]:
        tokens: set[str] = set()
        for route_key, route_rules in routes.items():
            tokens.add(route_key.lower())
            form_no = route_rules.get("form_no")
            if form_no:
                tokens.add(str(form_no).lower())
        return tokens

    def _contains_keyword(self, normalized_query: str, keyword: str) -> bool:
        keyword_value = str(keyword or "").strip().lower()
        if not keyword_value:
            return False
        return any(variant in normalized_query for variant in self._keyword_variants(keyword_value))

    def _keyword_variants(self, keyword: str) -> set[str]:
        variants = {keyword}
        queue = [keyword]
        while queue:
            current = queue.pop()
            for left, right in self.ZH_VARIANT_PAIRS:
                for old, new in ((left, right), (right, left)):
                    if old not in current:
                        continue
                    updated = current.replace(old, new)
                    if updated not in variants:
                        variants.add(updated)
                        queue.append(updated)
        return variants

    def _looks_like_address_change_request(self, normalized: str) -> bool:
        action_markers = ("改", "更改", "變更", "变更", "更新", "搬")
        address_markers = ("地址", "收税单地址", "收稅單地址", "通訊地址", "通讯地址", "業務地址", "业务地址", "辦公室", "办公室")
        return any(marker in normalized for marker in action_markers) and any(marker in normalized for marker in address_markers)

    def _has_scene_invitation(self, latest_turn: dict[str, Any]) -> bool:
        answer = str((latest_turn or {}).get("answer") or "")
        return any(marker in answer for marker in self.SCENE_INVITATION_MARKERS)

    def _is_affirmative_followup(self, query: str) -> bool:
        compact = self._normalize_reply_token(query)
        return compact in self.AFFIRMATIVE_FOLLOWUPS or bool(self.AFFIRMATIVE_FOLLOWUP_PATTERN.fullmatch(compact))

    def _infer_route_from_recent_turn(self, routes: dict[str, Any], latest_turn: dict[str, Any]) -> str | None:
        context_text = " ".join(
            [
                str((latest_turn or {}).get("query") or ""),
                str((latest_turn or {}).get("answer") or ""),
            ]
        ).lower()
        if not context_text:
            return None

        route_scores: dict[str, int] = {}
        for route_key, route_rules in routes.items():
            score = 0
            form_no = str(route_rules.get("form_no") or "").lower()
            if form_no and self._contains_keyword(context_text, form_no):
                score += 2
            score += sum(
                1 for keyword in route_rules.get("route_keywords", []) if self._contains_keyword(context_text, keyword)
            )
            if score:
                route_scores[route_key] = score

        if not route_scores:
            return None

        top_score = max(route_scores.values())
        top_routes = [route_key for route_key, score in route_scores.items() if score == top_score]
        if len(top_routes) != 1:
            return None
        return top_routes[0]

    def _normalize_reply_token(self, text: str) -> str:
        return re.sub(r"[\s\W_]+", "", text.strip().lower())

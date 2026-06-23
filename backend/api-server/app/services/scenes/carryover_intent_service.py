from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.deepseek_service import DeepSeekService


logger = logging.getLogger(__name__)


class SceneCarryoverIntentService:
    ALLOWED_SCENE_KEYS = {"hk_tax_address_change"}
    ALLOWED_ROUTE_KEYS = {"ir1249", "irc3111a"}
    ALLOWED_DECISION_TYPES = {
        "accept_previous_offer",
        "resume_existing_scene",
        "new_scene_request",
        "knowledge_query",
        "uncertain",
    }

    def __init__(self, deepseek_service: DeepSeekService | None = None) -> None:
        self.deepseek_service = deepseek_service or DeepSeekService()

    def is_enabled(self) -> bool:
        return bool(settings.DEEPSEEK_ENABLE_SCENE_CARRYOVER_INTENT and self.deepseek_service.is_enabled())

    def classify(
        self,
        query: str,
        memory_context: dict[str, Any],
        assistant_orchestration: dict[str, Any] | None,
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        default_result = self._default_result()
        if not assistant_orchestration:
            default_result["reason"] = "assistant_orchestration_missing"
            return default_result
        if not self.is_enabled():
            default_result["reason"] = "carryover_intent_disabled"
            default_result["fallback_used"] = True
            return default_result

        system_prompt = (
            "你是 NexusClaw 的会话编排判定器。"
            "你的任务不是回答问题，而是判断当前用户输入，是否是在承接上一轮助手发出的办理/填表邀请。"
            "你必须基于完整会话上下文做判断，不能只看关键词。"
            "如果无法确定，请输出 uncertain。"
            "只输出合法 JSON，不要输出解释文本。"
        )
        runtime_prompt = (
            "请根据以下上下文，判断当前用户输入是否应承接到办理流程。\n\n"
            f"【当前用户输入】\n{query.strip()}\n\n"
            f"【最近对话】\n{self._render_recent_turns(memory_context.get('recent_turns') or [])}\n\n"
            f"【上一轮助手编排快照】\n{json.dumps(assistant_orchestration, ensure_ascii=False, indent=2)}\n\n"
            f"【当前 session scene 状态】\n"
            f"{json.dumps(((memory_context.get('state') or {}).get('scene') or {}), ensure_ascii=False, indent=2)}\n\n"
            f"【项目上下文】\n"
            f"{json.dumps(self._project_scene_context(project_context), ensure_ascii=False, indent=2)}\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "should_resume_scene": true,\n'
            '  "decision_type": "accept_previous_offer",\n'
            '  "scene_key": "hk_tax_address_change",\n'
            '  "route_key": "ir1249",\n'
            '  "confidence": 0.0,\n'
            '  "reason": "一句话描述判断原因",\n'
            '  "evidence": ["证据1", "证据2"],\n'
            '  "should_ask_route_clarification": false\n'
            "}"
        )
        try:
            payload = self.deepseek_service.extract_structured_json(
                system_prompt=system_prompt,
                runtime_prompt=runtime_prompt,
                timeout_seconds=settings.DEEPSEEK_SCENE_CARRYOVER_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001
            logger.exception("scene_carryover_intent_call_failed")
            default_result["reason"] = "llm_exception"
            default_result["fallback_used"] = True
            return default_result

        if not isinstance(payload, dict):
            default_result["reason"] = "llm_invalid_payload"
            default_result["fallback_used"] = True
            return default_result

        normalized = self._normalize_payload(payload)
        if normalized["decision_type"] == "uncertain":
            normalized["fallback_used"] = True
        return normalized

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        decision_type = str(payload.get("decision_type") or "uncertain").strip()
        if decision_type not in self.ALLOWED_DECISION_TYPES:
            decision_type = "uncertain"

        scene_key = str(payload.get("scene_key") or "").strip() or None
        if scene_key not in self.ALLOWED_SCENE_KEYS:
            scene_key = None

        route_key = str(payload.get("route_key") or "").strip() or None
        if route_key not in self.ALLOWED_ROUTE_KEYS:
            route_key = None

        confidence_raw = payload.get("confidence")
        try:
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (TypeError, ValueError):
            confidence = 0.0

        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        should_ask_route_clarification = bool(payload.get("should_ask_route_clarification"))
        should_resume_scene = bool(payload.get("should_resume_scene"))
        if decision_type in {"accept_previous_offer", "resume_existing_scene", "new_scene_request"} and scene_key:
            should_resume_scene = True
        if decision_type == "knowledge_query":
            should_resume_scene = False

        return {
            "should_resume_scene": should_resume_scene,
            "decision_type": decision_type,
            "scene_key": scene_key,
            "route_key": route_key,
            "confidence": confidence,
            "reason": str(payload.get("reason") or decision_type),
            "evidence": [str(item) for item in evidence[:4] if str(item).strip()],
            "should_ask_route_clarification": should_ask_route_clarification,
            "fallback_used": False,
        }

    def _project_scene_context(self, project_context: dict[str, Any]) -> dict[str, Any]:
        settings_payload = project_context.get("settings") or {}
        return {
            "enabled_scene_keys": settings_payload.get("enabled_scene_keys_json") or ["hk_tax_address_change"],
            "scene_entry_mode": settings_payload.get("scene_entry_mode") or "chat",
            "supported_routes": {
                "ir1249": "個人 / 通訊地址 / 收稅單地址變更",
                "irc3111a": "公司 / 業務 / 辦公室地址變更",
            },
        }

    def _render_recent_turns(self, recent_turns: list[dict[str, Any]]) -> str:
        if not recent_turns:
            return "[]"
        compact_turns = [
            {
                "query": str(turn.get("query") or ""),
                "answer": str(turn.get("answer") or "")[:500],
            }
            for turn in recent_turns[-2:]
        ]
        return json.dumps(compact_turns, ensure_ascii=False, indent=2)

    def _default_result(self) -> dict[str, Any]:
        return {
            "should_resume_scene": False,
            "decision_type": "uncertain",
            "scene_key": None,
            "route_key": None,
            "confidence": 0.0,
            "reason": "",
            "evidence": [],
            "should_ask_route_clarification": False,
            "fallback_used": False,
        }

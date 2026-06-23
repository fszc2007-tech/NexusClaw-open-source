from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.scene import SceneCase
from app.services.scenes.address_analysis_service import AddressAnalysisService
from app.services.scenes.orchestrator import SceneOrchestrator
from app.services.scenes.rules_service import SceneRulesService
from app.services.scenes.scene_extraction_service import SceneExtractionService
from app.services.scenes.strategy_planner import SceneStrategyPlanner
from app.services.scenes.tool_runtime import SceneToolRuntime


class SceneStateService:
    def __init__(self, db: Session, rules_service: SceneRulesService | None = None) -> None:
        self.db = db
        self.rules_service = rules_service or SceneRulesService()
        self.tool_runtime = SceneToolRuntime(db, self.rules_service)
        self.extraction_service = SceneExtractionService()
        self.address_analysis_service = AddressAnalysisService()
        self.strategy_planner = SceneStrategyPlanner()
        self.orchestrator = SceneOrchestrator(
            self.rules_service,
            self.tool_runtime,
            self.extraction_service,
            self.address_analysis_service,
        )

    def serialize_scene(self, case: SceneCase, project_context: dict[str, Any]) -> dict[str, Any]:
        return self.orchestrator._serialize_scene(case, project_context)

    def get_field_status(self, case: SceneCase) -> dict[str, Any]:
        route_rules = self._get_route_rules(case)
        if not route_rules:
            return {
                "scene_key": case.scene_key,
                "route_key": case.route_key,
                "collected": [],
                "missing": [],
                "invalid": [],
                "visible_fields": [],
                "recommended_fields": [],
                "pending_confirmation": [],
                "confidence": {},
                "field_labels": {},
                "field_options": {},
            }

        payload = dict(case.payload_json or {})
        visible_fields = self.orchestrator._resolve_visible_fields(route_rules, payload)
        recommended_fields = self.orchestrator._resolve_recommended_fields(route_rules, payload)
        missing_fields = self.orchestrator._compute_missing_fields(route_rules, payload)
        pending_confirmation = self.orchestrator._get_pending_confirmation_fields(payload)
        field_labels = route_rules.get("field_labels", {})
        field_options = self.orchestrator._build_field_options(route_rules, payload)
        public_payload = self.orchestrator._public_payload(payload)
        progress = self.orchestrator._build_progress(route_rules, payload, missing_fields)
        recovery = self.orchestrator._build_recovery(
            case,
            missing_fields,
            [],
            self.orchestrator._build_available_artifacts(dict(case.artifacts_json or {}), "draft_only"),
        )

        collected = [
            field
            for field in dict.fromkeys([*visible_fields, *recommended_fields, *field_labels.keys()])
            if public_payload.get(field) not in (None, "", [], {})
        ]
        confidence = dict(payload.get("_field_confidence") or {})
        address_analysis = dict(payload.get("_address_analysis") or {})

        return {
            "scene_key": case.scene_key,
            "route_key": case.route_key,
            "collected": collected,
            "missing": missing_fields,
            "invalid": [],
            "visible_fields": visible_fields,
            "recommended_fields": recommended_fields,
            "pending_confirmation": pending_confirmation,
            "confidence": confidence,
            "address_analysis": address_analysis,
            "progress": progress,
            "recovery": recovery,
            "field_labels": field_labels,
            "field_options": field_options,
        }

    def merge_payload(
        self,
        case: SceneCase,
        payload_patch: dict[str, Any],
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        route_rules = self._require_route_rules(case)
        current_payload = dict(case.payload_json or {})
        next_payload = dict(current_payload)
        invalid_fields: list[dict[str, str]] = []
        changed_fields: list[str] = []

        allowed_fields = self._allowed_input_fields(route_rules, current_payload)
        for field_name, raw_value in payload_patch.items():
            if field_name not in allowed_fields:
                invalid_fields.append({"field": field_name, "reason": "unsupported_field"})
                continue

            previous_value = next_payload.get(field_name)
            if raw_value in (None, ""):
                next_payload = self._clear_field(next_payload, field_name)
                if previous_value not in (None, "", [], {}):
                    changed_fields.append(field_name)
                continue

            normalized_value = self.orchestrator._normalize_extracted_value(route_rules, field_name, raw_value)
            if normalized_value in (None, "", [], {}):
                invalid_fields.append({"field": field_name, "reason": "invalid_value"})
                continue

            next_payload[field_name] = normalized_value
            if previous_value != normalized_value:
                changed_fields.append(field_name)
                next_payload = self.orchestrator._remove_pending_confirmation(next_payload, field_name)

        if route_rules.get("form_no") == "IR1249" and next_payload.get("full_name") and not next_payload.get("signer_name"):
            next_payload["signer_name"] = next_payload["full_name"]
            if current_payload.get("signer_name") != next_payload["signer_name"]:
                changed_fields.append("signer_name")

        previous_address_structured = current_payload.get("address_structured")
        previous_address_analysis = current_payload.get("_address_analysis")
        previous_field_confidence = current_payload.get("_field_confidence")
        if next_payload.get("new_address") or "address_structured" in payload_patch:
            next_payload = self.orchestrator._enrich_address_payload(next_payload)
            if previous_address_structured != next_payload.get("address_structured"):
                changed_fields.append("address_structured")
            if previous_address_analysis != next_payload.get("_address_analysis"):
                changed_fields.append("_address_analysis")
            if previous_field_confidence != next_payload.get("_field_confidence"):
                changed_fields.append("_field_confidence")

        if changed_fields:
            case.payload_json = {key: value for key, value in next_payload.items() if value not in (None, "", [], {})}
            self._invalidate_downstream_artifacts(case)
            self._recompute_case_state(case, route_rules)

        scene_payload = self.serialize_scene(case, project_context)
        field_status = self.get_field_status(case)
        field_status["invalid"] = invalid_fields
        field_status["changed"] = list(dict.fromkeys(changed_fields))
        return {
            "scene": scene_payload,
            "field_status": field_status,
        }

    def get_next_actions(
        self,
        case: SceneCase,
        project_context: dict[str, Any],
        *,
        intent_mode: str | None = None,
    ) -> dict[str, Any]:
        scene_payload = self.serialize_scene(case, project_context)
        field_status = self.get_field_status(case)
        allowed_next_actions = scene_payload.get("next_actions", [])
        runtime_payload = dict(scene_payload.get("runtime") or {})
        highest_priority_missing_field = field_status["missing"][0] if field_status["missing"] else None
        next_prompt = self._build_next_prompt(case, field_status["missing"])
        next_question = next_prompt.get("question")
        next_question_fields = list(next_prompt.get("fields") or [])
        next_prompt_mode = next_prompt.get("collection_mode")

        blocking_reason = None
        if case.state == "ROUTE_AMBIGUOUS":
            blocking_reason = "ROUTE_SELECTION_REQUIRED"
        elif field_status["missing"]:
            blocking_reason = "FORM_FIELDS_MISSING"
        elif case.state == "REQUIRE_SIGNATURE_CONFIRMATION":
            blocking_reason = "USER_CONFIRMATION_REQUIRED"
        elif not allowed_next_actions and case.state == "DONE":
            blocking_reason = "CASE_COMPLETED"

        next_actions_payload = {
            "scene_key": case.scene_key,
            "case_id": case.case_code,
            "route_key": case.route_key,
            "state": case.state,
            "allowed_next_actions": allowed_next_actions,
            "confirmation_requirements": runtime_payload.get("confirmation_requirements", []),
            "progress": runtime_payload.get("progress", {}),
            "available_artifacts": runtime_payload.get("available_artifacts", {}),
            "blocking_reason": blocking_reason,
            "highest_priority_missing_field": highest_priority_missing_field,
            "next_question": next_question,
            "next_question_fields": next_question_fields,
            "next_prompt_mode": next_prompt_mode,
            "recovery": runtime_payload.get("recovery", {}),
        }
        next_actions_payload["planner"] = self.strategy_planner.build(
            case,
            scene_payload,
            field_status,
            next_actions_payload,
            intent_mode=intent_mode,
        )
        return next_actions_payload

    def attach_planner(self, scene_payload: dict[str, Any], next_actions_payload: dict[str, Any] | None) -> dict[str, Any]:
        result = dict(scene_payload or {})
        runtime = dict(result.get("runtime") or {})
        runtime["planner"] = ((next_actions_payload or {}).get("planner") or None)
        result["runtime"] = runtime
        return result

    def _build_next_prompt(self, case: SceneCase, missing_fields: list[str]) -> dict[str, Any]:
        if not missing_fields:
            if case.state == "REQUIRE_SIGNATURE_CONFIRMATION":
                return {
                    "fields": [],
                    "question": "請先確認你已完成簽署，之後我才能繼續處理郵件預覽或發送。",
                    "collection_mode": "confirm",
                }
            return {"fields": [], "question": None, "collection_mode": "idle"}

        route_rules = self._require_route_rules(case)
        payload = dict(case.payload_json or {})
        field_name = missing_fields[0]
        pending_confirmation_fields = self.orchestrator._get_pending_confirmation_fields(payload)
        if field_name in pending_confirmation_fields:
            return self.strategy_planner.build_confirmation_bundle(route_rules, payload, pending_confirmation_fields)
        return self.strategy_planner.build_collection_bundle(
            route_rules,
            payload,
            missing_fields,
            pending_confirmation_fields=pending_confirmation_fields,
            address_analysis=dict(payload.get("_address_analysis") or {}),
        )

    def _allowed_input_fields(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> set[str]:
        fields = set(route_rules.get("field_labels", {}).keys())
        fields.update(route_rules.get("required_fields", []))
        fields.update(self.orchestrator._resolve_visible_fields(route_rules, payload))
        fields.update(self.orchestrator._resolve_recommended_fields(route_rules, payload))
        if route_rules.get("form_no") == "IR1249":
            for profile in (route_rules.get("applicant_profiles") or {}).values():
                fields.update(profile.get("required_fields", []))
                fields.update(profile.get("visible_fields", []))
                fields.update(profile.get("recommended_fields", []))
        return {field for field in fields if field}

    def _clear_field(self, payload: dict[str, Any], field_name: str) -> dict[str, Any]:
        result = dict(payload)
        previous_value = result.get(field_name)
        result.pop(field_name, None)
        result = self.orchestrator._remove_pending_confirmation(result, field_name)
        if field_name == "new_address":
            result.pop("address_structured", None)
            result.pop("_address_analysis", None)
            confidence = dict(result.get("_field_confidence") or {})
            confidence.pop("address_structured", None)
            if confidence:
                result["_field_confidence"] = confidence
            else:
                result.pop("_field_confidence", None)
        if field_name == "full_name" and (
            result.get("signer_name") == previous_value
            or self.orchestrator._strip_name_prefix(str(result.get("signer_name") or "")) == str(previous_value or "")
        ):
            result.pop("signer_name", None)
        return result

    def _invalidate_downstream_artifacts(self, case: SceneCase) -> None:
        flags = dict(case.flags_json or {})
        artifacts = dict(case.artifacts_json or {})
        for key in ["pdf_generated", "signature_confirmed", "user_confirmed_send"]:
            flags.pop(key, None)
        for key in ["preview_pdf_path", "final_pdf_path", "mail_preview", "send_result"]:
            artifacts.pop(key, None)
        case.flags_json = flags
        case.artifacts_json = artifacts
        case.status = "active"
        case.completed_at = None

    def _recompute_case_state(self, case: SceneCase, route_rules: dict[str, Any]) -> None:
        payload = dict(case.payload_json or {})
        missing_fields = self.orchestrator._compute_missing_fields(route_rules, payload)
        case.state = "COLLECT_FORM" if missing_fields else "REVIEW_FORM"
        case.summary = self.orchestrator._build_summary(route_rules, payload, missing_fields)
        case.updated_at = datetime.utcnow()

    def _get_route_rules(self, case: SceneCase) -> dict[str, Any] | None:
        if not case.route_key:
            return None
        return self.rules_service.get_route_rules(case.scene_key, case.route_key)

    def _require_route_rules(self, case: SceneCase) -> dict[str, Any]:
        route_rules = self._get_route_rules(case)
        if not route_rules:
            raise ValueError("ROUTE_SELECTION_REQUIRED")
        return route_rules

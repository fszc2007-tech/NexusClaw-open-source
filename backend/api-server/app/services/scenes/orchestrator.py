from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import Any

from app.core.config import settings
from app.models.scene import SceneCase
from app.services.scenes.address_analysis_service import AddressAnalysisService
from app.services.scenes.scene_extraction_service import SceneExtractionService
from app.services.scenes.rules_service import SceneRulesService
from app.services.scenes.tool_runtime import SceneToolRuntime
from app.services.scenes.strategy_planner import SceneStrategyPlanner


class SceneOrchestrator:
    HIDDEN_PAYLOAD_FIELDS = {"address_structured", "_field_confidence", "_pending_confirmation_fields", "_address_analysis"}
    AFFIRMATIVE_RESPONSE_PATTERN = re.compile(
        r"^(是|對|对|正确|沒錯|没错|yes|y|ok|好|好的|可以|需要|要|係)(啊|呀|啦|喇|呢|哦|喔|嘛|吧|唷|哇|诶|欸)*$"
    )
    NEGATIVE_RESPONSE_PATTERN = re.compile(
        r"^(不是|不对|不對|不正确|no|n|唔係|不用|不需要)(啊|呀|啦|喇|呢|哦|喔|嘛|吧|唷|哇|诶|欸)*(重新填|重新填写)?$"
    )
    ACTION_LABELS = {
        "confirm_payload": "確認資料",
        "generate_pdf": "生成 PDF",
        "confirm_signature": "確認已簽署",
        "preview_mail": "預覽郵件",
        "send_mail": "發送郵件",
    }
    GATED_ACTIONS = {"confirm_payload", "confirm_signature", "send_mail"}

    def __init__(
        self,
        rules_service: SceneRulesService | None = None,
        tool_runtime: SceneToolRuntime | None = None,
        extraction_service: SceneExtractionService | None = None,
        address_analysis_service: AddressAnalysisService | None = None,
        strategy_planner: SceneStrategyPlanner | None = None,
    ) -> None:
        self.rules_service = rules_service or SceneRulesService()
        if not tool_runtime:
            raise ValueError("tool_runtime_required")
        self.tool_runtime = tool_runtime
        self.extraction_service = extraction_service or SceneExtractionService()
        self.address_analysis_service = address_analysis_service or AddressAnalysisService()
        self.strategy_planner = strategy_planner or SceneStrategyPlanner()

    def handle_message(
        self,
        case: SceneCase,
        route_decision: dict[str, Any],
        query: str,
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        scene_rules = self.rules_service.get_scene_rules(case.scene_key)
        case_route = route_decision.get("route_key") or case.route_key

        if not case_route:
            clarified_route = self._clarify_route(scene_rules, query)
            if clarified_route:
                case_route = clarified_route

        if not case_route:
            case.state = "ROUTE_AMBIGUOUS"
            case.summary = "需要先確認是通訊地址變更還是業務地址變更。"
            self.tool_runtime.write_event(
                case,
                event_type="route_ambiguous",
                actor_type="assistant",
                request_json={"query": query},
                result_json={"state": case.state},
            )
            return {
                "message": self._build_ambiguous_route_message(),
                "scene": self._serialize_scene(case, project_context),
            }

        case.route_key = case_route
        route_rules = self.rules_service.get_route_rules(case.scene_key, case.route_key)
        payload = dict(case.payload_json or {})
        confirmation_feedback = self._resolve_confirmation_feedback(route_rules, payload, query)
        payload = self._merge_payload(route_rules, payload, query)
        case.payload_json = payload
        missing_fields = self._compute_missing_fields(route_rules, payload)
        case.state = "COLLECT_FORM" if missing_fields else "REVIEW_FORM"
        case.summary = self._build_summary(route_rules, payload, missing_fields)
        case.updated_at = datetime.utcnow()
        self.tool_runtime.write_event(
            case,
            event_type="message_processed",
            actor_type="assistant",
            request_json={"query": query},
            result_json={"route_key": case.route_key, "missing_fields": missing_fields},
        )

        if missing_fields:
            next_prompt = self.strategy_planner.build_collection_bundle(
                route_rules,
                payload,
                missing_fields,
                pending_confirmation_fields=self._get_pending_confirmation_fields(payload),
                address_analysis=dict(payload.get("_address_analysis") or {}),
            )
            next_field = missing_fields[0]
            if next_field in self._get_pending_confirmation_fields(payload):
                confirmation_bundle = self.strategy_planner.build_confirmation_bundle(
                    route_rules,
                    payload,
                    self._get_pending_confirmation_fields(payload),
                )
                next_prompt_mode = str(confirmation_bundle.get("collection_mode") or next_prompt.get("collection_mode") or "")
                next_question = str(
                    confirmation_bundle.get("question") or self._build_confirmation_question(route_rules, next_field, payload)
                )
            else:
                next_prompt_mode = str(next_prompt.get("collection_mode") or "")
                next_question = str(next_prompt.get("question") or route_rules["field_questions"][next_field])
            message = self._build_collection_message(
                route_rules,
                next_question,
                payload,
                prompt_mode=next_prompt_mode,
                confirmation_feedback=confirmation_feedback,
            )
        else:
            message = self._build_ready_message(route_rules)

        return {
            "message": message,
            "scene": self._serialize_scene(case, project_context),
        }

    def perform_action(
        self,
        case: SceneCase,
        action_name: str,
        project_context: dict[str, Any],
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        route_rules = self.rules_service.get_route_rules(case.scene_key, case.route_key or "")
        payload = dict(case.payload_json or {})
        flags = dict(case.flags_json or {})
        artifacts = dict(case.artifacts_json or {})
        missing_fields = self._compute_missing_fields(route_rules, payload)

        if action_name == "confirm_payload":
            if missing_fields:
                raise ValueError("FORM_FIELDS_MISSING")
            self._assert_action_confirmation(case, action_name, payload, flags, artifacts, missing_fields, confirmation_token)
            flags["payload_confirmed"] = True
            case.flags_json = flags
            case.state = "REVIEW_FORM"
            message = "資料摘要已確認，可以生成 PDF。"
        elif action_name == "generate_pdf":
            if missing_fields:
                raise ValueError("FORM_FIELDS_MISSING")
            if not flags.get("payload_confirmed"):
                raise ValueError("USER_CONFIRMATION_REQUIRED")
            pdf_artifacts = self.tool_runtime.generate_pdf(case, route_rules["form_no"], payload)
            artifacts.update(
                {
                    "preview_pdf_path": pdf_artifacts["preview_path"],
                    "final_pdf_path": pdf_artifacts["final_path"],
                }
            )
            flags["pdf_generated"] = True
            case.artifacts_json = artifacts
            case.flags_json = flags
            case.state = "REQUIRE_SIGNATURE_CONFIRMATION" if route_rules.get("require_signature_confirmation") else "SHOW_SUBMISSION_GUIDE"
            message = "PDF 已生成。請繼續完成簽署確認，或查看官方提交指引。"
        elif action_name == "confirm_signature":
            if not flags.get("pdf_generated"):
                raise ValueError("PDF_GENERATION_FAILED")
            self._assert_action_confirmation(case, action_name, payload, flags, artifacts, missing_fields, confirmation_token)
            flags["signature_confirmed"] = True
            case.flags_json = flags
            case.state = "REVIEW_MAIL"
            message = "已記錄簽署確認。下一步可以預覽郵件。"
        elif action_name == "preview_mail":
            if not route_rules.get("allow_email_submission"):
                raise ValueError("MAIL_SEND_BLOCKED")
            if not flags.get("pdf_generated"):
                raise ValueError("PDF_GENERATION_FAILED")
            if route_rules.get("require_signature_confirmation") and not flags.get("signature_confirmed"):
                raise ValueError("USER_CONFIRMATION_REQUIRED")
            mail_preview = self.tool_runtime.preview_mail(
                route_rules,
                payload,
                {"final_path": artifacts.get("final_pdf_path")},
            )
            artifacts["mail_preview"] = mail_preview
            case.artifacts_json = artifacts
            case.state = "REVIEW_MAIL"
            message = "郵件預覽已生成。若專案啟用了真實發信，可繼續發送。"
        elif action_name == "send_mail":
            if not route_rules.get("allow_email_submission"):
                raise ValueError("MAIL_SEND_BLOCKED")
            if not flags.get("pdf_generated"):
                raise ValueError("PDF_GENERATION_FAILED")
            if route_rules.get("require_signature_confirmation") and not flags.get("signature_confirmed"):
                raise ValueError("USER_CONFIRMATION_REQUIRED")
            mail_preview = artifacts.get("mail_preview")
            if not mail_preview:
                raise ValueError("MAIL_PREVIEW_FAILED")
            self._assert_action_confirmation(case, action_name, payload, flags, artifacts, missing_fields, confirmation_token)
            send_result = self.tool_runtime.send_mail(mail_preview)
            artifacts["send_result"] = send_result
            flags["user_confirmed_send"] = True
            case.artifacts_json = artifacts
            case.flags_json = flags
            case.state = "DONE"
            case.status = "completed"
            case.completed_at = datetime.utcnow()
            message = "郵件已發送並完成審計記錄。"
        else:
            raise ValueError("unsupported_scene_action")

        case.updated_at = datetime.utcnow()
        case.summary = self._build_summary(route_rules, payload, self._compute_missing_fields(route_rules, payload))
        self.tool_runtime.write_event(
            case,
            event_type=f"action_{action_name}",
            actor_type="user",
            request_json={"action_name": action_name},
            result_json={"state": case.state, "status": case.status},
        )
        return {
            "message": message,
            "scene": self._serialize_scene(case, project_context),
        }

    def _serialize_scene(self, case: SceneCase, project_context: dict[str, Any]) -> dict[str, Any]:
        route_rules = self.rules_service.get_route_rules(case.scene_key, case.route_key) if case.route_key else None
        payload = dict(case.payload_json or {})
        public_payload = self._public_payload(payload)
        display_payload = self._build_display_payload(route_rules, payload, public_payload) if route_rules else dict(public_payload)
        missing_fields = self._compute_missing_fields(route_rules, payload) if route_rules else []
        pending_confirmation_fields = self._get_pending_confirmation_fields(payload) if route_rules else []
        visible_fields = self._resolve_visible_fields(route_rules, payload) if route_rules else []
        recommended_fields = self._resolve_recommended_fields(route_rules, payload) if route_rules else []
        field_options = self._build_field_options(route_rules, payload) if route_rules else {}
        runtime_config = self.rules_service.get_scene_runtime_config(project_context)
        mail_delivery_mode = runtime_config.get("mail_delivery_mode", "draft_only")
        flags = dict(case.flags_json or {})
        artifacts = dict(case.artifacts_json or {})

        next_actions: list[dict[str, Any]] = []
        if case.state in {"COLLECT_FORM", "REVIEW_FORM"} and not missing_fields:
            if not flags.get("payload_confirmed"):
                next_actions.append({"name": "confirm_payload", "label": "確認資料"})
            else:
                next_actions.append({"name": "generate_pdf", "label": "生成 PDF"})
        if case.state == "REQUIRE_SIGNATURE_CONFIRMATION":
            next_actions.append({"name": "confirm_signature", "label": "確認已簽署"})
        if route_rules and route_rules.get("allow_email_submission") and flags.get("pdf_generated"):
            if route_rules.get("require_signature_confirmation") and flags.get("signature_confirmed"):
                next_actions.append({"name": "preview_mail", "label": "預覽郵件"})
                if artifacts.get("mail_preview") and mail_delivery_mode == "send_enabled":
                    next_actions.append({"name": "send_mail", "label": "發送郵件"})

        confirmation_requirements = self._build_confirmation_requirements(case, payload, next_actions, missing_fields, flags, artifacts)
        confirmation_by_action = {item["action_name"]: item for item in confirmation_requirements}
        for action in next_actions:
            requirement = confirmation_by_action.get(action["name"])
            action["requires_confirmation"] = bool(requirement)
            if requirement:
                action["confirmation_token"] = requirement["confirmation_token"]
                action["confirmation_prompt"] = requirement["confirmation_prompt"]
                action["confirmation_type"] = requirement["confirmation_type"]

        progress = self._build_progress(route_rules, payload, missing_fields)
        available_artifacts = self._build_available_artifacts(artifacts, mail_delivery_mode)
        recovery = self._build_recovery(case, missing_fields, confirmation_requirements, available_artifacts)
        artifact_version = self._build_artifact_version(case)

        panels = {
            "summary": {
                "title": route_rules["title"] if route_rules else "地址變更場景",
                "payload": public_payload,
                "display_payload": display_payload,
                "missing_fields": missing_fields,
                "route_key": case.route_key,
                "field_labels": route_rules.get("field_labels", {}) if route_rules else {},
                "visible_fields": visible_fields,
                "recommended_fields": recommended_fields,
                "field_options": field_options,
                "pending_confirmation_fields": pending_confirmation_fields,
            },
            "route_overview": {
                "form_no": route_rules.get("form_no") if route_rules else None,
                "title": route_rules.get("title") if route_rules else "地址變更場景",
                "handling_mode": self._build_handling_mode(route_rules),
                "description": self._build_route_overview_description(route_rules, mail_delivery_mode),
                "submission_guide": route_rules.get("submission_guide") if route_rules else None,
            },
            "pdf_preview": {
                "preview_url": self._build_artifact_url(case, "preview_pdf", artifact_version)
                if artifacts.get("preview_pdf_path")
                else None,
                "final_url": self._build_artifact_url(case, "final_pdf", artifact_version)
                if artifacts.get("final_pdf_path")
                else None,
            },
            "mail_preview": artifacts.get("mail_preview"),
        }

        return {
            "scene_key": case.scene_key,
            "case_id": case.case_code,
            "state": case.state,
            "status": case.status,
            "route_key": case.route_key,
            "summary": case.summary,
            "missing_fields": missing_fields,
            "next_actions": next_actions,
            "runtime": {
                "stage": {
                    "code": case.state,
                    "label": self._build_stage_label(case.state),
                },
                "progress": progress,
                "available_artifacts": available_artifacts,
                "confirmation_requirements": confirmation_requirements,
                "last_activity": flags.get("_runtime_last_activity"),
                "last_failure": flags.get("_runtime_last_failure"),
                "recovery": recovery,
            },
            "panels": panels,
            "citations": (route_rules or {}).get("citations") or [],
            "mail_delivery_mode": mail_delivery_mode,
        }

    def _clarify_route(self, scene_rules: dict[str, Any], query: str) -> str | None:
        normalized = query.lower()
        matched: list[str] = []
        for route_key, route_rules in scene_rules.get("routes", {}).items():
            if any(keyword.lower() in normalized for keyword in route_rules.get("route_keywords", [])):
                matched.append(route_key)
        if len(matched) == 1:
            return matched[0]
        return None

    def _merge_payload(self, route_rules: dict[str, Any], payload: dict[str, Any], query: str) -> dict[str, Any]:
        result = dict(payload)
        normalized = query.strip()
        current_missing = self._compute_missing_fields(route_rules, result)
        current_visible = self._resolve_visible_fields(route_rules, result)
        expected_field = current_missing[0] if current_missing else None
        pending_confirmation_fields = self._get_pending_confirmation_fields(result)
        previous_expected_value = result.get(expected_field) if expected_field else None

        if expected_field and expected_field in pending_confirmation_fields:
            confirmation_bundle = self.strategy_planner.build_confirmation_bundle(route_rules, result, pending_confirmation_fields)
            bundle_fields = list(confirmation_bundle.get("fields") or [])
            if self._is_affirmative_response(normalized):
                if len(bundle_fields) > 1:
                    return self._finalize_pending_confirmation_bundle(result, bundle_fields, confirmed=True)
                return self._finalize_pending_confirmation(result, expected_field, confirmed=True)
            if self._is_negative_response(normalized):
                if len(bundle_fields) > 1:
                    return self._finalize_pending_confirmation_bundle(result, bundle_fields, confirmed=False)
                return self._finalize_pending_confirmation(result, expected_field, confirmed=False)

        llm_extracted = self.extraction_service.extract_fields(
            route_rules=route_rules,
            payload=result,
            query=normalized,
            missing_fields=current_missing,
            visible_fields=current_visible,
        )
        result = self._apply_extracted_fields(route_rules, result, llm_extracted)

        date_match = re.search(r"((?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|下个月\s*\d+\s*号|\d+\s*月\s*\d+\s*日)", normalized)
        if date_match and not result.get("effective_date"):
            result["effective_date"] = self._normalize_date_value(date_match.group(1))
        looks_like_date_only = bool(date_match and date_match.group(0) == normalized)

        phone_field = "daytime_phone" if route_rules["form_no"] == "IR1249" else "telephone_no"
        phone_match = None
        if not looks_like_date_only and not result.get(phone_field):
            for candidate in re.finditer(r"(\+?\d[\d\s-]{6,}\d)", normalized):
                candidate_raw = candidate.group(1)
                if date_match and candidate_raw == date_match.group(1):
                    continue
                compact_phone = re.sub(r"[^\d+]", "", candidate_raw)
                if len(compact_phone.replace("+", "")) < 8:
                    continue
                phone_match = candidate
        if phone_match:
            phone_value = re.sub(r"[^\d+]", "", phone_match.group(1))
            result[phone_field] = phone_value

        normalized_reference = self._normalize_reference_input(normalized, expected_field)
        if normalized_reference and expected_field in {
            "individual_file_no",
            "property_tax_file_no",
            "profits_tax_file_no",
            "employer_return_file_no",
        } and not result.get(expected_field):
            result[expected_field] = normalized_reference
        elif normalized_reference and not result.get("reference_id"):
            result["reference_id"] = normalized_reference

        if route_rules["form_no"] == "IR1249":
            applicant_type_map = {
                "salary earner": "salary earner",
                "property owner": "property owner",
                "sole proprietor": "sole proprietor",
                "business owner": "business owner",
                "employer": "employer",
                "受薪": "salary earner",
                "物业": "property owner",
                "独资": "sole proprietor",
                "业务": "business owner",
                "雇主": "employer",
            }
            for keyword, value in applicant_type_map.items():
                if keyword.lower() in normalized.lower() and not result.get("applicant_type"):
                    result["applicant_type"] = value
                    break
            if not result.get("applicant_type") and self._should_infer_applicant_type(normalized):
                result["applicant_type"] = self._infer_ir1249_applicant_type(normalized, result)
        else:
            br_match = re.search(r"\b([A-Z0-9-]{6,20})\b", normalized, re.IGNORECASE)
            if br_match and ("br" in normalized.lower() or "商业登记" in normalized) and not result.get("business_registration_no"):
                result["business_registration_no"] = br_match.group(1).upper()

        if self._looks_like_actual_address_input(normalized) and not result.get("new_address"):
            result["new_address"] = normalized

        if ("签署人" in normalized or "signer" in normalized.lower() or expected_field == "signer_name") and not result.get("signer_name"):
            result["signer_name"] = self._strip_name_prefix(
                normalized.replace("签署人", "").replace("signer", "").replace("是", "").strip() or normalized
            )
        elif expected_field in {"full_name", "individual_name"} and not self._looks_like_non_name_input(normalized) and not result.get("full_name"):
            result["full_name"] = self._strip_name_prefix(normalized)
            if route_rules["form_no"] == "IR1249":
                result["signer_name"] = result.get("signer_name") or self._strip_name_prefix(normalized)

        if route_rules["form_no"] == "IR1249" and result.get("full_name") and not result.get("signer_name"):
            result["signer_name"] = result["full_name"]

        if route_rules["form_no"] == "IRC3111A":
            if ("公司" in normalized or "business name" in normalized.lower() or expected_field == "business_name") and not result.get("business_name"):
                result["business_name"] = normalized

        if expected_field and not result.get(expected_field) and not self._is_generic_form_start_request(normalized) and self._should_fill_expected_field(expected_field, normalized):
            result[expected_field] = normalized

        if expected_field and expected_field in pending_confirmation_fields:
            if result.get(expected_field) and result.get(expected_field) != previous_expected_value:
                result = self._remove_pending_confirmation(result, expected_field)

        result = self._enrich_address_payload(result)
        return {key: value for key, value in result.items() if value}

    def _apply_extracted_fields(
        self,
        route_rules: dict[str, Any],
        payload: dict[str, Any],
        extracted_fields: dict[str, Any],
    ) -> dict[str, Any]:
        if not extracted_fields:
            return payload

        result = dict(payload)
        field_confidence = extracted_fields.get("_field_confidence")
        low_confidence_fields: set[str] = set()
        if isinstance(field_confidence, dict):
            low_confidence_fields = {
                key
                for key, value in field_confidence.items()
                if value == "low"
            }
            next_confidence = {
                **dict(result.get("_field_confidence") or {}),
                **{
                    key: value
                    for key, value in field_confidence.items()
                    if value in {"high", "medium", "low"}
                },
            }
            if next_confidence:
                result["_field_confidence"] = next_confidence
        for key, raw_value in extracted_fields.items():
            if key == "_field_confidence":
                continue
            value = self._normalize_extracted_value(route_rules, key, raw_value)
            if value in (None, "", [], {}):
                continue
            result[key] = value
            if key in low_confidence_fields:
                result = self._add_pending_confirmation(result, key)

        if route_rules.get("form_no") == "IR1249" and result.get("full_name") and not result.get("signer_name"):
            result["signer_name"] = result["full_name"]
        return result

    def _normalize_extracted_value(self, route_rules: dict[str, Any], field: str, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
        else:
            cleaned = value

        if field == "address_structured":
            return self._normalize_address_structured(cleaned)
        if field == "applicant_type":
            return self._normalize_applicant_type_value(route_rules, cleaned)
        if field in {"reference_id", "individual_file_no", "property_tax_file_no", "profits_tax_file_no", "employer_return_file_no"}:
            if not isinstance(cleaned, str):
                return None
            return self._normalize_reference_input(cleaned, field)
        if field in {"daytime_phone", "telephone_no"}:
            if not isinstance(cleaned, str):
                return None
            digits_only = re.sub(r"[^\d+]", "", cleaned)
            return digits_only or None
        if field in {"change_related_profits_tax_postal_address", "change_related_employer_return_postal_address", "company_chop", "user_confirmation"}:
            return self._normalize_bool_value(cleaned)
        if field in {"full_name", "individual_name", "signer_name"}:
            if not isinstance(cleaned, str) or self._looks_like_non_name_input(cleaned):
                return None
            return cleaned
        if field == "new_address":
            if not isinstance(cleaned, str) or self._is_generic_form_start_request(cleaned) or not self._looks_like_actual_address_input(cleaned):
                return None
            return cleaned
        if isinstance(cleaned, str):
            return cleaned or None
        return cleaned

    def _normalize_address_structured(self, value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None
        normalized: dict[str, str] = {}
        for key in ["area", "flat_room", "block", "floor", "building", "street", "district"]:
            raw = value.get(key)
            if not isinstance(raw, str):
                continue
            cleaned = " ".join(raw.strip().split())
            if not cleaned:
                continue
            if key == "area":
                mapped_area = self._normalize_area_value(cleaned)
                if mapped_area:
                    normalized[key] = mapped_area
                continue
            normalized[key] = cleaned
        return normalized or None

    def _normalize_applicant_type_value(self, route_rules: dict[str, Any], value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        candidate_map = {
            "salary earner": "salary earner",
            "受薪人士": "salary earner",
            "受薪": "salary earner",
            "property owner": "property owner",
            "物业持有人": "property owner",
            "物業持有人": "property owner",
            "sole proprietor": "sole proprietor",
            "独资经营者": "sole proprietor",
            "獨資經營者": "sole proprietor",
            "business owner": "business owner",
            "业务负责人": "business owner",
            "業務負責人": "business owner",
            "employer": "employer",
            "雇主": "employer",
        }
        mapped = candidate_map.get(normalized) or candidate_map.get(value.strip())
        if not mapped:
            valid_values = {
                str(option.get("value")).strip()
                for option in (route_rules.get("field_options") or {}).get("applicant_type", [])
                if option.get("value")
            }
            return value.strip() if value.strip() in valid_values else None
        return mapped

    def _normalize_area_value(self, value: str) -> str | None:
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

    def _normalize_bool_value(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "y", "1", "是", "需要", "需要同步", "要", "会"}:
                return True
            if normalized in {"false", "no", "n", "0", "否", "不用", "不需要", "不会"}:
                return False
        return None

    def _normalize_date_value(self, value: str) -> str:
        raw = value.strip()
        compact_match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
        if compact_match:
            return f"{compact_match.group(1)}-{compact_match.group(2)}-{compact_match.group(3)}"
        return raw

    def _compute_missing_fields(self, route_rules: dict[str, Any] | None, payload: dict[str, Any]) -> list[str]:
        if not route_rules:
            return []
        required_fields = self._resolve_required_fields(route_rules, payload)
        pending_confirmation_fields = self._get_pending_confirmation_fields(payload)
        missing: list[str] = []
        for field in pending_confirmation_fields:
            if field not in missing:
                missing.append(field)
        for field in required_fields:
            value = payload.get(field)
            if field == "new_address" and not self._is_address_complete(str(value or ""), payload):
                if field not in missing:
                    missing.append(field)
                continue
            if not value:
                if field not in missing:
                    missing.append(field)
        return self.strategy_planner.prioritize_missing_fields(
            route_rules,
            payload,
            missing,
            pending_confirmation_fields=pending_confirmation_fields,
            address_analysis=dict(payload.get("_address_analysis") or {}),
        )

    def _build_summary(self, route_rules: dict[str, Any], payload: dict[str, Any], missing_fields: list[str]) -> str:
        labels = route_rules.get("field_labels", {})
        public_payload = self._public_payload(payload)
        display_payload = self._build_display_payload(route_rules, payload, public_payload)
        filled = [f"{labels.get(key, key)}: {display_payload.get(key, value)}" for key, value in public_payload.items()]
        if missing_fields:
            missing_labels = [labels.get(field, field) for field in missing_fields]
            return f"當前已收集：{'；'.join(filled) or '暫無'}。仍缺少：{'、'.join(missing_labels)}。"
        return f"當前已收集：{'；'.join(filled)}。資料已齊，可進入下一步。"

    def _build_ambiguous_route_message(self) -> str:
        return (
            "### 我可以先幫你判斷應該用哪一份表格\n"
            "如果你要改的是個人或收稅單通訊地址，我會帶你走 `IR1249`，並繼續幫你收集資料、填寫官方 PDF。\n"
            "如果你要改的是公司或業務地址，我會帶你走 `IRC3111A`，並生成 PDF 與官方提交指引。\n\n"
            "### 請先確認這次屬於哪一種\n"
            "1. 個人 / 通訊地址變更\n"
            "2. 公司 / 業務地址變更"
        )

    def _build_collection_message(
        self,
        route_rules: dict[str, Any],
        next_question: str,
        payload: dict[str, Any],
        *,
        prompt_mode: str | None = None,
        confirmation_feedback: dict[str, Any] | None = None,
    ) -> str:
        filled_count = len(payload)
        if route_rules["form_no"] == "IR1249":
            ability = (
                "我會繼續逐項收集資料，幫你填寫官方 `IR1249`，生成 PDF，並在設定允許時提供郵件預覽或發送。"
            )
        else:
            ability = (
                "我會繼續逐項收集資料，幫你填寫官方 `IRC3111A`，生成 PDF，並提示你按官方方式提交。"
            )
        prompt_mode = str(prompt_mode or "").strip().lower()
        feedback_type = str((confirmation_feedback or {}).get("type") or "").strip().lower()
        feedback_fields = list((confirmation_feedback or {}).get("fields") or [])
        field_labels = route_rules.get("field_labels", {})
        if feedback_type == "confirmed":
            progress = "已按你的確認保留剛才解析的資料。"
        elif feedback_type == "rejected":
            labels = [field_labels.get(field, field) for field in feedback_fields]
            if labels:
                progress = f"已按你的回覆撤回剛才解析的「{'、'.join(labels)}」，接下來重新收集。"
            else:
                progress = "已按你的回覆撤回剛才解析的資料，接下來重新收集。"
        elif prompt_mode in {"confirm", "confirm_bundle"}:
            progress = "我先幫你確認剛才解析的資料，確認無誤後再繼續推進。"
        else:
            progress = "已開始記錄你剛才提供的資料。" if filled_count else "我們先從第一項資料開始。"
        option_block = ""
        if route_rules["form_no"] == "IR1249" and next_question == route_rules["field_questions"].get("applicant_type"):
            options = (route_rules.get("field_options") or {}).get("applicant_type") or []
            if options:
                lines = [f"{index}. {item['label']}" for index, item in enumerate(options, start=1)]
                option_block = "\n\n### 可選類別\n" + "\n".join(lines)
        return (
            f"### 已進入 {route_rules['form_no']} 辦理流程\n"
            f"{ability}\n"
            f"{progress}\n\n"
            f"### 下一步\n{next_question}{option_block}"
        )

    def _build_confirmation_question(self, route_rules: dict[str, Any], field: str, payload: dict[str, Any]) -> str:
        label = route_rules.get("field_labels", {}).get(field, field)
        value = self._format_public_value(route_rules, payload, field, payload.get(field))
        return f"請確認我理解的{label}是否正確：{value}。如果正確請回覆「是」，如不正確請直接發送正確資料。"

    def _resolve_confirmation_feedback(
        self,
        route_rules: dict[str, Any],
        payload: dict[str, Any],
        query: str,
    ) -> dict[str, Any] | None:
        normalized = query.strip()
        current_missing = self._compute_missing_fields(route_rules, payload)
        expected_field = current_missing[0] if current_missing else None
        pending_confirmation_fields = self._get_pending_confirmation_fields(payload)
        if not expected_field or expected_field not in pending_confirmation_fields:
            return None

        confirmation_bundle = self.strategy_planner.build_confirmation_bundle(route_rules, payload, pending_confirmation_fields)
        bundle_fields = list(confirmation_bundle.get("fields") or []) or [expected_field]
        if self._is_affirmative_response(normalized):
            return {"type": "confirmed", "fields": bundle_fields}
        if self._is_negative_response(normalized):
            return {"type": "rejected", "fields": bundle_fields}
        return None

    def _build_ready_message(self, route_rules: dict[str, Any]) -> str:
        if route_rules["form_no"] == "IR1249":
            next_step = "你現在可以先確認資料摘要，再生成 PDF；完成簽署確認後，我還能繼續幫你預覽郵件。"
        else:
            next_step = "你現在可以先確認資料摘要，再生成 PDF；之後我會繼續提示官方提交方式。"
        return (
            f"### {route_rules['form_no']} 所需資料已齊\n"
            f"{next_step}"
        )

    def _build_handling_mode(self, route_rules: dict[str, Any] | None) -> str:
        if not route_rules:
            return "待判斷"
        if route_rules.get("allow_email_submission"):
            return "可填寫 PDF，並在允許時進入郵件預覽 / 發送"
        return "可填寫 PDF，並提供官方提交指引"

    def _build_route_overview_description(self, route_rules: dict[str, Any] | None, mail_delivery_mode: str) -> str:
        if not route_rules:
            return "請先確認本次屬於通訊地址變更還是業務地址變更。"
        if route_rules["form_no"] == "IR1249":
            if mail_delivery_mode == "send_enabled":
                return "適用於個人或通訊地址變更。系統可繼續幫你採集資料、填寫官方 PDF、提醒簽署，並在確認後發送郵件。"
            return "適用於個人或通訊地址變更。系統可繼續幫你採集資料、填寫官方 PDF、提醒簽署，並生成郵件預覽。"
        return "適用於公司或業務地址變更。系統可繼續幫你採集資料、填寫官方 PDF，並提示你按官方方式提交。"

    def _build_stage_label(self, state: str | None) -> str:
        mapping = {
            "START": "開始",
            "ROUTE_AMBIGUOUS": "待確認場景",
            "COLLECT_FORM": "收集中",
            "REVIEW_FORM": "待確認資料",
            "REQUIRE_SIGNATURE_CONFIRMATION": "待確認簽署",
            "SHOW_SUBMISSION_GUIDE": "待提交",
            "REVIEW_MAIL": "待確認郵件",
            "DONE": "已完成",
            "FAILED": "已失敗",
        }
        return mapping.get(str(state or ""), str(state or "未知狀態"))

    def _build_progress(
        self,
        route_rules: dict[str, Any] | None,
        payload: dict[str, Any],
        missing_fields: list[str],
    ) -> dict[str, Any]:
        if not route_rules:
            return {
                "required_total": 0,
                "required_completed": 0,
                "recommended_total": 0,
                "recommended_completed": 0,
                "missing_count": 0,
                "completion_ratio": 0.0,
            }

        required_fields = self._resolve_required_fields(route_rules, payload)
        recommended_fields = self._resolve_recommended_fields(route_rules, payload)

        required_completed = 0
        for field in required_fields:
            value = payload.get(field)
            if field == "new_address":
                if self._is_address_complete(str(value or ""), payload):
                    required_completed += 1
                continue
            if value not in (None, "", [], {}):
                required_completed += 1

        recommended_completed = sum(1 for field in recommended_fields if payload.get(field) not in (None, "", [], {}))
        required_total = len(required_fields)
        completion_ratio = round((required_completed / required_total), 4) if required_total else 1.0

        return {
            "required_total": required_total,
            "required_completed": required_completed,
            "recommended_total": len(recommended_fields),
            "recommended_completed": recommended_completed,
            "missing_count": len(missing_fields),
            "completion_ratio": completion_ratio,
        }

    def _build_available_artifacts(self, artifacts: dict[str, Any], mail_delivery_mode: str) -> dict[str, Any]:
        return {
            "preview_pdf": bool(artifacts.get("preview_pdf_path")),
            "final_pdf": bool(artifacts.get("final_pdf_path")),
            "mail_preview": bool(artifacts.get("mail_preview")),
            "send_result": bool(artifacts.get("send_result")),
            "mail_delivery_mode": mail_delivery_mode,
        }

    def _build_confirmation_requirements(
        self,
        case: SceneCase,
        payload: dict[str, Any],
        next_actions: list[dict[str, Any]],
        missing_fields: list[str],
        flags: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        requirements: list[dict[str, Any]] = []
        for action in next_actions:
            action_name = str(action.get("name") or "")
            if action_name not in self.GATED_ACTIONS:
                continue
            requirements.append(
                {
                    "action_name": action_name,
                    "label": self.ACTION_LABELS.get(action_name, action_name),
                    "confirmation_type": "token",
                    "confirmation_prompt": self._build_action_confirmation_prompt(action_name),
                    "confirmation_token": self._compute_action_confirmation_token(
                        case,
                        action_name,
                        payload,
                        missing_fields,
                        flags,
                        artifacts,
                    ),
                }
            )
        return requirements

    def _build_action_confirmation_prompt(self, action_name: str) -> str:
        prompts = {
            "confirm_payload": "這會把目前資料標記為已確認。請在使用者明確表示資料無誤後再提交。",
            "confirm_signature": "這會記錄使用者已完成簽署。請在使用者明確表示已簽署後再提交。",
            "send_mail": "這會向稅局發出正式郵件。請在使用者明確授權發送後再提交。",
        }
        return prompts.get(action_name, "請先取得使用者的明確確認。")

    def _compute_action_confirmation_token(
        self,
        case: SceneCase,
        action_name: str,
        payload: dict[str, Any],
        missing_fields: list[str],
        flags: dict[str, Any],
        artifacts: dict[str, Any],
    ) -> str:
        payload_fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        fingerprint = "|".join(
            [
                case.case_code,
                case.scene_key,
                case.route_key or "",
                case.state or "",
                case.status or "",
                action_name,
                payload_fingerprint,
                ",".join(missing_fields),
                "1" if flags.get("payload_confirmed") else "0",
                "1" if flags.get("pdf_generated") else "0",
                "1" if flags.get("signature_confirmed") else "0",
                "1" if artifacts.get("mail_preview") else "0",
            ]
        )
        digest = hmac.new(
            settings.SCENE_CONFIRMATION_SECRET.encode("utf-8"),
            fingerprint.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest[:16]

    def _assert_action_confirmation(
        self,
        case: SceneCase,
        action_name: str,
        payload: dict[str, Any],
        flags: dict[str, Any],
        artifacts: dict[str, Any],
        missing_fields: list[str],
        confirmation_token: str | None,
    ) -> None:
        if action_name not in self.GATED_ACTIONS:
            return
        expected_token = self._compute_action_confirmation_token(case, action_name, payload, missing_fields, flags, artifacts)
        if not confirmation_token:
            raise ValueError("USER_CONFIRMATION_REQUIRED")
        if str(confirmation_token).strip() != expected_token:
            raise ValueError("INVALID_CONFIRMATION_TOKEN")

    def _build_recovery(
        self,
        case: SceneCase,
        missing_fields: list[str],
        confirmation_requirements: list[dict[str, Any]],
        available_artifacts: dict[str, Any],
    ) -> dict[str, Any]:
        error_code = case.last_error_code
        if not error_code:
            return {
                "last_error_code": None,
                "hint": None,
                "suggested_action": None,
                "retry_allowed": False,
                "auto_retry_action": None,
                "requires_status_refresh": False,
            }

        hint = None
        suggested_action = None
        retry_allowed = False
        auto_retry_action = None
        requires_status_refresh = False
        flags = dict(case.flags_json or {})
        if error_code == "FORM_FIELDS_MISSING":
            hint = "先補齊缺失欄位，再重新嘗試當前動作。"
            suggested_action = "collect_missing_fields"
        elif error_code == "USER_CONFIRMATION_REQUIRED":
            next_gate = confirmation_requirements[0] if confirmation_requirements else None
            if next_gate:
                hint = f"先取得使用者對「{next_gate['label']}」的明確確認，再帶上 confirmation_token 重試。"
                suggested_action = next_gate["action_name"]
            else:
                hint = "先重新讀取 scene 狀態，取得最新確認要求後再重試。"
                suggested_action = "refresh_scene_status"
            requires_status_refresh = True
        elif error_code == "INVALID_CONFIRMATION_TOKEN":
            hint = "確認 token 已失效，請重新取得最新 scene 狀態與 confirmation_token 後再重試。"
            suggested_action = "refresh_scene_status"
            requires_status_refresh = True
        elif error_code == "PDF_GENERATION_FAILED":
            hint = "請先確認 PDF 已成功生成；若尚未生成，先執行 generate_pdf。"
            suggested_action = "generate_pdf"
            if not missing_fields and flags.get("payload_confirmed"):
                retry_allowed = True
                auto_retry_action = "generate_pdf"
        elif error_code == "MAIL_PREVIEW_FAILED":
            hint = "請先生成郵件預覽，再決定是否發送。"
            suggested_action = "preview_mail"
            if flags.get("pdf_generated"):
                retry_allowed = True
                auto_retry_action = "preview_mail"
        elif error_code == "MAIL_SEND_BLOCKED":
            if available_artifacts.get("mail_delivery_mode") == "draft_only":
                hint = "當前專案只允許草稿模式，請使用郵件預覽與附件，由使用者自行發送。"
            else:
                hint = "當前路由不允許郵件發送，請改走官方提交方式。"
            suggested_action = "preview_mail" if available_artifacts.get("mail_preview") else None

        return {
            "last_error_code": error_code,
            "hint": hint,
            "suggested_action": suggested_action,
            "missing_fields": missing_fields,
            "retry_allowed": retry_allowed,
            "auto_retry_action": auto_retry_action,
            "requires_status_refresh": requires_status_refresh,
        }

    def _resolve_required_fields(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        required_fields = list(route_rules.get("required_fields", []))
        if route_rules.get("form_no") != "IR1249":
            return required_fields

        profile = self._get_ir1249_applicant_profile(route_rules, payload)
        return list(dict.fromkeys([*required_fields, *profile.get("required_fields", [])]))

    def _resolve_visible_fields(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        required_fields = self._resolve_required_fields(route_rules, payload)
        if route_rules.get("form_no") != "IR1249":
            return required_fields

        visible = ["effective_date", "new_address", "applicant_type", "daytime_phone"]
        profile = self._get_ir1249_applicant_profile(route_rules, payload)
        return list(dict.fromkeys([*visible, *profile.get("visible_fields", []), *required_fields]))

    def _resolve_recommended_fields(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        if route_rules.get("form_no") != "IR1249":
            return []
        profile = self._get_ir1249_applicant_profile(route_rules, payload)
        return list(profile.get("recommended_fields", []))

    def _build_field_options(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        if route_rules.get("form_no") != "IR1249":
            return route_rules.get("field_options", {})
        return route_rules.get("field_options", {})

    def _get_ir1249_applicant_profile(self, route_rules: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        applicant_profiles = route_rules.get("applicant_profiles", {})
        applicant_type = payload.get("applicant_type")
        if not applicant_type:
            return {}
        return applicant_profiles.get(applicant_type, applicant_profiles.get("salary earner", {}))

    def _infer_ir1249_applicant_type(self, normalized: str, payload: dict[str, Any]) -> str:
        lowered = normalized.lower()
        if any(keyword in lowered for keyword in ["property owner", "sole proprietor", "business owner", "employer"]):
            return payload.get("applicant_type") or "salary earner"
        if any(keyword in normalized for keyword in ["物业", "物業"]):
            return "property owner"
        if any(keyword in normalized for keyword in ["独资", "獨資"]):
            return "sole proprietor"
        if any(keyword in normalized for keyword in ["公司", "业务", "業務"]):
            return "business owner"
        if "雇主" in normalized:
            return "employer"
        return "salary earner"

    def _should_infer_applicant_type(self, normalized: str) -> bool:
        lowered = normalized.lower()
        explicit_keywords = [
            "salary earner",
            "property owner",
            "sole proprietor",
            "business owner",
            "employer",
            "受薪",
            "物业",
            "物業",
            "独资",
            "獨資",
            "业务",
            "業務",
            "公司",
            "雇主",
        ]
        return any(keyword in lowered or keyword in normalized for keyword in explicit_keywords)

    def _display_payload_value(self, route_rules: dict[str, Any], field: str, value: Any) -> Any:
        options = (route_rules.get("field_options") or {}).get(field) or []
        for option in options:
            if option.get("value") == value:
                return option.get("label") or value
        return value

    def _build_display_payload(
        self,
        route_rules: dict[str, Any],
        payload: dict[str, Any],
        public_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            key: self._format_public_value(route_rules, payload, key, value)
            for key, value in public_payload.items()
        }

    def _format_public_value(
        self,
        route_rules: dict[str, Any],
        payload: dict[str, Any],
        field: str,
        value: Any,
    ) -> Any:
        if field == "new_address":
            return self._format_address_display(payload, value)
        return self._display_payload_value(route_rules, field, value)

    def _format_address_display(self, payload: dict[str, Any], fallback: Any) -> Any:
        analysis = dict(payload.get("_address_analysis") or {})
        structured = dict(analysis.get("address_structured") or payload.get("address_structured") or {})
        if not structured:
            return fallback

        area_map = {
            "hk": "香港",
            "kln": "九龍",
            "nt": "新界",
            "others": "",
        }
        area = area_map.get(str(structured.get("area") or "").strip().lower(), "")
        district = str(structured.get("district") or "").strip()
        street = str(structured.get("street") or "").strip()
        building = str(structured.get("building") or "").strip()
        block = str(structured.get("block") or "").strip()
        floor = str(structured.get("floor") or "").strip()
        flat_room = str(structured.get("flat_room") or "").strip()

        parts: list[str] = []
        if area and not district.startswith(area):
            parts.append(area)
        parts.extend(part for part in [district, street, building, block] if part)
        if floor:
            parts.append(floor if floor.endswith(("樓", "层", "層", "/F", "F")) else f"{floor}樓")
        if flat_room:
            parts.append(flat_room)
        return "，".join(parts) if parts else fallback

    def _build_artifact_version(self, case: SceneCase) -> str:
        updated_at = getattr(case, "updated_at", None)
        if updated_at is None:
            return "0"
        return updated_at.strftime("%Y%m%d%H%M%S%f")

    def _build_artifact_url(self, case: SceneCase, artifact_key: str, version: str) -> str:
        return f"/api/v1/projects/{case.project_id}/scenes/{case.case_code}/artifacts/{artifact_key}?v={version}"

    def _public_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key not in self.HIDDEN_PAYLOAD_FIELDS
        }

    def _get_pending_confirmation_fields(self, payload: dict[str, Any]) -> list[str]:
        pending = payload.get("_pending_confirmation_fields") or []
        if not isinstance(pending, list):
            return []
        return [field for field in pending if isinstance(field, str) and payload.get(field)]

    def _add_pending_confirmation(self, payload: dict[str, Any], field: str) -> dict[str, Any]:
        pending = self._get_pending_confirmation_fields(payload)
        if field in pending:
            return payload
        return {
            **payload,
            "_pending_confirmation_fields": [*pending, field],
        }

    def _remove_pending_confirmation(self, payload: dict[str, Any], field: str) -> dict[str, Any]:
        pending = [item for item in self._get_pending_confirmation_fields(payload) if item != field]
        result = dict(payload)
        if pending:
            result["_pending_confirmation_fields"] = pending
        else:
            result.pop("_pending_confirmation_fields", None)
        field_confidence = dict(result.get("_field_confidence") or {})
        field_confidence.pop(field, None)
        if field_confidence:
            result["_field_confidence"] = field_confidence
        else:
            result.pop("_field_confidence", None)
        return result

    def _finalize_pending_confirmation(self, payload: dict[str, Any], field: str, confirmed: bool) -> dict[str, Any]:
        result = dict(payload)
        if not confirmed:
            old_value = result.get(field)
            result.pop(field, None)
            if field == "new_address":
                result.pop("address_structured", None)
                result.pop("_address_analysis", None)
                field_confidence = dict(result.get("_field_confidence") or {})
                field_confidence.pop("address_structured", None)
                if field_confidence:
                    result["_field_confidence"] = field_confidence
                else:
                    result.pop("_field_confidence", None)
            if field == "full_name" and (
                result.get("signer_name") == old_value
                or self._strip_name_prefix(str(result.get("signer_name") or "")) == str(old_value or "")
            ):
                result.pop("signer_name", None)
        result = self._remove_pending_confirmation(result, field)
        return {key: value for key, value in result.items() if value not in (None, "", [], {})}

    def _finalize_pending_confirmation_bundle(
        self,
        payload: dict[str, Any],
        fields: list[str],
        *,
        confirmed: bool,
    ) -> dict[str, Any]:
        result = dict(payload)
        for field in fields:
            result = self._finalize_pending_confirmation(result, field, confirmed=confirmed)
        return result

    def _is_affirmative_response(self, text: str) -> bool:
        normalized = self._normalize_reply_token(text)
        return bool(self.AFFIRMATIVE_RESPONSE_PATTERN.fullmatch(normalized))

    def _is_negative_response(self, text: str) -> bool:
        normalized = self._normalize_reply_token(text)
        return bool(self.NEGATIVE_RESPONSE_PATTERN.fullmatch(normalized))

    def _normalize_reply_token(self, text: str) -> str:
        return re.sub(r"[\s\W_]+", "", text.strip().lower())

    def _strip_name_prefix(self, text: str) -> str:
        cleaned = text.strip()
        prefixes = ["姓名是", "姓名", "name is", "name"]
        lowered = cleaned.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip(" ：:，,")
                break
        return cleaned or text.strip()

    def _should_fill_expected_field(self, expected_field: str, normalized: str) -> bool:
        if expected_field in {"applicant_type"}:
            return False
        if expected_field == "new_address":
            return self._looks_like_actual_address_input(normalized)
        if expected_field in {
            "effective_date",
            "reference_id",
            "individual_file_no",
            "property_tax_file_no",
            "profits_tax_file_no",
            "employer_return_file_no",
            "daytime_phone",
            "telephone_no",
        }:
            return False
        if expected_field in {"full_name", "individual_name", "signer_name"}:
            return not self._looks_like_non_name_input(normalized)
        return True

    def _looks_like_non_name_input(self, normalized: str) -> bool:
        lowered = normalized.lower()
        if any(token in lowered for token in ["road", "street", "flat", "room", "block", "floor"]):
            return True
        if any(token in normalized for token in ["地址", "电话", "電話", "月", "日", "号", "號"]):
            return True
        return self._normalize_reference_input(normalized, "reference_id") is not None

    def _is_address_complete(self, value: str, payload: dict[str, Any] | None = None) -> bool:
        analysis = self.address_analysis_service.analyze(value, (payload or {}).get("address_structured"))
        return bool(analysis.get("is_complete"))

    def _looks_like_actual_address_input(self, text: str) -> bool:
        return self.address_analysis_service.looks_like_address_input_text(text)

    def _enrich_address_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(payload)
        raw_address = str(result.get("new_address") or "").strip()
        if not raw_address:
            result.pop("address_structured", None)
            result.pop("_address_analysis", None)
            return result

        analysis = self.address_analysis_service.analyze(raw_address, result.get("address_structured"))
        if analysis.get("address_structured"):
            result["address_structured"] = analysis["address_structured"]
        else:
            result.pop("address_structured", None)

        result["_address_analysis"] = {
            "normalized_address": analysis.get("normalized_address"),
            "confidence": analysis.get("confidence"),
            "source": analysis.get("source"),
            "is_complete": analysis.get("is_complete"),
            "structured_count": analysis.get("structured_count"),
            "address_structured": analysis.get("address_structured"),
            "pdf_parts": analysis.get("pdf_parts"),
            "official": analysis.get("official"),
            "geo": analysis.get("geo"),
            "needs_confirmation": analysis.get("needs_confirmation"),
            "confirmation_reason": analysis.get("confirmation_reason"),
            "candidate_options": analysis.get("candidate_options"),
            "source_chain": analysis.get("source_chain"),
        }
        field_confidence = dict(result.get("_field_confidence") or {})
        confidence = analysis.get("confidence")
        if confidence:
            field_confidence["address_structured"] = confidence
        else:
            field_confidence.pop("address_structured", None)
        if field_confidence:
            result["_field_confidence"] = field_confidence
        else:
            result.pop("_field_confidence", None)
        return result

    def _normalize_reference_input(self, value: str, expected_field: str | None = None) -> str | None:
        raw = value.strip().upper()
        if not raw:
            return None

        compact = (
            raw.replace("（", "(")
            .replace("）", ")")
            .replace(" ", "")
            .replace("-", "")
            .replace("/", "")
        )

        hkid_match = re.fullmatch(r"([A-Z]{1,2})(\d{6})\(?([0-9A])\)?", compact, re.IGNORECASE)
        if hkid_match:
            return f"{hkid_match.group(1).upper()}{hkid_match.group(2)}({hkid_match.group(3).upper()})"

        if expected_field in {
            "reference_id",
            "individual_file_no",
            "property_tax_file_no",
            "profits_tax_file_no",
            "employer_return_file_no",
        } and re.fullmatch(r"[A-Z0-9]{6,20}", compact, re.IGNORECASE) and re.search(r"[A-Z]", compact) and re.search(r"\d", compact):
            return compact

        return None

    def _is_generic_form_start_request(self, normalized: str) -> bool:
        lower = normalized.lower()
        action_keywords = (
            "帮我填写",
            "幫我填寫",
            "帮我填",
            "幫我填",
            "开始填写",
            "開始填寫",
            "开始填表",
            "開始填表",
            "生成pdf",
            "生成 pdf",
            "我想改收稅單地址",
            "我想改收税单地址",
            "想改收稅單地址",
            "想改收税单地址",
            "改收稅單地址",
            "改收税单地址",
            "改通訊地址",
            "改通讯地址",
            "地址變更",
            "地址变更",
            "我搬家了",
            "搬家了",
            "開始辦理",
            "开始办理",
        )
        if any(keyword in normalized for keyword in action_keywords):
            return True
        return any(form_key in lower for form_key in ("ir1249", "irc3111a")) and any(
            keyword in normalized for keyword in ("帮我", "幫我", "填写", "填寫", "填表", "开始", "開始", "生成")
        )

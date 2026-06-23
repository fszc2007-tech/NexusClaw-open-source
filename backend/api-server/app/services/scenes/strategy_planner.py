from __future__ import annotations

from typing import Any

from app.models.scene import SceneCase


class SceneStrategyPlanner:
    VERSION = "scene_strategy_v1"

    def prioritize_missing_fields(
        self,
        route_rules: dict[str, Any] | None,
        payload: dict[str, Any],
        missing_fields: list[str],
        *,
        pending_confirmation_fields: list[str] | None = None,
        address_analysis: dict[str, Any] | None = None,
    ) -> list[str]:
        if not missing_fields:
            return []

        pending_confirmation_fields = list(pending_confirmation_fields or [])
        address_analysis = dict(address_analysis or {})
        ordered: list[str] = []
        seen: set[str] = set()

        def push(field_name: str | None) -> None:
            if not field_name:
                return
            if field_name not in missing_fields or field_name in seen:
                return
            ordered.append(field_name)
            seen.add(field_name)

        for field_name in pending_confirmation_fields:
            push(field_name)

        route_key = str((route_rules or {}).get("form_no") or "").upper()
        applicant_type = str(payload.get("applicant_type") or "").strip().lower()
        has_address = bool(str(payload.get("new_address") or "").strip())
        address_confidence = str(address_analysis.get("confidence") or "").strip().lower()
        address_complete = bool(address_analysis.get("is_complete"))

        push("applicant_type")
        if "new_address" in missing_fields and (not has_address or not address_complete or address_confidence in {"", "low", "medium"}):
            push("new_address")

        if route_key == "IR1249":
            if applicant_type in {"salary earner", "property owner", "sole proprietor"}:
                for field_name in ["full_name", "reference_id"]:
                    push(field_name)
            if applicant_type in {"business owner", "employer"}:
                for field_name in ["business_name", "designation"]:
                    push(field_name)
            if applicant_type == "property owner":
                for field_name in ["property_tax_location", "property_tax_file_no"]:
                    push(field_name)
            if applicant_type in {"sole proprietor", "business owner"}:
                push("profits_tax_file_no")
            if applicant_type == "employer":
                push("employer_return_file_no")

            for field_name in ["effective_date", "daytime_phone"]:
                push(field_name)

            if payload.get("full_name") and not payload.get("signer_name"):
                push("signer_name")
        else:
            for field_name in ["business_name", "business_registration_no", "effective_date", "telephone_no"]:
                push(field_name)

        for field_name in missing_fields:
            push(field_name)
        return ordered

    def build(
        self,
        case: SceneCase,
        scene_payload: dict[str, Any],
        field_status: dict[str, Any],
        next_actions_payload: dict[str, Any],
        *,
        intent_mode: str | None = None,
    ) -> dict[str, Any]:
        runtime = dict(scene_payload.get("runtime") or {})
        progress = dict(next_actions_payload.get("progress") or {})
        recovery = dict(next_actions_payload.get("recovery") or {})
        confirmation_requirements = list(next_actions_payload.get("confirmation_requirements") or [])
        allowed_next_actions = list(next_actions_payload.get("allowed_next_actions") or [])
        missing_fields = list(field_status.get("missing") or [])
        field_labels = dict(field_status.get("field_labels") or {})
        address_analysis = dict(field_status.get("address_analysis") or {})
        highest_priority_missing_field = next_actions_payload.get("highest_priority_missing_field")
        next_question = next_actions_payload.get("next_question")
        next_question_fields = list(next_actions_payload.get("next_question_fields") or [])
        next_prompt_mode = str(next_actions_payload.get("next_prompt_mode") or "").strip().lower()
        blocking_reason = next_actions_payload.get("blocking_reason")
        route_overview = ((scene_payload.get("panels") or {}).get("route_overview") or {})
        summary_payload = (((scene_payload.get("panels") or {}).get("summary") or {}).get("payload") or {})

        objective = self._build_objective(scene_payload, missing_fields, allowed_next_actions)
        next_step = self._build_next_step(
            blocking_reason=blocking_reason,
            highest_priority_missing_field=highest_priority_missing_field,
            field_labels=field_labels,
            next_question=next_question,
            next_question_fields=next_question_fields,
            next_prompt_mode=next_prompt_mode,
            confirmation_requirements=confirmation_requirements,
            allowed_next_actions=allowed_next_actions,
            recovery=recovery,
        )
        mode = self._resolve_mode(next_step)
        decision_reason = self._build_decision_reason(
            scene_payload=scene_payload,
            blocking_reason=blocking_reason,
            highest_priority_missing_field=highest_priority_missing_field,
            next_question_fields=next_question_fields,
            next_prompt_mode=next_prompt_mode,
            field_labels=field_labels,
            recovery=recovery,
            allowed_next_actions=allowed_next_actions,
        )
        address_review_note = self._build_address_review_note(
            address_analysis,
            has_address=bool(summary_payload.get("new_address")),
        )

        missing_labels = [field_labels.get(field, field) for field in missing_fields]
        status_headline = self._build_status_headline(next_step, field_labels, recovery)
        status_detail = self._build_status_detail(
            next_step=next_step,
            decision_reason=decision_reason,
            next_question=next_question,
            recovery=recovery,
            route_overview=route_overview,
        )

        return {
            "version": self.VERSION,
            "mode": mode,
            "intent_mode": intent_mode or "scene_request",
            "objective": objective,
            "decision_reason": decision_reason,
            "next_step": next_step,
            "status": {
                "scene_key": scene_payload.get("scene_key"),
                "route_key": scene_payload.get("route_key"),
                "stage_code": (runtime.get("stage") or {}).get("code"),
                "stage_label": (runtime.get("stage") or {}).get("label"),
                "required_total": progress.get("required_total", 0),
                "required_completed": progress.get("required_completed", 0),
                "missing_count": progress.get("missing_count", len(missing_fields)),
                "completion_ratio": progress.get("completion_ratio", 0),
                "blocking_reason": blocking_reason,
                "missing_fields": missing_fields,
                "missing_labels": missing_labels,
            },
            "communication": {
                "status_headline": status_headline,
                "status_detail": status_detail,
                "next_prompt": next_question,
                "address_review_note": address_review_note,
                "should_append_knowledge": intent_mode == "hybrid_request",
                "should_show_recovery": bool(recovery.get("last_error_code")),
            },
            "candidate_actions": [
                {
                    "name": action.get("name"),
                    "label": action.get("label"),
                    "requires_confirmation": bool(action.get("requires_confirmation")),
                }
                for action in allowed_next_actions
            ],
        }

    def _build_objective(
        self,
        scene_payload: dict[str, Any],
        missing_fields: list[str],
        allowed_next_actions: list[dict[str, Any]],
    ) -> str:
        route_overview = ((scene_payload.get("panels") or {}).get("route_overview") or {})
        form_no = route_overview.get("form_no") or scene_payload.get("route_key") or "scene"
        if missing_fields:
            return f"先補齊 {form_no} 的必填資料，再推進到確認與生成產物。"
        if allowed_next_actions:
            label = allowed_next_actions[0].get("label") or allowed_next_actions[0].get("name") or "下一步動作"
            return f"資料已齊，推進到「{label}」並完成後續提交準備。"
        if scene_payload.get("state") == "DONE":
            return "案件已完成，保留產物與審計結果供後續查看。"
        return f"維持 {form_no} 場景的穩定辦理狀態。"

    def _build_next_step(
        self,
        *,
        blocking_reason: str | None,
        highest_priority_missing_field: str | None,
        field_labels: dict[str, str],
        next_question: str | None,
        next_question_fields: list[str],
        next_prompt_mode: str,
        confirmation_requirements: list[dict[str, Any]],
        allowed_next_actions: list[dict[str, Any]],
        recovery: dict[str, Any],
    ) -> dict[str, Any]:
        if recovery.get("last_error_code"):
            step_type = "recover"
            if recovery.get("retry_allowed") and recovery.get("auto_retry_action"):
                return {
                    "type": step_type,
                    "action_name": recovery.get("auto_retry_action"),
                    "action_label": self._label_for_action(recovery.get("auto_retry_action")),
                    "question": next_question,
                }
            return {
                "type": step_type,
                "action_name": recovery.get("suggested_action"),
                "action_label": self._label_for_action(recovery.get("suggested_action")),
                "question": next_question,
            }
        if blocking_reason == "ROUTE_SELECTION_REQUIRED":
            return {"type": "choose_route", "question": next_question}
        if next_prompt_mode == "confirm_bundle" and len(next_question_fields) > 1:
            return {
                "type": "confirm_bundle",
                "fields": next_question_fields,
                "field_labels": [field_labels.get(field, field) for field in next_question_fields],
                "question": next_question,
            }
        if next_prompt_mode == "confirm" and highest_priority_missing_field:
            return {
                "type": "confirm_field",
                "field_name": highest_priority_missing_field,
                "field_label": field_labels.get(highest_priority_missing_field, highest_priority_missing_field),
                "question": next_question,
            }
        if len(next_question_fields) > 1:
            return {
                "type": "collect_bundle",
                "fields": next_question_fields,
                "field_labels": [field_labels.get(field, field) for field in next_question_fields],
                "question": next_question,
            }
        if highest_priority_missing_field:
            return {
                "type": "collect_field",
                "field_name": highest_priority_missing_field,
                "field_label": field_labels.get(highest_priority_missing_field, highest_priority_missing_field),
                "question": next_question,
            }
        if confirmation_requirements:
            requirement = confirmation_requirements[0]
            return {
                "type": "confirm_action",
                "action_name": requirement.get("action_name"),
                "action_label": requirement.get("label"),
                "question": requirement.get("confirmation_prompt") or next_question,
            }
        if allowed_next_actions:
            action = allowed_next_actions[0]
            return {
                "type": "execute_action",
                "action_name": action.get("name"),
                "action_label": action.get("label"),
                "question": next_question,
            }
        if blocking_reason == "CASE_COMPLETED":
            return {"type": "completed", "question": None}
        return {"type": "idle", "question": next_question}

    def _resolve_mode(self, next_step: dict[str, Any]) -> str:
        step_type = next_step.get("type")
        if step_type == "collect_field":
            return "collect"
        if step_type == "collect_bundle":
            return "collect_bundle"
        if step_type == "confirm_bundle":
            return "confirm_bundle"
        if step_type == "confirm_field":
            return "confirm"
        if step_type == "confirm_action":
            return "confirm"
        if step_type == "execute_action":
            return "execute"
        if step_type == "recover":
            return "recover"
        if step_type == "choose_route":
            return "route_select"
        if step_type == "completed":
            return "complete"
        return "observe"

    def _build_decision_reason(
        self,
        *,
        scene_payload: dict[str, Any],
        blocking_reason: str | None,
        highest_priority_missing_field: str | None,
        next_question_fields: list[str],
        next_prompt_mode: str,
        field_labels: dict[str, str],
        recovery: dict[str, Any],
        allowed_next_actions: list[dict[str, Any]],
    ) -> str:
        if recovery.get("last_error_code"):
            return str(recovery.get("hint") or "先處理最近一次失敗，再恢復主流程。")
        if blocking_reason == "ROUTE_SELECTION_REQUIRED":
            return "目前仍無法確定要走哪個表格路由，需先明確場景。"
        if next_prompt_mode == "confirm_bundle" and len(next_question_fields) > 1:
            labels = [field_labels.get(field, field) for field in next_question_fields]
            return f"先一起確認「{'、'.join(labels)}」是否解析正確，確認無誤後再繼續推進。"
        if next_prompt_mode == "confirm" and highest_priority_missing_field:
            field_label = field_labels.get(highest_priority_missing_field, highest_priority_missing_field)
            return f"先確認「{field_label}」是否解析正確，確認無誤後再繼續推進。"
        if highest_priority_missing_field:
            if len(next_question_fields) > 1:
                labels = [field_labels.get(field, field) for field in next_question_fields]
                return f"先一起收集「{'、'.join(labels)}」，這些欄位通常會成對出現，合併收集能減少來回追問。"
            field_label = field_labels.get(highest_priority_missing_field, highest_priority_missing_field)
            if highest_priority_missing_field == "applicant_type":
                return f"先收集「{field_label}」，因為它會決定後續需要顯示與收集的欄位。"
            return f"先補齊「{field_label}」，這是推進到下一個辦理動作的前置條件。"
        if allowed_next_actions:
            label = allowed_next_actions[0].get("label") or allowed_next_actions[0].get("name") or "下一步動作"
            return f"目前已具備前置條件，可以直接推進「{label}」。"
        if scene_payload.get("state") == "DONE":
            return "案件已完成，現在以產物查看與後續追溯為主。"
        return "目前維持現有場景狀態，等待新的使用者輸入。"

    def _build_status_headline(
        self,
        next_step: dict[str, Any],
        field_labels: dict[str, str],
        recovery: dict[str, Any],
    ) -> str:
        if recovery.get("last_error_code"):
            action_label = next_step.get("action_label") or "恢復流程"
            if recovery.get("retry_allowed"):
                return f"目前先做恢復動作：{action_label}"
            return "目前先刷新並校正流程狀態"
        if next_step.get("type") == "confirm_bundle":
            labels = [str(item).strip() for item in (next_step.get("field_labels") or []) if str(item).strip()]
            return f"目前先一起確認「{'、'.join(labels)}」"
        if next_step.get("type") == "confirm_field":
            return f"目前先確認「{next_step.get('field_label') or '欄位'}」"
        if next_step.get("type") == "collect_bundle":
            labels = [str(item).strip() for item in (next_step.get("field_labels") or []) if str(item).strip()]
            return f"目前先一起收集「{'、'.join(labels)}」"
        if next_step.get("type") == "collect_field":
            return f"目前先收集「{next_step.get('field_label') or field_labels.get(next_step.get('field_name', ''), next_step.get('field_name'))}」"
        if next_step.get("type") == "confirm_action":
            return f"目前先取得「{next_step.get('action_label') or '確認'}」"
        if next_step.get("type") == "execute_action":
            return f"目前可執行「{next_step.get('action_label') or '下一步'}」"
        if next_step.get("type") == "completed":
            return "目前案件已完成"
        if next_step.get("type") == "choose_route":
            return "目前先確認辦理路由"
        return "目前保持場景處理狀態"

    def _build_status_detail(
        self,
        *,
        next_step: dict[str, Any],
        decision_reason: str,
        next_question: str | None,
        recovery: dict[str, Any],
        route_overview: dict[str, Any],
    ) -> str:
        detail_parts = [decision_reason]
        if next_question and next_step.get("type") in {"collect_field", "collect_bundle", "confirm_action", "confirm_field", "confirm_bundle", "choose_route"}:
            detail_parts.append(f"下一句要問的是：{next_question}")
        if next_step.get("type") == "execute_action" and next_step.get("action_label"):
            detail_parts.append(f"可直接推進：{next_step['action_label']}")
        if recovery.get("requires_status_refresh"):
            detail_parts.append("先取最新 confirmation token，再決定是否重試。")
        if route_overview.get("form_no"):
            detail_parts.append(f"當前表格：{route_overview['form_no']}")
        return " ".join(part for part in detail_parts if part)

    def _build_address_review_note(self, address_analysis: dict[str, Any], *, has_address: bool) -> str | None:
        if not address_analysis or not has_address:
            return None
        structured = dict(address_analysis.get("address_structured") or {})
        if not structured:
            return None
        if address_analysis.get("is_complete") and not address_analysis.get("needs_confirmation"):
            return None
        ordered_keys = [
            ("district", "地區"),
            ("street", "街道"),
            ("building", "大廈"),
            ("block", "座數"),
            ("floor", "樓層"),
            ("flat_room", "室號"),
        ]
        parts = [f"{label}:{structured[key]}" for key, label in ordered_keys if structured.get(key)]
        if not parts:
            return None
        return "地址解析待你確認：" + "；".join(parts)

    def _label_for_action(self, action_name: Any) -> str | None:
        mapping = {
            "confirm_payload": "確認資料",
            "generate_pdf": "生成 PDF",
            "confirm_signature": "確認已簽署",
            "preview_mail": "預覽郵件",
            "send_mail": "發送郵件",
            "refresh_scene_status": "刷新 scene 狀態",
            "collect_missing_fields": "補齊缺失欄位",
        }
        normalized = str(action_name or "").strip()
        return mapping.get(normalized) or normalized or None

    def build_collection_bundle(
        self,
        route_rules: dict[str, Any] | None,
        payload: dict[str, Any],
        missing_fields: list[str],
        *,
        pending_confirmation_fields: list[str] | None = None,
        address_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ordered_missing = self.prioritize_missing_fields(
            route_rules,
            payload,
            missing_fields,
            pending_confirmation_fields=pending_confirmation_fields,
            address_analysis=address_analysis,
        )
        if not ordered_missing:
            return {"fields": [], "question": None, "collection_mode": "idle"}

        field_questions = dict((route_rules or {}).get("field_questions") or {})
        applicant_type = str(payload.get("applicant_type") or "").strip().lower()
        first = ordered_missing[0]

        if first == "new_address":
            return {
                "fields": [first],
                "question": self._build_address_followup_question(route_rules, payload, address_analysis, field_questions),
                "collection_mode": "single",
            }

        bundle_fields = [first]
        if first == "applicant_type":
            pass
        elif applicant_type in {"salary earner", "property owner", "sole proprietor"} and ordered_missing[:2] == ["full_name", "reference_id"]:
            bundle_fields = ["full_name", "reference_id"]
        elif applicant_type in {"business owner", "employer"} and ordered_missing[:2] == ["business_name", "designation"]:
            bundle_fields = ["business_name", "designation"]
        elif first == "effective_date" and "daytime_phone" in ordered_missing[1:3]:
            bundle_fields = ["effective_date", "daytime_phone"]
        elif first == "business_name":
            second = ordered_missing[1] if len(ordered_missing) > 1 else None
            if second in {"profits_tax_file_no", "employer_return_file_no"}:
                bundle_fields = ["business_name", second]

        if len(bundle_fields) <= 1:
            return {
                "fields": [first],
                "question": field_questions.get(first),
                "collection_mode": "single",
            }

        labels = [(route_rules or {}).get("field_labels", {}).get(field, field) for field in bundle_fields]
        prompt_lines = [f"{index}. {field_questions.get(field) or f'請提供{label}。'}" for index, (field, label) in enumerate(zip(bundle_fields, labels), start=1)]
        return {
            "fields": bundle_fields,
            "question": "請一次補充以下資料：\n" + "\n".join(prompt_lines),
            "collection_mode": "bundle",
        }

    def build_confirmation_bundle(
        self,
        route_rules: dict[str, Any] | None,
        payload: dict[str, Any],
        pending_fields: list[str],
    ) -> dict[str, Any]:
        if not pending_fields:
            return {"fields": [], "question": None, "collection_mode": "idle"}

        candidate_fields = [field for field in pending_fields if payload.get(field) not in (None, "", [], {})]
        if not candidate_fields:
            return {"fields": [], "question": None, "collection_mode": "idle"}

        field_labels = dict((route_rules or {}).get("field_labels") or {})
        bundle_fields = [candidate_fields[0]]
        if candidate_fields[:2] == ["full_name", "reference_id"]:
            bundle_fields = ["full_name", "reference_id"]
        elif candidate_fields[:2] == ["effective_date", "daytime_phone"]:
            bundle_fields = ["effective_date", "daytime_phone"]

        if len(bundle_fields) <= 1:
            field = bundle_fields[0]
            label = field_labels.get(field, field)
            return {
                "fields": [field],
                "question": f"請確認我理解的{label}是否正確：{payload.get(field)}。如果正確請回覆「是」，如不正確請直接發送正確資料。",
                "collection_mode": "confirm",
            }

        lines = []
        for index, field in enumerate(bundle_fields, start=1):
            label = field_labels.get(field, field)
            lines.append(f"{index}. {label}：{payload.get(field)}")
        return {
            "fields": bundle_fields,
            "question": (
                "請一起確認以下資料是否正確：\n"
                + "\n".join(lines)
                + "\n如果都正確請直接回覆「是」，如有任何一項不正確，請直接發送修正後的完整資料。"
            ),
            "collection_mode": "confirm_bundle",
        }

    def _build_address_followup_question(
        self,
        route_rules: dict[str, Any] | None,
        payload: dict[str, Any],
        address_analysis: dict[str, Any] | None,
        field_questions: dict[str, str],
    ) -> str:
        default_question = field_questions.get("new_address") or "請提供完整地址。"
        raw_address = str(payload.get("new_address") or "").strip()
        if not raw_address:
            return default_question

        analysis = dict(address_analysis or {})
        structured = dict(analysis.get("address_structured") or {})
        recognized_parts: list[str] = []
        if structured.get("district"):
            recognized_parts.append(f"地區「{structured['district']}」")
        if structured.get("street"):
            recognized_parts.append(f"片段「{structured['street']}」")
        if structured.get("building"):
            recognized_parts.append(f"樓宇 / 屋苑「{structured['building']}」")
        if not recognized_parts:
            recognized_parts.append(f"地址片段「{raw_address}」")

        missing_parts = self._build_address_missing_parts(structured)
        if not missing_parts:
            return default_question

        recognized_text = "、".join(recognized_parts)
        missing_text = "、".join(missing_parts)
        return (
            f"我目前先記錄到 {recognized_text}。"
            f" 為了把地址完整填進表格，還需要你補充：{missing_text}。"
            " 你可以直接回覆完整地址，也可以只補充缺少的部分。"
        )

    def _build_address_missing_parts(self, structured: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        has_district = bool(str(structured.get("district") or "").strip())
        has_street = bool(str(structured.get("street") or "").strip())
        has_building = bool(str(structured.get("building") or "").strip())
        has_block = bool(str(structured.get("block") or "").strip())
        has_floor = bool(str(structured.get("floor") or "").strip())
        has_flat_room = bool(str(structured.get("flat_room") or "").strip())

        if not has_district and not has_street:
            missing.append("所屬地區 / 屋苑所在位置")
        elif not has_district:
            missing.append("地區")
        elif not has_street and not has_building:
            missing.append("街道 / 門牌")

        if not has_building and not has_street:
            missing.append("樓宇 / 屋苑名稱")
        if not has_block:
            missing.append("第幾座 / 棟")
        if not has_floor:
            missing.append("樓層")
        if not has_flat_room:
            missing.append("室號")
        return missing

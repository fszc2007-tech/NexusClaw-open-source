from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.chat import ChatSession
from app.models.scene import SceneCase
from app.services.chat_session_service import ChatSessionService
from app.services.scenes.orchestrator import SceneOrchestrator
from app.services.scenes.router import SceneRouter
from app.services.scenes.rules_service import SceneRulesService
from app.services.scenes.scene_extraction_service import SceneExtractionService
from app.services.scenes.state_service import SceneStateService
from app.services.scenes.tool_runtime import SceneToolRuntime


class SceneService:
    def __init__(self, db: Session):
        self.db = db
        self.rules_service = SceneRulesService()
        self.tool_runtime = SceneToolRuntime(db, self.rules_service)
        self.extraction_service = SceneExtractionService()
        self.router = SceneRouter()
        self.session_service = ChatSessionService(db)
        self.state_service = SceneStateService(db, self.rules_service)
        self.orchestrator = SceneOrchestrator(self.rules_service, self.tool_runtime, self.extraction_service)

    def maybe_handle_chat(
        self,
        project_id: int,
        session: ChatSession,
        query: str,
        memory_context: dict[str, Any],
        project_context: dict[str, Any],
        route_decision: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        route_decision = route_decision or self.router.route(query, memory_context, project_context)
        if not route_decision:
            return None

        case = self._get_or_create_case(
            project_id=project_id,
            session=session,
            scene_key=route_decision["scene_key"],
            case_code=((memory_context.get("state") or {}).get("scene") or {}).get("case_id"),
        )
        result = self.orchestrator.handle_message(case, route_decision, query, project_context)
        self.db.flush()
        result["field_status"] = self.state_service.get_field_status(case)
        result["next_actions"] = self.state_service.get_next_actions(
            case,
            project_context,
            intent_mode=route_decision.get("intent_mode"),
        )
        result["scene"] = self.state_service.attach_planner(result["scene"], result["next_actions"])
        result["intent_mode"] = route_decision.get("intent_mode", "scene_request")
        result["classification_reason"] = route_decision.get("reason")
        return result

    def classify_chat_intent(
        self,
        query: str,
        memory_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        return self.router.classify(query, memory_context, project_context)

    def start_case(
        self,
        project_id: int,
        project_context: dict[str, Any],
        scene_key: str,
        route_key: str | None,
        session_code: str | None,
        source: str,
        initial_query: str | None,
        selected_kb_ids: list[int] | None,
        switches: dict[str, Any] | None,
        resume_if_exists: bool = True,
    ) -> dict[str, Any]:
        session = self.session_service.get_or_create_session(
            project_id=project_id,
            session_code=session_code,
            source=source,
            selected_kb_ids=selected_kb_ids,
            switches=switches,
        )
        case = None
        if resume_if_exists:
            case = self._find_active_case(project_id, session.id, scene_key)
            if case and route_key and case.route_key and case.route_key != route_key:
                case = None
            if not case:
                case = self._get_or_create_case(
                    project_id=project_id,
                    session=session,
                    scene_key=scene_key,
                    case_code=((session.state_json or {}).get("scene") or {}).get("case_id"),
                )
        else:
            case = self._create_case(project_id=project_id, session=session, scene_key=scene_key)

        route_decision = {
            "scene_key": scene_key,
            "route_key": route_key or self._infer_route_key(initial_query, session, project_context, scene_key),
            "reason": "explicit_start",
        }
        query = (initial_query or "").strip() or "開始辦理"
        result = self.orchestrator.handle_message(case, route_decision, query, project_context)
        self.session_service.sync_scene_state(session, result["scene"])
        self.tool_runtime.write_event(
            case,
            event_type="scene_started",
            actor_type="assistant",
            request_json={
                "source": source,
                "session_code": session.session_code,
                "route_key": route_decision["route_key"],
            },
            result_json={"state": case.state, "route_key": case.route_key},
        )
        self._record_runtime_activity(
            case,
            event_type="scene_started",
            details={"route_key": case.route_key, "state": case.state},
        )
        self.db.commit()
        next_actions = self.state_service.get_next_actions(case, project_context)
        return {
            "session_id": session.session_code,
            "message": result["message"],
            "scene": self.state_service.attach_planner(result["scene"], next_actions),
            "field_status": self.state_service.get_field_status(case),
            "next_actions": next_actions,
        }

    def get_case_detail(self, project_id: int, case_id: str, project_context: dict[str, Any]) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        next_actions = self.state_service.get_next_actions(case, project_context)
        return self.state_service.attach_planner(self.state_service.serialize_scene(case, project_context), next_actions)

    def get_field_status(self, project_id: int, case_id: str) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        return self.state_service.get_field_status(case)

    def get_next_actions(self, project_id: int, case_id: str, project_context: dict[str, Any]) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        return self.state_service.get_next_actions(case, project_context)

    def merge_payload(
        self,
        project_id: int,
        case_id: str,
        payload_patch: dict[str, Any],
        project_context: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        try:
            result = self.state_service.merge_payload(case, payload_patch, project_context)
            self.tool_runtime.write_event(
                case,
                event_type="payload_updated",
                actor_type="assistant",
                request_json={"payload": payload_patch, "source": source},
                result_json={
                    "state": case.state,
                    "missing_fields": result["scene"].get("missing_fields", []),
                },
            )
            self._record_runtime_activity(
                case,
                event_type="payload_updated",
                details={
                    "changed_fields": result["field_status"].get("changed", []),
                    "missing_fields": result["scene"].get("missing_fields", []),
                },
            )
            latest_field_status = self.state_service.get_field_status(case)
            result["scene"] = self.state_service.serialize_scene(case, project_context)
            result["field_status"] = {
                **latest_field_status,
                "invalid": result["field_status"].get("invalid", []),
                "changed": result["field_status"].get("changed", []),
            }
            self._sync_session_scene_state(case, result["scene"])
            self.db.commit()
            result["next_actions"] = self.state_service.get_next_actions(case, project_context)
            result["scene"] = self.state_service.attach_planner(result["scene"], result["next_actions"])
            return result
        except ValueError as exc:
            self._record_runtime_failure(
                case,
                error_code=str(exc),
                event_type="payload_update_failed",
                details={"payload_fields": sorted(payload_patch.keys())},
            )
            self.db.commit()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def update_field(
        self,
        project_id: int,
        case_id: str,
        field_name: str,
        value: Any,
        project_context: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        return self.merge_payload(
            project_id=project_id,
            case_id=case_id,
            payload_patch={field_name: value},
            project_context=project_context,
            source=source,
        )

    def execute_action(
        self,
        project_id: int,
        case_id: str,
        action_name: str,
        project_context: dict[str, Any],
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        try:
            result = self.orchestrator.perform_action(
                case,
                action_name,
                project_context,
                confirmation_token=confirmation_token,
            )
            self._record_runtime_activity(
                case,
                event_type=f"action_{action_name}",
                details={"action_name": action_name, "state": result["scene"].get("state")},
            )
            next_actions = self.state_service.get_next_actions(case, project_context)
            result["scene"] = self.state_service.attach_planner(
                self.state_service.serialize_scene(case, project_context),
                next_actions,
            )
            result["next_actions"] = next_actions
            self._sync_session_scene_state(case, result["scene"])
            self.db.commit()
            return result
        except ValueError as exc:
            self._record_runtime_failure(
                case,
                error_code=str(exc),
                event_type=f"action_{action_name}_failed",
                details={"action_name": action_name},
            )
            self.db.commit()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def recover_case(
        self,
        project_id: int,
        case_id: str,
        project_context: dict[str, Any],
        strategy: str | None = None,
        source: str = "openclaw",
    ) -> dict[str, Any]:
        case = self._get_case(project_id, case_id)
        scene_payload = self.state_service.serialize_scene(case, project_context)
        runtime_recovery = dict((scene_payload.get("runtime") or {}).get("recovery") or {})
        normalized_strategy = str(strategy or "auto").strip().lower() or "auto"
        selected_action = self._select_recovery_action(case, runtime_recovery, normalized_strategy)

        if not selected_action:
            next_actions = self.state_service.get_next_actions(case, project_context)
            return {
                "message": self._build_recovery_message(runtime_recovery, None, recovered=False),
                "scene": self.state_service.attach_planner(scene_payload, next_actions),
                "field_status": self.state_service.get_field_status(case),
                "next_actions": next_actions,
                "recovery_execution": {
                    "strategy": normalized_strategy,
                    "attempted_action": None,
                    "status": "refreshed",
                    "recovered": False,
                    "source": source,
                },
            }

        try:
            result = self.orchestrator.perform_action(case, selected_action, project_context)
            self._record_runtime_activity(
                case,
                event_type=f"recovery_{selected_action}",
                details={"strategy": normalized_strategy, "action_name": selected_action, "source": source},
            )
            next_actions = self.state_service.get_next_actions(case, project_context)
            result["scene"] = self.state_service.attach_planner(
                self.state_service.serialize_scene(case, project_context),
                next_actions,
            )
            result["field_status"] = self.state_service.get_field_status(case)
            result["next_actions"] = next_actions
            result["recovery_execution"] = {
                "strategy": normalized_strategy,
                "attempted_action": selected_action,
                "status": "recovered",
                "recovered": True,
                "source": source,
            }
            self._sync_session_scene_state(case, result["scene"])
            self.db.commit()
            return result
        except ValueError as exc:
            self._record_runtime_failure(
                case,
                error_code=str(exc),
                event_type=f"recovery_{selected_action}_failed",
                details={"strategy": normalized_strategy, "action_name": selected_action, "source": source},
            )
            self.db.commit()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def serve_artifact(self, project_id: int, case_id: str, artifact_key: str) -> FileResponse:
        case = self._get_case(project_id, case_id)
        artifacts = case.artifacts_json or {}
        key_map = {
            "preview_pdf": artifacts.get("preview_pdf_path"),
            "final_pdf": artifacts.get("final_pdf_path"),
        }
        artifact_path = key_map.get(artifact_key)
        if not artifact_path or not Path(artifact_path).exists():
            raise HTTPException(status_code=404, detail="artifact_not_found")
        return FileResponse(
            path=artifact_path,
            filename=Path(artifact_path).name,
            media_type="application/pdf",
            content_disposition_type="inline",
        )

    def _get_case(self, project_id: int, case_id: str) -> SceneCase:
        case = (
            self.db.query(SceneCase)
            .filter(SceneCase.project_id == project_id, SceneCase.case_code == case_id)
            .first()
        )
        if not case:
            raise HTTPException(status_code=404, detail="scene_case_not_found")
        return case

    def _get_or_create_case(
        self,
        project_id: int,
        session: ChatSession,
        scene_key: str,
        case_code: str | None,
    ) -> SceneCase:
        case = None
        if case_code:
            case = (
                self.db.query(SceneCase)
                .filter(SceneCase.project_id == project_id, SceneCase.case_code == case_code)
                .first()
            )
        if case:
            return case

        case = (
            self.db.query(SceneCase)
            .filter(
                SceneCase.project_id == project_id,
                SceneCase.session_id == session.id,
                SceneCase.scene_key == scene_key,
                SceneCase.status == "active",
            )
            .order_by(SceneCase.id.desc())
            .first()
        )
        if case:
            return case

        case = SceneCase(
            case_code=f"case_{uuid4().hex[:12]}",
            project_id=project_id,
            session_id=session.id,
            scene_key=scene_key,
            route_key=None,
            state="START",
            status="active",
            payload_json={},
            artifacts_json={},
            flags_json={},
        )
        self.db.add(case)
        self.db.flush()
        return case

    def _create_case(
        self,
        project_id: int,
        session: ChatSession,
        scene_key: str,
    ) -> SceneCase:
        case = SceneCase(
            case_code=f"case_{uuid4().hex[:12]}",
            project_id=project_id,
            session_id=session.id,
            scene_key=scene_key,
            route_key=None,
            state="START",
            status="active",
            payload_json={},
            artifacts_json={},
            flags_json={},
        )
        self.db.add(case)
        self.db.flush()
        return case

    def _find_active_case(self, project_id: int, session_id: int, scene_key: str) -> SceneCase | None:
        return (
            self.db.query(SceneCase)
            .filter(
                SceneCase.project_id == project_id,
                SceneCase.session_id == session_id,
                SceneCase.scene_key == scene_key,
                SceneCase.status == "active",
            )
            .order_by(SceneCase.id.desc())
            .first()
        )

    def _infer_route_key(
        self,
        initial_query: str | None,
        session: ChatSession,
        project_context: dict[str, Any],
        scene_key: str,
    ) -> str | None:
        if not initial_query:
            scene_state = ((session.state_json or {}).get("scene") or {})
            if scene_state.get("scene_key") == scene_key:
                return scene_state.get("route_key")
            return None

        memory_context = {
            "state": session.state_json or {},
        }
        route_decision = self.router.route(initial_query, memory_context, project_context)
        if route_decision and route_decision.get("scene_key") == scene_key:
            return route_decision.get("route_key")
        return None

    def _sync_session_scene_state(self, case: SceneCase, scene_payload: dict[str, Any]) -> None:
        session = self.db.query(ChatSession).filter(ChatSession.id == case.session_id).first()
        if not session:
            return
        self.session_service.sync_scene_state(session, scene_payload)

    def _record_runtime_activity(self, case: SceneCase, event_type: str, details: dict[str, Any] | None = None) -> None:
        flags = dict(case.flags_json or {})
        flags["_runtime_last_activity"] = {
            "event_type": event_type,
            "details": details or {},
            "at": datetime.utcnow().isoformat(),
        }
        flags.pop("_runtime_last_failure", None)
        case.flags_json = flags
        case.last_error_code = None
        case.updated_at = datetime.utcnow()

    def _record_runtime_failure(
        self,
        case: SceneCase,
        error_code: str,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        flags = dict(case.flags_json or {})
        flags["_runtime_last_failure"] = {
            "event_type": event_type,
            "error_code": error_code,
            "details": details or {},
            "at": datetime.utcnow().isoformat(),
        }
        case.flags_json = flags
        case.last_error_code = error_code
        case.updated_at = datetime.utcnow()

    def _select_recovery_action(
        self,
        case: SceneCase,
        recovery_payload: dict[str, Any],
        strategy: str,
    ) -> str | None:
        if not recovery_payload.get("last_error_code"):
            return None
        if strategy in {"refresh", "refresh_scene_status", "status"}:
            return None
        if strategy in {"generate_pdf", "preview_mail"}:
            return strategy
        if strategy not in {"auto", "retry"}:
            return None
        if recovery_payload.get("retry_allowed") and recovery_payload.get("auto_retry_action"):
            return str(recovery_payload["auto_retry_action"])
        return None

    def _build_recovery_message(
        self,
        recovery_payload: dict[str, Any],
        attempted_action: str | None,
        recovered: bool,
    ) -> str:
        if recovered and attempted_action:
            return f"已按恢復策略重新執行「{attempted_action}」，目前 scene 狀態已更新。"
        hint = recovery_payload.get("hint")
        if hint:
            return str(hint)
        return "目前沒有可自動恢復的動作，已返回最新 scene 狀態。"

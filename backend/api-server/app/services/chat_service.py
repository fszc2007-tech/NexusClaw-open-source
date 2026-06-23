from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import re
from typing import Any, AsyncIterator
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text_locale import format_reply_text
from app.models.chat import ChatMessage, ChatSession
from app.models.knowledge import KnowledgeBase, KnowledgeItem
from app.services.deepseek_service import DeepSeekService
from app.services.knowledge_compilation_service import KnowledgeCompilationService
from app.services.knowledge_service import KnowledgeService
from app.services.project_service import ProjectService
from app.services.retrieval_service import RetrievalService
from app.services.scenes.carryover_intent_service import SceneCarryoverIntentService
from app.services.scenes.service import SceneService


logger = logging.getLogger(__name__)


class ChatService:
    SUPPORTED_MEMORY_SCOPES = {"off", "session_only"}
    REPLY_LOCALE = "zh-Hant"
    CITATION_PATTERN = re.compile(r"\[(s\d+)\]")
    CONTEXT_DEPENDENT_PATTERNS = (
        r"^(那|那么|這|这|這個|这个|這個問題|这个问题|這種情況|这种情况|它|他|她|該|该|此|上面|上述|前面|剛才|刚才|還|还|再|然後|然后|接著|接着)",
        r"(需要什么材料|要什么材料|怎么办|怎么做|去哪里|在哪里|多久|多长时间|要预约吗|可以代办吗)$",
        r"(這個表|这个表|該表|该表|此表|這個欄位|这个字段|該欄位|该字段|上題|上一題|前一題|剛才那題|刚才那题)",
        r"^(可以吗|行吗|能吗|会吗|对吗)$",
    )
    ASSISTANT_IDENTITY_PATTERNS = (
        r"^(你|妳)(是誰|是谁|係邊個|係咩|是什麼助手|是做什麼的|能做什麼|可以做什麼|叫什麼名字|叫咩名)[？?]?$",
        r"^介紹(一下)?你自己[。？?]?$",
        r"^whoareyou[？?]?$",
    )
    KNOWLEDGE_STAT_QUERY_KEYWORDS = (
        "申請",
        "辦理",
        "报名",
        "報名",
        "统计",
        "統計",
        "人数",
        "人數",
        "总数",
        "總數",
        "符合要求",
        "表格",
        "表裏",
        "表裡",
        "表中",
        "數據",
        "数据",
        "百分率",
        "宗數",
        "違規",
    )

    REGION_KEYWORDS = {
        "香港": ("香港", "hk"),
        "澳门": ("澳门", "macao", "macau"),
        "内地": ("内地",),
    }

    FOCUS_KEYWORDS = {
        "材料": ("材料", "资料", "证件", "提交", "照片"),
        "流程": ("流程", "步骤", "怎么办", "如何办理", "怎样办"),
        "预约": ("预约",),
        "地点": ("地点", "哪里", "窗口", "大厅", "地址", "部门"),
        "时限": ("多久", "几天", "时间", "时限", "期限", "有效期"),
        "费用": ("收费", "费用", "多少钱", "价格"),
        "条件": ("条件", "要求", "资格", "适用对象"),
    }

    INTENT_KEYWORDS = {
        "办理港澳通行证": ("港澳通行证", "通行证"),
        "办理居住证": ("居住证",),
        "社保业务办理": ("社保", "社会保险"),
        "公积金业务办理": ("公积金",),
        "护照业务办理": ("护照",),
    }

    IDENTITY_KEYWORDS = {
        "首次办理": ("首次", "初次"),
        "续签": ("续签", "签注", "再次办理"),
        "补办": ("补办", "遗失"),
        "换发": ("换发", "到期换证"),
    }

    APPLICANT_KEYWORDS = {
        "本人": ("本人",),
        "代办": ("代办", "委托"),
        "老人": ("老人", "长者", "老年人"),
        "未成年人": ("未成年人", "儿童", "小孩", "未满18"),
    }

    REGION_DEPENDENT_FOCUS = {"预约", "地点", "时限", "条件"}
    AUTHORIZED_SCOPE_MARKERS = (
        "authorized",
        "authorised",
        "official",
        "knowledge",
        "policy",
        "service",
        "授權",
        "授权",
        "官方",
        "知識",
        "知识",
        "政策",
        "服務",
        "服务",
    )
    AUTHORIZED_ALIAS_REPLACEMENTS = (
        (re.compile(r"\bofficial\\s+service\\b", re.IGNORECASE), "official service"),
        (re.compile(r"\bauthorized\\s+knowledge\\b", re.IGNORECASE), "authorized knowledge"),
    )
    AUTHORIZED_HARD_REFUSAL_PATTERNS = {
        "out_of_scope": (
            r"(與本知識庫無關|和本知识库无关|unrelated to this knowledge base)",
        ),
        "unverified_case": (
            r"(聽講|听讲|聽說|听说|傳聞|传闻|小道消息|內部消息|内部消息|未公布|未公佈|爆料)",
            r"(預測|预测|估計|估计|會唔會|会不会)",
            r"(一定會|一定会|保證|保证|包唔包|包不包|必定|肯定批|一定批|會唔會批|会不会批)",
            r"(個別情況|个别情况|我呢個情況|我这个情况|我可唔可以|我可不可以).*(一定|必定|保證|保证)",
        ),
    }
    ENGLISH_REPLY_PATTERNS = (
        "reply in english",
        "answer in english",
        "respond in english",
        "please use english",
        "in english",
    )

    def __init__(self, db: Session):
        self.db = db
        self.knowledge_service = KnowledgeService(db)
        self.knowledge_compilation_service = KnowledgeCompilationService(db)
        self.project_service = ProjectService(db)
        self.retrieval_service = RetrievalService(db)
        self.deepseek_service = DeepSeekService()
        self.scene_carryover_intent_service = SceneCarryoverIntentService(self.deepseek_service)
        self.reply_locale = self.REPLY_LOCALE

    def ask(
        self,
        project_id: int,
        session_id: str | None,
        query: str,
        use_memory: bool = True,
        source: str = "portal",
        selected_kb_ids: list[int] | None = None,
        switches: dict | None = None,
    ) -> dict:
        project_context = self.project_service.get_active_project_context(project_id)
        if not project_context["project"]:
            raise ValueError("project_not_found")
        self.reply_locale = self._resolve_reply_locale(query, project_context)

        session = self._get_or_create_session(
            project_id=project_id,
            session_code=session_id,
            source=source,
            selected_kb_ids=selected_kb_ids,
            switches=switches,
        )

        should_use_memory = self._should_use_memory(use_memory, project_context["settings"])
        memory_expired = self._expire_session_memory_if_needed(session, project_context["settings"])
        memory_context = self._build_memory_context(session=session, use_memory=should_use_memory and not memory_expired)
        if self._is_assistant_identity_query(query):
            return self._finalize_direct_answer(
                project_id=project_id,
                session=session,
                query=query,
                rewritten_query=" ".join(query.strip().split()),
                answer=self._build_assistant_identity_answer(project_context),
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                response_mode="persona",
                model_name="persona-direct-v1",
                prompt_snapshot="[persona]",
                use_memory=use_memory,
                scene_intent={"intent_mode": "assistant_identity"},
                carryover_decision=None,
            )
        scene_runtime = self._resolve_scene_runtime(
            project_id=project_id,
            session=session,
            query=query,
            memory_context=memory_context,
            project_context=project_context,
        )
        scene_intent = scene_runtime["scene_intent"]
        scene_result = scene_runtime["scene_result"]
        carryover_decision = scene_runtime["carryover_decision"]
        if scene_result:
            hybrid_context = self._build_hybrid_scene_context(
                project_id=project_id,
                project_name=project_context["project"]["company_name"],
                query=query,
                memory_context=memory_context,
                session=session,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                scene_result=scene_result,
            )
            return self._finalize_scene_response(
                project_id=project_id,
                session=session,
                query=query,
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                scene_result=scene_result,
                hybrid_context=hybrid_context,
                carryover_decision=carryover_decision,
            )
        rewritten_query = self._normalize_scope_aliases(
            self.deepseek_service.rewrite_query(
                self._rewrite_query(query, memory_context),
                memory_context["recent_turns"],
            ),
            project_context,
        )

        effective_kb_ids = self._resolve_chat_kb_ids(project_id, selected_kb_ids, session.selected_kb_ids)
        compilation_context = self.knowledge_compilation_service.build_chat_compilation_context(
            project_id=project_id,
            kb_ids=effective_kb_ids,
            query=rewritten_query,
            settings=project_context["settings"],
            switches=switches,
        )
        ranked_items = self.retrieval_service.retrieve(
            project_id=project_id,
            query=rewritten_query,
            selected_kb_ids=effective_kb_ids,
            rewritten_query=rewritten_query,
            scene_state=memory_context.get("state") or {},
        )
        strategy = str(compilation_context.get("strategy") or "compiled_first")
        prompt_ranked_items, sources, compiled_used = self._merge_compilation_with_retrieval(
            compilation_context=compilation_context,
            ranked_items=ranked_items,
            strategy=strategy,
        )
        retrieval_usable = self._should_accept_retrieval(rewritten_query, ranked_items, switches)
        effective_retrieval_usable = retrieval_usable or bool(compilation_context.get("usable"))
        policy_decision = self._evaluate_policy_decision(
            project_context=project_context,
            query=query,
            rewritten_query=rewritten_query,
            ranked_items=ranked_items,
            retrieval_usable=effective_retrieval_usable,
        )
        if policy_decision:
            return self._finalize_direct_answer(
                project_id=project_id,
                session=session,
                query=query,
                rewritten_query=rewritten_query,
                answer=policy_decision["message"],
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                response_mode="policy_refusal",
                model_name="policy-guard-v1",
                prompt_snapshot="[policy_refusal]",
                use_memory=use_memory,
                scene_intent=scene_intent,
                carryover_decision=carryover_decision,
                policy_basis=policy_decision["policy_basis"],
            )

        next_state = self._extract_state(
            query=query,
            previous_state=session.state_json or {},
            ranked_items=ranked_items,
            previous_summary=session.summary,
        )
        updated_summary = self._build_session_summary(
            previous_summary=session.summary,
            state=next_state,
            latest_query=query,
            ranked_items=ranked_items,
        )
        safety_flags = self._detect_safety_flags(query)
        system_prompt = self._build_system_prompt(project_context["project"]["company_name"])
        answer_memory_context = self._build_answer_memory_context(query, rewritten_query, memory_context)
        runtime_prompt = self._build_runtime_prompt(
            prompt_template=project_context["settings"]["prompt_template"],
            query=query,
            rewritten_query=rewritten_query,
            memory_context=answer_memory_context,
            ranked_items=prompt_ranked_items,
        )
        answer, model_name = self._generate_answer(
            project_name=project_context["project"]["company_name"],
            query=query,
            rewritten_query=rewritten_query,
            ranked_items=prompt_ranked_items,
            memory_context=answer_memory_context,
            state=next_state,
            retrieval_usable=effective_retrieval_usable,
            system_prompt=system_prompt,
            runtime_prompt=runtime_prompt,
        )
        answer = self._append_scene_help_cta(
            answer=answer,
            query=query,
            rewritten_query=rewritten_query,
            ranked_items=ranked_items,
        )
        scene_entry_hint = self._build_scene_entry_hint(scene_intent)
        suggested_actions = self._build_suggested_actions(query, rewritten_query, sources)
        orchestration_snapshot = self._build_knowledge_orchestration_snapshot(
            scene_intent=scene_intent,
            scene_entry_hint=scene_entry_hint,
            suggested_actions=suggested_actions,
            carryover_decision=carryover_decision,
            answer=answer,
        )

        session.title = self._build_session_title(session.title, next_state, query)
        session.selected_kb_ids = effective_kb_ids or []
        session.switches_json = switches or session.switches_json or {}
        session.summary = updated_summary
        session.state_json = next_state or None
        session.last_active_at = datetime.utcnow()

        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            query_raw=query,
            query_rewritten=rewritten_query,
            answer=answer,
            source_docs=sources,
            used_memory=memory_context["used"],
            memory_snapshot_json=memory_context["snapshot"] if memory_context["used"] else None,
            safety_flags_json=safety_flags,
            orchestration_json=orchestration_snapshot,
            prompt_snapshot=runtime_prompt,
            model_name=model_name,
            trace_id=uuid4().hex[:16],
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        return {
            "project_id": project_id,
            "session_id": session.session_code,
            "query": query,
            "query_raw": query,
            "rewritten_query": rewritten_query,
            "answer": answer,
            "suggested_actions": suggested_actions,
            "sources": sources,
            "use_memory": use_memory,
            "memory": {
                "used": memory_context["used"],
                "summary_hit": memory_context["summary_hit"],
                "state_hit": memory_context["state_hit"],
                "preference_hit": False,
            },
            "policy_basis": {
                "source_mode": "compiled_knowledge" if compilation_context.get("page_hits") else ("knowledge_base" if ranked_items else "none"),
                "compiled_context_used": compiled_used,
                "source_count": len(sources),
                "compiled_page_count": len(compilation_context.get("page_hits") or []),
                "raw_source_count": len([item for item in sources if "chunk_id" in item or item.get("knowledge_id")]),
                "conflict_detected": False,
                "retrieval_usable": effective_retrieval_usable,
                "decision": "answer",
                "decision_reason": compilation_context.get("fallback_reason") or ("retrieval_usable" if retrieval_usable else "fallback_answer"),
            },
            "compilation": {
                "enabled": bool(compilation_context.get("enabled")),
                "strategy": compilation_context.get("strategy"),
                "page_hits": compilation_context.get("page_hits") or [],
                "fallback_reason": compilation_context.get("fallback_reason"),
            },
            "intent_mode": scene_intent.get("intent_mode"),
            "scene_entry_hint": scene_entry_hint,
            "prompt_snapshot": message.prompt_snapshot,
            "trace_id": message.trace_id,
            "response_mode": "knowledge",
            "scene": None,
            "field_status": None,
            "next_actions": None,
            "orchestration": orchestration_snapshot,
            "carryover_decision": carryover_decision,
        }

    async def stream_ask(
        self,
        project_id: int,
        session_id: str | None,
        query: str,
        use_memory: bool = True,
        source: str = "portal",
        selected_kb_ids: list[int] | None = None,
        switches: dict | None = None,
    ) -> AsyncIterator[str]:
        project_context = self.project_service.get_active_project_context(project_id)
        if not project_context["project"]:
            raise ValueError("project_not_found")
        self.reply_locale = self._resolve_reply_locale(query, project_context)

        session = self._get_or_create_session(
            project_id=project_id,
            session_code=session_id,
            source=source,
            selected_kb_ids=selected_kb_ids,
            switches=switches,
        )
        should_use_memory = self._should_use_memory(use_memory, project_context["settings"])
        memory_expired = self._expire_session_memory_if_needed(session, project_context["settings"])
        memory_context = self._build_memory_context(session=session, use_memory=should_use_memory and not memory_expired)
        if self._is_assistant_identity_query(query):
            response_data = self._finalize_direct_answer(
                project_id=project_id,
                session=session,
                query=query,
                rewritten_query=" ".join(query.strip().split()),
                answer=self._build_assistant_identity_answer(project_context),
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                response_mode="persona",
                model_name="persona-direct-v1",
                prompt_snapshot="[persona]",
                use_memory=use_memory,
                scene_intent={"intent_mode": "assistant_identity"},
                carryover_decision=None,
            )
            yield self._sse_event(
                "meta",
                {
                    "session_id": session.session_code,
                    "rewritten_query": response_data["rewritten_query"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "trace_id": response_data["trace_id"],
                    "use_memory": use_memory,
                    "retrieval_usable": False,
                    "response_mode": "knowledge",
                    "scene": None,
                    "field_status": None,
                    "next_actions": None,
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": None,
                },
            )
            yield self._sse_event("delta", {"content": response_data["answer"]})
            yield self._sse_event(
                "done",
                {
                    "session_id": session.session_code,
                    "answer": response_data["answer"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "model_name": "persona-direct-v1",
                    "trace_id": response_data["trace_id"],
                    "response_mode": "knowledge",
                    "scene": None,
                    "field_status": None,
                    "next_actions": None,
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": None,
                },
            )
            return
        scene_runtime = self._resolve_scene_runtime(
            project_id=project_id,
            session=session,
            query=query,
            memory_context=memory_context,
            project_context=project_context,
        )
        scene_intent = scene_runtime["scene_intent"]
        scene_result = scene_runtime["scene_result"]
        carryover_decision = scene_runtime["carryover_decision"]
        if scene_result:
            trace_id = uuid4().hex[:16]
            hybrid_context = self._build_hybrid_scene_context(
                project_id=project_id,
                project_name=project_context["project"]["company_name"],
                query=query,
                memory_context=memory_context,
                session=session,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                scene_result=scene_result,
            )
            response_data = self._finalize_scene_response(
                project_id=project_id,
                session=session,
                query=query,
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                scene_result=scene_result,
                hybrid_context=hybrid_context,
                trace_id=trace_id,
                carryover_decision=carryover_decision,
            )
            yield self._sse_event(
                "meta",
                {
                    "session_id": session.session_code,
                    "rewritten_query": response_data["rewritten_query"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "trace_id": trace_id,
                    "use_memory": use_memory,
                    "retrieval_usable": False,
                    "response_mode": "scene",
                    "scene": response_data["scene"],
                    "field_status": response_data["field_status"],
                    "next_actions": response_data["next_actions"],
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": carryover_decision,
                },
            )
            yield self._sse_event("delta", {"content": response_data["answer"]})
            yield self._sse_event(
                "done",
                {
                    "session_id": session.session_code,
                    "answer": response_data["answer"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "model_name": "scene-orchestrator-v1",
                    "trace_id": trace_id,
                    "response_mode": "scene",
                    "scene": response_data["scene"],
                    "field_status": response_data["field_status"],
                    "next_actions": response_data["next_actions"],
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": carryover_decision,
                },
            )
            return
        rewritten_query = self._normalize_scope_aliases(
            self.deepseek_service.rewrite_query(
                self._rewrite_query(query, memory_context),
                memory_context["recent_turns"],
            ),
            project_context,
        )
        effective_kb_ids = self._resolve_chat_kb_ids(project_id, selected_kb_ids, session.selected_kb_ids)
        compilation_context = self.knowledge_compilation_service.build_chat_compilation_context(
            project_id=project_id,
            kb_ids=effective_kb_ids,
            query=rewritten_query,
            settings=project_context["settings"],
            switches=switches,
        )
        ranked_items = self.retrieval_service.retrieve(
            project_id=project_id,
            query=rewritten_query,
            selected_kb_ids=effective_kb_ids,
            rewritten_query=rewritten_query,
            scene_state=memory_context.get("state") or {},
        )
        strategy = str(compilation_context.get("strategy") or "compiled_first")
        prompt_ranked_items, response_sources, compiled_used = self._merge_compilation_with_retrieval(
            compilation_context=compilation_context,
            ranked_items=ranked_items,
            strategy=strategy,
        )
        retrieval_usable = self._should_accept_retrieval(rewritten_query, ranked_items, switches)
        effective_retrieval_usable = retrieval_usable or bool(compilation_context.get("usable"))
        policy_decision = self._evaluate_policy_decision(
            project_context=project_context,
            query=query,
            rewritten_query=rewritten_query,
            ranked_items=ranked_items,
            retrieval_usable=effective_retrieval_usable,
        )
        if policy_decision:
            response_data = self._finalize_direct_answer(
                project_id=project_id,
                session=session,
                query=query,
                rewritten_query=rewritten_query,
                answer=policy_decision["message"],
                memory_context=memory_context,
                source=source,
                selected_kb_ids=selected_kb_ids,
                switches=switches,
                response_mode="policy_refusal",
                model_name="policy-guard-v1",
                prompt_snapshot="[policy_refusal]",
                use_memory=use_memory,
                scene_intent=scene_intent,
                carryover_decision=carryover_decision,
                policy_basis=policy_decision["policy_basis"],
            )
            yield self._sse_event(
                "meta",
                {
                    "session_id": session.session_code,
                    "rewritten_query": response_data["rewritten_query"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "trace_id": response_data["trace_id"],
                    "use_memory": use_memory,
                    "retrieval_usable": False,
                    "response_mode": "knowledge",
                    "scene": None,
                    "field_status": None,
                    "next_actions": None,
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": carryover_decision,
                    "policy_basis": response_data["policy_basis"],
                },
            )
            yield self._sse_event("delta", {"content": response_data["answer"]})
            yield self._sse_event(
                "done",
                {
                    "session_id": session.session_code,
                    "answer": response_data["answer"],
                    "sources": [],
                    "suggested_actions": response_data["suggested_actions"],
                    "model_name": "policy-guard-v1",
                    "trace_id": response_data["trace_id"],
                    "response_mode": "knowledge",
                    "scene": None,
                    "field_status": None,
                    "next_actions": None,
                    "intent_mode": response_data["intent_mode"],
                    "orchestration": response_data["orchestration"],
                    "carryover_decision": carryover_decision,
                    "policy_basis": response_data["policy_basis"],
                },
            )
            return
        next_state = self._extract_state(
            query=query,
            previous_state=session.state_json or {},
            ranked_items=ranked_items,
            previous_summary=session.summary,
        )
        updated_summary = self._build_session_summary(
            previous_summary=session.summary,
            state=next_state,
            latest_query=query,
            ranked_items=ranked_items,
        )
        safety_flags = self._detect_safety_flags(query)
        system_prompt = self._build_system_prompt(project_context["project"]["company_name"])
        answer_memory_context = self._build_answer_memory_context(query, rewritten_query, memory_context)
        runtime_prompt = self._build_runtime_prompt(
            prompt_template=project_context["settings"]["prompt_template"],
            query=query,
            rewritten_query=rewritten_query,
            memory_context=answer_memory_context,
            ranked_items=prompt_ranked_items,
        )
        trace_id = uuid4().hex[:16]
        scene_entry_hint = self._build_scene_entry_hint(scene_intent)
        suggested_actions = self._build_suggested_actions(query, rewritten_query, ranked_items)

        yield self._sse_event(
            "meta",
            {
                "session_id": session.session_code,
                "rewritten_query": rewritten_query,
                "sources": response_sources,
                "suggested_actions": suggested_actions,
                "trace_id": trace_id,
                "use_memory": use_memory,
                "retrieval_usable": retrieval_usable,
                "compiled_context_used": compiled_used,
                "compilation": {
                    "enabled": bool(compilation_context.get("enabled")),
                    "strategy": compilation_context.get("strategy"),
                    "page_hits": compilation_context.get("page_hits") or [],
                    "fallback_reason": compilation_context.get("fallback_reason"),
                },
                "response_mode": "knowledge",
                "scene": None,
                "field_status": None,
                "next_actions": None,
                "intent_mode": scene_intent.get("intent_mode"),
                "scene_entry_hint": scene_entry_hint,
                "carryover_decision": carryover_decision,
            },
        )

        if (
            self._should_force_rule_based_answer(query, rewritten_query, ranked_items)
            or not effective_retrieval_usable
            or not self.deepseek_service.is_enabled()
        ):
            answer = (
                self._build_chunk_fallback_answer(query, rewritten_query, prompt_ranked_items)
                if self._is_chunk_evidence_mode(prompt_ranked_items)
                else self._build_answer(
                    query=query,
                    rewritten_query=rewritten_query,
                    project_name=project_context["project"]["company_name"],
                    ranked_items=prompt_ranked_items,
                    memory_context=answer_memory_context,
                    state=next_state,
                )
            )
            answer = self._append_scene_help_cta(
                answer=answer,
                query=query,
                rewritten_query=rewritten_query,
                ranked_items=ranked_items,
            )
            yield self._sse_event("delta", {"content": answer})
            model_name = "rule-based-rag-memory-v1"
        elif self._is_chunk_evidence_mode(prompt_ranked_items):
            answer, model_name = self._generate_answer(
                project_name=project_context["project"]["company_name"],
                query=query,
                rewritten_query=rewritten_query,
                ranked_items=prompt_ranked_items,
                memory_context=answer_memory_context,
                state=next_state,
                retrieval_usable=effective_retrieval_usable,
                system_prompt=system_prompt,
                runtime_prompt=runtime_prompt,
            )
            yield self._sse_event("delta", {"content": answer})
        else:
            model_name = settings.DEEPSEEK_CHAT_MODEL
            chunks: list[str] = []
            try:
                async for chunk in self.deepseek_service.stream_answer(system_prompt, runtime_prompt, self.reply_locale):
                    chunks.append(chunk)
                    yield self._sse_event("delta", {"content": chunk})
            except Exception as exc:  # noqa: BLE001
                yield self._sse_event("error", {"message": str(exc)})
            answer = "".join(chunks).strip()
            if not answer:
                answer = self._build_answer(
                    query=query,
                    rewritten_query=rewritten_query,
                    project_name=project_context["project"]["company_name"],
                    ranked_items=prompt_ranked_items,
                    memory_context=answer_memory_context,
                    state=next_state,
                )
            final_answer = self._append_scene_help_cta(
                answer=answer,
                query=query,
                rewritten_query=rewritten_query,
                ranked_items=ranked_items,
            )
            suffix = final_answer[len(answer):] if final_answer.startswith(answer) else ""
            if suffix:
                yield self._sse_event("delta", {"content": suffix})
            answer = final_answer

        orchestration_snapshot = self._build_knowledge_orchestration_snapshot(
            scene_intent=scene_intent,
            scene_entry_hint=scene_entry_hint,
            suggested_actions=suggested_actions,
            carryover_decision=carryover_decision,
            answer=answer,
        )

        session.title = self._build_session_title(session.title, next_state, query)
        session.selected_kb_ids = effective_kb_ids or []
        session.switches_json = switches or session.switches_json or {}
        session.summary = updated_summary
        session.state_json = next_state or None
        session.last_active_at = datetime.utcnow()

        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            query_raw=query,
            query_rewritten=rewritten_query,
            answer=answer,
            source_docs=response_sources,
            used_memory=memory_context["used"],
            memory_snapshot_json=memory_context["snapshot"] if memory_context["used"] else None,
            safety_flags_json=safety_flags,
            orchestration_json=orchestration_snapshot,
            prompt_snapshot=runtime_prompt,
            model_name=model_name,
            trace_id=trace_id,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        yield self._sse_event(
            "done",
            {
                "session_id": session.session_code,
                "answer": answer,
                "sources": response_sources,
                "suggested_actions": suggested_actions,
                "model_name": model_name,
                "trace_id": trace_id,
                "compilation": {
                    "enabled": bool(compilation_context.get("enabled")),
                    "strategy": compilation_context.get("strategy"),
                    "page_hits": compilation_context.get("page_hits") or [],
                    "fallback_reason": compilation_context.get("fallback_reason"),
                },
                "response_mode": "knowledge",
                "scene": None,
                "field_status": None,
                "next_actions": None,
                "intent_mode": scene_intent.get("intent_mode"),
                "scene_entry_hint": scene_entry_hint,
                "orchestration": orchestration_snapshot,
                "carryover_decision": carryover_decision,
            },
        )

    def list_sessions(self, project_id: int) -> list[dict]:
        project_settings = self.project_service.get_memory_settings(project_id)
        sessions = (
            self.db.query(ChatSession)
            .filter(ChatSession.project_id == project_id)
            .order_by(ChatSession.last_active_at.desc(), ChatSession.id.desc())
            .all()
        )
        result = []
        expired_any = False
        for session in sessions:
            expired_any = self._expire_session_memory_if_needed(session, project_settings) or expired_any
            latest_message = (
                self.db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .first()
            )
            result.append(
                {
                    "session_id": session.session_code,
                    "title": session.title,
                    "source": session.source,
                    "status": session.status,
                    "selected_kb_ids": session.selected_kb_ids or [],
                    "summary": session.summary,
                    "state_json": session.state_json or {},
                    "last_query": latest_message.query_raw if latest_message else None,
                    "last_answer": latest_message.answer if latest_message else None,
                    "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
                }
            )
        if expired_any:
            self.db.commit()
        return result

    def get_session_detail(self, project_id: int, session_id: str) -> dict | None:
        project_settings = self.project_service.get_memory_settings(project_id)
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.project_id == project_id, ChatSession.session_code == session_id)
            .first()
        )
        if not session:
            return None
        if self._expire_session_memory_if_needed(session, project_settings):
            self.db.commit()

        turns = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .all()
        )
        return {
            "session_id": session.session_code,
            "title": session.title,
            "source": session.source,
            "status": session.status,
            "selected_kb_ids": session.selected_kb_ids or [],
            "summary": session.summary,
            "state_json": session.state_json or {},
            "turns": [self._serialize_turn(turn) for turn in turns],
        }

    def clear_session_memory(self, project_id: int, session_id: str) -> bool:
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.project_id == project_id, ChatSession.session_code == session_id)
            .first()
        )
        if not session:
            return False

        self._reset_session_memory_fields(session)
        session.last_active_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def _should_accept_retrieval(
        self,
        query: str,
        ranked_items: list[dict[str, Any]],
        switches: dict[str, Any] | None,
    ) -> bool:
        if switches and switches.get("retrieval_guard") is False:
            return bool(ranked_items)
        return self.deepseek_service.check_retrieval(query, ranked_items)

    def _merge_compilation_with_retrieval(
        self,
        *,
        compilation_context: dict[str, Any],
        ranked_items: list[dict[str, Any]],
        strategy: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        compilation_items = list(compilation_context.get("reference_items") or [])
        compilation_sources = list(compilation_context.get("raw_sources") or [])
        compilation_usable = bool(compilation_context.get("usable"))

        if not compilation_items or not compilation_usable:
            return ranked_items, (compilation_sources or ranked_items), False

        if strategy == "raw_first":
            prompt_items = ranked_items or compilation_items
            if ranked_items:
                prompt_items = self._merge_prompt_items(ranked_items, compilation_items, limit=max(len(ranked_items), 6))
            response_sources = self._merge_source_items(ranked_items, compilation_sources)
            return prompt_items, response_sources, bool(compilation_items)

        if strategy == "hybrid":
            prompt_items = self._merge_prompt_items(compilation_items, ranked_items, limit=6)
            response_sources = self._merge_source_items(compilation_sources, ranked_items)
            return prompt_items, response_sources, True

        prompt_items = self._merge_prompt_items(compilation_items, ranked_items, limit=6)
        response_sources = self._merge_source_items(compilation_sources, ranked_items)
        return prompt_items, response_sources, True

    def _merge_prompt_items(
        self,
        primary_items: list[dict[str, Any]],
        secondary_items: list[dict[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in list(primary_items) + list(secondary_items):
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("compilation_page_id") or item.get("chunk_id") or item.get("knowledge_id") or item.get("source_id") or ""),
                str(item.get("title") or item.get("document_name") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                break
        return merged

    def _merge_source_items(
        self,
        primary_items: list[dict[str, Any]],
        secondary_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in list(primary_items) + list(secondary_items):
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("source_type") or item.get("source_kind") or ""),
                str(item.get("source_id") or item.get("chunk_id") or item.get("knowledge_id") or ""),
                str(item.get("source_ref_id") or item.get("file_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _build_system_prompt(self, project_name: str) -> str:
        localized_project_name = self._format_reply_text(project_name)
        return (
            f"你是 {localized_project_name} 的知識問答助手。"
            "會話記憶只可用於理解當前問題的上下文、補全省略資訊、維持多輪對話連續性。"
            "對政策、材料、資格、流程、時限等事實結論，必須優先依據提供的參考資料回答，不得僅根據會話記憶推斷。"
            "如果會話記憶與參考資料衝突，以參考資料為準。"
            "請優先依據提供的參考資料回答，嚴禁編造不存在的政策、流程或材料要求。"
            "如果資料不足，必須直接說明現有資料不足以確認，不得以常識補全。"
            "對個案裁定、傳聞、預測、未公開資訊或超出授權知識範圍的問題，必須拒絕推測，並建議使用者改為查閱官方資料或聯絡官方渠道。"
            "回答語氣要自然、專業、可靠、非技術化，不要輸出系統內部推理描述。"
            "預設使用繁體中文作答；若使用者明確要求英文，則改用英文。"
        )

    def _build_runtime_prompt(
        self,
        prompt_template: str | None,
        query: str,
        rewritten_query: str,
        memory_context: dict[str, Any],
        ranked_items: list[dict[str, Any]],
    ) -> str:
        if self._is_chunk_evidence_mode(ranked_items):
            return self._build_chunk_runtime_prompt(query, rewritten_query, ranked_items)
        qa_block = self._render_reference_block(ranked_items)
        history_block = self._render_history_block(memory_context)
        template = prompt_template or "參考資料：{qa}\n歷史對話：{history}\n使用者問題：{query}"
        prompt_body = (
            template.replace("{qa}", qa_block or "暫無參考資料")
            .replace("{history}", history_block or "暫無歷史對話")
            .replace("{query}", rewritten_query or query)
        )
        answer_contract = (
            "[Answer Contract]\n"
            "- 當前使用者問題是最高優先級；歷史對話只可用於補全代詞、省略詞或明確承接的上下文。\n"
            "- 如果當前問題已明確包含年份、對象、表名、行名、欄位或統計口徑，不得用歷史對話替換或覆蓋這些條件。\n"
            "- 回答統計、表格、數字、比例、欄位定義時，先給直接答案；若使用表格資料，需對齊行名與欄位名。\n"
            "- 使用者問「表格數據」時，應列出該行的主要欄位，不要只抽取其中一個數字。\n"
            "- 不要輸出「已結合上下文」「系統理解您正在諮詢」這類內部推理說明。\n"
            "- 回答順序固定為：直接結論 -> 必要說明/限制 -> 資料來源。\n"
            "- 若資料不足，統一使用「現有資料不足以確認」作為核心拒答語。\n"
            "- 若問題超出授權知識範圍、涉及個案裁定、傳聞或預測，不得嘗試回答。\n"
            "- 術語口徑以當前授權知識庫為準；不得引入未在資料中出現的客戶、機構或考試專名。\n"
        )
        return (
            f"[Output Policy]\nreply_locale: {self.reply_locale}\n預設以繁體中文輸出；如使用者明確要求英文，則以英文輸出。\n\n"
            f"{answer_contract}\n{prompt_body}"
        )

    def _is_assistant_identity_query(self, query: str) -> bool:
        compact = re.sub(r"\s+", "", query.strip().lower())
        if not compact:
            return False
        return any(re.fullmatch(pattern, compact, re.IGNORECASE) for pattern in self.ASSISTANT_IDENTITY_PATTERNS)

    def _build_assistant_identity_answer(self, project_context: dict[str, Any]) -> str:
        settings = project_context.get("settings") or {}
        persona = dict(settings.get("persona") or {})
        opening_text = str(persona.get("opening_text") or settings.get("opening_text") or "").strip()
        if opening_text:
            return self._format_reply_text(opening_text)

        assistant_name = str(persona.get("assistant_name") or "").strip()
        assistant_role = str(persona.get("assistant_role") or "").strip()
        project_name = self._format_reply_text((project_context.get("project") or {}).get("company_name") or "NexusClaw")
        if assistant_name and assistant_role:
            identity_line = f"我是 {assistant_name}，{assistant_role}。"
        else:
            identity_line = f"我是 {project_name} 的智能問答助手。"
        capability_line = "我會根據目前接入的知識庫內容，協助回答相關資訊查詢，並在資料不足時直接說明限制。"
        return self._format_reply_text(f"{identity_line}{capability_line}")

    def _generate_answer(
        self,
        project_name: str,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
        memory_context: dict[str, Any],
        state: dict[str, Any],
        retrieval_usable: bool,
        system_prompt: str,
        runtime_prompt: str,
    ) -> tuple[str, str]:
        fallback_answer = self._build_answer(
            query=query,
            rewritten_query=rewritten_query,
            project_name=project_name,
            ranked_items=ranked_items,
            memory_context=memory_context,
            state=state,
        )
        if self._should_force_rule_based_answer(query, rewritten_query, ranked_items):
            return fallback_answer, "rule-based-rag-memory-v1"
        if not retrieval_usable or not self.deepseek_service.is_enabled():
            if self._is_chunk_evidence_mode(ranked_items):
                return self._build_chunk_fallback_answer(query, rewritten_query, ranked_items), "rule-based-rag-memory-v1"
            return fallback_answer, "rule-based-rag-memory-v1"
        try:
            answer, model_name = self.deepseek_service.answer(
                self._build_chunk_system_prompt(project_name) if self._is_chunk_evidence_mode(ranked_items) else system_prompt,
                runtime_prompt,
                self.reply_locale,
            )
            cleaned_answer = answer or fallback_answer
            if self._is_chunk_evidence_mode(ranked_items):
                if self._validate_chunk_answer(cleaned_answer, ranked_items):
                    return cleaned_answer, model_name
                return self._build_chunk_fallback_answer(query, rewritten_query, ranked_items), "rule-based-rag-memory-v1"
            return cleaned_answer, model_name
        except Exception:  # noqa: BLE001
            if self._is_chunk_evidence_mode(ranked_items):
                return self._build_chunk_fallback_answer(query, rewritten_query, ranked_items), "rule-based-rag-memory-v1"
            return fallback_answer, "rule-based-rag-memory-v1"

    def _append_scene_help_cta(
        self,
        answer: str,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> str:
        if not self._should_offer_scene_help(query, rewritten_query, ranked_items):
            return answer
        if "需要我幫您完成表格的填寫嗎" in answer or "需要我帮你完成表格的填写吗" in answer:
            return answer
        cta = (
            "\n\n如果需要，我也可以繼續幫您完成表格填寫、PDF 生成，"
            "並在允許的情況下準備郵件預覽。需要我幫您完成表格的填寫嗎？"
        )
        return f"{answer.rstrip()}{cta}"

    def _should_offer_scene_help(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> bool:
        source = " ".join(
            [
                query,
                rewritten_query,
                " ".join(str(item.get("title") or "") for item in ranked_items[:3]),
                " ".join(str(item.get("snippet") or "") for item in ranked_items[:2]),
            ]
        ).lower()
        scene_keywords = (
            "ir1249",
            "irc3111a",
            "postal address",
            "business address",
            "taxctr1",
            "地址變更",
            "改地址",
            "更改地址",
            "變更地址",
            "通訊地址",
            "通讯地址",
            "收稅單地址",
            "收稅單地址",
            "稅務地址",
            "稅務地址",
            "業務地址",
            "業務地址",
        )
        return any(keyword in source for keyword in scene_keywords)

    def _build_suggested_actions(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        if not self._should_offer_scene_help(query, rewritten_query, ranked_items):
            return []

        source = " ".join(
            [
                query.lower(),
                rewritten_query.lower(),
                " ".join(str(item.get("title") or "").lower() for item in ranked_items[:3]),
                " ".join(str(item.get("snippet") or "").lower() for item in ranked_items[:2]),
            ]
        )

        generic_actions = [
            {
                "key": "scene_route_help",
                "label": "開始判斷該用哪份表",
                "prompt": "我想辦理香港稅務地址變更，請幫我判斷應該使用 IR1249 還是 IRC3111A。",
            },
            {
                "key": "scene_start_ir1249",
                "label": "開始填寫 IR1249",
                "prompt": "我想改收稅單地址，請幫我開始填寫 IR1249。",
            },
            {
                "key": "scene_start_irc3111a",
                "label": "開始填寫 IRC3111A",
                "prompt": "公司搬辦公室了，請幫我開始填寫 IRC3111A。",
            },
        ]

        if any(keyword in source for keyword in ("irc3111a", "business address", "业务地址", "業務地址", "搬办公室", "搬辦公室", "公司地址")):
            return [
                {
                    "key": "scene_start_irc3111a",
                    "label": "開始填寫 IRC3111A",
                    "prompt": "公司搬辦公室了，請幫我開始填寫 IRC3111A。",
                },
                {
                    "key": "scene_route_help",
                    "label": "幫我判斷是否該用這份表",
                    "prompt": "我這次是公司或業務地址變更，請幫我確認是否應該使用 IRC3111A。",
                },
            ]

        if any(keyword in source for keyword in ("ir1249", "postal address", "通訊地址", "通讯地址", "收税单地址", "收稅單地址")):
            return [
                {
                    "key": "scene_start_ir1249",
                    "label": "開始填寫 IR1249",
                    "prompt": "我想改收稅單地址，請幫我開始填寫 IR1249。",
                },
                {
                    "key": "scene_route_help",
                    "label": "幫我判斷是否該用這份表",
                    "prompt": "我這次是個人或通訊地址變更，請幫我確認是否應該使用 IR1249。",
                },
            ]

        return generic_actions

    def _finalize_direct_answer(
        self,
        project_id: int,
        session: ChatSession,
        query: str,
        rewritten_query: str,
        answer: str,
        memory_context: dict[str, Any],
        source: str,
        selected_kb_ids: list[int] | None,
        switches: dict | None,
        response_mode: str,
        model_name: str,
        prompt_snapshot: str,
        use_memory: bool,
        scene_intent: dict[str, Any],
        carryover_decision: dict[str, Any] | None,
        policy_basis: dict[str, Any] | None = None,
        source_docs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        trace_id = uuid4().hex[:16]
        next_state = dict(session.state_json or {})
        updated_summary = self._build_session_summary(
            previous_summary=session.summary,
            state=next_state,
            latest_query=query,
            ranked_items=[],
        )
        orchestration_snapshot = self._build_knowledge_orchestration_snapshot(
            scene_intent=scene_intent,
            scene_entry_hint=None,
            suggested_actions=[],
            carryover_decision=carryover_decision,
            answer=answer,
        )

        session.title = self._build_session_title(session.title, next_state, query)
        session.selected_kb_ids = self._resolve_chat_kb_ids(project_id, selected_kb_ids, session.selected_kb_ids) or []
        session.switches_json = switches or session.switches_json or {}
        session.summary = updated_summary
        session.state_json = next_state or None
        session.last_active_at = datetime.utcnow()

        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            query_raw=query,
            query_rewritten=rewritten_query,
            answer=answer,
            source_docs=source_docs or [],
            used_memory=memory_context["used"],
            memory_snapshot_json=memory_context["snapshot"] if memory_context["used"] else None,
            safety_flags_json=self._detect_safety_flags(query),
            orchestration_json=orchestration_snapshot,
            prompt_snapshot=prompt_snapshot,
            model_name=model_name,
            trace_id=trace_id,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        return {
            "project_id": project_id,
            "session_id": session.session_code,
            "query": query,
            "query_raw": query,
            "rewritten_query": rewritten_query,
            "answer": answer,
            "suggested_actions": [],
            "sources": source_docs or [],
            "use_memory": use_memory,
            "memory": {
                "used": memory_context["used"],
                "summary_hit": memory_context["summary_hit"],
                "state_hit": memory_context["state_hit"],
                "preference_hit": False,
            },
            "policy_basis": policy_basis
            or {
                "source_mode": response_mode,
                "source_count": len(source_docs or []),
                "retrieval_usable": False,
                "decision": "answer",
                "decision_reason": response_mode,
            },
            "intent_mode": scene_intent.get("intent_mode"),
            "scene_entry_hint": None,
            "prompt_snapshot": message.prompt_snapshot,
            "trace_id": trace_id,
            "response_mode": "knowledge",
            "scene": None,
            "field_status": None,
            "next_actions": None,
            "orchestration": orchestration_snapshot,
            "carryover_decision": carryover_decision,
        }

    def _render_reference_block(self, ranked_items: list[dict[str, Any]]) -> str:
        if self._is_chunk_evidence_mode(ranked_items):
            blocks: list[str] = []
            for index, item in enumerate(ranked_items, start=1):
                meta = item.get("chunk_meta") or {}
                section = " > ".join(meta.get("heading_path") or [])
                pages = meta.get("page_numbers") or []
                rows = meta.get("row_range") or []
                blocks.append(
                    "\n".join(
                        [
                            f"[SOURCE s{index}]",
                            f"source_id: {item.get('chunk_id')}",
                            f"source_kind: {item.get('source_kind') or ''}",
                            f"title: {item['title']}",
                            f"document_name: {item.get('document_name') or ''}",
                            f"source_url: {item.get('source_url') or ''}",
                            f"section: {section}",
                            f"page_numbers: {pages}",
                            f"row_range: {rows}",
                            f"authority_level: {item.get('authority_level') or ''}",
                            "content:",
                            str(item.get("citation_text") or item.get("contextual_text") or item["snippet"]),
                        ]
                    )
                )
            return "\n\n".join(blocks)
        blocks: list[str] = []
        for index, item in enumerate(ranked_items, start=1):
            lines = [
                f"[{index}] 標題：{item['title']}",
                f"來源：{item.get('document_name') or '人工知識'}",
            ]
            if item.get("source_url"):
                lines.append(f"官方連結：{item.get('source_url')}")
            lines.append(f"摘要：{item['snippet']}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _render_history_block(self, memory_context: dict[str, Any]) -> str:
        segments: list[str] = []
        if memory_context.get("summary"):
            segments.append(f"會話摘要：{memory_context['summary']}")
        state = memory_context.get("state") or {}
        if state:
            segments.append(f"會話狀態：{json.dumps(state, ensure_ascii=False)}")
        for turn in memory_context.get("recent_turns", []):
            if turn.get("query"):
                segments.append(f"使用者：{turn['query']}")
            if turn.get("answer"):
                segments.append(f"助手：{turn['answer']}")
        return "\n".join(segments)

    def _is_chunk_evidence_mode(self, ranked_items: list[dict[str, Any]]) -> bool:
        return bool(ranked_items) and "chunk_id" in ranked_items[0]

    def _build_chunk_system_prompt(self, project_name: str) -> str:
        localized_project_name = self._format_reply_text(project_name)
        return (
            f"你是 {localized_project_name} 的知識助手。"
            "你只能根據提供的 sources 回答，不得使用 sources 之外的知識補全事實。"
            "對流程、材料、表格欄位、政策條件、期限、例外情況，必須做句子級引用，例如 [s1]。"
            "如果 sources 不足以支持答案，直接回答：現有資料不足以確認。"
            "如果 sources 之間有衝突，優先採用 authority_level 更高，且 source_kind=file 或 manual 的來源。"
            "source_kind=file_qa 不能單獨作為最終依據。"
            "預設使用繁體中文作答；若使用者明確要求英文，則改用英文。"
        )

    def _build_chunk_runtime_prompt(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> str:
        reference_block = self._render_reference_block(ranked_items)
        return (
            f"用戶問題：\n{rewritten_query or query}\n\n"
            "回答要求：\n"
            "- 先給直接結論\n"
            "- 再補充條件、限制、例外情況\n"
            "- 每個關鍵結論後面要標記 [sX]\n"
            "- 若資料不足，明確說「現有資料不足以確認」\n\n"
            f"可用資料：\n{reference_block}"
        )

    def _extract_citations(self, answer: str) -> list[str]:
        return list(dict.fromkeys(self.CITATION_PATTERN.findall(answer or "")))

    def _validate_chunk_answer(self, answer: str, ranked_items: list[dict[str, Any]]) -> bool:
        source_map = {f"s{index}": item for index, item in enumerate(ranked_items, start=1)}
        cited = self._extract_citations(answer)
        if not cited:
            return False
        if any(citation not in source_map for citation in cited):
            return False
        if not settings.FILE_QA_ALLOWED_AS_SOLO_EVIDENCE:
            cited_items = [source_map[citation] for citation in cited]
            if cited_items and all(item.get("source_kind") == "file_qa" for item in cited_items):
                return False
        return True

    def _build_chunk_fallback_answer(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> str:
        if not ranked_items:
            return "現有資料不足以確認。"
        lines = ["結論："]
        top = ranked_items[0]
        lines.append(
            f"根據目前最相關的資料，《{self._format_reply_text(top['title'])}》提供了與此問題最直接相關的依據 [s1]。"
        )
        lines.append("")
        lines.append("補充說明：")
        for index, item in enumerate(ranked_items[:2], start=1):
            snippet = self._format_reply_text(str(item.get("snippet") or item.get("citation_text") or ""))
            source_kind = item.get("source_kind") or "source"
            lines.append(f"- 來源類型為 {source_kind}，命中內容為：{snippet} [s{index}]")
        if not settings.FILE_QA_ALLOWED_AS_SOLO_EVIDENCE and all(
            item.get("source_kind") == "file_qa" for item in ranked_items[:1]
        ):
            lines.append("")
            lines.append("現有資料不足以確認是否可僅依 file_qa 作最終判斷。")
        return "\n".join(lines)

    def _sse_event(self, event: str, payload: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def list_logs(
        self,
        project_id: int,
        session_id: str | None = None,
        query_keyword: str | None = None,
        answer_keyword: str | None = None,
    ) -> list[dict]:
        sessions = (
            self.db.query(ChatSession)
            .filter(ChatSession.project_id == project_id)
            .order_by(ChatSession.last_active_at.desc(), ChatSession.id.desc())
            .all()
        )
        results: list[dict] = []
        for session in sessions:
            if session_id and session.session_code != session_id:
                continue

            latest_message = (
                self.db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .first()
            )
            if not latest_message:
                continue

            if query_keyword and query_keyword not in (latest_message.query_raw or ""):
                continue
            if answer_keyword and answer_keyword not in (latest_message.answer or ""):
                continue

            results.append(
                {
                    "session_id": session.session_code,
                    "title": session.title,
                    "source": session.source,
                    "query": latest_message.query_raw,
                    "rewritten_query": latest_message.query_rewritten,
                    "answer": latest_message.answer,
                    "feedback": "pending",
                    "used_memory": latest_message.used_memory,
                    "trace_id": latest_message.trace_id,
                    "updated_at": latest_message.created_at.isoformat() if latest_message.created_at else None,
                }
            )
        return results

    def get_log_detail(self, project_id: int, session_id: str) -> dict | None:
        detail = self.get_session_detail(project_id, session_id)
        if not detail:
            return None
        return detail

    def _get_or_create_session(
        self,
        project_id: int,
        session_code: str | None,
        source: str,
        selected_kb_ids: list[int] | None,
        switches: dict | None,
    ) -> ChatSession:
        session = None
        if session_code:
            session = (
                self.db.query(ChatSession)
                .filter(ChatSession.project_id == project_id, ChatSession.session_code == session_code)
                .first()
            )
        if session:
            return session

        session = ChatSession(
            session_code=session_code or f"sess_{uuid4().hex[:12]}",
            project_id=project_id,
            source=source,
            title="新對話",
            selected_kb_ids=selected_kb_ids or [],
            switches_json=switches or {},
            last_active_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.flush()
        return session

    def _resolve_chat_kb_ids(
        self,
        project_id: int,
        selected_kb_ids: list[int] | None,
        session_kb_ids: list[int] | None,
    ) -> list[int] | None:
        if selected_kb_ids:
            return selected_kb_ids
        if session_kb_ids:
            return session_kb_ids
        default_kb_ids = [
            int(kb_id)
            for (kb_id,) in (
                self.db.query(KnowledgeBase.id)
                .filter(KnowledgeBase.project_id == project_id, KnowledgeBase.is_default.is_(True))
                .order_by(KnowledgeBase.id.asc())
                .all()
            )
        ]
        return default_kb_ids or None

    def _should_use_memory(self, requested: bool, settings: dict[str, Any]) -> bool:
        if not requested:
            return False
        if not settings.get("capability_memory", True):
            return False
        return self._normalize_memory_scope(settings.get("memory_scope")) != "off"

    def _normalize_memory_scope(self, scope: Any) -> str:
        return str(scope) if str(scope) in self.SUPPORTED_MEMORY_SCOPES else "session_only"

    def _get_memory_ttl_days(self, settings: dict[str, Any]) -> int:
        ttl_days = settings.get("memory_ttl_days", 7)
        try:
            return max(int(ttl_days), 1)
        except (TypeError, ValueError):
            return 7

    def _expire_session_memory_if_needed(self, session: ChatSession, settings: dict[str, Any]) -> bool:
        if self._normalize_memory_scope(settings.get("memory_scope")) == "off":
            if session.summary or session.state_json:
                self._reset_session_memory_fields(session)
                return True
            return False
        if not session.last_active_at:
            return False
        ttl_days = self._get_memory_ttl_days(settings)
        if datetime.utcnow() - session.last_active_at < timedelta(days=ttl_days):
            return False
        if not (session.summary or session.state_json):
            return False
        self._reset_session_memory_fields(session)
        return True

    def _reset_session_memory_fields(self, session: ChatSession) -> None:
        session.summary = None
        session.state_json = None

    def _resolve_scene_runtime(
        self,
        project_id: int,
        session: ChatSession,
        query: str,
        memory_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        scene_service = SceneService(self.db)
        assistant_orchestration = self._get_latest_assistant_orchestration(session.id)
        carryover_decision: dict[str, Any] | None = None
        scene_intent: dict[str, Any] | None = None
        route_decision: dict[str, Any] | None = None

        if self._should_try_scene_carryover(query, memory_context, assistant_orchestration):
            carryover_decision = self.scene_carryover_intent_service.classify(
                query=query,
                memory_context=memory_context,
                assistant_orchestration=assistant_orchestration,
                project_context=project_context,
            )
            logger.info(
                "scene_carryover_decision session=%s decision=%s confidence=%.3f fallback=%s route=%s",
                session.session_code,
                carryover_decision.get("decision_type"),
                float(carryover_decision.get("confidence") or 0.0),
                carryover_decision.get("fallback_used"),
                carryover_decision.get("route_key"),
            )
            if self._should_accept_carryover_decision(carryover_decision):
                scene_intent = self._build_scene_intent_from_carryover(carryover_decision)
                route_decision = self._build_route_decision_from_carryover(carryover_decision)
            elif (
                carryover_decision
                and carryover_decision.get("decision_type") == "knowledge_query"
                and not carryover_decision.get("fallback_used")
            ):
                scene_intent = self._build_knowledge_intent_from_carryover(carryover_decision)
            elif carryover_decision and not settings.SCENE_CARRYOVER_FALLBACK_TO_RULES:
                scene_intent = self._build_uncertain_intent_from_carryover(carryover_decision)

        if scene_intent is None:
            scene_intent = scene_service.classify_chat_intent(
                query=query,
                memory_context=memory_context,
                project_context=project_context,
            )
        if route_decision is None and scene_intent.get("should_route_scene"):
            route_decision = {
                "scene_key": scene_intent.get("scene_key"),
                "route_key": scene_intent.get("route_key"),
                "reason": scene_intent.get("reason"),
                "intent_mode": scene_intent.get("intent_mode"),
                "carryover_decision": carryover_decision,
            }

        scene_result = scene_service.maybe_handle_chat(
            project_id=project_id,
            session=session,
            query=query,
            memory_context=memory_context,
            project_context=project_context,
            route_decision=route_decision,
        )
        return {
            "scene_intent": scene_intent,
            "scene_result": scene_result,
            "carryover_decision": carryover_decision,
            "assistant_orchestration": assistant_orchestration,
        }

    def _should_try_scene_carryover(
        self,
        query: str,
        memory_context: dict[str, Any],
        assistant_orchestration: dict[str, Any] | None,
    ) -> bool:
        if not assistant_orchestration:
            return False
        state_scene = ((memory_context.get("state") or {}).get("scene") or {})
        if state_scene and state_scene.get("state") not in {"DONE", "FAILED"}:
            return True
        if not self._is_context_dependent(query):
            return False
        if assistant_orchestration.get("response_mode") == "scene":
            return True
        if assistant_orchestration.get("scene_entry_hint"):
            return True
        return bool(assistant_orchestration.get("suggested_actions"))

    def _should_accept_carryover_decision(self, carryover_decision: dict[str, Any] | None) -> bool:
        if not carryover_decision or carryover_decision.get("fallback_used"):
            return False
        if not carryover_decision.get("should_resume_scene"):
            return False
        if not carryover_decision.get("scene_key"):
            return False
        return float(carryover_decision.get("confidence") or 0.0) >= settings.SCENE_CARRYOVER_MIN_CONFIDENCE

    def _build_scene_intent_from_carryover(self, carryover_decision: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent_mode": "scene_request",
            "should_route_scene": True,
            "scene_key": carryover_decision.get("scene_key"),
            "route_key": None if carryover_decision.get("should_ask_route_clarification") else carryover_decision.get("route_key"),
            "reason": f"llm_carryover:{carryover_decision.get('decision_type')}",
            "carryover_decision": carryover_decision,
        }

    def _build_route_decision_from_carryover(self, carryover_decision: dict[str, Any]) -> dict[str, Any]:
        return {
            "scene_key": carryover_decision.get("scene_key"),
            "route_key": None if carryover_decision.get("should_ask_route_clarification") else carryover_decision.get("route_key"),
            "reason": f"llm_carryover:{carryover_decision.get('decision_type')}",
            "intent_mode": "scene_request",
            "carryover_decision": carryover_decision,
        }

    def _build_knowledge_intent_from_carryover(self, carryover_decision: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent_mode": "knowledge_query",
            "should_route_scene": False,
            "scene_key": carryover_decision.get("scene_key"),
            "route_key": carryover_decision.get("route_key"),
            "reason": f"llm_carryover:{carryover_decision.get('decision_type')}",
            "carryover_decision": carryover_decision,
        }

    def _build_uncertain_intent_from_carryover(self, carryover_decision: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent_mode": "knowledge_query",
            "should_route_scene": False,
            "scene_key": carryover_decision.get("scene_key"),
            "route_key": carryover_decision.get("route_key"),
            "reason": f"llm_carryover:{carryover_decision.get('decision_type') or 'uncertain'}",
            "carryover_decision": carryover_decision,
        }

    def _get_latest_assistant_orchestration(self, session_id: int) -> dict[str, Any] | None:
        latest_message = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .first()
        )
        if not latest_message:
            return None
        orchestration = dict(latest_message.orchestration_json or {})
        if orchestration:
            return orchestration
        return {
            "response_mode": "scene" if str(latest_message.prompt_snapshot or "").startswith("[scene:") else "knowledge",
            "scene_entry_hint": None,
            "suggested_actions": [],
            "answer_excerpt": str(latest_message.answer or "")[:240],
            "query": latest_message.query_raw,
        }

    def _build_memory_context(self, session: ChatSession, use_memory: bool) -> dict[str, Any]:
        recent_turns = self._list_recent_turns(session.id, limit=3) if use_memory else []
        summary = session.summary.strip() if use_memory and session.summary else ""
        state = dict(session.state_json or {}) if use_memory and session.state_json else {}
        used = bool(recent_turns or summary or state)

        snapshot = {
            "recent_turns": [
                {
                    "query": self._redact_sensitive_text(turn["query"]),
                    "answer": self._redact_sensitive_text(turn["answer"]),
                }
                for turn in recent_turns
            ],
            "summary": self._redact_sensitive_text(summary) if summary else "",
            "state": state,
        }
        return {
            "used": used,
            "summary_hit": bool(summary),
            "state_hit": bool(state),
            "recent_turns": recent_turns,
            "summary": summary,
            "state": state,
            "snapshot": snapshot,
        }

    def _build_empty_memory_context(self) -> dict[str, Any]:
        return {
            "used": False,
            "summary_hit": False,
            "state_hit": False,
            "recent_turns": [],
            "summary": "",
            "state": {},
            "snapshot": {"recent_turns": [], "summary": "", "state": {}},
        }

    def _build_answer_memory_context(
        self,
        query: str,
        rewritten_query: str,
        memory_context: dict[str, Any],
    ) -> dict[str, Any]:
        if not memory_context.get("used"):
            return memory_context
        question = rewritten_query or query
        if not self._is_context_dependent(question):
            return self._build_empty_memory_context()

        state = dict(memory_context.get("state") or {})
        if self._is_statistical_or_table_query(question):
            state = {
                key: value
                for key, value in state.items()
                if key in {"knowledge_topic", "stat_scope", "table_context", "updated_at"}
            }
        return {
            **memory_context,
            "state": state,
            "state_hit": bool(state),
            "summary": "" if self._is_statistical_or_table_query(question) else memory_context.get("summary", ""),
            "summary_hit": bool(memory_context.get("summary")) and not self._is_statistical_or_table_query(question),
        }

    def _list_recent_turns(self, session_id: int, limit: int = 3) -> list[dict[str, str]]:
        turns = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
            .all()
        )
        serialized = []
        for turn in reversed(turns):
            serialized.append(
                {
                    "query": turn.query_raw or "",
                    "answer": turn.answer or "",
                }
            )
        return serialized

    def _rewrite_query(self, query: str, memory_context: dict[str, Any]) -> str:
        normalized = " ".join(query.strip().split())
        if not normalized or not memory_context["used"]:
            return normalized
        if not self._is_context_dependent(normalized):
            return normalized

        state = memory_context["state"]
        parts: list[str] = []
        if state.get("knowledge_topic") and self._is_statistical_or_table_query(normalized):
            parts.append(f"延續知識主題《{state['knowledge_topic']}》")
            carried_metric_scope = self._build_carried_stat_metric_scope(normalized, str(state.get("stat_scope") or ""))
            if carried_metric_scope:
                parts.append(f"沿用統計欄位或口徑：{carried_metric_scope}")
        if state.get("intent"):
            parts.append(state["intent"])
        if state.get("region"):
            parts.append(f"辦理地區為{state['region']}")

        identity_type = state.get("user_profile", {}).get("identity_type")
        if identity_type:
            parts.append(identity_type)

        applicant_type = state.get("user_profile", {}).get("applicant_type")
        if applicant_type and applicant_type not in {"本人"}:
            parts.append(f"申請人為{applicant_type}")

        if not parts and memory_context["summary_hit"]:
            parts.append(memory_context["summary"])

        if not parts and memory_context["recent_turns"]:
            latest_turn = memory_context["recent_turns"][-1]
            if latest_turn["query"]:
                parts.append(f"延續上輪問題「{latest_turn['query']}」")

        if not parts:
            return normalized
        return "，".join(parts + [normalized])

    def _build_carried_stat_metric_scope(self, query: str, previous_scope: str) -> str:
        if not previous_scope:
            return ""
        carried = []
        for keyword in ("報考", "出席", "應考", "符合要求", "百分率", "總數"):
            if keyword in previous_scope and keyword not in query:
                carried.append(keyword)
        return "、".join(carried)

    def _is_context_dependent(self, query: str) -> bool:
        compact = query.strip()
        if len(compact) <= 8:
            return True
        return any(re.search(pattern, compact, re.IGNORECASE) for pattern in self.CONTEXT_DEPENDENT_PATTERNS)

    def _is_statistical_or_table_query(self, query: str) -> bool:
        query_text = self._normalize_question_text(query)
        return any(keyword in query_text for keyword in self.KNOWLEDGE_STAT_QUERY_KEYWORDS)

    def _should_force_rule_based_answer(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> bool:
        if self._is_chunk_evidence_mode(ranked_items):
            return False
        if not ranked_items:
            return False
        question = rewritten_query or query
        if not self._is_statistical_or_table_query(question):
            return False
        evidence_text = " ".join(
            " ".join([str(item.get("title") or ""), str(item.get("snippet") or "")])
            for item in ranked_items[:3]
        )
        return "」為" in evidence_text or "人。" in evidence_text or "宗。" in evidence_text

    def _extract_state(
        self,
        query: str,
        previous_state: dict[str, Any],
        ranked_items: list[dict[str, Any]],
        previous_summary: str | None,
    ) -> dict[str, Any]:
        query_text = query.strip()
        top_title = ranked_items[0]["title"] if ranked_items else ""
        if self._is_statistical_or_table_query(query_text):
            state = {
                "knowledge_topic": self._derive_knowledge_topic(query_text, top_title),
                "stat_scope": self._derive_stat_scope(query_text, top_title),
                "updated_at": datetime.utcnow().isoformat(),
            }
            return {key: value for key, value in state.items() if value}

        state = {
            "intent": self._derive_intent(query_text, previous_state.get("intent"), top_title),
            "region": self._detect_region(query_text, previous_state.get("region"), previous_summary or ""),
            "user_profile": {
                "identity_type": self._detect_identity_type(
                    query_text, previous_state.get("user_profile", {}).get("identity_type"), top_title
                ),
                "applicant_type": self._detect_applicant_type(
                    query_text, previous_state.get("user_profile", {}).get("applicant_type")
                ),
            },
            "current_focus": self._detect_focuses(query_text, previous_state.get("current_focus") or []),
        }
        state["user_profile"] = {key: value for key, value in state["user_profile"].items() if value}
        state["missing_slots"] = self._build_missing_slots(state)
        state["updated_at"] = datetime.utcnow().isoformat()
        return {key: value for key, value in state.items() if value or key in {"current_focus", "missing_slots"}}

    def _derive_knowledge_topic(self, query: str, fallback_title: str) -> str | None:
        query_text = query.strip()
        table_match = re.search(r"《([^》]+)》", query_text)
        if table_match:
            return table_match.group(1)
        if fallback_title:
            fallback_match = re.search(r"《([^》]+)》", fallback_title)
            return fallback_match.group(1) if fallback_match else fallback_title[:40]
        return None

    def _derive_stat_scope(self, query: str, fallback_title: str) -> str | None:
        query_source = self._normalize_question_text(query)
        fallback_source = self._normalize_question_text(fallback_title)
        source = query_source
        scopes = []
        if "基本入學要求" in source and "符合要求" not in source:
            scopes.append("符合要求")
        for keyword in ("全體考生", "日校考生", "自修生", "男生", "女生", "報考", "出席", "應考", "符合要求", "百分率", "總數"):
            if keyword in source:
                scopes.append(keyword)
        if not scopes:
            for keyword in ("全體考生", "日校考生", "自修生", "男生", "女生", "報考", "出席", "應考", "符合要求", "百分率", "總數"):
                if keyword in fallback_source:
                    scopes.append(keyword)
        return "、".join(dict.fromkeys(scopes)) if scopes else None

    def _derive_intent(self, query: str, previous_intent: str | None, fallback_title: str) -> str | None:
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(keyword in query for keyword in keywords):
                return intent
        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(keyword in fallback_title for keyword in keywords):
                return intent
        if previous_intent:
            return previous_intent
        return f"諮詢《{fallback_title}》相關事項" if fallback_title else None

    def _detect_region(self, query: str, previous_region: str | None, previous_summary: str) -> str | None:
        source = f"{query} {previous_summary}"
        for region, keywords in self.REGION_KEYWORDS.items():
            if any(keyword.lower() in source.lower() for keyword in keywords):
                return region
        return previous_region

    def _detect_identity_type(self, query: str, previous_identity_type: str | None, fallback_title: str) -> str | None:
        source = f"{query} {fallback_title}"
        for identity_type, keywords in self.IDENTITY_KEYWORDS.items():
            if any(keyword in source for keyword in keywords):
                return identity_type
        return previous_identity_type

    def _detect_applicant_type(self, query: str, previous_applicant_type: str | None) -> str | None:
        for applicant_type, keywords in self.APPLICANT_KEYWORDS.items():
            if any(keyword in query for keyword in keywords):
                return applicant_type
        return previous_applicant_type or "本人"

    def _detect_focuses(self, query: str, previous_focuses: list[str]) -> list[str]:
        focuses = list(previous_focuses)
        for focus, keywords in self.FOCUS_KEYWORDS.items():
            if any(keyword in query for keyword in keywords) and focus not in focuses:
                focuses.append(focus)
        if not focuses:
            focuses = ["流程"]
        return focuses[:4]

    def _build_missing_slots(self, state: dict[str, Any]) -> list[str]:
        missing_slots: list[str] = []
        if state.get("intent") and not state.get("region"):
            if any(focus in self.REGION_DEPENDENT_FOCUS for focus in state.get("current_focus", [])):
                missing_slots.append("辦理地區")
        if state.get("intent") and not state.get("user_profile", {}).get("identity_type"):
            missing_slots.append("辦理類型")
        return missing_slots

    def _build_session_summary(
        self,
        previous_summary: str | None,
        state: dict[str, Any],
        latest_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> str:
        segments = []
        if state.get("knowledge_topic"):
            segments.append(f"最近知識查詢主題為《{state['knowledge_topic']}》")
        if state.get("stat_scope"):
            segments.append(f"統計口徑包含{state['stat_scope']}")
        if state.get("intent"):
            segments.append(f"使用者當前諮詢事項為{state['intent']}")
        if state.get("region"):
            segments.append(f"地區為{state['region']}")
        identity_type = state.get("user_profile", {}).get("identity_type")
        if identity_type:
            segments.append(f"辦理類型為{identity_type}")
        applicant_type = state.get("user_profile", {}).get("applicant_type")
        if applicant_type and applicant_type != "本人":
            segments.append(f"申請人為{applicant_type}")
        if state.get("current_focus"):
            segments.append(f"當前關注{ '、'.join(state['current_focus']) }")
        if ranked_items:
            segments.append(f"最近命中的知識主題為《{ranked_items[0]['title']}》")
        elif previous_summary:
            segments.append("當前輪未命中明確知識，延續既有會話主線")
        segments.append(f"最近一輪問題是「{self._redact_sensitive_text(latest_query)}」")
        return "；".join(segments)

    def _build_session_title(self, current_title: str | None, state: dict[str, Any], query: str) -> str:
        if current_title and current_title != "新對話":
            return current_title
        if state.get("knowledge_topic"):
            return str(state["knowledge_topic"])[:24]
        if state.get("intent"):
            return state["intent"][:24]
        return query[:24]

    def _detect_safety_flags(self, query: str) -> dict[str, Any]:
        matched_types: list[str] = []
        if re.search(r"\b1\d{10}\b", query):
            matched_types.append("phone")
        if re.search(r"\b\d{17}[\dXx]\b", query):
            matched_types.append("id_card")
        return {
            "contains_sensitive_input": bool(matched_types),
            "matched_types": matched_types,
            "redacted_query": self._redact_sensitive_text(query),
        }

    def _redact_sensitive_text(self, text: str) -> str:
        redacted = re.sub(r"\b1(\d{2})\d{4}(\d{4})\b", r"1\1****\2", text)
        redacted = re.sub(r"\b(\d{6})\d{8,11}([\dXx]{4})\b", r"\1********\2", redacted)
        return redacted

    def _rank_knowledge_items(self, query: str, items: list[KnowledgeItem]) -> list[dict]:
        scored_items: list[dict] = []
        query_tokens = self._tokenize_text(query)
        if not query_tokens:
            query_tokens = {query.lower()}

        for item in items:
            haystack = " ".join(
                [
                    item.title or "",
                    item.content or "",
                    " ".join(item.keywords_json or []),
                ]
            ).lower()
            overlap = sum(1 for token in query_tokens if token in haystack)
            if overlap == 0 and query.lower() not in haystack:
                continue
            score = round(min(overlap / max(len(query_tokens), 1) + 0.35, 0.99), 4)
            scored_items.append(
                {
                    "knowledge_id": item.id,
                    "kb_id": item.kb_id,
                    "title": item.title,
                    "document_name": item.document_name,
                    "score": score,
                    "snippet": item.content[:180],
                }
            )

        scored_items.sort(key=lambda item: item["score"], reverse=True)
        return scored_items[:3]

    def _tokenize_text(self, text: str) -> set[str]:
        normalized = text.lower().strip()
        if not normalized:
            return set()

        tokens = {token for token in re.split(r"[\s,，。！？；：、/()（）]+", normalized) if token}
        for token in list(tokens):
            if len(token) <= 1:
                continue
            if re.search(r"[\u4e00-\u9fff]", token):
                tokens.update(token[index : index + 2] for index in range(len(token) - 1))

        return tokens

    def _build_answer(
        self,
        query: str,
        rewritten_query: str,
        project_name: str,
        ranked_items: list[dict[str, Any]],
        memory_context: dict[str, Any],
        state: dict[str, Any],
    ) -> str:
        if not ranked_items:
            clarification = ""
            if state.get("missing_slots"):
                clarification = f"目前仍需補充{'、'.join(state['missing_slots'])}後，再進一步判斷。"
            no_result_answer = (
                f"目前 {self._format_reply_text(project_name)} 知識庫中，暫未檢索到與相關問題直接匹配的已生效知識。"
                f"{clarification or '建議補充更具體的事項名稱、地區或辦理類型後再試。'}"
            )
            return self._format_reply_text(no_result_answer)

        top = self._select_primary_answer_item(query, rewritten_query, ranked_items)
        context_line = ""
        if (
            memory_context["used"]
            and state.get("intent")
            and not self._is_statistical_or_table_query(rewritten_query or query)
        ):
            context_line = f"已結合當前會話上下文，系統理解您正在諮詢「{self._format_reply_text(str(state['intent']))}」。"
        clarification = ""
        if state.get("missing_slots") and self._should_show_missing_slots_hint(query, rewritten_query):
            clarification = f"如需更精確判斷，建議補充{'、'.join(state['missing_slots'])}。"

        answer_parts = [
            part
            for part in [
                context_line,
                self._build_direct_knowledge_answer(query, rewritten_query, top),
                self._build_knowledge_reference_line(top),
                self._build_metric_scope_note(query, rewritten_query),
                clarification,
            ]
            if part
        ]
        return self._format_reply_text("\n\n".join(answer_parts))

    def _select_primary_answer_item(
        self,
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not ranked_items:
            return {}

        query_text = self._normalize_question_text(rewritten_query or query)
        best_item = ranked_items[0]
        best_score = float("-inf")
        for index, item in enumerate(ranked_items):
            item_text = self._normalize_question_text(
                " ".join(
                    [
                        str(item.get("title") or ""),
                        str(item.get("snippet") or ""),
                    ]
                )
            )
            score = float(item.get("score") or 0.0) * 100
            score += self._score_answer_item_alignment(query_text, item_text)
            score -= index * 0.01
            if score > best_score:
                best_score = score
                best_item = item
        return best_item

    def _score_answer_item_alignment(self, query_text: str, item_text: str) -> float:
        score = 0.0

        facet_groups = [
            ["全體考生", "日校考生", "自修生", "學校考生", "所有學校考生"],
            ["男生", "女生"],
        ]
        for group in facet_groups:
            query_facet = next((facet for facet in group if facet in query_text), None)
            if not query_facet:
                continue
            if query_facet in item_text:
                score += 8
            for facet in group:
                if facet != query_facet and facet in item_text:
                    score -= 6

        keyword_weights = {
            "報考": 4,
            "出席": 4,
            "應考": 4,
            "符合要求": 5,
            "基本入學要求": 5,
            "百分率": 4,
            "宗數": 4,
            "總數": 3,
            "違反手提電話規則": 6,
        }
        for keyword, weight in keyword_weights.items():
            if keyword in query_text and keyword in item_text:
                score += weight

        if "報考" in query_text and "出席總人數" in item_text:
            score -= 3
        if ("出席" in query_text or "應考" in query_text) and "報考" in item_text:
            score -= 3

        return score

    def _build_direct_knowledge_answer(
        self,
        query: str,
        rewritten_query: str,
        top: dict[str, Any],
    ) -> str:
        query_text = self._normalize_question_text(rewritten_query or query)
        snippet_text = str(top.get("snippet") or "")
        if self._is_table_data_request(query_text):
            table_answer = self._build_structured_table_row_answer(query_text, snippet_text)
            if table_answer:
                return table_answer

        snippet = self._extract_fact_value_from_snippet(snippet_text, query_text)
        if not snippet:
            return "現有資料顯示，暫時只能確認與此問題相關，但缺少可直接引用的答案內容。"

        subject = self._statement_subject_from_query(query_text)
        if subject.startswith("延續知識主題") or subject.startswith("沿用統計欄位"):
            subject = ""
        if not subject:
            subject = self._statement_subject_from_structured_evidence(str(top.get("snippet") or ""), query_text)
        if subject and self._looks_like_short_fact(snippet):
            return f"{subject}為 {snippet}"
        return snippet

    def _is_table_data_request(self, query_text: str) -> bool:
        return any(
            keyword in query_text
            for keyword in (
                "表格數據是什麼",
                "表格数据是什么",
                "表格數據",
                "表格数据",
                "表數據",
                "表数据",
                "的表格",
                "表裏是什麼",
                "表里是什么",
                "表中是什麼",
                "表中是什么",
            )
        )

    def _build_structured_table_row_answer(self, query_text: str, snippet: str) -> str:
        fields = self._extract_structured_fields(snippet)
        if not fields:
            return ""

        row_label = self._structured_field_value(fields, "考生類別")
        if not row_label:
            row_match = re.search(r"行項目為「([^」]+)」", snippet)
            row_label = row_match.group(1).strip() if row_match else ""

        rows = []
        for label, raw_value in fields:
            if label == "考生類別":
                continue
            rows.append(
                f"- {self._format_structured_label(label)}："
                f"{self._normalize_structured_value(raw_value, label, query_text).rstrip('。')}"
            )

        if not rows:
            return ""
        intro = f"該表「{row_label}」的主要數據如下：" if row_label else "該表的主要數據如下："
        return "\n".join([intro, *rows])

    def _extract_structured_fields(self, snippet: str) -> list[tuple[str, str]]:
        return [
            (label.strip(), value.strip())
            for label, value in re.findall(r"「([^」]+)」為\s*([^。「」]+(?:\([^)]*\))?%?)", snippet)
        ]

    def _structured_field_value(self, fields: list[tuple[str, str]], expected_label: str) -> str:
        for label, value in fields:
            if label == expected_label:
                return value
        return ""

    def _format_structured_label(self, label: str) -> str:
        normalized = label.strip()
        if " " in normalized:
            base, suffix = normalized.split(" ", 1)
            return f"{base}（{suffix.strip()}）"
        return normalized

    def _build_knowledge_reference_line(self, top: dict[str, Any]) -> str:
        references: list[str] = []
        document_name = str(top.get("document_name") or "").strip()
        if document_name:
            references.append(document_name)

        title = str(top.get("title") or "").strip()
        table_match = re.match(r"^(《[^》]+》)", title)
        if table_match:
            references.append(table_match.group(1))

        source_url = str(top.get("source_url") or "").strip()
        if not references and not source_url:
            return ""
        lines: list[str] = []
        if references:
            label = "Source" if self._is_english_reply_locale() else "資料來源"
            lines.append(f"{label}：{'，'.join(dict.fromkeys(references))}。")
        if source_url:
            link_label = "Official link" if self._is_english_reply_locale() else "官方資料連結"
            lines.append(f"{link_label}：{source_url}")
        return "\n".join(lines)

    def _build_metric_scope_note(self, query: str, rewritten_query: str) -> str:
        query_text = self._normalize_question_text(rewritten_query or query)
        if "報考" in query_text:
            return "以上數字指報考人數口徑，不等同出席／應考人數。"
        if "出席" in query_text or "應考" in query_text:
            return "以上數字指出席／應考口徑，與報考人數屬不同統計口徑。"
        return ""

    def _normalize_question_text(self, text: str) -> str:
        return re.sub(r"\s+", "", text or "").strip()

    def _statement_subject_from_query(self, query_text: str) -> str:
        normalized = query_text.strip("？?。！!；;：:")
        normalized = re.sub(r"^(請問|想問|想查詢|我想知道|可否告知|可以告訴我)", "", normalized)
        suffixes = [
            "總共有多少宗",
            "共有多少宗",
            "有多少宗",
            "是多少宗",
            "總共有多少人",
            "共有多少人",
            "有多少人",
            "是多少人",
            "總共有多少",
            "共有多少",
            "有多少",
            "為多少",
            "是多少",
        ]
        for suffix in suffixes:
            if normalized.endswith(suffix):
                return normalized[: -len(suffix)].strip()
        return normalized if len(normalized) <= 48 else ""

    def _normalize_answer_snippet(self, snippet: str) -> str:
        normalized = re.sub(r"\s+", " ", snippet or "").strip()
        normalized = normalized.replace(" 。", "。").replace(" ，", "，")
        if normalized and normalized[-1] not in "。！？":
            normalized += "。"
        return normalized

    def _extract_fact_value_from_snippet(self, snippet: str, query_text: str) -> str:
        normalized = self._normalize_answer_snippet(snippet)
        if not normalized:
            return ""

        structured_value = self._extract_structured_value_from_snippet(normalized, query_text)
        if structured_value:
            return structured_value

        core = normalized.rstrip("。！？")
        field_match = re.match(r"^「(?P<label>[^」]+)」為\s*(?P<value>.+)$", core)
        if not field_match:
            return normalized

        label = field_match.group("label").strip()
        value = field_match.group("value").strip()
        if re.fullmatch(r"[\d,]+(?:\.\d+)?", value):
            if "宗" in query_text or label == "宗數":
                value = f"{value}宗"
            elif "人" in query_text or "人數" in label:
                value = f"{value}人"
        return self._normalize_answer_snippet(value)

    def _extract_structured_value_from_snippet(self, snippet: str, query_text: str) -> str:
        selected = self._select_structured_field(snippet, query_text)
        return selected[1] if selected else ""

    def _select_structured_field(self, snippet: str, query_text: str) -> tuple[str, str] | None:
        field_matches = self._extract_structured_fields(snippet)
        if not field_matches:
            return None
        best_value = ""
        best_label = ""
        best_score = float("-inf")
        for label, raw_value in field_matches:
            value = raw_value.strip()
            score = self._score_structured_field(query_text, label)
            if score > best_score:
                best_score = score
                best_label = label
                best_value = self._normalize_structured_value(value, label, query_text)

        return (best_label, best_value) if best_score > 0 else None

    def _statement_subject_from_structured_evidence(self, snippet: str, query_text: str) -> str:
        selected = self._select_structured_field(snippet, query_text)
        if not selected:
            return ""
        label, _value = selected
        row_label = self._structured_field_value(self._extract_structured_fields(snippet), "考生類別")
        if not row_label:
            row_match = re.search(r"行項目為「([^」]+)」", snippet)
            row_label = row_match.group(1).strip() if row_match else ""
        formatted_label = self._format_structured_label(label)
        return f"{row_label}{formatted_label}" if row_label else formatted_label

    def _score_structured_field(self, query_text: str, label: str) -> float:
        score = 0.0
        if "符合" in query_text and "符合要求" in label:
            score += 7
        if "基本入學要求" in query_text and "符合要求" in label:
            score += 5
        if "總數" in query_text and "總數" in label:
            score += 4
        if "百分率" in query_text and "百分率" in label:
            score += 5
        if ("出席" in query_text or "應考" in query_text) and "出席" in label:
            score += 5
        if "報考" in query_text and "報考" in label:
            score += 5
        if "宗" in query_text and "宗數" in label:
            score += 5
        if "男生" in query_text and "男生" in label:
            score += 4
        if "女生" in query_text and "女生" in label:
            score += 4

        if "總數" in query_text and "出席總人數" in label and "出席" not in query_text and "應考" not in query_text:
            score -= 5
        if "報考" in query_text and "出席" in label:
            score -= 5
        if ("出席" in query_text or "應考" in query_text) and "符合要求" in label:
            score -= 2
        if label == "考生類別":
            score -= 10

        return score

    def _normalize_structured_value(self, value: str, label: str, query_text: str) -> str:
        normalized_value = value.strip()
        if re.fullmatch(r"[\d,]+(?:\.\d+)?", normalized_value):
            if "宗" in query_text or label == "宗數":
                normalized_value = f"{normalized_value}宗"
            elif "百分率" in label or "%" in normalized_value or "百分率" in query_text:
                normalized_value = f"{normalized_value}%"
            else:
                normalized_value = f"{normalized_value}人"
        return self._normalize_answer_snippet(normalized_value)

    def _should_show_missing_slots_hint(self, query: str, rewritten_query: str) -> bool:
        query_text = self._normalize_question_text(rewritten_query or query)
        workflow_keywords = (
            "辦理",
            "申請",
            "流程",
            "步驟",
            "材料",
            "文件",
            "地址",
            "變更",
            "更改",
            "提交",
            "寄送",
            "郵寄",
            "下載",
            "上載",
            "確認",
        )
        return any(keyword in query_text for keyword in workflow_keywords)

    def _looks_like_short_fact(self, snippet: str) -> bool:
        core = snippet.strip().rstrip("。！？")
        if len(core) > 24:
            return False
        return bool(re.search(r"\d", core)) or "％" in core or "%" in core

    def _resolve_reply_locale(self, query: str, project_context: dict[str, Any]) -> str:
        del project_context
        normalized = " ".join((query or "").strip().split()).lower()
        if any(pattern in normalized for pattern in self.ENGLISH_REPLY_PATTERNS):
            return "en"
        alpha_count = len(re.findall(r"[A-Za-z]", normalized))
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", normalized))
        if alpha_count >= 12 and alpha_count > cjk_count * 3:
            return "en"
        return self.REPLY_LOCALE

    def _is_english_reply_locale(self) -> bool:
        return self.reply_locale.lower().startswith("en")

    def _normalize_scope_aliases(self, text: str, project_context: dict[str, Any]) -> str:
        if not self._is_authorized_policy_project_context(project_context):
            return text
        normalized = text or ""
        for pattern, replacement in self.AUTHORIZED_ALIAS_REPLACEMENTS:
            normalized = pattern.sub(replacement, normalized)
        return normalized

    def _is_authorized_policy_project_context(self, project_context: dict[str, Any]) -> bool:
        project = project_context.get("project") or {}
        settings_payload = project_context.get("settings") or {}
        source = " ".join(
            [
                str(project.get("company_name") or ""),
                str(settings_payload.get("opening_text") or ""),
                str(settings_payload.get("prompt_template") or ""),
                " ".join(str(item) for item in (settings_payload.get("recommended_questions") or [])),
            ]
        ).lower()
        return any(marker.lower() in source for marker in self.AUTHORIZED_SCOPE_MARKERS)

    def _evaluate_policy_decision(
        self,
        *,
        project_context: dict[str, Any],
        query: str,
        rewritten_query: str,
        ranked_items: list[dict[str, Any]],
        retrieval_usable: bool,
    ) -> dict[str, Any] | None:
        if not self._is_authorized_policy_project_context(project_context):
            return None

        normalized_query = self._normalize_question_text(self._normalize_scope_aliases(f"{query} {rewritten_query}", project_context))
        hard_reason = self._match_authorized_hard_refusal(normalized_query)
        if hard_reason:
            return {
                "message": self._build_policy_refusal_message(hard_reason),
                "policy_basis": self._build_policy_basis(reason=hard_reason, retrieval_usable=False),
            }

        if not ranked_items or not self._is_authorized_retrieval_confident(ranked_items, retrieval_usable):
            return {
                "message": self._build_policy_refusal_message("insufficient_evidence"),
                "policy_basis": self._build_policy_basis(reason="insufficient_evidence", retrieval_usable=False),
            }
        return None

    def _match_authorized_hard_refusal(self, normalized_query: str) -> str | None:
        if not settings.ENABLE_HARD_SCOPE_REFUSAL:
            return None
        for reason, patterns in self.AUTHORIZED_HARD_REFUSAL_PATTERNS.items():
            if any(re.search(pattern, normalized_query, re.IGNORECASE) for pattern in patterns):
                return reason
        return None

    def _is_authorized_retrieval_confident(
        self,
        ranked_items: list[dict[str, Any]],
        retrieval_usable: bool,
    ) -> bool:
        if not ranked_items or not retrieval_usable:
            return False
        top_score = float(ranked_items[0].get("score") or 0.0)
        if top_score < settings.RETRIEVAL_REFUSAL_MIN_SCORE:
            return False
        if len(ranked_items) == 1:
            return True
        second_score = float(ranked_items[1].get("score") or 0.0)
        if top_score >= settings.RETRIEVAL_REFUSAL_MIN_SCORE + 0.18:
            return True
        return top_score - second_score >= settings.RETRIEVAL_REFUSAL_MIN_MARGIN

    def _build_policy_basis(self, *, reason: str, retrieval_usable: bool) -> dict[str, Any]:
        return {
            "source_mode": "policy_refusal",
            "source_count": 0,
            "retrieval_usable": retrieval_usable,
            "decision": "refuse",
            "decision_reason": reason,
        }

    def _build_policy_refusal_message(self, reason: str) -> str:
        official_contact = settings.OFFICIAL_CONTACT_EMAIL or "the official channel"
        if self._is_english_reply_locale():
            if reason == "insufficient_evidence":
                return (
                    "The currently available materials are not sufficient for me to confirm this accurately.\n\n"
                    f"Please refer to the official source or contact the official channel for confirmation: {official_contact}"
                )
            if reason == "out_of_scope":
                return (
                    "This question is outside the scope that I can confirm from the currently authorized materials, "
                    "so I should not make assumptions.\n\n"
                    f"Please refer to the official source or contact: {official_contact}"
                )
            return (
                "This question involves rumours, predictions, unpublished information, or case-by-case judgement that I cannot confirm "
                "from the current authorized materials.\n\n"
                f"Please refer to the official source or contact: {official_contact}"
            )

        if reason == "insufficient_evidence":
            return (
                "現有資料不足以確認。\n\n"
                f"建議您參考官方資料，或聯絡官方渠道作進一步查詢：{official_contact}"
            )
        if reason == "out_of_scope":
            return (
                "這個問題不在我目前可根據現有授權資料確認的範圍內，因此我不能作出推測或判斷。\n\n"
                f"建議您參考官方資料，或聯絡官方渠道作進一步查詢：{official_contact}"
            )
        return (
            "這類問題涉及個別情況、傳聞、預測或未公開資訊，我目前不能根據現有資料直接確認。\n\n"
            f"建議以官方公布為準；如需正式確認，可聯絡：{official_contact}"
        )

    def _format_reply_text(self, text: str) -> str:
        return format_reply_text(text, self.reply_locale)

    def _serialize_turn(self, turn: ChatMessage) -> dict[str, Any]:
        return {
            "id": turn.id,
            "query": turn.query_raw,
            "rewritten_query": turn.query_rewritten,
            "answer": turn.answer,
            "sources": turn.source_docs or [],
            "used_memory": turn.used_memory,
            "memory_snapshot": turn.memory_snapshot_json,
            "safety_flags": turn.safety_flags_json,
            "orchestration": turn.orchestration_json,
            "prompt_snapshot": turn.prompt_snapshot,
            "model_name": turn.model_name,
            "trace_id": turn.trace_id,
            "created_at": turn.created_at.isoformat() if turn.created_at else None,
        }

    def _finalize_scene_response(
        self,
        project_id: int,
        session: ChatSession,
        query: str,
        memory_context: dict[str, Any],
        source: str,
        selected_kb_ids: list[int] | None,
        switches: dict | None,
        scene_result: dict[str, Any],
        hybrid_context: dict[str, Any] | None = None,
        trace_id: str | None = None,
        carryover_decision: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scene_payload = scene_result["scene"]
        hybrid_context = hybrid_context or {}
        planner = ((scene_result.get("next_actions") or {}).get("planner") or {})
        final_answer = self._compose_scene_answer(scene_result["message"], hybrid_context, planner)
        next_state_json = dict(session.state_json or {})
        next_state_json["scene"] = {
            "scene_key": scene_payload["scene_key"],
            "case_id": scene_payload["case_id"],
            "route_key": scene_payload.get("route_key"),
            "state": scene_payload["state"],
            "missing_fields": scene_payload.get("missing_fields", []),
            "updated_at": datetime.utcnow().isoformat(),
        }

        session.title = scene_payload.get("summary")[:24] if scene_payload.get("summary") else session.title
        session.selected_kb_ids = self._resolve_chat_kb_ids(project_id, selected_kb_ids, session.selected_kb_ids) or []
        session.switches_json = switches or session.switches_json or {}
        session.summary = scene_payload.get("summary")
        session.state_json = next_state_json
        session.last_active_at = datetime.utcnow()
        scene_suggested_actions = self._build_scene_suggested_actions(scene_payload)
        orchestration_snapshot = self._build_scene_orchestration_snapshot(
            scene_payload=scene_payload,
            scene_result=scene_result,
            suggested_actions=scene_suggested_actions,
            carryover_decision=carryover_decision,
            answer=final_answer,
        )

        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            query_raw=query,
            query_rewritten=query,
            answer=final_answer,
            source_docs=hybrid_context.get("sources", []),
            used_memory=memory_context["used"],
            memory_snapshot_json=memory_context["snapshot"] if memory_context["used"] else None,
            safety_flags_json=self._detect_safety_flags(query),
            orchestration_json=orchestration_snapshot,
            prompt_snapshot=f"[scene:{scene_payload['scene_key']}]",
            model_name="scene-orchestrator-v1",
            trace_id=trace_id or uuid4().hex[:16],
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        return {
            "project_id": project_id,
            "session_id": session.session_code,
            "query": query,
            "query_raw": query,
            "rewritten_query": query,
            "answer": final_answer,
            "suggested_actions": scene_suggested_actions,
            "sources": hybrid_context.get("sources", []),
            "use_memory": memory_context["used"],
            "memory": {
                "used": memory_context["used"],
                "summary_hit": memory_context["summary_hit"],
                "state_hit": memory_context["state_hit"],
                "preference_hit": False,
            },
            "policy_basis": {
                "source_mode": "hybrid_scene" if hybrid_context.get("retrieval_usable") else "scene",
                "source_count": len(hybrid_context.get("sources", [])) or len(scene_payload.get("citations", [])),
                "retrieval_usable": bool(hybrid_context.get("retrieval_usable")),
            },
            "intent_mode": scene_result.get("intent_mode", "scene_request"),
            "classification_reason": scene_result.get("classification_reason"),
            "scene_entry_hint": None,
            "hybrid_context": hybrid_context or None,
            "prompt_snapshot": message.prompt_snapshot,
            "trace_id": message.trace_id,
            "response_mode": "scene",
            "scene": scene_payload,
            "field_status": scene_result.get("field_status"),
            "next_actions": scene_result.get("next_actions"),
            "orchestration": orchestration_snapshot,
            "carryover_decision": carryover_decision,
        }

    def _build_scene_suggested_actions(self, scene_payload: dict[str, Any]) -> list[dict[str, str]]:
        if not scene_payload:
            return []
        summary_panel = ((scene_payload.get("panels") or {}).get("summary") or {})
        pending_confirmation_fields = summary_panel.get("pending_confirmation_fields") or []
        if pending_confirmation_fields:
            field = str(pending_confirmation_fields[0])
            return [
                {
                    "key": f"scene-confirm-{field}",
                    "label": "是，正確",
                    "prompt": "是",
                },
                {
                    "key": f"scene-rewrite-{field}",
                    "label": "不對，重填",
                    "prompt": "不是",
                },
            ]
        if scene_payload.get("route_key") != "ir1249":
            return []
        if "applicant_type" not in (scene_payload.get("missing_fields") or []):
            return []
        options = (summary_panel.get("field_options") or {}).get("applicant_type") or []
        actions: list[dict[str, str]] = []
        for option in options:
            value = str(option.get("value") or "").strip()
            label = str(option.get("label") or value).strip()
            if not value or not label:
                continue
            actions.append(
                {
                    "key": f"scene-applicant-type-{value}",
                    "label": label,
                    "prompt": value,
                }
            )
        return actions

    def _build_hybrid_scene_context(
        self,
        project_id: int,
        project_name: str,
        query: str,
        memory_context: dict[str, Any],
        session: ChatSession,
        selected_kb_ids: list[int] | None,
        switches: dict[str, Any] | None,
        scene_result: dict[str, Any],
    ) -> dict[str, Any]:
        if scene_result.get("intent_mode") != "hybrid_request":
            return {}

        rewritten_query = self.deepseek_service.rewrite_query(
            self._rewrite_query(query, memory_context),
            memory_context["recent_turns"],
        )
        effective_kb_ids = self._resolve_chat_kb_ids(project_id, selected_kb_ids, session.selected_kb_ids)
        ranked_items = self.retrieval_service.retrieve(
            project_id=project_id,
            query=rewritten_query,
            selected_kb_ids=effective_kb_ids,
            rewritten_query=rewritten_query,
            scene_state=memory_context.get("state") or {},
        )
        retrieval_usable = self._should_accept_retrieval(rewritten_query, ranked_items, switches)
        support_text = self._build_hybrid_support_text(
            project_name=project_name,
            query=query,
            rewritten_query=rewritten_query,
            memory_context=memory_context,
            ranked_items=ranked_items,
            retrieval_usable=retrieval_usable,
        )
        return {
            "rewritten_query": rewritten_query,
            "retrieval_usable": retrieval_usable,
            "sources": ranked_items if retrieval_usable else [],
            "support_text": support_text,
        }

    def _build_hybrid_support_text(
        self,
        project_name: str,
        query: str,
        rewritten_query: str,
        memory_context: dict[str, Any],
        ranked_items: list[dict[str, Any]],
        retrieval_usable: bool,
    ) -> str | None:
        if not retrieval_usable or not ranked_items:
            return None

        fallback = self._build_hybrid_support_fallback(ranked_items)
        if not self.deepseek_service.is_enabled():
            return fallback

        system_prompt = (
            f"你是 {self._format_reply_text(project_name)} 的辦事知識補充助手。"
            "你正在為一段已進入辦理流程的回覆提供補充說明。"
            "請只回答本輪知識疑問，保持 2 到 4 句，語氣簡潔、準確；預設使用繁體中文，若使用者明確要求英文則改用英文。"
        )
        runtime_prompt = (
            "你現在不需要重述整個辦理流程，只需要補充政策依據、材料要求或表格說明。\n"
            f"使用者問題：{rewritten_query or query}\n\n"
            f"參考資料：\n{self._render_reference_block(ranked_items[:3])}\n\n"
            f"歷史上下文：\n{self._render_history_block(memory_context) or '暫無'}"
        )
        try:
            answer, _ = self.deepseek_service.answer(system_prompt, runtime_prompt, self.reply_locale)
            return answer or fallback
        except Exception:  # noqa: BLE001
            return fallback

    def _build_hybrid_support_fallback(self, ranked_items: list[dict[str, Any]]) -> str | None:
        if not ranked_items:
            return None
        top = ranked_items[0]
        parts = [
            self._build_direct_knowledge_answer("", "", top),
            self._build_knowledge_reference_line(top),
        ]
        return self._format_reply_text("\n\n".join(part for part in parts if part))

    def _compose_scene_answer(
        self,
        base_message: str,
        hybrid_context: dict[str, Any],
        planner: dict[str, Any] | None = None,
    ) -> str:
        planner_text = self._build_scene_planner_text(planner or {})
        support_text = str((hybrid_context or {}).get("support_text") or "").strip()
        parts = [base_message.rstrip()]
        if planner_text and planner_text not in base_message:
            parts.append(f"### 當前策略\n{planner_text}")
        if support_text and support_text not in base_message:
            parts.append(f"### 補充說明\n{support_text}")
        return "\n\n".join(part for part in parts if part)

    def _build_scene_planner_text(self, planner: dict[str, Any]) -> str | None:
        if not planner:
            return None
        communication = dict(planner.get("communication") or {})
        status = dict(planner.get("status") or {})
        lines: list[str] = []

        headline = str(communication.get("status_headline") or "").strip()
        if headline:
            lines.append(f"- {headline}")

        detail = str(communication.get("status_detail") or "").strip()
        if detail:
            lines.append(f"- {detail}")

        missing_labels = [str(item).strip() for item in (status.get("missing_labels") or []) if str(item).strip()]
        if missing_labels:
            preview = "、".join(missing_labels[:3])
            if len(missing_labels) > 3:
                preview += " 等"
            lines.append(f"- 目前仍缺：{preview}")

        address_review_note = str(communication.get("address_review_note") or "").strip()
        if address_review_note:
            lines.append(f"- {address_review_note}")

        if not lines:
            return None
        return "\n".join(lines)

    def _build_scene_entry_hint(self, scene_intent: dict[str, Any]) -> dict[str, Any] | None:
        intent_mode = scene_intent.get("intent_mode")
        if intent_mode not in {"scene_request", "hybrid_request"}:
            return None
        if scene_intent.get("should_route_scene"):
            return None

        route_key = scene_intent.get("route_key")
        if route_key == "ir1249":
            return {
                "scene_key": "hk_tax_address_change",
                "route_key": "ir1249",
                "prompt": "我想改收稅單地址，請幫我開始填寫 IR1249。",
            }
        if route_key == "irc3111a":
            return {
                "scene_key": "hk_tax_address_change",
                "route_key": "irc3111a",
                "prompt": "公司搬辦公室了，請幫我開始填寫 IRC3111A。",
            }
        return {
            "scene_key": "hk_tax_address_change",
            "route_key": None,
            "prompt": "我想辦理香港稅務地址變更，請幫我判斷應該使用 IR1249 還是 IRC3111A。",
        }

    def _build_knowledge_orchestration_snapshot(
        self,
        scene_intent: dict[str, Any],
        scene_entry_hint: dict[str, Any] | None,
        suggested_actions: list[dict[str, str]],
        carryover_decision: dict[str, Any] | None,
        answer: str,
    ) -> dict[str, Any]:
        return {
            "response_mode": "knowledge",
            "intent_mode": scene_intent.get("intent_mode"),
            "should_route_scene": bool(scene_intent.get("should_route_scene")),
            "reason": scene_intent.get("reason"),
            "scene_entry_hint": scene_entry_hint,
            "suggested_actions": suggested_actions,
            "carryover_decision": carryover_decision,
            "answer_excerpt": answer[:240],
        }

    def _build_scene_orchestration_snapshot(
        self,
        scene_payload: dict[str, Any],
        scene_result: dict[str, Any],
        suggested_actions: list[dict[str, str]],
        carryover_decision: dict[str, Any] | None,
        answer: str,
    ) -> dict[str, Any]:
        return {
            "response_mode": "scene",
            "intent_mode": scene_result.get("intent_mode"),
            "should_route_scene": True,
            "reason": scene_result.get("classification_reason"),
            "scene_entry_hint": None,
            "suggested_actions": suggested_actions,
            "carryover_decision": carryover_decision,
            "scene": {
                "scene_key": scene_payload.get("scene_key"),
                "case_id": scene_payload.get("case_id"),
                "route_key": scene_payload.get("route_key"),
                "state": scene_payload.get("state"),
                "missing_fields": scene_payload.get("missing_fields") or [],
            },
            "answer_excerpt": answer[:240],
        }

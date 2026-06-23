from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.text_locale import to_traditional_data
from app.models.knowledge import KnowledgeBase
from app.models.project import Project, ProjectMember, ProjectPersona, ProjectSetting
from app.models.user import User


class ProjectService:
    SUPPORTED_MEMORY_SCOPES = {"off", "session_only"}
    SUPPORTED_COMPILATION_STRATEGIES = {"compiled_first", "raw_first", "hybrid", "disabled"}

    def __init__(self, db: Session):
        self.db = db

    def list_projects(self, current_user: User | None = None) -> list[dict]:
        query = self.db.query(Project)
        if current_user and current_user.system_role != "super_admin":
            query = query.join(ProjectMember, ProjectMember.project_id == Project.id).filter(ProjectMember.user_id == current_user.id)
        items = query.order_by(Project.id.desc()).all()
        return [self._serialize_project(item) for item in items]

    def list_public_projects(self) -> list[dict]:
        items = (
            self.db.query(Project)
            .filter(Project.status == "active")
            .order_by(Project.id.desc())
            .all()
        )
        return [self._serialize_project(item) for item in items]

    def get_project(self, project_id: int) -> dict | None:
        item = self.db.query(Project).filter(Project.id == project_id).first()
        return self._serialize_project(item) if item else None

    def get_persona(self, project_id: int) -> dict | None:
        persona = self.db.query(ProjectPersona).filter(ProjectPersona.project_id == project_id).first()
        if persona:
            return self._serialize_persona(persona)

        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        settings = self._ensure_settings(project_id)
        opening_text = settings.opening_text or f"您好，我是 {project.company_name} 的智能問答助手。"
        assistant_name, assistant_role = self._derive_persona_from_opening_text(
            opening_text,
            project.company_name or project.legacy_name,
        )
        return {
            "project_id": project_id,
            "assistant_name": assistant_name,
            "assistant_role": assistant_role,
            "system_prompt": settings.prompt_template,
            "style_rules": None,
            "opening_text": opening_text,
            "recommended_questions": settings.recommended_questions or [],
            "source": "project_settings_fallback",
        }

    def get_public_project(self, project_id: int) -> dict | None:
        item = self.db.query(Project).filter(Project.id == project_id, Project.status == "active").first()
        return self._serialize_project(item) if item else None

    def create_project(self, payload: dict) -> dict:
        payload = to_traditional_data(payload)
        company_name = payload["company_name"]
        project = Project(
            project_key=payload["project_key"],
            legacy_name=company_name,
            company_name=company_name,
            description=payload.get("description"),
            logo_url=payload.get("logo_url"),
            status=payload.get("status", "active"),
        )
        self.db.add(project)
        self.db.flush()

        settings = ProjectSetting(
            project_id=project.id,
            opening_mode="card",
            opening_text=f"您好，歡迎使用{project.company_name}智慧問答平台。",
            recommended_questions=["如何辦理相關業務？"],
            hot_questions=[],
            hot_policies=[],
            prompt_template="你是一个专业的业务问答助手。参考资料：{qa}\n历史对话：{history}\n用户问题：{query}",
            capability_multi_turn=payload.get("capabilities", {}).get("multi_turn", True),
            capability_memory=payload.get("capabilities", {}).get("memory", True),
            capability_sensitive_detection=payload.get("capabilities", {}).get("sensitive_detection", True),
            capability_gov_domain_check=payload.get("capabilities", {}).get("gov_domain_check", True),
            capability_knowledge_tree=payload.get("capabilities", {}).get("knowledge_tree", False),
            capability_knowledge_compilation=payload.get("capabilities", {}).get("knowledge_compilation", False),
            memory_scope="session_only",
            memory_ttl_days=7,
            preference_memory_enabled=False,
            compilation_strategy="compiled_first",
            compilation_min_score=0.82,
            compilation_min_supporting_source_count=2,
            compilation_allow_with_warning=False,
            enabled_scene_keys_json=["hk_tax_address_change"],
            scene_entry_mode="chat",
            scene_runtime_config_json={"mail_delivery_mode": app_settings.SCENE_MAIL_DELIVERY_MODE},
            enabled=True,
        )
        self.db.add(settings)
        self.db.add(
            KnowledgeBase(
                project_id=project.id,
                name=f"kb_{project.project_key}",
                description="項目預設知識庫",
                is_default=True,
            )
        )
        self.db.commit()
        self.db.refresh(project)
        return self._serialize_project(project)

    def update_project(self, project_id: int, payload: dict) -> dict | None:
        payload = to_traditional_data(payload)
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        next_company_name = payload.get("company_name", project.company_name)
        project.company_name = next_company_name
        project.legacy_name = next_company_name
        project.description = payload.get("description", project.description)
        project.logo_url = payload.get("logo_url", project.logo_url)
        project.status = payload.get("status", project.status)

        capabilities = payload.get("capabilities")
        if capabilities is not None:
            settings = self._ensure_settings(project_id)
            settings.capability_multi_turn = capabilities.get("multi_turn", settings.capability_multi_turn)
            settings.capability_memory = capabilities.get("memory", settings.capability_memory)
            settings.capability_sensitive_detection = capabilities.get(
                "sensitive_detection", settings.capability_sensitive_detection
            )
            settings.capability_gov_domain_check = capabilities.get(
                "gov_domain_check", settings.capability_gov_domain_check
            )
            settings.capability_knowledge_tree = capabilities.get(
                "knowledge_tree", settings.capability_knowledge_tree
            )
            settings.capability_knowledge_compilation = capabilities.get(
                "knowledge_compilation", settings.capability_knowledge_compilation
            )

        self.db.commit()
        self.db.refresh(project)
        return self._serialize_project(project)

    def get_opening_settings(self, project_id: int) -> dict:
        settings = self._ensure_settings(project_id)
        return {
            "project_id": project_id,
            "mode": settings.opening_mode,
            "opening_text": settings.opening_text,
            "recommended_questions": settings.recommended_questions or [],
            "hot_questions": settings.hot_questions or [],
            "hot_policies": settings.hot_policies or [],
            "enabled": settings.enabled,
        }

    def update_opening_settings(self, project_id: int, payload: dict) -> dict:
        payload = to_traditional_data(payload)
        settings = self._ensure_settings(project_id)
        settings.opening_mode = payload.get("mode", settings.opening_mode)
        settings.opening_text = payload.get("opening_text", settings.opening_text)
        settings.recommended_questions = payload.get("recommended_questions", settings.recommended_questions or [])
        settings.hot_questions = payload.get("hot_questions", settings.hot_questions or [])
        settings.hot_policies = payload.get("hot_policies", settings.hot_policies or [])
        settings.enabled = payload.get("enabled", settings.enabled)
        self.db.commit()
        return self.get_opening_settings(project_id)

    def get_prompt_settings(self, project_id: int) -> dict:
        settings = self._ensure_settings(project_id)
        return {
            "project_id": project_id,
            "prompt_template": settings.prompt_template,
        }

    def update_prompt_settings(self, project_id: int, payload: dict) -> dict:
        settings = self._ensure_settings(project_id)
        settings.prompt_template = payload.get("prompt_template", settings.prompt_template)
        self.db.commit()
        return self.get_prompt_settings(project_id)

    def get_memory_settings(self, project_id: int) -> dict:
        settings = self._ensure_settings(project_id)
        return {
            "project_id": project_id,
            "capability_memory": settings.capability_memory,
            "memory_scope": self._normalize_memory_scope(settings.memory_scope),
            "memory_ttl_days": self._normalize_memory_ttl_days(settings.memory_ttl_days),
            "preference_memory_enabled": False,
            "enabled_scene_keys_json": settings.enabled_scene_keys_json or [],
            "scene_entry_mode": settings.scene_entry_mode,
            "scene_runtime_config_json": settings.scene_runtime_config_json or {},
        }

    def update_memory_settings(self, project_id: int, payload: dict) -> dict:
        settings = self._ensure_settings(project_id)
        settings.capability_memory = payload.get("capability_memory", settings.capability_memory)
        settings.memory_scope = self._normalize_memory_scope(payload.get("memory_scope", settings.memory_scope))
        settings.memory_ttl_days = self._normalize_memory_ttl_days(payload.get("memory_ttl_days", settings.memory_ttl_days))
        settings.preference_memory_enabled = False
        settings.enabled_scene_keys_json = payload.get("enabled_scene_keys_json", settings.enabled_scene_keys_json or [])
        settings.scene_entry_mode = payload.get("scene_entry_mode", settings.scene_entry_mode)
        settings.scene_runtime_config_json = payload.get(
            "scene_runtime_config_json", settings.scene_runtime_config_json or {}
        )
        self.db.commit()
        return self.get_memory_settings(project_id)

    def get_knowledge_compilation_settings(self, project_id: int) -> dict:
        settings = self._ensure_settings(project_id)
        return {
            "project_id": project_id,
            "capability_knowledge_compilation": settings.capability_knowledge_compilation,
            "compilation_strategy": self._normalize_compilation_strategy(settings.compilation_strategy),
            "compilation_min_score": self._normalize_compilation_min_score(settings.compilation_min_score),
            "compilation_min_supporting_source_count": self._normalize_compilation_min_supporting_source_count(
                settings.compilation_min_supporting_source_count
            ),
            "compilation_allow_with_warning": bool(settings.compilation_allow_with_warning),
        }

    def update_knowledge_compilation_settings(self, project_id: int, payload: dict) -> dict:
        settings = self._ensure_settings(project_id)
        settings.capability_knowledge_compilation = bool(
            payload.get("capability_knowledge_compilation", settings.capability_knowledge_compilation)
        )
        settings.compilation_strategy = self._normalize_compilation_strategy(
            payload.get("compilation_strategy", settings.compilation_strategy)
        )
        settings.compilation_min_score = self._normalize_compilation_min_score(
            payload.get("compilation_min_score", settings.compilation_min_score)
        )
        settings.compilation_min_supporting_source_count = self._normalize_compilation_min_supporting_source_count(
            payload.get(
                "compilation_min_supporting_source_count",
                settings.compilation_min_supporting_source_count,
            )
        )
        settings.compilation_allow_with_warning = bool(
            payload.get("compilation_allow_with_warning", settings.compilation_allow_with_warning)
        )
        self.db.commit()
        return self.get_knowledge_compilation_settings(project_id)

    def get_active_project_context(self, project_id: int) -> dict:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        settings = self._ensure_settings(project_id)
        return {
            "project": self._serialize_project(project) if project else None,
            "settings": {
                "prompt_template": settings.prompt_template,
                "opening_text": settings.opening_text,
                "recommended_questions": settings.recommended_questions or [],
                "capability_multi_turn": settings.capability_multi_turn,
                "capability_memory": settings.capability_memory,
                "capability_sensitive_detection": settings.capability_sensitive_detection,
                "capability_gov_domain_check": settings.capability_gov_domain_check,
                "capability_knowledge_tree": settings.capability_knowledge_tree,
                "capability_knowledge_compilation": settings.capability_knowledge_compilation,
                "memory_scope": self._normalize_memory_scope(settings.memory_scope),
                "memory_ttl_days": self._normalize_memory_ttl_days(settings.memory_ttl_days),
                "preference_memory_enabled": False,
                "compilation_strategy": self._normalize_compilation_strategy(settings.compilation_strategy),
                "compilation_min_score": self._normalize_compilation_min_score(settings.compilation_min_score),
                "compilation_min_supporting_source_count": self._normalize_compilation_min_supporting_source_count(
                    settings.compilation_min_supporting_source_count
                ),
                "compilation_allow_with_warning": bool(settings.compilation_allow_with_warning),
                "enabled_scene_keys_json": settings.enabled_scene_keys_json or ["hk_tax_address_change"],
                "scene_entry_mode": settings.scene_entry_mode or "chat",
                "scene_runtime_config_json": settings.scene_runtime_config_json
                or {"mail_delivery_mode": app_settings.SCENE_MAIL_DELIVERY_MODE},
                "persona": self.get_persona(project_id),
            },
        }

    def _ensure_settings(self, project_id: int) -> ProjectSetting:
        settings = self.db.query(ProjectSetting).filter(ProjectSetting.project_id == project_id).first()
        if settings:
            return settings

        settings = ProjectSetting(
            project_id=project_id,
            opening_mode="card",
            opening_text="您好，歡迎使用智慧問答平台。",
            recommended_questions=[],
            hot_questions=[],
            hot_policies=[],
            prompt_template="你是一个专业的业务问答助手。参考资料：{qa}\n历史对话：{history}\n用户问题：{query}",
            capability_memory=True,
            capability_knowledge_compilation=False,
            memory_scope="session_only",
            memory_ttl_days=7,
            preference_memory_enabled=False,
            compilation_strategy="compiled_first",
            compilation_min_score=0.82,
            compilation_min_supporting_source_count=2,
            compilation_allow_with_warning=False,
            enabled_scene_keys_json=["hk_tax_address_change"],
            scene_entry_mode="chat",
            scene_runtime_config_json={"mail_delivery_mode": app_settings.SCENE_MAIL_DELIVERY_MODE},
            enabled=True,
        )
        self.db.add(settings)
        self.db.flush()
        return settings

    def _serialize_project(self, item: Project | None) -> dict | None:
        if not item:
            return None
        settings = self.db.query(ProjectSetting).filter(ProjectSetting.project_id == item.id).first()
        return {
            "id": item.id,
            "project_key": item.project_key,
            "company_name": item.company_name or item.legacy_name,
            "name": item.company_name or item.legacy_name,
            "description": item.description,
            "logo_url": item.logo_url,
            "status": item.status,
            "capabilities": {
                "multi_turn": settings.capability_multi_turn if settings else True,
                "memory": settings.capability_memory if settings else True,
                "sensitive_detection": settings.capability_sensitive_detection if settings else True,
                "gov_domain_check": settings.capability_gov_domain_check if settings else True,
                "knowledge_tree": settings.capability_knowledge_tree if settings else False,
                "knowledge_compilation": settings.capability_knowledge_compilation if settings else False,
                "scenes": bool((settings.enabled_scene_keys_json if settings else ["hk_tax_address_change"])),
            },
        }

    def _serialize_persona(self, persona: ProjectPersona) -> dict:
        return {
            "project_id": persona.project_id,
            "assistant_name": persona.assistant_name,
            "assistant_role": persona.assistant_role,
            "system_prompt": persona.system_prompt,
            "style_rules": persona.style_rules,
            "opening_text": persona.opening_text,
            "recommended_questions": self._parse_recommended_questions(persona.recommended_questions),
            "source": "project_persona",
        }

    def _parse_recommended_questions(self, raw_value: object) -> list[str]:
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        if not raw_value:
            return []
        text = str(raw_value).strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                import json

                payload = json.loads(text)
                if isinstance(payload, list):
                    return [str(item).strip() for item in payload if str(item).strip()]
            except Exception:  # noqa: BLE001
                pass
        return [segment.strip() for segment in text.replace("；", "\n").replace(";", "\n").splitlines() if segment.strip()]

    def _derive_persona_from_opening_text(self, opening_text: str, fallback_name: str) -> tuple[str, str]:
        text = opening_text.strip()
        if not text:
            return fallback_name, "智能問答助手"

        stripped = (
            text.replace("您好，", "")
            .replace("您好，我是", "")
            .replace("你好，", "")
            .replace("你好，我是", "")
            .replace("我是", "")
            .strip()
        )
        candidate = stripped.split("，", 1)[0].split(",", 1)[0].split("。", 1)[0].strip()
        if not candidate:
            return fallback_name, "智能問答助手"

        role_keywords = ("助理", "助手", "客服", "顧問", "專員", "機械人", "机器人", "bot", "Bot")
        for keyword in role_keywords:
            index = candidate.find(keyword)
            if index >= 0:
                assistant_name = candidate[:index].strip()
                return assistant_name or fallback_name, candidate
        return fallback_name, candidate

    def _normalize_memory_scope(self, memory_scope: object) -> str:
        scope = str(memory_scope or "session_only")
        return scope if scope in self.SUPPORTED_MEMORY_SCOPES else "session_only"

    def _normalize_memory_ttl_days(self, ttl_days: object) -> int:
        try:
            return min(max(int(ttl_days), 1), 365)
        except (TypeError, ValueError):
            return 7

    def _normalize_compilation_strategy(self, strategy: object) -> str:
        value = str(strategy or "compiled_first")
        return value if value in self.SUPPORTED_COMPILATION_STRATEGIES else "compiled_first"

    def _normalize_compilation_min_score(self, score: object) -> float:
        try:
            value = float(score)
        except (TypeError, ValueError):
            return 0.82
        return min(max(value, 0.0), 1.0)

    def _normalize_compilation_min_supporting_source_count(self, count: object) -> int:
        try:
            value = int(count)
        except (TypeError, ValueError):
            return 2
        return min(max(value, 1), 20)

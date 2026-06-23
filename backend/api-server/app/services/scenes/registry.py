from __future__ import annotations

from typing import Any

from app.services.scenes.rules_service import SceneRulesService


class SceneRegistry:
    def __init__(self, rules_service: SceneRulesService | None = None) -> None:
        self.rules_service = rules_service or SceneRulesService()

    def list_enabled_scene_keys(self, project_context: dict[str, Any]) -> list[str]:
        settings = project_context.get("settings", {})
        enabled = settings.get("enabled_scene_keys_json") or ["hk_tax_address_change"]
        return [item for item in enabled if item]

    def is_enabled(self, project_context: dict[str, Any], scene_key: str) -> bool:
        return scene_key in self.list_enabled_scene_keys(project_context)

    def get_scene_definition(self, scene_key: str) -> dict[str, Any]:
        return self.rules_service.get_scene_rules(scene_key)

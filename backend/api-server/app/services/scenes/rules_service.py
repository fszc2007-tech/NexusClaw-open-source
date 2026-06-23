from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RULES_ROOT = Path(__file__).resolve().parent / "config" / "rules"
MAPPINGS_ROOT = Path(__file__).resolve().parent / "config" / "mappings"


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class SceneRulesService:
    def __init__(self) -> None:
        self._scene_rules = _load_json(str(RULES_ROOT / "ird_rules.json"))

    def get_scene_rules(self, scene_key: str) -> dict[str, Any]:
        if self._scene_rules["scene_key"] != scene_key:
            raise ValueError("scene_rules_not_found")
        return self._scene_rules

    def get_route_rules(self, scene_key: str, route_key: str) -> dict[str, Any]:
        scene_rules = self.get_scene_rules(scene_key)
        route_rules = scene_rules.get("routes", {}).get(route_key)
        if not route_rules:
            raise ValueError("route_rules_not_found")
        return route_rules

    def get_mapping(self, form_no: str) -> dict[str, Any]:
        filename = f"{form_no.lower()}_fields.json"
        mapping_path = MAPPINGS_ROOT / filename
        if not mapping_path.exists():
            raise ValueError("mapping_not_found")
        return _load_json(str(mapping_path))

    def get_scene_runtime_config(self, project_context: dict[str, Any]) -> dict[str, Any]:
        settings = project_context.get("settings", {})
        return settings.get("scene_runtime_config_json") or {"mail_delivery_mode": "draft_only"}

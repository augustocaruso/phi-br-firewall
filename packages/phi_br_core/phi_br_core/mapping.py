from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


class PlaceholderIndex:
    def __init__(self, path: Path) -> None:
        self.path = path

    def assign(self, placeholder_key: str, session_id: str) -> None:
        placeholders = self._read()
        sessions = placeholders.setdefault(placeholder_key, [])
        if session_id not in sessions:
            sessions.append(session_id)
        self._write(placeholders)

    def resolve(self, placeholder_keys: list[str]) -> dict[str, str]:
        placeholders = self._read()
        resolved: dict[str, str] = {}
        for placeholder_key in placeholder_keys:
            sessions = placeholders.get(placeholder_key, [])
            if len(sessions) == 1:
                resolved[placeholder_key] = sessions[0]
            elif len(sessions) > 1:
                raise ValueError(f"placeholder {placeholder_key} is ambiguous")
        return resolved

    def _read(self) -> dict[str, list[str]]:
        if not self.path.exists():
            return {}
        raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        placeholders = raw.get("placeholders", {})
        if not isinstance(placeholders, dict):
            return {}

        parsed: dict[str, list[str]] = {}
        for key, value in placeholders.items():
            if isinstance(key, str) and isinstance(value, list):
                parsed[key] = [item for item in value if isinstance(item, str)]
        return parsed

    def _write(self, placeholders: dict[str, list[str]]) -> None:
        write_json_atomic(self.path, {"placeholders": placeholders})

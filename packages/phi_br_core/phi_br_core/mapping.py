from __future__ import annotations

import json
from os import getpid
from pathlib import Path
from secrets import token_hex
from typing import Any


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{getpid()}.{token_hex(3)}.tmp")
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

    def next_key(self, prefix: str) -> str:
        placeholders = self._read()
        highest = 0
        marker = f"{prefix}_"
        for placeholder_key in placeholders:
            if not placeholder_key.startswith(marker):
                continue
            suffix = placeholder_key.removeprefix(marker)
            if suffix.isdecimal():
                highest = max(highest, int(suffix))
        return f"{prefix}_{highest + 1:03d}"

    def remove_sessions(self, session_ids: list[str]) -> None:
        if not session_ids:
            return
        removed = set(session_ids)
        placeholders = self._read()
        cleaned: dict[str, list[str]] = {}
        for placeholder_key, sessions in placeholders.items():
            active_sessions = [session_id for session_id in sessions if session_id not in removed]
            if active_sessions:
                cleaned[placeholder_key] = active_sessions
        self._write(cleaned)

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

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
        placeholders, counters = self._read_state()
        sessions = placeholders.setdefault(placeholder_key, [])
        if session_id not in sessions:
            sessions.append(session_id)
        self._remember_key(counters, placeholder_key)
        self._write(placeholders, counters)

    def next_key(self, prefix: str) -> str:
        placeholders, counters = self._read_state()
        highest = counters.get(prefix, 0)
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
        placeholders, counters = self._read_state()
        cleaned: dict[str, list[str]] = {}
        for placeholder_key, sessions in placeholders.items():
            active_sessions = [session_id for session_id in sessions if session_id not in removed]
            if active_sessions:
                cleaned[placeholder_key] = active_sessions
        self._write(cleaned, counters)

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
        return self._read_state()[0]

    def _read_state(self) -> tuple[dict[str, list[str]], dict[str, int]]:
        if not self.path.exists():
            return {}, {}
        raw: Any = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}, {}
        placeholders = raw.get("placeholders", {})
        if not isinstance(placeholders, dict):
            placeholders = {}

        parsed: dict[str, list[str]] = {}
        for key, value in placeholders.items():
            if isinstance(key, str) and isinstance(value, list):
                parsed[key] = [item for item in value if isinstance(item, str)]

        counters: dict[str, int] = {}
        raw_counters = raw.get("counters", {})
        if isinstance(raw_counters, dict):
            for key, value in raw_counters.items():
                if isinstance(key, str) and isinstance(value, int) and value >= 0:
                    counters[key] = value

        for placeholder_key in parsed:
            self._remember_key(counters, placeholder_key)

        return parsed, counters

    def _write(self, placeholders: dict[str, list[str]], counters: dict[str, int]) -> None:
        write_json_atomic(self.path, {"counters": counters, "placeholders": placeholders})

    @staticmethod
    def _remember_key(counters: dict[str, int], placeholder_key: str) -> None:
        prefix, separator, suffix = placeholder_key.rpartition("_")
        if separator != "_" or not prefix or not suffix.isdecimal():
            return
        counters[prefix] = max(counters.get(prefix, 0), int(suffix))

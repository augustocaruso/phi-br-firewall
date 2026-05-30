from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from secrets import token_hex
from typing import Any

from phi_br_core.mapping import write_json_atomic


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    path: Path
    created_at: datetime
    expires_at: datetime
    source: str


class SessionStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def create(
        self, source: str, now: datetime | None = None, ttl_hours: int = 24
    ) -> SessionRecord:
        created_at = self._normalize_datetime(now)
        expires_at = created_at + timedelta(hours=ttl_hours)
        session_id = f"phi-{created_at.strftime('%Y%m%d-%H%M%S')}-{token_hex(3)}"
        path = self.session_path(session_id)
        path.mkdir(parents=True, exist_ok=False)
        record = SessionRecord(
            session_id=session_id,
            path=path,
            created_at=created_at,
            expires_at=expires_at,
            source=source,
        )
        write_json_atomic(path / "metadata.json", self._metadata_payload(record))
        return record

    def session_path(self, session_id: str) -> Path:
        if "/" in session_id or "\\" in session_id or session_id in {"", ".", ".."}:
            raise ValueError("invalid session_id")
        return self.base_dir / session_id

    def purge_expired(self, now: datetime | None = None) -> list[str]:
        current_time = self._normalize_datetime(now)
        purged: list[str] = []
        if not self.base_dir.exists():
            return purged

        for path in self.base_dir.iterdir():
            if not path.is_dir():
                continue
            record = self._read_record(path)
            if record is None or record.expires_at > current_time:
                continue
            self._delete_session_dir(path)
            purged.append(record.session_id)
        return purged

    def _read_record(self, path: Path) -> SessionRecord | None:
        metadata_path = path / "metadata.json"
        if not metadata_path.exists():
            return None
        raw: Any = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        session_id = raw.get("session_id")
        created_at = raw.get("created_at")
        expires_at = raw.get("expires_at")
        source = raw.get("source")
        if not isinstance(session_id, str):
            return None
        if not isinstance(created_at, str):
            return None
        if not isinstance(expires_at, str):
            return None
        if not isinstance(source, str):
            return None
        return SessionRecord(
            session_id=session_id,
            path=path,
            created_at=datetime.fromisoformat(created_at),
            expires_at=datetime.fromisoformat(expires_at),
            source=source,
        )

    def _delete_session_dir(self, path: Path) -> None:
        base = self.base_dir.resolve()
        target = path.resolve()
        if target.parent != base or not path.name.startswith("phi-"):
            raise ValueError("refusing to delete unsafe session path")
        shutil.rmtree(target)

    @staticmethod
    def _metadata_payload(record: SessionRecord) -> dict[str, str]:
        return {
            "session_id": record.session_id,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "source": record.source,
        }

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(tz=UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

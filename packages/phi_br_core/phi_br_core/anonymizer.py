from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from phi_br_core.clinical_rendering import ClinicalReplacementRenderer
from phi_br_core.entities import ENTITY_TO_PLACEHOLDER_PREFIX
from phi_br_core.mapping import PlaceholderIndex, write_json_atomic
from phi_br_core.models import PhiAuditResult, PhiFinding, PhiScrubResult, PhiScrubSummary
from phi_br_core.policy import PhiPolicy
from phi_br_core.sessions import SessionStore
from phi_br_core.spans import resolve_overlaps


class StablePlaceholderAnonymizer:
    def __init__(self, base_dir: Path | str = ".tmp/phi") -> None:
        self.base_dir = Path(base_dir)
        self.index = PlaceholderIndex(self.base_dir / "index.json")
        self.sessions = SessionStore(self.base_dir, placeholder_index=self.index)

    def scrub(
        self,
        text: str,
        findings: list[PhiFinding],
        source: str = "unknown",
        policy: PhiPolicy | None = None,
    ) -> PhiScrubResult:
        session = self.sessions.create(source=source)
        accepted = resolve_overlaps(findings)
        renderer = ClinicalReplacementRenderer(text, accepted, policy or PhiPolicy())
        by_value: dict[tuple[str, str], str] = {}
        items: dict[str, dict[str, str]] = {}
        replacements: list[tuple[PhiFinding, str]] = []
        scrubbed_text = text

        for finding in accepted:
            placeholder_key = by_value.get((finding.entity_type, finding.text))
            if placeholder_key is None:
                prefix = ENTITY_TO_PLACEHOLDER_PREFIX.get(finding.entity_type, finding.entity_type)
                placeholder_key = self.index.next_key(prefix)
                by_value[(finding.entity_type, finding.text)] = placeholder_key
                items[placeholder_key] = {
                    "value": finding.text,
                    "entity_type": finding.entity_type,
                }
                self.index.assign(placeholder_key, session.session_id)
            replacements.append((finding, renderer.render(placeholder_key, finding)))

        for finding, replacement in sorted(
            replacements, key=lambda item: item[0].start, reverse=True
        ):
            scrubbed_text = (
                scrubbed_text[: finding.start]
                + replacement
                + scrubbed_text[finding.end :]
            )

        mapping_path = session.path / "mapping.json"
        write_json_atomic(
            mapping_path,
            {
                "session_id": session.session_id,
                "items": items,
            },
        )
        return PhiScrubResult(
            ok=True,
            action="scrub",
            scrubbed_text=scrubbed_text,
            mapping_path=str(mapping_path),
            session_id=session.session_id,
            audit=PhiAuditResult(safe=True, residual_findings=[]),
            summary=PhiScrubSummary(
                entities_replaced=len(accepted),
                entity_types=sorted({finding.entity_type for finding in accepted}),
            ),
        )

    def restore(self, text: str, mapping_path: Path | str) -> str:
        mapping = self._read_mapping(Path(mapping_path))
        restored = text
        for placeholder_key, item in sorted(
            mapping.items(), key=lambda entry: len(entry[0]), reverse=True
        ):
            restored = re.sub(
                rf"\[{re.escape(placeholder_key)}(?:[^\]]*)?\]",
                item["value"],
                restored,
            )
        return restored

    @staticmethod
    def _read_mapping(mapping_path: Path) -> dict[str, dict[str, str]]:
        raw: Any = json.loads(mapping_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("invalid mapping file")
        items = raw.get("items")
        if not isinstance(items, dict):
            raise ValueError("invalid mapping file")

        parsed: dict[str, dict[str, str]] = {}
        for key, value in items.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            original = value.get("value")
            entity_type = value.get("entity_type")
            if isinstance(original, str) and isinstance(entity_type, str):
                parsed[key] = {"value": original, "entity_type": entity_type}
        return parsed

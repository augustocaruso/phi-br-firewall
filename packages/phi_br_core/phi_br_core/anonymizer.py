from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from phi_br_core.clinical_rendering import ClinicalReplacementRenderer
from phi_br_core.date_formatting import DateGranularity, format_date_pt_br
from phi_br_core.entities import ENTITY_TO_PLACEHOLDER_PREFIX
from phi_br_core.formatting import apply_text_case
from phi_br_core.mapping import PlaceholderIndex, write_json_atomic
from phi_br_core.models import PhiAuditResult, PhiFinding, PhiScrubResult, PhiScrubSummary
from phi_br_core.placeholders import parse_placeholder
from phi_br_core.policy import PhiPolicy
from phi_br_core.sessions import SessionStore
from phi_br_core.spans import resolve_overlaps

_PLACEHOLDER_RE = re.compile(r"\[[A-Z0-9_]+_\d{3}(?:[^\]]*)?\]")
_SUPPORTED_RENDER_OPTIONS = {"case", "date"}


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
        items: dict[str, dict[str, Any]] = {}
        replacements: list[tuple[PhiFinding, str]] = []
        scrubbed_text = text

        for finding in accepted:
            placeholder_key = by_value.get((finding.entity_type, finding.text))
            rendered = renderer.render(placeholder_key, finding) if placeholder_key else None
            if placeholder_key is None:
                prefix = ENTITY_TO_PLACEHOLDER_PREFIX.get(finding.entity_type, finding.entity_type)
                placeholder_key = self.index.next_key(prefix)
                by_value[(finding.entity_type, finding.text)] = placeholder_key
                rendered = renderer.render(placeholder_key, finding)
                item: dict[str, Any] = {
                    "value": finding.text,
                    "entity_type": finding.entity_type,
                }
                if rendered.public_meta:
                    item["public_meta"] = rendered.public_meta
                if rendered.private_meta:
                    item["private_meta"] = rendered.private_meta
                items[placeholder_key] = item
                self.index.assign(placeholder_key, session.session_id)
            if rendered is None:
                rendered = renderer.render(placeholder_key, finding)
            replacements.append((finding, rendered.text))

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

        def replace(match: re.Match[str]) -> str:
            placeholder = parse_placeholder(match.group(0))
            item = mapping.get(placeholder.key)
            if item is None:
                return match.group(0)
            return _render_mapping_item(item, placeholder.render_options)

        return _PLACEHOLDER_RE.sub(replace, text)

    @staticmethod
    def _read_mapping(mapping_path: Path) -> dict[str, dict[str, Any]]:
        raw: Any = json.loads(mapping_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("invalid mapping file")
        items = raw.get("items")
        if not isinstance(items, dict):
            raise ValueError("invalid mapping file")

        parsed: dict[str, dict[str, Any]] = {}
        for key, value in items.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            original = value.get("value")
            entity_type = value.get("entity_type")
            if isinstance(original, str) and isinstance(entity_type, str):
                public_meta = value.get("public_meta")
                private_meta = value.get("private_meta")
                parsed[key] = {
                    "value": original,
                    "entity_type": entity_type,
                    "public_meta": public_meta if isinstance(public_meta, dict) else {},
                    "private_meta": private_meta if isinstance(private_meta, dict) else {},
                }
        return parsed


def _render_mapping_item(item: dict[str, Any], render_options: dict[str, str]) -> str:
    unsupported_options = set(render_options) - _SUPPORTED_RENDER_OPTIONS
    if unsupported_options:
        raise ValueError("invalid render option")

    value = str(item["value"])
    rendered = value

    if "date" in render_options:
        rendered = _render_date_mapping_item(item, render_options["date"])

    if "case" in render_options:
        rendered = apply_text_case(rendered, render_options["case"])

    return rendered


def _render_date_mapping_item(item: dict[str, Any], format_name: str) -> str:
    value = str(item["value"])
    if format_name == "original":
        return value

    private_meta = item.get("private_meta")
    if not isinstance(private_meta, dict):
        raise ValueError("date render option unavailable")

    iso_value = private_meta.get("iso")
    if not isinstance(iso_value, str):
        raise ValueError("date render option unavailable")

    granularity = _date_granularity(private_meta.get("gran"))
    return format_date_pt_br(date.fromisoformat(iso_value), format_name, granularity)


def _date_granularity(value: object) -> DateGranularity:
    if value == "month":
        return "month"
    return "day"

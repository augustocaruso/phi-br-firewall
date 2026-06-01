from __future__ import annotations

import re
from pathlib import Path

from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.core import scrub_text
from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.models import PhiRedactResult, PhiRestoreResult
from phi_br_core.policy import PhiPolicy
from phi_br_core.sessions import SessionStore

PLACEHOLDER_PATTERN = re.compile(r"\[([A-Z0-9_]+_\d{3})(?:[^\]]*)?\]")


def redact_text(text: str, policy: PhiPolicy | None = None) -> PhiRedactResult:
    active_policy = policy or PhiPolicy()
    purge_expired(active_policy)
    scrub = scrub_text(text, active_policy)
    if not scrub.ok:
        return PhiRedactResult(ok=False, reason="audit_failed")
    return PhiRedactResult(
        ok=True,
        redacted_text=scrub.scrubbed_text,
        session_id=scrub.session_id,
        summary=scrub.summary,
    )


def restore_active_text(text: str, policy: PhiPolicy | None = None) -> PhiRestoreResult:
    active_policy = policy or PhiPolicy()
    purge_expired(active_policy)
    base_dir = Path(active_policy.mapping.base_dir)
    placeholder_keys = sorted(set(PLACEHOLDER_PATTERN.findall(text)))
    if not placeholder_keys:
        return PhiRestoreResult(ok=True, restored_text=text)

    try:
        resolved = PlaceholderIndex(base_dir / "index.json").resolve(placeholder_keys)
    except ValueError:
        return PhiRestoreResult(ok=False, reason="placeholder_owner_ambiguous")

    if set(resolved) != set(placeholder_keys):
        return PhiRestoreResult(ok=False, reason="placeholder_owner_missing")

    anonymizer = StablePlaceholderAnonymizer(base_dir=base_dir)
    restored = text
    sessions_used = sorted(set(resolved.values()))
    for session_id in sessions_used:
        mapping_path = base_dir / session_id / "mapping.json"
        if not mapping_path.exists():
            return PhiRestoreResult(ok=False, reason="mapping_missing")
        try:
            restored = anonymizer.restore(restored, mapping_path)
        except ValueError:
            return PhiRestoreResult(ok=False, reason="invalid_render_option")

    if PLACEHOLDER_PATTERN.search(restored):
        return PhiRestoreResult(ok=False, reason="restore_incomplete")

    return PhiRestoreResult(
        ok=True,
        restored_text=restored,
        contains_phi=True,
        sessions_used=sessions_used,
    )


def purge_expired(policy: PhiPolicy) -> list[str]:
    base_dir = Path(policy.mapping.base_dir)
    index = PlaceholderIndex(base_dir / "index.json")
    return SessionStore(base_dir, placeholder_index=index).purge_expired()

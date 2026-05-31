from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import typer

from phi_br_core import clipboard
from phi_br_core.analyzer import build_analyzer, build_registry
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.audit import audit_text
from phi_br_core.core import scrub_text
from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.policy import PhiPolicy
from phi_br_core.sessions import SessionStore

app = typer.Typer(no_args_is_help=True)
PLACEHOLDER_PATTERN = re.compile(r"\[([A-Z0-9_]+_\d{3})(?:[^\]]*)?\]")
CUSTOM_RECOGNIZERS = (
    "BR_CPF",
    "BR_CNS",
    "BR_CRM",
    "BR_CEP",
    "BR_PHONE",
    "BR_EMAIL",
    "BR_ADDRESS",
    "BR_CONTEXTUAL_IDENTIFIER",
    "BR_CLINICAL_RECORD_ID",
    "BR_VISIT_ID",
    "BR_EXAM_ID",
    "BR_AUTHORIZATION_ID",
    "BR_DATE",
    "BR_AGE",
    "BR_INSTITUTION",
    "BR_PATIENT_NAME",
    "BR_FAMILY_MEMBER_NAME",
    "BR_HEALTHCARE_PROFESSIONAL_NAME",
)


class RestoreError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@app.callback()
def main() -> None:
    """phi-br-presidio-firewall command line."""


@app.command()
def check() -> None:
    """Verify that phi can start."""
    policy = _policy()
    _purge_expired(policy)
    policy.mapping.persist = False
    base_dir = Path(policy.mapping.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    probe_path = base_dir / ".check-write"
    probe_path.write_text("ok", encoding="utf-8")
    probe_path.unlink(missing_ok=True)

    registry = build_registry([policy.language, "en"])
    supported_entities = set(registry.get_supported_entities())
    custom_recognizers = sorted(
        entity for entity in CUSTOM_RECOGNIZERS if entity in supported_entities
    )
    missing_recognizers = sorted(set(CUSTOM_RECOGNIZERS) - set(custom_recognizers))
    if missing_recognizers:
        raise typer.Exit(code=1)

    build_analyzer(policy)
    presidio_anonymizer = importlib.import_module("presidio_anonymizer")
    if not hasattr(presidio_anonymizer, "AnonymizerEngine"):
        raise typer.Exit(code=1)
    scrub = scrub_text("Paciente Teste, CPF 935.411.347-80.", policy)
    if not scrub.ok or "935.411.347-80" in scrub.scrubbed_text:
        raise typer.Exit(code=1)
    audit = audit_text("Paciente [PACIENTE_001], CPF [CPF_001].", policy)
    if not audit.safe:
        raise typer.Exit(code=1)

    _echo_json(
        {
            "ok": True,
            "package_import": True,
            "presidio_analyzer": True,
            "presidio_anonymizer": True,
            "custom_recognizers": custom_recognizers,
            "scrub": True,
            "audit": True,
            "base_dir_writable": True,
        }
    )


@app.command()
def redact() -> None:
    """Redact clipboard text and write the safe text back to the clipboard."""
    policy = _policy()
    _purge_expired(policy)
    source_text = clipboard.read_clipboard()
    result = scrub_text(source_text, policy)
    if not result.ok:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_redact_failed",
                "printed_phi": False,
                "reason": "audit_failed",
            }
        )
        raise typer.Exit(code=1)
    clipboard.write_clipboard(result.scrubbed_text)
    _echo_json(
        {
            "ok": result.ok,
            "action": "clipboard_redacted",
            "printed_phi": False,
            "session_id": result.session_id,
            "summary": result.summary.model_dump(),
        }
    )


@app.command(hidden=True)
def scrub_stdin(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Internal stdin redaction for local integrations."""
    if not json_output:
        _echo_json({"ok": False, "reason": "json_required"})
        raise typer.Exit(code=1)

    try:
        policy = _policy()
        _purge_expired(policy)
        result = scrub_text(sys.stdin.read(), policy)
    except Exception as error:
        _echo_json({"ok": False, "reason": "scrub_failed"})
        raise typer.Exit(code=1) from error

    if not result.ok:
        _echo_json({"ok": False, "reason": "audit_failed"})
        raise typer.Exit(code=1)

    _echo_json(
        {
            "ok": True,
            "scrubbed_text": result.scrubbed_text,
            "session_id": result.session_id,
            "summary": result.summary.model_dump(),
        }
    )


@app.command()
def restore() -> None:
    """Restore clipboard placeholders locally without printing restored text."""
    policy = _policy()
    _purge_expired(policy)
    redacted_text = clipboard.read_clipboard()
    try:
        restored_text = _restore_from_active_index(redacted_text, Path(policy.mapping.base_dir))
    except RestoreError as error:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_restore_failed",
                "printed_phi": False,
                "reason": error.reason,
            }
        )
        raise typer.Exit(code=1) from error
    clipboard.write_clipboard(restored_text)
    _echo_json({"ok": True, "action": "clipboard_restored", "printed_phi": False})


@app.command()
def status() -> None:
    """Print local session counts and metadata only."""
    policy = _policy()
    purged = _purge_expired(policy)
    base_dir = Path(policy.mapping.base_dir)
    _echo_json(
        {
            "ok": True,
            "active_sessions": len(_session_ids(base_dir)),
            "placeholder_keys": len(_placeholder_keys(base_dir)),
            "purged_expired_sessions": len(purged),
        }
    )


@app.command()
def purge(
    all_sessions: bool = typer.Option(False, "--all", help="Delete all local sessions."),
) -> None:
    """Delete expired local sessions, or all sessions with --all."""
    policy = _policy()
    purged = _purge_all(policy) if all_sessions else _purge_expired(policy)
    _echo_json({"ok": True, "action": "purged", "purged_sessions": len(purged)})


def _policy() -> PhiPolicy:
    policy = PhiPolicy()
    base_dir = os.environ.get("PHI_BASE_DIR")
    if base_dir:
        policy.mapping.base_dir = base_dir
    return policy


def _purge_expired(policy: PhiPolicy) -> list[str]:
    base_dir = Path(policy.mapping.base_dir)
    index = PlaceholderIndex(base_dir / "index.json")
    return SessionStore(base_dir, placeholder_index=index).purge_expired()


def _purge_all(policy: PhiPolicy) -> list[str]:
    base_dir = Path(policy.mapping.base_dir)
    index = PlaceholderIndex(base_dir / "index.json")
    return SessionStore(base_dir, placeholder_index=index).purge_all()


def _restore_from_active_index(text: str, base_dir: Path) -> str:
    placeholder_keys = sorted(set(PLACEHOLDER_PATTERN.findall(text)))
    if not placeholder_keys:
        return text

    try:
        resolved = PlaceholderIndex(base_dir / "index.json").resolve(placeholder_keys)
    except ValueError as error:
        raise RestoreError("placeholder_owner_ambiguous") from error
    if set(resolved) != set(placeholder_keys):
        raise RestoreError("placeholder_owner_missing")

    anonymizer = StablePlaceholderAnonymizer(base_dir=base_dir)
    restored = text
    for session_id in sorted(set(resolved.values())):
        mapping_path = base_dir / session_id / "mapping.json"
        if not mapping_path.exists():
            raise RestoreError("mapping_missing")
        restored = anonymizer.restore(restored, mapping_path)
    if PLACEHOLDER_PATTERN.search(restored):
        raise RestoreError("restore_incomplete")
    return restored


def _session_ids(base_dir: Path) -> list[str]:
    return [record.session_id for record in SessionStore(base_dir).list_records()]


def _placeholder_keys(base_dir: Path) -> list[str]:
    index_path = base_dir / "index.json"
    if not index_path.exists():
        return []
    raw: Any = json.loads(index_path.read_text(encoding="utf-8"))
    placeholders = raw.get("placeholders", {}) if isinstance(raw, dict) else {}
    if not isinstance(placeholders, dict):
        return []
    return [key for key in placeholders if isinstance(key, str)]


def _echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, sort_keys=True))

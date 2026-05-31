from __future__ import annotations

import json
import os
import re
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
PLACEHOLDER_PATTERN = re.compile(r"\[([A-Z0-9_]+_\d{3})\]")


@app.callback()
def main() -> None:
    """phi-br-presidio-firewall command line."""


@app.command()
def check() -> None:
    """Verify that phi can start."""
    policy = _policy()
    _purge_expired(policy)
    base_dir = Path(policy.mapping.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    probe_path = base_dir / ".check-write"
    probe_path.write_text("ok", encoding="utf-8")
    probe_path.unlink(missing_ok=True)

    registry = build_registry([policy.language, "en"])
    supported_entities = set(registry.get_supported_entities())
    if "BR_CPF" not in supported_entities:
        raise typer.Exit(code=1)

    build_analyzer(policy)
    scrub = scrub_text("Paciente Teste, CPF 935.411.347-80.", policy)
    if not scrub.ok or "935.411.347-80" in scrub.scrubbed_text:
        raise typer.Exit(code=1)
    audit = audit_text("Paciente [PACIENTE_001], CPF [CPF_001].", policy)
    if not audit.safe:
        raise typer.Exit(code=1)

    typer.echo("phi baseline ok")


@app.command()
def redact() -> None:
    """Redact clipboard text and write the safe text back to the clipboard."""
    policy = _policy()
    _purge_expired(policy)
    source_text = clipboard.read_clipboard()
    result = scrub_text(source_text, policy)
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


@app.command()
def restore() -> None:
    """Restore clipboard placeholders locally without printing restored text."""
    policy = _policy()
    _purge_expired(policy)
    redacted_text = clipboard.read_clipboard()
    restored_text = _restore_from_active_index(redacted_text, Path(policy.mapping.base_dir))
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
            "base_dir": str(base_dir),
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
    store = SessionStore(base_dir, placeholder_index=index)
    purged: list[str] = []
    if not base_dir.exists():
        return purged
    for path in base_dir.iterdir():
        if not path.is_dir():
            continue
        record = store._read_record(path)
        if record is None:
            continue
        store._delete_session_dir(path)
        purged.append(record.session_id)
    index.remove_sessions(purged)
    return purged


def _restore_from_active_index(text: str, base_dir: Path) -> str:
    placeholder_keys = sorted(set(PLACEHOLDER_PATTERN.findall(text)))
    if not placeholder_keys:
        return text

    resolved = PlaceholderIndex(base_dir / "index.json").resolve(placeholder_keys)
    anonymizer = StablePlaceholderAnonymizer(base_dir=base_dir)
    restored = text
    for session_id in sorted(set(resolved.values())):
        mapping_path = base_dir / session_id / "mapping.json"
        if mapping_path.exists():
            restored = anonymizer.restore(restored, mapping_path)
    return restored


def _session_ids(base_dir: Path) -> list[str]:
    store = SessionStore(base_dir)
    if not base_dir.exists():
        return []
    session_ids: list[str] = []
    for path in base_dir.iterdir():
        if not path.is_dir():
            continue
        record = store._read_record(path)
        if record is not None:
            session_ids.append(record.session_id)
    return session_ids


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

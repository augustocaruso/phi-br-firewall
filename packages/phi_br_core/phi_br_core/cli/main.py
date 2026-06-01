from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import typer

from phi_br_core import clipboard
from phi_br_core.analyzer import build_analyzer, build_registry
from phi_br_core.api import redact_text, restore_active_text
from phi_br_core.audit import audit_text
from phi_br_core.bench import run_benchmark
from phi_br_core.core import scrub_text
from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.policy import NlpPolicy, PhiPolicy
from phi_br_core.recognizers.nlp_adapter import nlp_model_available
from phi_br_core.sessions import SessionStore

app = typer.Typer(no_args_is_help=True)
api_app = typer.Typer(no_args_is_help=True)
app.add_typer(api_app, name="api", help="Programmatic stdin/stdout API.")
CUSTOM_RECOGNIZERS = (
    "BR_CPF",
    "BR_RG",
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
OPTIONAL_NLP_RECOGNIZERS = ("BR_PERSON_NAME",)


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
    nlp_status = _nlp_status(policy)
    if policy.nlp.enabled and not nlp_status["available"]:
        _echo_json({"ok": False, "reason": "nlp_model_unavailable", "nlp": nlp_status})
        raise typer.Exit(code=1)

    registry = build_registry([policy.language, "en"], policy=policy)
    supported_entities = set(registry.get_supported_entities())
    expected_recognizers = CUSTOM_RECOGNIZERS + (
        OPTIONAL_NLP_RECOGNIZERS if policy.nlp.enabled else ()
    )
    custom_recognizers = sorted(
        entity for entity in expected_recognizers if entity in supported_entities
    )
    missing_recognizers = sorted(set(expected_recognizers) - set(custom_recognizers))
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
            "nlp": nlp_status,
            "scrub": True,
            "audit": True,
            "base_dir_writable": True,
        }
    )


@app.command()
def bench(
    iterations: int = typer.Option(3, "--iterations", min=1, help="Iterations per benchmark."),
) -> None:
    """Measure local phi runtime costs with synthetic text only."""
    policy = _policy()
    _purge_expired(policy)
    _echo_json(run_benchmark(policy, iterations=iterations))


@app.command()
def redact() -> None:
    """Redact clipboard text and write the safe text back to the clipboard."""
    policy = _policy()
    _purge_expired(policy)
    try:
        source_text = clipboard.read_clipboard()
    except clipboard.ClipboardError as error:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_redact_failed",
                "printed_phi": False,
                "reason": error.reason,
            }
        )
        raise typer.Exit(code=1) from error
    result = scrub_text(source_text, policy)
    if not result.ok:
        _echo_json(_scrub_failure_payload("clipboard_redact_failed", result))
        raise typer.Exit(code=1)
    try:
        clipboard.write_clipboard(result.scrubbed_text)
    except clipboard.ClipboardError as error:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_redact_failed",
                "printed_phi": False,
                "reason": error.reason,
            }
        )
        raise typer.Exit(code=1) from error
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
        _echo_json(_scrub_failure_payload("scrub_failed", result))
        raise typer.Exit(code=1)

    _echo_json(
        {
            "ok": True,
            "scrubbed_text": result.scrubbed_text,
            "session_id": result.session_id,
            "summary": result.summary.model_dump(),
        }
    )


@api_app.command("redact")
def api_redact(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Redact stdin text and print safe JSON without using the clipboard."""
    if not json_output:
        _echo_json({"ok": False, "action": "redact_failed", "reason": "json_required"})
        raise typer.Exit(code=1)

    try:
        result = redact_text(sys.stdin.read(), _policy())
    except Exception as error:
        _echo_json({"ok": False, "action": "redact_failed", "reason": "redact_failed"})
        raise typer.Exit(code=1) from error

    if not result.ok:
        _echo_json(
            {
                "ok": False,
                "action": "redact_failed",
                "reason": result.reason or "redact_failed",
            }
        )
        raise typer.Exit(code=1)

    _echo_json(
        {
            "ok": True,
            "action": result.action,
            "redacted_text": result.redacted_text,
            "session_id": result.session_id,
            "summary": result.summary.model_dump(),
        }
    )


@api_app.command("restore")
def api_restore(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Restore stdin placeholders and print JSON. Successful output contains PHI."""
    if not json_output:
        _echo_json({"ok": False, "action": "restore_failed", "reason": "json_required"})
        raise typer.Exit(code=1)

    try:
        result = restore_active_text(sys.stdin.read(), _policy())
    except Exception as error:
        _echo_json(
            {
                "ok": False,
                "action": "restore_failed",
                "reason": "restore_failed",
                "contains_phi": False,
            }
        )
        raise typer.Exit(code=1) from error

    if not result.ok:
        _echo_json(
            {
                "ok": False,
                "action": "restore_failed",
                "reason": result.reason or "restore_failed",
                "contains_phi": False,
            }
        )
        raise typer.Exit(code=1)

    _echo_json(
        {
            "ok": True,
            "action": result.action,
            "restored_text": result.restored_text,
            "contains_phi": result.contains_phi,
            "sessions_used": result.sessions_used,
        }
    )


@app.command()
def restore() -> None:
    """Restore clipboard placeholders locally without printing restored text."""
    policy = _policy()
    try:
        redacted_text = clipboard.read_clipboard()
    except clipboard.ClipboardError as error:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_restore_failed",
                "printed_phi": False,
                "reason": error.reason,
            }
        )
        raise typer.Exit(code=1) from error
    result = restore_active_text(redacted_text, policy)
    if not result.ok:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_restore_failed",
                "printed_phi": False,
                "reason": result.reason or "restore_failed",
            }
        )
        raise typer.Exit(code=1)
    try:
        clipboard.write_clipboard(result.restored_text)
    except clipboard.ClipboardError as error:
        _echo_json(
            {
                "ok": False,
                "action": "clipboard_restore_failed",
                "printed_phi": False,
                "reason": error.reason,
            }
        )
        raise typer.Exit(code=1) from error
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
    nlp_updates: dict[str, object] = {}
    nlp_enabled = os.environ.get("PHI_NLP_ENABLED", os.environ.get("PHI_NLP"))
    if nlp_enabled is not None:
        nlp_updates["enabled"] = _truthy(nlp_enabled)
    nlp_model = os.environ.get("PHI_NLP_MODEL")
    if nlp_model:
        nlp_updates["model"] = nlp_model
    nlp_min_score = os.environ.get("PHI_NLP_MIN_SCORE")
    if nlp_min_score:
        nlp_updates["min_score"] = float(nlp_min_score)
    if nlp_updates:
        policy.nlp = NlpPolicy(**(policy.nlp.model_dump() | nlp_updates))
    if nlp_enabled is None:
        policy.nlp = NlpPolicy(
            **(policy.nlp.model_dump() | {"enabled": nlp_model_available(policy.nlp)})
        )
    return policy


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _nlp_status(policy: PhiPolicy) -> dict[str, object]:
    return {
        "available": nlp_model_available(policy.nlp),
        "enabled": policy.nlp.enabled,
        "model": policy.nlp.model,
        "provider": policy.nlp.provider,
    }


def _scrub_failure_payload(action: str, result: Any) -> dict[str, object]:
    residual_findings = getattr(getattr(result, "audit", None), "residual_findings", [])
    residual_entity_types = sorted(
        {
            getattr(finding, "entity_type", "")
            for finding in residual_findings
            if getattr(finding, "entity_type", "")
        }
    )
    return {
        "ok": False,
        "action": action,
        "printed_phi": False,
        "reason": "audit_failed",
        "residual_count": len(residual_findings),
        "residual_entity_types": residual_entity_types,
    }


def _purge_expired(policy: PhiPolicy) -> list[str]:
    base_dir = Path(policy.mapping.base_dir)
    index = PlaceholderIndex(base_dir / "index.json")
    return SessionStore(base_dir, placeholder_index=index).purge_expired()


def _purge_all(policy: PhiPolicy) -> list[str]:
    base_dir = Path(policy.mapping.base_dir)
    index = PlaceholderIndex(base_dir / "index.json")
    return SessionStore(base_dir, placeholder_index=index).purge_all()


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

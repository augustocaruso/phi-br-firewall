from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from phi_br_core.cli.main import app
from phi_br_core.mapping import PlaceholderIndex
from phi_br_core.models import PhiAuditResult, PhiScrubResult, PhiScrubSummary
from typer.testing import CliRunner

runner = CliRunner()


def test_redact_and_restore_clipboard_without_printing_phi(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )

    redact = runner.invoke(app, ["redact"])

    assert redact.exit_code == 0
    redact_payload = json.loads(redact.stdout)
    assert redact_payload["ok"] is True
    assert redact_payload["action"] == "clipboard_redacted"
    assert redact_payload["printed_phi"] is False
    assert "[PACIENTE_001]" in clipboard["text"]
    assert "[CPF_001]" in clipboard["text"]
    assert "935.411.347-80" not in clipboard["text"]
    assert "935.411.347-80" not in redact.stdout
    assert "Joao da Silva" not in redact.stdout

    restore = runner.invoke(app, ["restore"])

    assert restore.exit_code == 0
    restore_payload = json.loads(restore.stdout)
    assert restore_payload == {
        "ok": True,
        "action": "clipboard_restored",
        "printed_phi": False,
    }
    assert clipboard["text"] == "Paciente Joao da Silva, CPF 935.411.347-80."
    assert "935.411.347-80" not in restore.stdout
    assert "Joao da Silva" not in restore.stdout


def test_restore_uses_active_index_for_multiple_placeholder_owners(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )

    first_redact = runner.invoke(app, ["redact"])
    assert first_redact.exit_code == 0
    first_redacted = clipboard["text"]

    clipboard["text"] = "Paciente Maria Souza, CPF 123.456.789-09."
    second_redact = runner.invoke(app, ["redact"])
    assert second_redact.exit_code == 0

    clipboard["text"] = first_redacted
    restore = runner.invoke(app, ["restore"])

    assert restore.exit_code == 0
    assert clipboard["text"] == "Paciente Joao da Silva, CPF 935.411.347-80."
    assert "935.411.347-80" not in restore.stdout


def test_status_prints_counts_without_phi(monkeypatch, tmp_path: Path) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )
    assert runner.invoke(app, ["redact"]).exit_code == 0

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["active_sessions"] == 1
    assert payload["placeholder_keys"] == 2
    assert "base_dir" not in payload
    assert "935.411.347-80" not in result.stdout
    assert "Joao da Silva" not in result.stdout


def test_check_reports_health_without_persisting_mapping(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["presidio_analyzer"] is True
    assert "BR_CPF" in payload["custom_recognizers"]
    assert list(tmp_path.rglob("mapping.json")) == []
    assert list(tmp_path.rglob("metadata.json")) == []
    assert not (tmp_path / "index.json").exists()


def test_purge_deletes_expired_sessions_and_cleans_index(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )
    assert runner.invoke(app, ["redact"]).exit_code == 0
    session_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    metadata_path = session_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["expires_at"] = (
        datetime.now(tz=UTC) - timedelta(seconds=1)
    ).isoformat()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = runner.invoke(app, ["purge"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["purged_sessions"] == 1
    assert session_dir.exists() is False
    assert PlaceholderIndex(tmp_path / "index.json").resolve(["PACIENTE_001", "CPF_001"]) == {}


def test_purge_all_deletes_active_sessions(monkeypatch, tmp_path: Path) -> None:
    clipboard = {"text": "Paciente Joao da Silva, CPF 935.411.347-80."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )
    assert runner.invoke(app, ["redact"]).exit_code == 0

    result = runner.invoke(app, ["purge", "--all"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["purged_sessions"] == 1
    assert [path for path in tmp_path.iterdir() if path.is_dir()] == []
    assert PlaceholderIndex(tmp_path / "index.json").resolve(["PACIENTE_001", "CPF_001"]) == {}


def test_restore_fails_closed_when_placeholder_owner_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente [PACIENTE_001], CPF [CPF_001]."}

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )

    result = runner.invoke(app, ["restore"])

    assert result.exit_code != 0
    assert clipboard["text"] == "Paciente [PACIENTE_001], CPF [CPF_001]."
    assert "PACIENTE_001" not in result.stdout
    assert "CPF_001" not in result.stdout


def test_restore_fails_closed_when_mapping_file_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente [PACIENTE_001]."}
    PlaceholderIndex(tmp_path / "index.json").assign("PACIENTE_001", "phi-missing")

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: clipboard.update(text=value),
    )

    result = runner.invoke(app, ["restore"])

    assert result.exit_code != 0
    assert clipboard["text"] == "Paciente [PACIENTE_001]."
    assert "PACIENTE_001" not in result.stdout


def test_redact_does_not_write_clipboard_when_scrub_fails(
    monkeypatch, tmp_path: Path
) -> None:
    clipboard = {"text": "Paciente Joao da Silva."}

    def unsafe_scrub(*_args: object, **_kwargs: object) -> PhiScrubResult:
        return PhiScrubResult(
            ok=False,
            action="scrub",
            scrubbed_text="Paciente Joao da Silva.",
            mapping_path="",
            session_id="",
            audit=PhiAuditResult(safe=False, residual_findings=[]),
            summary=PhiScrubSummary(entities_replaced=0, entity_types=[]),
        )

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr("phi_br_core.clipboard.read_clipboard", lambda: clipboard["text"])
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: pytest.fail(f"clipboard write should not happen: {value}"),
    )
    monkeypatch.setattr("phi_br_core.cli.main.scrub_text", unsafe_scrub)

    result = runner.invoke(app, ["redact"])

    assert result.exit_code != 0
    assert clipboard["text"] == "Paciente Joao da Silva."


def test_scrub_stdin_outputs_safe_json_without_printing_phi(
    monkeypatch, tmp_path: Path
) -> None:
    raw_text = "Paciente Joao da Silva, CPF 935.411.347-80."

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))

    result = runner.invoke(app, ["scrub-stdin", "--json"], input=raw_text)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "[PACIENTE_001]" in payload["scrubbed_text"]
    assert "[CPF_001]" in payload["scrubbed_text"]
    assert payload["session_id"]
    assert payload["summary"]["entities_replaced"] == 2
    assert "Joao da Silva" not in result.stdout
    assert "935.411.347-80" not in result.stdout


def test_api_redact_and_restore_use_stdin_stdout_without_clipboard(
    monkeypatch, tmp_path: Path
) -> None:
    raw_text = "Paciente Joao da Silva, CPF 935.411.347-80."

    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "phi_br_core.clipboard.read_clipboard",
        lambda: pytest.fail("clipboard read should not happen"),
    )
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda value: pytest.fail(f"clipboard write should not happen: {value}"),
    )

    redact = runner.invoke(app, ["api", "redact", "--json"], input=raw_text)

    assert redact.exit_code == 0
    redact_payload = json.loads(redact.stdout)
    assert redact_payload["ok"] is True
    assert redact_payload["action"] == "redact"
    assert "[PACIENTE_001]" in redact_payload["redacted_text"]
    assert "[CPF_001]" in redact_payload["redacted_text"]
    assert redact_payload["session_id"]
    assert redact_payload["summary"]["entities_replaced"] == 2
    assert "Joao da Silva" not in redact.stdout
    assert "935.411.347-80" not in redact.stdout

    restore = runner.invoke(
        app,
        ["api", "restore", "--json"],
        input=redact_payload["redacted_text"],
    )

    assert restore.exit_code == 0
    restore_payload = json.loads(restore.stdout)
    assert restore_payload == {
        "ok": True,
        "action": "restore",
        "restored_text": raw_text,
        "contains_phi": True,
        "sessions_used": [redact_payload["session_id"]],
    }


def test_api_restore_failure_does_not_print_placeholders(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PHI_BASE_DIR", str(tmp_path))

    result = runner.invoke(app, ["api", "restore", "--json"], input="Paciente [PACIENTE_001].")

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload == {
        "ok": False,
        "action": "restore_failed",
        "reason": "placeholder_owner_missing",
        "contains_phi": False,
    }
    assert "PACIENTE_001" not in result.stdout

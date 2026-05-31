from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from phi_br_core.cli.main import app
from phi_br_core.mapping import PlaceholderIndex
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
    assert "935.411.347-80" not in result.stdout
    assert "Joao da Silva" not in result.stdout


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

from __future__ import annotations

from pathlib import Path

from phi_br_core import PhiPolicy, redact_text, restore_active_text
from phi_br_core.mapping import PlaceholderIndex


def test_redact_and_restore_active_text_without_clipboard(
    monkeypatch, tmp_path: Path
) -> None:
    raw_text = "Paciente Joao da Silva, CPF 935.411.347-80."
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)

    monkeypatch.setattr(
        "phi_br_core.clipboard.read_clipboard",
        lambda: (_ for _ in ()).throw(AssertionError("clipboard read should not happen")),
    )
    monkeypatch.setattr(
        "phi_br_core.clipboard.write_clipboard",
        lambda _value: (_ for _ in ()).throw(
            AssertionError("clipboard write should not happen")
        ),
    )

    redacted = redact_text(raw_text, policy)
    restored = restore_active_text(redacted.redacted_text, policy)

    assert redacted.ok is True
    assert redacted.action == "redact"
    assert "[PACIENTE_001]" in redacted.redacted_text
    assert "[CPF_001]" in redacted.redacted_text
    assert "Joao da Silva" not in redacted.redacted_text
    assert "935.411.347-80" not in redacted.redacted_text
    assert restored.ok is True
    assert restored.action == "restore"
    assert restored.restored_text == raw_text
    assert restored.contains_phi is True
    assert restored.sessions_used == [redacted.session_id]


def test_restore_active_text_without_placeholders_is_noop(tmp_path: Path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)

    restored = restore_active_text("Sem placeholders.", policy)

    assert restored.ok is True
    assert restored.restored_text == "Sem placeholders."
    assert restored.contains_phi is False
    assert restored.sessions_used == []


def test_restore_active_text_fails_closed_when_placeholder_owner_missing(
    tmp_path: Path,
) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)

    restored = restore_active_text("Paciente [PACIENTE_001].", policy)

    assert restored.ok is False
    assert restored.reason == "placeholder_owner_missing"
    assert restored.restored_text == ""
    assert restored.contains_phi is False
    assert restored.sessions_used == []


def test_restore_active_text_fails_closed_when_mapping_file_missing(
    tmp_path: Path,
) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    PlaceholderIndex(tmp_path / "index.json").assign("PACIENTE_001", "phi-missing")

    restored = restore_active_text("Paciente [PACIENTE_001].", policy)

    assert restored.ok is False
    assert restored.reason == "mapping_missing"
    assert restored.restored_text == ""
    assert restored.contains_phi is False
    assert restored.sessions_used == []

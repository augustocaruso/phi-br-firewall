from __future__ import annotations

from pathlib import Path

import pytest
from phi_br_core import PhiPolicy, redact_text, restore_active_text
from phi_br_core.anonymizer import StablePlaceholderAnonymizer


def test_restore_active_text_restores_multiple_sessions_without_session_loop_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)

    first = redact_text("Paciente ANA SILVA.", policy)
    second = redact_text("Paciente BIA COSTA.", policy)

    def fail_restore(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("restore_active_text should not call per-session restore")

    monkeypatch.setattr(StablePlaceholderAnonymizer, "restore", fail_restore)

    restored = restore_active_text(
        "Primeira [PACIENTE_001|case=title]. Segunda [PACIENTE_002|case=title].",
        policy,
    )

    assert first.ok is True
    assert second.ok is True
    assert restored.ok is True
    assert restored.restored_text == "Primeira Ana Silva. Segunda Bia Costa."

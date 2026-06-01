from __future__ import annotations

import subprocess

from phi_br_core import clipboard


def test_clipboard_uses_wayland_socket_discovered_from_runtime_dir(monkeypatch, tmp_path) -> None:
    (tmp_path / "wayland-1").touch()
    calls: list[tuple[list[str], dict[str, str] | None, str | None]] = []

    def fake_which(command: str) -> str | None:
        if command in {"wl-paste", "wl-copy"}:
            return f"/usr/bin/{command}"
        return None

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool = False,
        text: bool,
        env: dict[str, str] | None = None,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, env, input))
        return subprocess.CompletedProcess(command, 0, stdout="Paciente Joao")

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(clipboard.shutil, "which", fake_which)
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    assert clipboard.read_clipboard() == "Paciente Joao"
    clipboard.write_clipboard("Paciente [PACIENTE_001]")

    assert calls[0][0] == ["wl-paste", "--type", "text"]
    assert calls[0][1] is not None
    assert calls[0][1]["XDG_RUNTIME_DIR"] == str(tmp_path)
    assert calls[0][1]["WAYLAND_DISPLAY"] == "wayland-1"
    assert calls[1][0] == ["wl-copy"]
    assert calls[1][2] == "Paciente [PACIENTE_001]"


def test_clipboard_unavailable_raises_structured_error(monkeypatch) -> None:
    monkeypatch.setattr(clipboard.shutil, "which", lambda _command: None)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)

    try:
        clipboard.read_clipboard()
    except clipboard.ClipboardError as error:
        assert error.reason == "clipboard_unavailable"
    else:
        raise AssertionError("expected ClipboardError")

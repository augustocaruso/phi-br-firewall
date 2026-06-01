from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class ClipboardError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def read_clipboard() -> str:
    provider = _provider()
    if provider is None:
        raise ClipboardError("clipboard_unavailable")

    try:
        completed = subprocess.run(
            provider.read_command,
            check=True,
            capture_output=True,
            text=True,
            env=provider.env,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ClipboardError("clipboard_read_failed") from error
    return completed.stdout


def write_clipboard(value: str) -> None:
    provider = _provider()
    if provider is None:
        raise ClipboardError("clipboard_unavailable")

    try:
        subprocess.run(provider.write_command, input=value, check=True, text=True, env=provider.env)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ClipboardError("clipboard_write_failed") from error


class _ClipboardProvider:
    def __init__(
        self,
        read_command: list[str],
        write_command: list[str],
        env: dict[str, str] | None = None,
    ) -> None:
        self.read_command = read_command
        self.write_command = write_command
        self.env = env


def _provider() -> _ClipboardProvider | None:
    if shutil.which("pbpaste") and shutil.which("pbcopy"):
        return _ClipboardProvider(["pbpaste"], ["pbcopy"])

    wayland_env = _wayland_env()
    if wayland_env and shutil.which("wl-paste") and shutil.which("wl-copy"):
        return _ClipboardProvider(["wl-paste", "--type", "text"], ["wl-copy"], wayland_env)

    x11_env = _x11_env()
    if x11_env and shutil.which("xclip"):
        return _ClipboardProvider(
            ["xclip", "-selection", "clipboard", "-out"],
            ["xclip", "-selection", "clipboard"],
            x11_env,
        )
    if x11_env and shutil.which("xsel"):
        return _ClipboardProvider(
            ["xsel", "--clipboard", "--output"],
            ["xsel", "--clipboard", "--input"],
            x11_env,
        )

    return None


def _wayland_env() -> dict[str, str] | None:
    env = os.environ.copy()
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    display = env.get("WAYLAND_DISPLAY")
    if runtime_dir and display and (Path(runtime_dir) / display).exists():
        return env

    uid_runtime = Path(f"/run/user/{os.getuid()}")
    candidate_runtime = Path(runtime_dir) if runtime_dir else uid_runtime
    if not candidate_runtime.exists():
        candidate_runtime = uid_runtime
    if not candidate_runtime.exists():
        return None

    for socket in sorted(candidate_runtime.glob("wayland-*")):
        if socket.name.endswith(".lock"):
            continue
        env["XDG_RUNTIME_DIR"] = str(candidate_runtime)
        env["WAYLAND_DISPLAY"] = socket.name
        return env
    return None


def _x11_env() -> dict[str, str] | None:
    env = os.environ.copy()
    if env.get("DISPLAY"):
        return env

    x11_dir = Path("/tmp/.X11-unix")
    if not x11_dir.exists():
        return None
    for socket in sorted(x11_dir.glob("X*")):
        suffix = socket.name.removeprefix("X")
        if suffix.isdigit():
            env["DISPLAY"] = f":{suffix}"
            return env
    return None

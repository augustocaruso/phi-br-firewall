from __future__ import annotations

import subprocess


def read_clipboard() -> str:
    completed = subprocess.run(["pbpaste"], check=True, capture_output=True, text=True)
    return completed.stdout


def write_clipboard(value: str) -> None:
    subprocess.run(["pbcopy"], input=value, check=True, text=True)

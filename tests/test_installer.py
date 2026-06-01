from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path


def test_installer_preserves_remote_spacy_wheel_filename(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fake_tool_dir = tmp_path / "phi-br-presidio-firewall" / "bin"
    fake_tool_dir.mkdir(parents=True)
    fake_python = fake_tool_dir / "python"
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)
    disabled_installer = tmp_path / "install-functions.sh"
    installer_source = (repo_root / "scripts" / "install.sh").read_text(encoding="utf-8")
    disabled_installer.write_text(installer_source.replace('\nmain "$@"\n', "\n"), encoding="utf-8")

    harness = textwrap.dedent(
        f"""
        set -euo pipefail

        uv() {{
          if [ "$1 $2" = "tool dir" ]; then
            printf '%s\\n' {str(tmp_path)!r}
            return 0
          fi
          if [ "$1 $2" = "pip install" ]; then
            wheel="${{@: -1}}"
            case "$wheel" in
              */pt_core_news_md-3.8.0-py3-none-any.whl) return 0 ;;
              *) printf 'invalid wheel filename: %s\\n' "$wheel" >&2; return 42 ;;
            esac
          fi
          printf 'unexpected uv call: %s\\n' "$*" >&2
          return 43
        }}

        curl() {{
          while [ "$#" -gt 0 ]; do
            if [ "$1" = "-o" ]; then
              shift
              printf 'fake wheel' > "$1"
              return 0
            fi
            shift
          done
          return 44
        }}

        source {str(disabled_installer)!r}
        SPACY_PT_MODEL_PACKAGE="https://github.com/explosion/spacy-models/releases/download/pt_core_news_md-3.8.0/pt_core_news_md-3.8.0-py3-none-any.whl"
        install_spacy_model
        """
    )

    result = subprocess.run(
        ["bash", "-lc", harness],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr

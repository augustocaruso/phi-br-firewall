from __future__ import annotations

from phi_br_core.cli.main import app
from typer.testing import CliRunner


def test_check_prints_baseline_ok() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert result.output == "phi baseline ok\n"

from __future__ import annotations

import json

from phi_br_core.cli.main import app
from typer.testing import CliRunner


def test_check_prints_baseline_ok() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["presidio_analyzer"] is True
    assert payload["presidio_anonymizer"] is True
    assert "BR_CPF" in payload["custom_recognizers"]

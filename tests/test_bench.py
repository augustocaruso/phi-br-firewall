from __future__ import annotations

import json
from pathlib import Path

from phi_br_core.bench import run_benchmark
from phi_br_core.cli.main import app
from phi_br_core.policy import PhiPolicy
from typer.testing import CliRunner

runner = CliRunner()


def test_run_benchmark_returns_safe_timing_shape(tmp_path: Path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)

    result = run_benchmark(policy, iterations=1)

    assert result["ok"] is True
    assert result["iterations"] == 1
    assert set(result["timings_ms"]) == {
        "analyzer_build_cold",
        "analyzer_build_cached",
        "scan",
        "scrub",
        "restore",
    }
    assert result["sample"]["characters"] > 0
    serialized = json.dumps(result)
    assert "JOAO" not in serialized
    assert "935.411.347-80" not in serialized
    assert not list(tmp_path.rglob("mapping.json"))


def test_bench_command_prints_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "phi_br_core.cli.main.run_benchmark",
        lambda policy, iterations: {
            "ok": True,
            "iterations": iterations,
            "sample": {"characters": 10},
            "timings_ms": {
                "scan": {"count": iterations, "min": 1.0, "avg": 1.0, "max": 1.0}
            },
        },
    )

    result = runner.invoke(app, ["bench", "--iterations", "2"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["iterations"] == 2

from __future__ import annotations

from collections.abc import Callable
from statistics import mean
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from phi_br_core.analyzer import build_analyzer, clear_analyzer_cache
from phi_br_core.api import redact_text, restore_active_text
from phi_br_core.core import scan_text, scrub_text
from phi_br_core.policy import PhiPolicy

_SAMPLE_TEXT = """\
Data do atendimento: 20/10/2024
Paciente JOAO DA SILVA, CPF 935.411.347-80.
Prontuario: 123456
Acompanhante: MARIA SILVA (mae)
Retorno em dezembro/2024.
"""


def run_benchmark(policy: PhiPolicy | None = None, iterations: int = 3) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be positive")

    active_policy = (policy or PhiPolicy()).model_copy(deep=True)
    with TemporaryDirectory(prefix="phi-bench-") as base_dir:
        active_policy.mapping.base_dir = base_dir

        clear_analyzer_cache()
        analyzer_build_cold = _measure(lambda: build_analyzer(active_policy), 1)
        analyzer_build_cached = _measure(
            lambda: build_analyzer(active_policy),
            iterations,
        )
        scan = _measure(lambda: scan_text(_SAMPLE_TEXT, active_policy), iterations)
        scrub = _measure(lambda: scrub_text(_SAMPLE_TEXT, active_policy), iterations)

        redacted = redact_text(_SAMPLE_TEXT, active_policy)
        if not redacted.ok:
            raise RuntimeError("benchmark redaction failed")
        restore = _measure(
            lambda: restore_active_text(redacted.redacted_text, active_policy),
            iterations,
        )

    return {
        "ok": True,
        "iterations": iterations,
        "sample": {"characters": len(_SAMPLE_TEXT), "lines": len(_SAMPLE_TEXT.splitlines())},
        "timings_ms": {
            "analyzer_build_cold": analyzer_build_cold,
            "analyzer_build_cached": analyzer_build_cached,
            "scan": scan,
            "scrub": scrub,
            "restore": restore,
        },
    }


def _measure(callback: Callable[[], object], iterations: int) -> dict[str, float | int]:
    durations_ms: list[float] = []
    for _ in range(iterations):
        started = perf_counter()
        callback()
        durations_ms.append((perf_counter() - started) * 1000)

    return {
        "count": iterations,
        "min": round(min(durations_ms), 3),
        "avg": round(mean(durations_ms), 3),
        "max": round(max(durations_ms), 3),
    }

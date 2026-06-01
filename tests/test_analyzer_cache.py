from __future__ import annotations

from phi_br_core.analyzer import build_analyzer, clear_analyzer_cache
from phi_br_core.policy import PhiPolicy


def test_build_analyzer_reuses_engine_for_equivalent_runtime_policy() -> None:
    clear_analyzer_cache()
    first_policy = PhiPolicy()
    second_policy = PhiPolicy()
    second_policy.mapping.base_dir = "/tmp/phi-other"

    first = build_analyzer(first_policy)
    second = build_analyzer(second_policy)

    assert first is second


def test_build_analyzer_uses_distinct_cache_entry_for_threshold_change() -> None:
    clear_analyzer_cache()

    default = build_analyzer(PhiPolicy(min_score=0.45))
    stricter = build_analyzer(PhiPolicy(min_score=0.75))

    assert default is not stricter

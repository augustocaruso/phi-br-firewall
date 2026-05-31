from __future__ import annotations

from phi_br_core.models import PhiFinding
from phi_br_core.spans import resolve_overlaps


def finding(entity_type: str, text: str, start: int, end: int, score: float) -> PhiFinding:
    return PhiFinding(entity_type=entity_type, text=text, start=start, end=end, score=score)


def test_resolve_overlaps_keeps_more_specific_entity() -> None:
    findings = [
        finding("BR_DATE", "12345", 7, 12, 0.99),
        finding("BR_CRM", "CRM-DF 12345", 0, 12, 0.85),
    ]

    resolved = resolve_overlaps(findings)

    assert [item.entity_type for item in resolved] == ["BR_CRM"]


def test_resolve_overlaps_keeps_containing_phi_span_to_avoid_partial_redaction() -> None:
    findings = [
        finding("BR_ADDRESS", "Rua A, 123, CEP 70000-000", 9, 34, 0.70),
        finding("BR_CEP", "70000-000", 25, 34, 0.95),
    ]

    resolved = resolve_overlaps(findings)

    assert [(item.entity_type, item.start, item.end) for item in resolved] == [
        ("BR_ADDRESS", 9, 34)
    ]


def test_resolve_overlaps_keeps_containing_same_entity_span_to_avoid_partial_redaction() -> None:
    findings = [
        finding("BR_CPF", "935.411.347-80", 4, 18, 0.70),
        finding("BR_CPF", "411.347-80", 8, 18, 0.95),
    ]

    resolved = resolve_overlaps(findings)

    assert [(item.start, item.end, item.score) for item in resolved] == [(4, 18, 0.70)]


def test_resolve_overlaps_uses_score_when_same_entity_spans_cross() -> None:
    findings = [
        finding("BR_CPF", "935.411.347", 4, 15, 0.70),
        finding("BR_CPF", "411.347-80", 8, 18, 0.95),
    ]

    resolved = resolve_overlaps(findings)

    assert [(item.start, item.end, item.score) for item in resolved] == [(8, 18, 0.95)]


def test_resolve_overlaps_uses_longer_span_when_specificity_and_score_match() -> None:
    findings = [
        finding("BR_CPF", "411.347-80", 8, 18, 0.95),
        finding("BR_CPF", "935.411.347-80", 4, 18, 0.95),
    ]

    resolved = resolve_overlaps(findings)

    assert [(item.start, item.end) for item in resolved] == [(4, 18)]


def test_resolve_overlaps_preserves_non_overlapping_spans_in_text_order() -> None:
    findings = [
        finding("BR_CPF", "935.411.347-80", 28, 42, 0.95),
        finding("BR_PATIENT_NAME", "Joao da Silva", 9, 22, 0.80),
    ]

    resolved = resolve_overlaps(findings)

    assert [item.entity_type for item in resolved] == ["BR_PATIENT_NAME", "BR_CPF"]

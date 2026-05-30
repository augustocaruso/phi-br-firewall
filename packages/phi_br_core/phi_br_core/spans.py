from __future__ import annotations

from phi_br_core.entities import ENTITY_SPECIFICITY
from phi_br_core.models import PhiFinding


def _overlaps(left: PhiFinding, right: PhiFinding) -> bool:
    return left.start < right.end and right.start < left.end


def _priority(finding: PhiFinding) -> tuple[int, float, int, int]:
    return (
        ENTITY_SPECIFICITY.get(finding.entity_type, 0),
        finding.score,
        finding.end - finding.start,
        -finding.start,
    )


def resolve_overlaps(findings: list[PhiFinding]) -> list[PhiFinding]:
    prioritized = sorted(findings, key=_priority, reverse=True)
    accepted: list[PhiFinding] = []

    for candidate in prioritized:
        if any(_overlaps(candidate, current) for current in accepted):
            continue
        accepted.append(candidate)

    return sorted(accepted, key=lambda finding: finding.start)

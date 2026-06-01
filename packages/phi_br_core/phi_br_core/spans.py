from __future__ import annotations

from phi_br_core.entities import ENTITY_SPECIFICITY
from phi_br_core.models import PhiFinding


def _overlaps(left: PhiFinding, right: PhiFinding) -> bool:
    return left.start < right.end and right.start < left.end


def _contains(left: PhiFinding, right: PhiFinding) -> bool:
    return left.start <= right.start and left.end >= right.end


def _priority(finding: PhiFinding) -> tuple[int, float, int, int]:
    return (
        ENTITY_SPECIFICITY.get(finding.entity_type, 0),
        finding.score,
        finding.end - finding.start,
        -finding.start,
    )


def _candidate_replaces_current(candidate: PhiFinding, current: PhiFinding) -> bool:
    if candidate.start == current.start and candidate.end == current.end:
        return _priority(candidate) > _priority(current)
    if _contains(candidate, current):
        return True
    if _contains(current, candidate):
        return False
    return _priority(candidate) > _priority(current)


def resolve_overlaps(findings: list[PhiFinding]) -> list[PhiFinding]:
    prioritized = sorted(findings, key=_priority, reverse=True)
    accepted: list[PhiFinding] = []

    for candidate in prioritized:
        conflicts = [current for current in accepted if _overlaps(candidate, current)]
        if not conflicts:
            accepted.append(candidate)
            continue
        if all(_candidate_replaces_current(candidate, current) for current in conflicts):
            accepted = [current for current in accepted if current not in conflicts]
            accepted.append(candidate)
            continue

    return sorted(accepted, key=lambda finding: finding.start)

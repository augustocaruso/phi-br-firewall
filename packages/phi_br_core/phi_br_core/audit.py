from __future__ import annotations

from phi_br_core.analyzer import build_analyzer
from phi_br_core.models import PhiAuditResult, PhiFinding
from phi_br_core.placeholders import PLACEHOLDER_PATTERN
from phi_br_core.policy import PhiPolicy
from phi_br_core.spans import resolve_overlaps
from phi_br_core.strict_audit import strict_audit_findings


def audit_text(text: str, policy: PhiPolicy) -> PhiAuditResult:
    audit_source = _mask_placeholders(text)
    analyzer = build_analyzer(policy)
    results = analyzer.analyze(
        text=audit_source,
        language=policy.language,
        score_threshold=policy.audit_threshold,
    )
    findings = [
        PhiFinding(
            entity_type=result.entity_type,
            text=text[result.start : result.end],
            start=result.start,
            end=result.end,
            score=float(result.score),
        )
        for result in results
    ]
    residual_findings = resolve_overlaps(
        [*findings, *strict_audit_findings(audit_source)]
    )
    return PhiAuditResult(safe=not residual_findings, residual_findings=residual_findings)


def _mask_placeholders(text: str) -> str:
    return PLACEHOLDER_PATTERN.sub(lambda match: " " * (match.end() - match.start()), text)

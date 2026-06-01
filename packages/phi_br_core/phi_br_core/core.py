from __future__ import annotations

from pathlib import Path

from phi_br_core.analyzer import build_analyzer
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.audit import audit_text
from phi_br_core.clinical_rendering import ClinicalReplacementRenderer
from phi_br_core.entities import ENTITY_TO_PLACEHOLDER_PREFIX
from phi_br_core.models import (
    PhiAuditResult,
    PhiFinding,
    PhiScanResult,
    PhiScrubResult,
    PhiScrubSummary,
)
from phi_br_core.policy import PhiPolicy
from phi_br_core.spans import resolve_overlaps


def scan_text(text: str, policy: PhiPolicy) -> PhiScanResult:
    analyzer = build_analyzer(policy)
    results = analyzer.analyze(
        text=text,
        language=policy.language,
        score_threshold=policy.min_score,
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
    return PhiScanResult(findings=resolve_overlaps(findings))


def scrub_text(text: str, policy: PhiPolicy) -> PhiScrubResult:
    scan = scan_text(text, policy)
    if not policy.mapping.persist:
        result = _scrub_without_persistence(text, scan.findings, policy)
        audit = audit_text(result.scrubbed_text, policy)
        if not audit.safe:
            repaired = _scrub_without_persistence(
                result.scrubbed_text,
                audit.residual_findings,
                policy,
            )
            repaired = _with_combined_summary(result, repaired)
            audit = audit_text(repaired.scrubbed_text, policy)
            return _apply_audit(repaired, audit)
        return _apply_audit(result, audit)

    anonymizer = StablePlaceholderAnonymizer(base_dir=policy.mapping.base_dir)
    result = anonymizer.scrub(text, scan.findings, source="core", policy=policy)
    audit = audit_text(result.scrubbed_text, policy)
    if not audit.safe:
        repaired = anonymizer.scrub_existing_session(
            text=result.scrubbed_text,
            findings=audit.residual_findings,
            session_id=result.session_id,
            mapping_path=result.mapping_path,
            policy=policy,
        )
        repaired = _with_combined_summary(result, repaired)
        audit = audit_text(repaired.scrubbed_text, policy)
        return _apply_audit(repaired, audit)
    return _apply_audit(result, audit)


def restore_text(text: str, mapping_path: str) -> str:
    mapping_file = Path(mapping_path)
    anonymizer = StablePlaceholderAnonymizer(base_dir=mapping_file.parent.parent)
    return anonymizer.restore(text, mapping_file)


def _apply_audit(result: PhiScrubResult, audit: PhiAuditResult) -> PhiScrubResult:
    safe_audit = audit if audit.safe else _without_residual_text(audit)
    return result.model_copy(
        update={
            "audit": safe_audit,
            "ok": safe_audit.safe,
            "scrubbed_text": result.scrubbed_text if safe_audit.safe else "",
        }
    )


def _without_residual_text(audit: PhiAuditResult) -> PhiAuditResult:
    return audit.model_copy(
        update={
            "residual_findings": [
                finding.model_copy(update={"text": ""}) for finding in audit.residual_findings
            ]
        }
    )


def _with_combined_summary(
    initial: PhiScrubResult, repaired: PhiScrubResult
) -> PhiScrubResult:
    return repaired.model_copy(
        update={
            "summary": PhiScrubSummary(
                entities_replaced=(
                    initial.summary.entities_replaced
                    + repaired.summary.entities_replaced
                ),
                entity_types=sorted(
                    set(initial.summary.entity_types) | set(repaired.summary.entity_types)
                ),
            )
        }
    )


def _scrub_without_persistence(
    text: str, findings: list[PhiFinding], policy: PhiPolicy
) -> PhiScrubResult:
    accepted = resolve_overlaps(findings)
    renderer = ClinicalReplacementRenderer(text, accepted, policy)
    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    replacements: list[tuple[PhiFinding, str]] = []
    scrubbed_text = text

    for finding in accepted:
        placeholder_key = by_value.get((finding.entity_type, finding.text))
        if placeholder_key is None:
            prefix = ENTITY_TO_PLACEHOLDER_PREFIX.get(finding.entity_type, finding.entity_type)
            next_count = counters.get(prefix, 0) + 1
            counters[prefix] = next_count
            placeholder_key = f"{prefix}_{next_count:03d}"
            by_value[(finding.entity_type, finding.text)] = placeholder_key
        replacements.append((finding, renderer.render(placeholder_key, finding).text))

    for finding, replacement in sorted(
        replacements, key=lambda item: item[0].start, reverse=True
    ):
        scrubbed_text = (
            scrubbed_text[: finding.start]
            + replacement
            + scrubbed_text[finding.end :]
        )

    return PhiScrubResult(
        ok=True,
        action="scrub",
        scrubbed_text=scrubbed_text,
        mapping_path="",
        session_id="",
        audit=PhiAuditResult(safe=True, residual_findings=[]),
        summary=PhiScrubSummary(
            entities_replaced=len(accepted),
            entity_types=sorted({finding.entity_type for finding in accepted}),
        ),
    )

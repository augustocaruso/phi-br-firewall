from __future__ import annotations

from pathlib import Path

from phi_br_core.analyzer import build_analyzer
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.audit import audit_text
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
        result = _scrub_without_persistence(text, scan.findings)
        audit = audit_text(result.scrubbed_text, policy)
        return _apply_audit(result, audit)

    anonymizer = StablePlaceholderAnonymizer(base_dir=policy.mapping.base_dir)
    result = anonymizer.scrub(text, scan.findings, source="core")
    audit = audit_text(result.scrubbed_text, policy)
    return _apply_audit(result, audit)


def restore_text(text: str, mapping_path: str) -> str:
    mapping_file = Path(mapping_path)
    anonymizer = StablePlaceholderAnonymizer(base_dir=mapping_file.parent.parent)
    return anonymizer.restore(text, mapping_file)


def _apply_audit(result: PhiScrubResult, audit: PhiAuditResult) -> PhiScrubResult:
    return result.model_copy(
        update={
            "audit": audit,
            "ok": audit.safe,
            "scrubbed_text": result.scrubbed_text if audit.safe else "",
        }
    )


def _scrub_without_persistence(text: str, findings: list[PhiFinding]) -> PhiScrubResult:
    accepted = resolve_overlaps(findings)
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
        replacements.append((finding, placeholder_key))

    for finding, placeholder_key in sorted(
        replacements, key=lambda item: item[0].start, reverse=True
    ):
        scrubbed_text = (
            scrubbed_text[: finding.start]
            + f"[{placeholder_key}]"
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

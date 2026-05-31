from __future__ import annotations

from pathlib import Path

from phi_br_core.analyzer import build_analyzer
from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.audit import audit_text
from phi_br_core.models import PhiFinding, PhiScanResult, PhiScrubResult
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
    anonymizer = StablePlaceholderAnonymizer(base_dir=policy.mapping.base_dir)
    result = anonymizer.scrub(text, scan.findings, source="core")
    audit = audit_text(result.scrubbed_text, policy)
    result.audit = audit
    result.ok = audit.safe
    return result


def restore_text(text: str, mapping_path: str) -> str:
    mapping_file = Path(mapping_path)
    anonymizer = StablePlaceholderAnonymizer(base_dir=mapping_file.parent.parent)
    return anonymizer.restore(text, mapping_file)

from __future__ import annotations

from pydantic import BaseModel


class PhiFinding(BaseModel):
    entity_type: str
    text: str
    start: int
    end: int
    score: float


class PhiScanResult(BaseModel):
    findings: list[PhiFinding]


class PhiAuditResult(BaseModel):
    safe: bool
    residual_findings: list[PhiFinding]


class PhiScrubSummary(BaseModel):
    entities_replaced: int
    entity_types: list[str]


class PhiScrubResult(BaseModel):
    ok: bool
    action: str
    scrubbed_text: str
    mapping_path: str
    session_id: str
    audit: PhiAuditResult
    summary: PhiScrubSummary

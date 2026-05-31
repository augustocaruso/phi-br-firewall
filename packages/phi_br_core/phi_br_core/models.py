from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class PhiFinding(BaseModel):
    entity_type: str
    text: str
    start: int = Field(ge=0)
    end: int
    score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_positive_span(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


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


class PhiRedactResult(BaseModel):
    ok: bool
    action: str = "redact"
    redacted_text: str = ""
    session_id: str = ""
    summary: PhiScrubSummary = Field(
        default_factory=lambda: PhiScrubSummary(entities_replaced=0, entity_types=[])
    )
    reason: str = ""


class PhiRestoreResult(BaseModel):
    ok: bool
    action: str = "restore"
    restored_text: str = ""
    contains_phi: bool = False
    sessions_used: list[str] = Field(default_factory=list)
    reason: str = ""

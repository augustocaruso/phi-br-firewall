from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MappingPolicy(BaseModel):
    persist: bool = True
    base_dir: str = ".tmp/phi"
    delete_by_default: bool = True
    encrypt_future: bool = True


class DatePolicy(BaseModel):
    strategy: Literal["placeholder", "shift", "preserve_relative"] = "placeholder"
    preserve_relative_dates: bool = True


class AgePolicy(BaseModel):
    strategy: Literal["placeholder", "age_band", "preserve"] = "age_band"


class SessionPolicy(BaseModel):
    ttl_hours: int = 24
    purge_expired_on_start: bool = True
    max_sessions: int = 20
    delete_by_default: bool = True


class PhiPolicy(BaseModel):
    mode: Literal["pseudonymize", "redact", "audit_only"] = "pseudonymize"
    fail_closed: bool = True
    language: str = "pt"
    min_score: float = 0.45
    audit_threshold: float = 0.35
    mapping: MappingPolicy = Field(default_factory=MappingPolicy)
    dates: DatePolicy = Field(default_factory=DatePolicy)
    ages: AgePolicy = Field(default_factory=AgePolicy)
    sessions: SessionPolicy = Field(default_factory=SessionPolicy)

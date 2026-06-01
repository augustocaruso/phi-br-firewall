from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MappingPolicy(PolicyModel):
    persist: bool = True
    base_dir: str = ".tmp/phi"
    delete_by_default: bool = True
    encrypt_future: bool = True


class DatePolicy(PolicyModel):
    strategy: Literal["placeholder", "shift", "preserve_relative"] = "preserve_relative"
    preserve_relative_dates: bool = True


class AgePolicy(PolicyModel):
    strategy: Literal["placeholder", "age_band", "preserve"] = "age_band"


class NlpPolicy(PolicyModel):
    enabled: bool = False
    provider: Literal["spacy"] = "spacy"
    model: str = "pt_core_news_md"
    min_score: float = Field(default=0.70, ge=0, le=1)


class SessionPolicy(PolicyModel):
    ttl_hours: int = Field(default=24, gt=0)
    purge_expired_on_start: bool = True
    max_sessions: int = Field(default=20, gt=0)
    delete_by_default: bool = True


class PhiPolicy(PolicyModel):
    mode: Literal["pseudonymize", "redact", "audit_only"] = "pseudonymize"
    fail_closed: bool = True
    language: str = "pt"
    min_score: float = Field(default=0.45, ge=0, le=1)
    audit_threshold: float = Field(default=0.35, ge=0, le=1)
    mapping: MappingPolicy = Field(default_factory=MappingPolicy)
    dates: DatePolicy = Field(default_factory=DatePolicy)
    ages: AgePolicy = Field(default_factory=AgePolicy)
    nlp: NlpPolicy = Field(default_factory=NlpPolicy)
    sessions: SessionPolicy = Field(default_factory=SessionPolicy)

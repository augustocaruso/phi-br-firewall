from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from phi_br_core.date_formatting import parse_phi_date
from phi_br_core.entities import (
    BR_AGE,
    BR_DATE,
    BR_FAMILY_MEMBER_NAME,
    BR_HEALTHCARE_PROFESSIONAL_NAME,
    BR_INSTITUTION,
    BR_PATIENT_NAME,
)
from phi_br_core.formatting import detect_text_case
from phi_br_core.models import PhiFinding
from phi_br_core.placeholders import Placeholder, serialize_placeholder
from phi_br_core.policy import PhiPolicy

_YEAR_RE = re.compile(r"(\d{1,3})\s+anos?", re.IGNORECASE)
_MONTH_AGE_RE = re.compile(r"(\d{1,2})\s+m[eê]s(?:es)?", re.IGNORECASE)
_BIRTH_DATE_CONTEXT_RE = re.compile(
    r"(?:data\s+de\s+nascimento|nascimento|dn|nascid[ao])"
    r"\s*(?::|-)?\s*(?:em\s*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RenderedReplacement:
    text: str
    public_meta: dict[str, str]
    private_meta: dict[str, str]


class ClinicalReplacementRenderer:
    def __init__(self, text: str, findings: list[PhiFinding], policy: PhiPolicy) -> None:
        self.text = text
        self.policy = policy
        self.anchor_date = self._find_anchor_date(findings)

    def render(self, placeholder_key: str, finding: PhiFinding) -> RenderedReplacement:
        public_meta: dict[str, str] = {}
        private_meta: dict[str, str] = {}

        if finding.entity_type == BR_AGE and self.policy.ages.strategy == "age_band":
            age_band = _age_band(finding.text)
            if age_band is not None:
                public_meta = {"kind": "age", "band": age_band, "src": "exact"}
                return _rendered(placeholder_key, public_meta, private_meta)

        if (
            finding.entity_type == BR_DATE
            and self.policy.dates.strategy == "preserve_relative"
        ):
            public_meta, private_meta = self._date_metadata(finding)
            return _rendered(placeholder_key, public_meta, private_meta)

        if finding.entity_type in _NAME_ROLES:
            public_meta = _name_metadata(finding.text, _NAME_ROLES[finding.entity_type])
            return _rendered(placeholder_key, public_meta, private_meta)

        if finding.entity_type == BR_INSTITUTION:
            public_meta = _institution_metadata(finding.text)
            return _rendered(placeholder_key, public_meta, private_meta)

        return _rendered(placeholder_key, public_meta, private_meta)

    def _find_anchor_date(self, findings: list[PhiFinding]) -> date | None:
        for finding in findings:
            if finding.entity_type != BR_DATE or self._is_birth_date(finding):
                continue
            parsed = parse_phi_date(finding.text)
            if parsed is not None:
                return parsed.value
        return None

    def _date_metadata(self, finding: PhiFinding) -> tuple[dict[str, str], dict[str, str]]:
        role = "birth" if self._is_birth_date(finding) else "event"
        private_meta: dict[str, str] = {}

        parsed = parse_phi_date(finding.text)
        rel: str | None = None
        if parsed is not None:
            private_meta = {
                "gran": parsed.granularity,
                "iso": parsed.value.isoformat(),
                "src_fmt": parsed.source_format,
            }

        if self._is_birth_date(finding) or parsed is None or self.anchor_date is None:
            public_meta = {"kind": "date", "role": role}
            if parsed is not None:
                public_meta["gran"] = parsed.granularity
                public_meta["src_fmt"] = parsed.source_format
            return public_meta, private_meta

        delta_months = _month_delta(self.anchor_date, parsed.value)
        if delta_months == 0:
            rel = "T0"
        else:
            sign = "+" if delta_months > 0 else "-"
            rel = f"T{sign}{abs(delta_months)}m"

        public_meta = {
            "kind": "date",
            "role": role,
            "rel": rel,
            "gran": parsed.granularity,
            "src_fmt": parsed.source_format,
        }
        return public_meta, private_meta

    def _is_birth_date(self, finding: PhiFinding) -> bool:
        context = self.text[max(0, finding.start - 80) : finding.start].lower()
        return _BIRTH_DATE_CONTEXT_RE.search(context) is not None


_NAME_ROLES = {
    BR_PATIENT_NAME: "patient",
    BR_FAMILY_MEMBER_NAME: "family",
    BR_HEALTHCARE_PROFESSIONAL_NAME: "professional",
}


def _rendered(
    placeholder_key: str,
    public_meta: dict[str, str],
    private_meta: dict[str, str],
) -> RenderedReplacement:
    return RenderedReplacement(
        text=serialize_placeholder(Placeholder(key=placeholder_key, public_meta=public_meta)),
        public_meta=public_meta,
        private_meta=private_meta,
    )


def _name_metadata(value: str, role: str) -> dict[str, str]:
    return {
        "kind": "name",
        "role": role,
        "case": detect_text_case(value),
        "form": "full" if len(value.split()) > 1 else "single",
    }


def _institution_metadata(value: str) -> dict[str, str]:
    detected_case = detect_text_case(value)
    form = "acronym" if detected_case == "upper" and " " not in value.strip() else "name"
    return {"kind": "institution", "case": detected_case, "form": form}


def _month_delta(anchor: date, value: date) -> int:
    return (value.year - anchor.year) * 12 + value.month - anchor.month


def _age_band(value: str) -> str | None:
    years_match = _YEAR_RE.search(value)
    months_match = _MONTH_AGE_RE.search(value)
    years = int(years_match.group(1)) if years_match else 0
    months = int(months_match.group(1)) if months_match else 0
    if not years_match and not months_match:
        return None

    total_months = years * 12 + months
    if total_months < 1:
        return "recem-nascido"
    if total_months < 24:
        return "lactente"
    if total_months < 72:
        return "pre-escolar"
    if total_months < 144:
        return "escolar"
    if total_months < 216:
        return "adolescente"
    if total_months < 480:
        return "adulto jovem"
    if total_months < 720:
        return "adulto"
    return "idoso"

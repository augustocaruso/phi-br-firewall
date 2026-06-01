from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from phi_br_core.date_formatting import ParsedPhiDate, parse_phi_date
from phi_br_core.entities import (
    BR_AGE,
    BR_DATE,
    BR_FAMILY_MEMBER_NAME,
    BR_HEALTHCARE_PROFESSIONAL_NAME,
    BR_INSTITUTION,
    BR_PATIENT_NAME,
    BR_PERSON_NAME,
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
_PROFESSIONAL_RESIDENT_RE = re.compile(r"\bR[1-6]\b", re.IGNORECASE)
_PROFESSIONAL_STUDENT_RE = re.compile(
    r"\b(?:estudante\s+de\s+medicina|acad[eê]mic[oa](?:\s+de\s+medicina)?)\b",
    re.IGNORECASE,
)
_PROFESSIONAL_INTERN_RE = re.compile(r"\bintern[oa]\b", re.IGNORECASE)
_NAME_TOKEN_RE = re.compile(
    r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-Za-zÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç]+"
)
_NON_NAME_TOKENS = {
    "a",
    "ao",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "dr",
    "dra",
    "drª",
    "drº",
    "doutor",
    "doutora",
    "medica",
    "médica",
    "medico",
    "médico",
    "pela",
    "pelo",
    "prof",
    "professor",
    "professora",
}


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

        parsed = parse_phi_date(finding.text, self.anchor_date)
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

        rel = _relative_date_label(self.anchor_date, parsed)

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
    BR_PERSON_NAME: "person",
}


def _rendered(
    placeholder_key: str,
    public_meta: dict[str, str],
    private_meta: dict[str, str],
) -> RenderedReplacement:
    return RenderedReplacement(
        text=_compact_placeholder_text(placeholder_key, public_meta),
        public_meta=public_meta,
        private_meta=private_meta,
    )


def _compact_placeholder_text(placeholder_key: str, public_meta: dict[str, str]) -> str:
    label = _compact_label(public_meta)
    if label is None:
        return serialize_placeholder(Placeholder(key=placeholder_key))
    return f"[{placeholder_key}:{label}]"


def _compact_label(public_meta: dict[str, str]) -> str | None:
    if public_meta.get("kind") == "date":
        fmt = _compact_date_format(public_meta.get("src_fmt", ""))
        if public_meta.get("role") == "birth":
            return _join_label_parts("birth", fmt)
        return _join_label_parts(public_meta.get("rel") or "data", fmt)
    if public_meta.get("kind") == "age":
        return _slug(public_meta.get("band", ""))
    if public_meta.get("kind") == "name":
        form = public_meta.get("form", "")
        case = public_meta.get("case", "")
        return _join_label_parts(form, case)
    return None


def _name_metadata(value: str, role: str) -> dict[str, str]:
    return {
        "kind": "name",
        "role": role,
        "case": detect_text_case(value),
        "form": _name_form(value, role),
    }


def _name_form(value: str, role: str) -> str:
    if role == "professional":
        if _PROFESSIONAL_RESIDENT_RE.search(value):
            return "resident"
        if _PROFESSIONAL_STUDENT_RE.search(value):
            return "student"
        if _PROFESSIONAL_INTERN_RE.search(value):
            return "intern"

    name_tokens = [
        token
        for token in _NAME_TOKEN_RE.findall(value)
        if token.lower().rstrip(".") not in _NON_NAME_TOKENS
    ]
    return "full" if len(name_tokens) > 1 else "first"


def _institution_metadata(value: str) -> dict[str, str]:
    detected_case = detect_text_case(value)
    form = "acronym" if detected_case == "upper" and " " not in value.strip() else "name"
    return {"kind": "institution", "case": detected_case, "form": form}


def _join_label_parts(*parts: str | None) -> str | None:
    clean_parts = [part for part in parts if part]
    if not clean_parts:
        return None
    return "/".join(clean_parts)


def _compact_date_format(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace(" ", "-")


def _slug(value: str) -> str | None:
    normalized = "-".join(value.strip().lower().split())
    return normalized or None


def _month_delta(anchor: date, value: date) -> int:
    return (value.year - anchor.year) * 12 + value.month - anchor.month


def _relative_date_label(anchor: date, parsed: ParsedPhiDate) -> str:
    if parsed.granularity == "year":
        delta_years = parsed.value.year - anchor.year
        if delta_years == 0:
            return "T0"
        sign = "+" if delta_years > 0 else "-"
        return f"T{sign}{abs(delta_years)}a"

    delta_months = _month_delta(anchor, parsed.value)
    if delta_months == 0:
        return "T0"
    sign = "+" if delta_months > 0 else "-"
    return f"T{sign}{abs(delta_months)}m"


def _age_band(value: str) -> str | None:
    years_match = _YEAR_RE.search(value)
    months_match = _MONTH_AGE_RE.search(value)
    years = int(years_match.group(1)) if years_match else 0
    months = int(months_match.group(1)) if months_match else 0
    if not years_match and not months_match:
        return None

    total_months = years * 12 + months
    if total_months < 1:
        return "newborn"
    if total_months < 24:
        return "infant"
    if total_months < 72:
        return "preschool"
    if total_months < 144:
        return "school-age"
    if total_months < 216:
        return "adolescent"
    if total_months < 480:
        return "young-adult"
    if total_months < 720:
        return "adult"
    return "older-adult"

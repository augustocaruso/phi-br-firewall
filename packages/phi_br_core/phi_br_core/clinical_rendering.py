from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from phi_br_core.entities import BR_AGE, BR_DATE
from phi_br_core.models import PhiFinding
from phi_br_core.policy import PhiPolicy

_MONTHS = {
    "jan": 1,
    "janeiro": 1,
    "fev": 2,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abr": 4,
    "abril": 4,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "jul": 7,
    "julho": 7,
    "ago": 8,
    "agosto": 8,
    "set": 9,
    "setembro": 9,
    "out": 10,
    "outubro": 10,
    "nov": 11,
    "novembro": 11,
    "dez": 12,
    "dezembro": 12,
}
_MONTH_PATTERN = (
    r"jan(?:eiro)?|fev(?:ereiro)?|mar[cç]o|abr(?:il)?|mai(?:o)?|jun(?:ho)?|"
    r"jul(?:ho)?|ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|dez(?:embro)?"
)
_BR_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_PATTERN})[/-](\d{{2,4}})\b", re.IGNORECASE)
_TEXT_MONTH_RE = re.compile(
    rf"\b(?:(\d{{1,2}})\s+de\s+)?({_MONTH_PATTERN})(?:\s+de)?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"(\d{1,3})\s+anos?", re.IGNORECASE)
_MONTH_AGE_RE = re.compile(r"(\d{1,2})\s+m[eê]s(?:es)?", re.IGNORECASE)
_BIRTH_DATE_CONTEXT_RE = re.compile(
    r"(?:data\s+de\s+nascimento|nascimento|dn|nascid[ao])"
    r"\s*(?::|-)?\s*(?:em\s*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedDate:
    value: date


class ClinicalReplacementRenderer:
    def __init__(self, text: str, findings: list[PhiFinding], policy: PhiPolicy) -> None:
        self.text = text
        self.policy = policy
        self.anchor_date = self._find_anchor_date(findings)

    def render(self, placeholder_key: str, finding: PhiFinding) -> str:
        if finding.entity_type == BR_AGE and self.policy.ages.strategy == "age_band":
            age_band = _age_band(finding.text)
            if age_band is not None:
                return f"[{placeholder_key}: {age_band}]"

        if (
            finding.entity_type == BR_DATE
            and self.policy.dates.strategy == "preserve_relative"
        ):
            return f"[{placeholder_key}: {self._date_label(finding)}]"

        return f"[{placeholder_key}]"

    def _find_anchor_date(self, findings: list[PhiFinding]) -> date | None:
        for finding in findings:
            if finding.entity_type != BR_DATE or self._is_birth_date(finding):
                continue
            parsed = _parse_date(finding.text)
            if parsed is not None:
                return parsed.value
        return None

    def _date_label(self, finding: PhiFinding) -> str:
        if self._is_birth_date(finding):
            return "nascimento"

        parsed = _parse_date(finding.text)
        if parsed is None or self.anchor_date is None:
            return "data"

        delta_months = _month_delta(self.anchor_date, parsed.value)
        if delta_months == 0:
            return "T0"
        sign = "+" if delta_months > 0 else "-"
        return f"T{sign}{abs(delta_months)}m"

    def _is_birth_date(self, finding: PhiFinding) -> bool:
        context = self.text[max(0, finding.start - 80) : finding.start].lower()
        return _BIRTH_DATE_CONTEXT_RE.search(context) is not None


def _parse_date(value: str) -> ParsedDate | None:
    stripped = value.strip()
    if match := _ISO_DATE_RE.search(stripped):
        return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    if match := _BR_NUMERIC_DATE_RE.search(stripped):
        year = _normalize_year(match.group(3))
        return _safe_date(year, int(match.group(2)), int(match.group(1)))

    if match := _MONTH_YEAR_RE.search(stripped):
        year = _normalize_year(match.group(2))
        month = _month_number(match.group(1))
        return _safe_date(year, month, 1) if month is not None else None

    if match := _TEXT_MONTH_RE.search(stripped):
        day = int(match.group(1) or "1")
        month = _month_number(match.group(2))
        return _safe_date(int(match.group(3)), month, day) if month is not None else None

    return None


def _safe_date(year: int, month: int, day: int) -> ParsedDate | None:
    try:
        return ParsedDate(date(year, month, day))
    except ValueError:
        return None


def _normalize_year(value: str) -> int:
    year = int(value)
    return 2000 + year if year < 100 else year


def _month_number(value: str) -> int | None:
    key = value.lower().replace("ç", "c")
    return _MONTHS.get(key)


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

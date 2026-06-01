from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from babel.dates import format_date

DateGranularity = Literal["day", "month", "year"]

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
_BR_PARTIAL_DAY_MONTH_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_PATTERN})[/-](\d{{2,4}})\b", re.IGNORECASE)
_TEXT_MONTH_RE = re.compile(
    rf"\b(?:(\d{{1,2}})\s+de\s+)?({_MONTH_PATTERN})(?:\s+de)?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_STANDALONE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


@dataclass(frozen=True)
class ParsedPhiDate:
    value: date
    granularity: DateGranularity
    source_format: str


def parse_phi_date(value: str, reference_date: date | None = None) -> ParsedPhiDate | None:
    stripped = value.strip()
    if match := _ISO_DATE_RE.search(stripped):
        return _safe_date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            "day",
            "yyyy-mm-dd",
        )

    if match := _BR_NUMERIC_DATE_RE.search(stripped):
        year_text = match.group(3)
        year = _normalize_year(year_text)
        source_format = "dd/mm/yy" if len(year_text) == 2 else "dd/mm/yyyy"
        return _safe_date(year, int(match.group(2)), int(match.group(1)), "day", source_format)

    if reference_date is not None and (match := _BR_PARTIAL_DAY_MONTH_RE.search(stripped)):
        day = int(match.group(1))
        month = int(match.group(2))
        year = _infer_partial_date_year(day, month, reference_date)
        return _safe_date(year, month, day, "day", "dd/mm")

    if match := _MONTH_YEAR_RE.search(stripped):
        year_text = match.group(2)
        year = _normalize_year(year_text)
        month_number = _month_number(match.group(1))
        if month_number is None:
            return None
        source_format = "month/yy" if len(year_text) == 2 else "month/yyyy"
        return _safe_date(year, month_number, 1, "month", source_format)

    if match := _TEXT_MONTH_RE.search(stripped):
        day_text = match.group(1)
        month_number = _month_number(match.group(2))
        if month_number is None:
            return None
        granularity: DateGranularity = "day" if day_text else "month"
        source_format = "d month yyyy" if day_text else "month yyyy"
        return _safe_date(
            int(match.group(3)),
            month_number,
            int(day_text or "1"),
            granularity,
            source_format,
        )

    if match := _STANDALONE_YEAR_RE.fullmatch(stripped):
        return _safe_date(int(match.group(1)), 1, 1, "year", "yyyy")

    return None


def format_date_pt_br(
    value: date,
    format_name: str,
    granularity: DateGranularity = "day",
) -> str:
    if format_name == "original":
        return value.isoformat()
    if format_name == "iso":
        return value.isoformat()
    if format_name == "short":
        return str(format_date(value, "dd/MM/yyyy", locale="pt_BR"))
    if format_name == "medium":
        return str(format_date(value, "medium", locale="pt_BR"))
    if format_name == "long":
        if granularity == "year":
            return str(format_date(value, "y", locale="pt_BR"))
        if granularity == "month":
            return str(format_date(value, "MMMM 'de' y", locale="pt_BR"))
        return str(format_date(value, "long", locale="pt_BR"))
    if format_name == "month_year":
        if granularity == "year":
            return str(format_date(value, "y", locale="pt_BR"))
        return str(format_date(value, "MMMM 'de' y", locale="pt_BR"))
    raise ValueError("invalid date render option")


def _safe_date(
    year: int,
    month: int,
    day: int,
    granularity: DateGranularity,
    source_format: str,
) -> ParsedPhiDate | None:
    try:
        return ParsedPhiDate(date(year, month, day), granularity, source_format)
    except ValueError:
        return None


def _normalize_year(value: str) -> int:
    year = int(value)
    return 2000 + year if year < 100 else year


def _infer_partial_date_year(day: int, month: int, reference_date: date) -> int:
    candidates: list[date] = []
    for year in (reference_date.year - 1, reference_date.year, reference_date.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return reference_date.year
    return min(candidates, key=lambda candidate: abs(candidate - reference_date)).year


def _month_number(value: str) -> int | None:
    key = value.lower().replace("ç", "c")
    return _MONTHS.get(key)

from __future__ import annotations

import re

from phi_br_core.entities import (
    BR_ADDRESS,
    BR_CONTEXTUAL_IDENTIFIER,
    BR_DATE,
    BR_FAMILY_MEMBER_NAME,
    BR_RG,
)
from phi_br_core.models import PhiFinding

_RG_RE = re.compile(
    r"\bRG\s*(?:n[ºo.]?\s*)?[:#-]?\s*(?P<value>\d{1,2}\.?\d{3}\.?\d{3}(?:[-.]?[0-9Xx]{1,2})?)\b",
    flags=re.IGNORECASE,
)
_LABELED_IDENTIFIER_RE = re.compile(
    r"\b(?:n[ºo.]?\s*)?(?:SES|protocolo|senha)\s*[:#-]?\s*(?P<value>[A-Z]{0,4}\d{4,12})\b",
    flags=re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?P<value>(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4})|"
    r"(?:(?:[0-2]?\d|3[01])/(?:0[1-9]|1[0-2]))|"
    r"(?:(?:19|20)\d{2}))\b"
)
_NAME = (
    r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-Za-zÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç]+"
    r"(?:\s+(?:da|de|do|das|dos|e)\s+"
    r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-Za-zÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç]+"
    r"|\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-Za-zÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç]+){1,4}"
)
_FAMILY_FIELD_RE = re.compile(
    rf"(?im)^\s*(?:filia[cç][aã]o|irm[aã]os?|contatos?)\s*:\s*(?P<value>[^\n\r]*?(?P<name>{_NAME}))"
)
_LOCATION_FIELD_RE = re.compile(
    r"(?im)^\s*(?:naturalidade|proced[eê]ncia)\s*:\s*(?P<value>(?!\[)[^\n\r]+)"
)


def strict_audit_findings(text: str) -> list[PhiFinding]:
    findings: list[PhiFinding] = []
    findings.extend(_find_labeled_values(text, _RG_RE, BR_RG, 0.95))
    findings.extend(
        _find_labeled_values(text, _LABELED_IDENTIFIER_RE, BR_CONTEXTUAL_IDENTIFIER, 0.92)
    )
    findings.extend(_find_labeled_values(text, _DATE_RE, BR_DATE, 0.80))
    findings.extend(_find_labeled_values(text, _FAMILY_FIELD_RE, BR_FAMILY_MEMBER_NAME, 0.82))
    findings.extend(_find_labeled_values(text, _LOCATION_FIELD_RE, BR_ADDRESS, 0.78))
    return findings


def _find_labeled_values(
    text: str,
    pattern: re.Pattern[str],
    entity_type: str,
    score: float,
) -> list[PhiFinding]:
    findings: list[PhiFinding] = []
    for match in pattern.finditer(text):
        group_name = "name" if "name" in match.groupdict() else "value"
        raw_value = match.group("value") if "value" in match.groupdict() else ""
        if "[" in raw_value:
            continue
        start, end = match.span(group_name)
        value = text[start:end]
        if value.strip().startswith("["):
            continue
        findings.append(
            PhiFinding(
                entity_type=entity_type,
                text=value,
                start=start,
                end=end,
                score=score,
            )
        )
    return findings

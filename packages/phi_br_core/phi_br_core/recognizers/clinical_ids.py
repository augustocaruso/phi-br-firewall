from __future__ import annotations

import re
from dataclasses import dataclass

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import (
    BR_AUTHORIZATION_ID,
    BR_CLINICAL_RECORD_ID,
    BR_EXAM_ID,
    BR_VISIT_ID,
)


@dataclass(frozen=True)
class _ClinicalIdRule:
    entity_type: str
    context_regex: str
    score: float


_VALUE_PATTERN = r"(?P<value>[A-Z]{0,4}\d{4,12}(?:[-/]\d{1,8})?)"
_RULES: tuple[_ClinicalIdRule, ...] = (
    _ClinicalIdRule(
        BR_CLINICAL_RECORD_ID,
        r"prontu[aá]rio|registro\s+hospitalar|registro\s+cl[ií]nico|ficha",
        0.88,
    ),
    _ClinicalIdRule(
        BR_AUTHORIZATION_ID,
        r"guia|autoriza[cç][aã]o|senha\s+de\s+autoriza[cç][aã]o",
        0.86,
    ),
    _ClinicalIdRule(BR_EXAM_ID, r"laudo|exame|pedido\s+de\s+exame", 0.84),
    _ClinicalIdRule(BR_VISIT_ID, r"atendimento|consulta|passagem", 0.78),
)


class ClinicalIdRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entities=[
                BR_CLINICAL_RECORD_ID,
                BR_AUTHORIZATION_ID,
                BR_EXAM_ID,
                BR_VISIT_ID,
            ],
            supported_language="pt",
            context=["prontuario", "prontuário", "guia", "laudo", "atendimento"],
        )
        self._compiled_rules = [
            (
                rule,
                re.compile(
                    rf"\b(?:{rule.context_regex})\b\s*(?:n[ºo.]?\s*)?[:#-]?\s*{_VALUE_PATTERN}\b",
                    flags=re.IGNORECASE,
                ),
            )
            for rule in _RULES
        ]

    def load(self) -> None:
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        del nlp_artifacts
        requested = set(entities)
        results: list[RecognizerResult] = []
        for rule, pattern in self._compiled_rules:
            if rule.entity_type not in requested:
                continue
            for match in pattern.finditer(text):
                start, end = match.span("value")
                results.append(
                    RecognizerResult(
                        entity_type=rule.entity_type,
                        start=start,
                        end=end,
                        score=rule.score,
                    )
                )
        return results

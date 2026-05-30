from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import BR_HEALTHCARE_PROFESSIONAL_NAME, BR_PATIENT_NAME

_NAME_WORD = r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][a-záàâãéèêíìîóòôõúùûç]+"
_CONNECTOR = r"(?:da|de|do|das|dos|e)"
_NAME = rf"{_NAME_WORD}(?:\s+(?:{_CONNECTOR}\s+)?{_NAME_WORD}){{0,4}}"
_MEDICATION_TERMS = {
    "amoxicilina",
    "dipirona",
    "ibuprofeno",
    "losartana",
    "metformina",
    "omeprazol",
    "paracetamol",
    "prednisona",
    "quetiapina",
    "sertralina",
}


class ClinicalNameContextRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entities=[BR_PATIENT_NAME, BR_HEALTHCARE_PROFESSIONAL_NAME],
            supported_language="pt",
            context=["paciente", "dra", "dr", "medico", "médico", "profissional"],
        )
        self._patient_pattern = re.compile(
            rf"\b(?:Paciente|paciente|Usu[aá]rio|usu[aá]rio|Cliente|cliente)\s+(?P<name>{_NAME})\b",
        )
        self._professional_pattern = re.compile(
            rf"\b(?:Dr\.?|dr\.?|Dra\.?|dra\.?|M[eé]dico|m[eé]dico|M[eé]dica|m[eé]dica)\s+(?P<name>{_NAME})\b",
        )

    def load(self) -> None:
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        del nlp_artifacts
        results: list[RecognizerResult] = []
        requested = set(entities)
        if BR_PATIENT_NAME in requested:
            results.extend(self._results_for(text, self._patient_pattern, BR_PATIENT_NAME, 0.75))
        if BR_HEALTHCARE_PROFESSIONAL_NAME in requested:
            results.extend(
                self._results_for(
                    text,
                    self._professional_pattern,
                    BR_HEALTHCARE_PROFESSIONAL_NAME,
                    0.78,
                )
            )
        return results

    def _results_for(
        self,
        text: str,
        pattern: re.Pattern[str],
        entity_type: str,
        score: float,
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for match in pattern.finditer(text):
            name = match.group("name")
            if self._contains_medication_term(name):
                continue
            start, end = match.span("name")
            results.append(
                RecognizerResult(
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    score=score,
                )
            )
        return results

    @staticmethod
    def _contains_medication_term(name: str) -> bool:
        words = {word.lower() for word in re.findall(r"\w+", name, flags=re.UNICODE)}
        return bool(words & _MEDICATION_TERMS)

from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import (
    BR_FAMILY_MEMBER_NAME,
    BR_HEALTHCARE_PROFESSIONAL_NAME,
    BR_PATIENT_NAME,
)

_NAME_WORD = r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][A-Za-zÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç]+"
_CONNECTOR = r"(?:da|de|do|das|dos|e)"
_NAME = rf"{_NAME_WORD}(?:\s+(?:{_CONNECTOR}\s+)?{_NAME_WORD}){{0,4}}"
_LABEL_SEPARATOR = r"\s*(?::|-)?\s+"
_PROFESSIONAL_LEADING_CONTEXT = r"(?:(?:d[ao]|pel[ao]|ao|a|à)\s+)?"
_PROFESSIONAL_TITLE_PREFIX = r"(?:(?:prof\.?|professor(?:a)?)\s+)?"
_PROFESSIONAL_TITLE = (
    r"(?:dr\.?|dra\.?|drª\.?|drº\.?|dr\(a\)\.?|doutor(?:a)?|m[eé]dic[oa])"
)
_MEDICATION_TERMS = {
    "aripiprazol",
    "buspirona",
    "clonazepam",
    "divalproato",
    "escitalopram",
    "fluoxetina",
    "lamotrigina",
    "litio",
    "lítio",
    "melatonina",
    "olanzapina",
    "quetiapina",
    "risperidona",
    "sertralina",
    "valproato",
    "venlafaxina",
    "zolpidem",
}
_FIELD_LABEL_TERMS = {
    "atendimento",
    "autorizacao",
    "autorização",
    "cep",
    "clinica",
    "clínica",
    "cns",
    "convenio",
    "convênio",
    "cpf",
    "crm",
    "data",
    "dn",
    "email",
    "e-mail",
    "endereco",
    "endereço",
    "exame",
    "guia",
    "hospital",
    "laboratorio",
    "laboratório",
    "laudo",
    "nascimento",
    "pedido",
    "prontuario",
    "prontuário",
    "registro",
    "telefone",
    "tel",
}
_WORD_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


class ClinicalNameContextRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entities=[
                BR_PATIENT_NAME,
                BR_FAMILY_MEMBER_NAME,
                BR_HEALTHCARE_PROFESSIONAL_NAME,
            ],
            supported_language="pt",
            context=[
                "paciente",
                "acompanhante",
                "mae",
                "mãe",
                "pai",
                "dra",
                "dr",
                "interno",
                "medico",
                "médico",
                "profissional",
            ],
        )
        self._patient_pattern = re.compile(
            rf"\b(?i:paciente|usu[aá]rio|cliente){_LABEL_SEPARATOR}(?P<name>{_NAME})\b",
        )
        self._patient_name_label_pattern = re.compile(
            rf"(?im)^\s*(?i:nome(?:\s+(?:completo|social|do\s+paciente))?)"
            rf"\s*:\s*(?P<name>{_NAME})\b",
        )
        self._family_label_pattern = re.compile(
            rf"\b(?i:acompanhante|respons[aá]vel|m[aã]e|pai|filh[ao]|av[oóô])"
            rf"{_LABEL_SEPARATOR}(?P<name>{_NAME})\b",
        )
        self._family_parenthetical_pattern = re.compile(
            rf"\b(?P<name>{_NAME})\s*\((?i:m[aã]e|pai|filh[ao]|av[oóô])\)",
        )
        self._professional_pattern = re.compile(
            rf"\b(?P<name>(?i:{_PROFESSIONAL_LEADING_CONTEXT}"
            rf"{_PROFESSIONAL_TITLE_PREFIX}{_PROFESSIONAL_TITLE}){_LABEL_SEPARATOR}{_NAME})\b",
        )
        self._professional_role_pattern = re.compile(
            rf"\b(?P<name>{_NAME}\s*"
            r"\((?i:intern[oa]|residente|staff|preceptor[ao]?|m[eé]dic[oa])[^)]*\))",
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
            results.extend(
                self._results_for(
                    text,
                    self._patient_name_label_pattern,
                    BR_PATIENT_NAME,
                    0.82,
                )
            )
        if BR_FAMILY_MEMBER_NAME in requested:
            results.extend(
                self._results_for(
                    text,
                    self._family_label_pattern,
                    BR_FAMILY_MEMBER_NAME,
                    0.74,
                )
            )
            results.extend(
                self._results_for(
                    text,
                    self._family_parenthetical_pattern,
                    BR_FAMILY_MEMBER_NAME,
                    0.76,
                )
            )
        if BR_HEALTHCARE_PROFESSIONAL_NAME in requested:
            results.extend(
                self._results_for(
                    text,
                    self._professional_pattern,
                    BR_HEALTHCARE_PROFESSIONAL_NAME,
                    0.78,
                )
            )
            results.extend(
                self._results_for(
                    text,
                    self._professional_role_pattern,
                    BR_HEALTHCARE_PROFESSIONAL_NAME,
                    0.76,
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
            span = self._trim_field_label_suffix(match)
            if span is None:
                continue
            start, end = span
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
    def _trim_field_label_suffix(match: re.Match[str]) -> tuple[int, int] | None:
        name_start = match.start("name")
        name = match.group("name")
        words = list(_WORD_PATTERN.finditer(name))
        if not words:
            return None

        for index, word in enumerate(words):
            if word.group(0).lower() not in _FIELD_LABEL_TERMS:
                continue
            if index == 0:
                return None
            return name_start, name_start + words[index - 1].end()

        return match.span("name")

    @staticmethod
    def _contains_medication_term(name: str) -> bool:
        words = {word.lower() for word in _WORD_PATTERN.findall(name)}
        return bool(words & _MEDICATION_TERMS)

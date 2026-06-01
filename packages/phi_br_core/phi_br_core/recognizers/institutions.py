from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.recognizer_result import RecognizerResult

from phi_br_core.entities import BR_INSTITUTION

_FIELD_LABEL_TERMS = {
    "atendimento",
    "autorizacao",
    "autorização",
    "cep",
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
    "laudo",
    "nascimento",
    "pedido",
    "prontuario",
    "prontuário",
    "registro",
    "telefone",
    "tel",
}
_LABEL_SEPARATOR = r"\s*(?::|-)?\s+"
_WORD_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
_TRAILING_DATE_FRAGMENT_RE = re.compile(
    r"\s+(?:dia|em)\s+\d{1,2}$",
    flags=re.IGNORECASE,
)
_INSTITUTION_ACRONYM_RE = re.compile(r"\b[A-Z]{3,8}(?:\s+DF)?\b")
_INSTITUTION_ACRONYM_CONTEXT_RE = re.compile(
    r"(?:ambulat[oó]rio|cl[ií]nica|equipe|hospital|internad[oa]\s+n[oa]|"
    r"institui[cç][aã]o|proced[eê]ncia|psiquiatria|servi[cç]o|telemedicina|"
    r"unidade|upa|ubs)\b",
    flags=re.IGNORECASE,
)
_CLINICAL_ACRONYM_DENYLIST = {
    "BEG",
    "BI",
    "BT",
    "CPK",
    "CR",
    "CT",
    "DA",
    "DI",
    "DN",
    "DS",
    "EAS",
    "ECG",
    "ECT",
    "EEG",
    "FAL",
    "FC",
    "GGT",
    "GJ",
    "Hb".upper(),
    "HCV",
    "HDA",
    "HDL",
    "HIV",
    "HT",
    "IMC",
    "LAB",
    "LDL",
    "LME",
    "MG",
    "NA",
    "NR",
    "PA",
    "PAD",
    "PAS",
    "PCR",
    "QP",
    "RNM",
    "TC",
    "TEC",
    "TGO",
    "TGP",
    "TGL",
    "TR",
    "TSH",
    "VCM",
    "VHS",
    "VO",
}


class InstitutionRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_INSTITUTION,
            patterns=[
                Pattern(
                    name="healthcare_institution",
                    regex=(
                        r"\b(?:Hospital|Cl[ií]nica|UBS|UPA|CAPS|Instituto|"
                        r"Unidade\s+B[aá]sica\s+de\s+Sa[uú]de|"
                        rf"Laborat[oó]rio){_LABEL_SEPARATOR}[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]"
                        r"[\wÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç .'-]{2,60}"
                        r"(?:\s*\([A-Z]{2,8}\))?"
                    ),
                    score=0.7,
                ),
                Pattern(
                    name="healthcare_institution_acronym",
                    regex=r"(?!)",
                    score=0.0,
                )
            ],
            context=[
                "ambulatorio",
                "ambulatório",
                "dermatopediatria",
                "hospital",
                "clinica",
                "clínica",
                "ubs",
                "upa",
                "laboratorio",
                "instituto",
            ],
            supported_language="pt",
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
        regex_flags: int | None = None,
    ) -> list[RecognizerResult]:
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        trimmed = [self._trim_result(text, result) for result in results]
        if BR_INSTITUTION in set(entities):
            trimmed.extend(self._institution_acronym_results(text))
        return trimmed

    @staticmethod
    def _trim_result(text: str, result: RecognizerResult) -> RecognizerResult:
        value = text[result.start : result.end]
        words = list(_WORD_PATTERN.finditer(value))
        end = result.end

        for index, word in enumerate(words):
            if index == 0 or word.group(0).lower() not in _FIELD_LABEL_TERMS:
                continue
            end = result.start + words[index - 1].end()
            break

        value = text[result.start : end]
        date_fragment = _TRAILING_DATE_FRAGMENT_RE.search(value)
        if date_fragment is not None and text[end : end + 1] in {"/", "-", "."}:
            end = result.start + date_fragment.start()

        while end > result.start and text[end - 1] in " .,:;":
            end -= 1

        return RecognizerResult(
            entity_type=result.entity_type,
            start=result.start,
            end=end,
            score=result.score,
            analysis_explanation=result.analysis_explanation,
            recognition_metadata=result.recognition_metadata,
        )

    @staticmethod
    def _institution_acronym_results(text: str) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for match in _INSTITUTION_ACRONYM_RE.finditer(text):
            value = match.group(0)
            if value in _CLINICAL_ACRONYM_DENYLIST:
                continue
            if not InstitutionRecognizer._has_acronym_context(text, match.start()):
                continue
            results.append(
                RecognizerResult(
                    entity_type=BR_INSTITUTION,
                    start=match.start(),
                    end=match.end(),
                    score=0.72,
                )
            )
        return results

    @staticmethod
    def _has_acronym_context(text: str, start: int) -> bool:
        line_start = text.rfind("\n", 0, start) + 1
        prefix = text[max(line_start, start - 60) : start]
        return _INSTITUTION_ACRONYM_CONTEXT_RE.search(prefix) is not None

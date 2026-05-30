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
_WORD_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


class InstitutionRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_INSTITUTION,
            patterns=[
                Pattern(
                    name="healthcare_institution",
                    regex=(
                        r"\b(?:Hospital|Cl[ií]nica|UBS|UPA|Unidade\s+B[aá]sica\s+de\s+Sa[uú]de|"
                        r"Laborat[oó]rio)\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]"
                        r"[\wÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç .'-]{2,60}"
                    ),
                    score=0.7,
                )
            ],
            context=["hospital", "clinica", "clínica", "ubs", "upa", "laboratorio"],
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
        return [self._trim_result(text, result) for result in results]

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

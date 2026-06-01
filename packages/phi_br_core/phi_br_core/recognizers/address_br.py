from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import BR_ADDRESS
from phi_br_core.placeholders import parse_placeholder

_ADDRESS_LABEL_RE = re.compile(
    r"(?im)^[ \t]*(?:endere[cç]o|resid[eê]ncia|moradia|bairro|naturalidade|proced[eê]ncia)"
    r"[ \t]*:[ \t]*(?P<address>[^\n\r]+)"
)
_RESIDENCE_CONTEXT_RE = re.compile(
    r"\b(?i:residentes?|reside(?:m)?|mora(?:m)?)\s+em\s+"
    r"(?P<address>[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][^,\n\r.;]{1,80})"
)
_GEOGRAPHIC_CONTEXT_RE = re.compile(
    r"\b(?i:nasceu|viveu|morou|mudou|residiu|procedente)\b"
    r"(?:(?![\n\r.;]).){0,50}?\b(?i:em|n[ao]|para)\s+"
    r"(?P<address>[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][^,\n\r.;]{1,80})"
)
_NEXT_FIELD_RE = re.compile(
    r"\s+\b(?:telefone|tel|celular|cep|cpf|cns|prontu[aá]rio|dn|idade|nome|h[áa]|at[eé])\b\s*:?",
    re.IGNORECASE,
)


class AddressBrRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entities=[BR_ADDRESS],
            supported_language="pt",
            context=[
                "endereco",
                "endereço",
                "residencia",
                "residência",
                "moradia",
                "bairro",
                "naturalidade",
                "procedencia",
                "procedência",
                "residentes",
                "residente",
                "reside",
                "moram",
            ],
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
        if BR_ADDRESS not in set(entities):
            return []

        results: list[RecognizerResult] = []
        results.extend(self._results_for(text, _ADDRESS_LABEL_RE, 0.82))
        results.extend(self._results_for(text, _RESIDENCE_CONTEXT_RE, 0.66))
        results.extend(self._results_for(text, _GEOGRAPHIC_CONTEXT_RE, 0.62))
        return results

    @staticmethod
    def _results_for(
        text: str, pattern: re.Pattern[str], score: float
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for match in pattern.finditer(text):
            start, end = match.span("address")
            end = _trim_address_end(text, start, end)
            if end <= start:
                continue
            if _is_placeholder(text[start:end].strip()):
                continue
            results.append(
                RecognizerResult(
                    entity_type=BR_ADDRESS,
                    start=start,
                    end=end,
                    score=score,
                )
            )
        return results


def _trim_address_end(text: str, start: int, end: int) -> int:
    value = text[start:end]
    if sentence_boundary := re.search(r"\.\s+", value):
        end = start + sentence_boundary.start()
        value = text[start:end]
    if next_field := _NEXT_FIELD_RE.search(value):
        end = start + next_field.start()

    while end > start and text[end - 1] in " .,:;":
        end -= 1
    return end


def _is_placeholder(value: str) -> bool:
    try:
        parse_placeholder(value)
    except ValueError:
        return False
    return True

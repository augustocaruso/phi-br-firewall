from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from phi_br_core.entities import BR_AGE

_AGE_PATTERN = re.compile(
    r"\b(?P<age>"
    r"\d{1,3}\s+anos?(?:\s+e\s+\d{1,2}\s+m[eê]s(?:es)?)?(?:\s+de\s+idade)?"
    r"|"
    r"\d{1,2}\s+m[eê]s(?:es)?(?:\s+de\s+idade)?"
    r")\b",
    flags=re.IGNORECASE,
)
_DURATION_PREFIX_PATTERN = re.compile(
    r"(?:^|\W)(?:h[áa](?:\s+pelo\s+menos)?|faz|desde|para|por|durante|em|ap[oó]s)\s+$",
    flags=re.IGNORECASE,
)


class AgeBrRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entities=[BR_AGE],
            supported_language="pt",
            context=["idade", "anos", "meses", "nascimento", "paciente"],
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
        if BR_AGE not in set(entities):
            return []

        results: list[RecognizerResult] = []
        for match in _AGE_PATTERN.finditer(text):
            if self._looks_like_duration(text, match.start("age"), match.end("age")):
                continue
            results.append(
                RecognizerResult(
                    entity_type=BR_AGE,
                    start=match.start("age"),
                    end=match.end("age"),
                    score=0.72,
                )
            )
        return results

    @staticmethod
    def _looks_like_duration(text: str, start: int, end: int) -> bool:
        value = text[start:end]
        if re.search(r"\bde\s+idade\b", value, flags=re.IGNORECASE):
            return False
        prefix = text[max(0, start - 32) : start]
        return bool(_DURATION_PREFIX_PATTERN.search(prefix))

from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.recognizer_result import RecognizerResult

from phi_br_core.entities import BR_CONTEXTUAL_IDENTIFIER

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
_LABELED_IDENTIFIER_RE = re.compile(
    r"\b(?:n[ºo.]?\s*)?(?:SES|ID|protocolo|senha)\s*[:#-]?\s*(?P<value>[A-Z]{0,4}\d{4,12})\b",
    flags=re.IGNORECASE,
)
_SYSTEM_IDENTIFIER_RE = re.compile(
    r"\b(?:via|sistema|plataforma|no\s+sistema|na\s+plataforma|"
    r"pelo\s+sistema|pela\s+plataforma)\s+"
    r"(?P<value>[Ss][Ii][Ss][A-Za-z0-9_-]{2,30})\b",
)


class ContextualIdentifierRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_CONTEXTUAL_IDENTIFIER,
            patterns=[
                Pattern(
                    name="url_with_scheme",
                    regex=(
                        r"\bhttps?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*"
                        r"[A-Za-z0-9/#]"
                    ),
                    score=0.75,
                ),
                Pattern(
                    name="domain_with_optional_path",
                    regex=(
                        r"(?<!@)\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}"
                        r"(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*[A-Za-z0-9/#])?"
                    ),
                    score=0.65,
                ),
            ],
            context=["portal", "link", "url", "site", "sistema"],
            supported_language="pt",
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
        regex_flags: int | None = None,
    ) -> list[RecognizerResult]:
        email_spans = [match.span() for match in _EMAIL_PATTERN.finditer(text)]
        results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        filtered = [
            result
            for result in results
            if not self._is_email_fragment(text, result, email_spans)
        ]
        if BR_CONTEXTUAL_IDENTIFIER in set(entities):
            filtered.extend(self._labeled_identifier_results(text))
            filtered.extend(self._system_identifier_results(text))
        return filtered

    @staticmethod
    def _labeled_identifier_results(text: str) -> list[RecognizerResult]:
        return [
            RecognizerResult(
                entity_type=BR_CONTEXTUAL_IDENTIFIER,
                start=match.start("value"),
                end=match.end("value"),
                score=0.86,
            )
            for match in _LABELED_IDENTIFIER_RE.finditer(text)
        ]

    @staticmethod
    def _system_identifier_results(text: str) -> list[RecognizerResult]:
        return [
            RecognizerResult(
                entity_type=BR_CONTEXTUAL_IDENTIFIER,
                start=match.start("value"),
                end=match.end("value"),
                score=0.78,
            )
            for match in _SYSTEM_IDENTIFIER_RE.finditer(text)
        ]

    @staticmethod
    def _is_email_fragment(
        text: str,
        result: RecognizerResult,
        email_spans: list[tuple[int, int]],
    ) -> bool:
        value = text[result.start : result.end].lower()
        if "://" in value:
            return False
        return any(result.start < end and start < result.end for start, end in email_spans)

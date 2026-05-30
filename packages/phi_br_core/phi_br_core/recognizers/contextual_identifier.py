from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.recognizer_result import RecognizerResult

from phi_br_core.entities import BR_CONTEXTUAL_IDENTIFIER

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
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
        return [
            result
            for result in results
            if not any(result.start < end and start < result.end for start, end in email_spans)
        ]

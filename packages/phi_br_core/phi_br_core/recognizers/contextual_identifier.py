from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_CONTEXTUAL_IDENTIFIER


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

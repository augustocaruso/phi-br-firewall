from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_EMAIL


class EmailBrRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_EMAIL,
            patterns=[
                Pattern(
                    name="email_address",
                    regex=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                    score=0.9,
                )
            ],
            context=["email", "e-mail", "contato"],
            supported_language="pt",
        )

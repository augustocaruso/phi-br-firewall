from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_PHONE


class PhoneBrRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_PHONE,
            patterns=[
                Pattern(
                    name="br_phone_with_context",
                    regex=r"\b(?:telefone|tel|celular|cel)[:\s-]*(?:\(?\d{2}\)?\s*)?9?\d{4}-?\d{4}\b",
                    score=0.8,
                ),
                Pattern(
                    name="br_phone_with_area_code",
                    regex=r"(?<!\d)\(?\d{2}\)?\s*9?\d{4}-?\d{4}\b",
                    score=0.75,
                ),
            ],
            context=["telefone", "tel", "celular", "contato"],
            supported_language="pt",
        )

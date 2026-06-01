from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_RG


class RgRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_RG,
            patterns=[
                Pattern(
                    name="rg_with_label",
                    regex=(
                        r"\bRG\s*(?:n[ºo.]?\s*)?[:#-]?\s*"
                        r"\d{1,2}\.?\d{3}\.?\d{3}(?:[-.]?[0-9Xx]{1,2})?\b"
                    ),
                    score=0.88,
                ),
            ],
            context=["rg", "identidade", "documento"],
            supported_language="pt",
        )

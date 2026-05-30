from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_CNS


class CnsRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_CNS,
            patterns=[
                Pattern(
                    name="cns_contextual",
                    regex=(
                        r"\b(?:CNS|cart[aã]o\s+nacional\s+de\s+sa[uú]de|"
                        r"cart[aã]o\s+sus|SUS)[:\s-]*\d{15}\b"
                    ),
                    score=0.9,
                )
            ],
            context=["cns", "sus", "cartao", "cartão"],
            supported_language="pt",
        )

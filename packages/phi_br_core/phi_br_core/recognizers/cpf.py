from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_CPF
from phi_br_core.validators import validate_cpf


class CpfRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_CPF,
            patterns=[
                Pattern(
                    name="cpf_formatted_or_digits",
                    regex=r"\b(?:CPF[:\s]*)?\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
                    score=0.85,
                )
            ],
            context=["cpf", "cadastro", "documento"],
            supported_language="pt",
        )

    def validate_result(self, pattern_text: str) -> bool:
        return validate_cpf(pattern_text)

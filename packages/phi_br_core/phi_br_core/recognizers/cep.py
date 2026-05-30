from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_CEP


class CepRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_CEP,
            patterns=[
                Pattern(
                    name="cep_with_optional_label",
                    regex=r"\b(?:CEP[:\s]*)?\d{5}-?\d{3}\b",
                    score=0.75,
                )
            ],
            context=["cep", "endereco", "endereço", "residencia", "residência"],
            supported_language="pt",
        )

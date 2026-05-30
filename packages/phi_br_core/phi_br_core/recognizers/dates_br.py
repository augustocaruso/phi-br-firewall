from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_DATE


class DateBrRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_DATE,
            patterns=[
                Pattern(
                    name="br_numeric_date",
                    regex=r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
                    score=0.6,
                )
            ],
            context=["data", "nascimento", "consulta", "internacao", "internação"],
            supported_language="pt",
        )

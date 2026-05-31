from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_DATE


class DateBrRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        month = (
            r"jan(?:eiro)?|fev(?:ereiro)?|mar[cç]o|abr(?:il)?|mai(?:o)?|jun(?:ho)?|"
            r"jul(?:ho)?|ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|"
            r"dez(?:embro)?"
        )
        super().__init__(
            supported_entity=BR_DATE,
            patterns=[
                Pattern(
                    name="br_numeric_date",
                    regex=r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b",
                    score=0.85,
                ),
                Pattern(
                    name="iso_date",
                    regex=r"\b(?:\d{4}-\d{1,2}-\d{1,2})\b",
                    score=0.85,
                ),
                Pattern(
                    name="br_month_year_slash",
                    regex=rf"\b(?i:(?:{month})[/-]\d{{2,4}})\b",
                    score=0.78,
                ),
                Pattern(
                    name="br_text_month_date",
                    regex=rf"\b(?i:(?:\d{{1,2}}\s+de\s+)?(?:{month})(?:\s+de)?\s+\d{{4}})\b",
                    score=0.78,
                ),
            ],
            context=[
                "alta",
                "atendimento",
                "consulta",
                "data",
                "dn",
                "exame",
                "internacao",
                "internação",
                "nascimento",
                "retorno",
            ],
            supported_language="pt",
        )

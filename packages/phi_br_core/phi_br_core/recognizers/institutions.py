from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_INSTITUTION


class InstitutionRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_INSTITUTION,
            patterns=[
                Pattern(
                    name="healthcare_institution",
                    regex=(
                        r"\b(?:Hospital|Cl[ií]nica|UBS|UPA|Unidade\s+B[aá]sica\s+de\s+Sa[uú]de|"
                        r"Laborat[oó]rio)\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]"
                        r"[\wÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç .'-]{2,60}"
                    ),
                    score=0.7,
                )
            ],
            context=["hospital", "clinica", "clínica", "ubs", "upa", "laboratorio"],
            supported_language="pt",
        )

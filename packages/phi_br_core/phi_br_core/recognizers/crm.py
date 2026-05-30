from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from phi_br_core.entities import BR_CRM

UF = r"(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)"


class CrmRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity=BR_CRM,
            patterns=[
                Pattern(
                    name="crm_uf_before_number",
                    regex=rf"\bCRM[\s/-]*{UF}[\s-]*\d{{4,7}}\b",
                    score=0.9,
                ),
                Pattern(
                    name="crm_uf_after_number",
                    regex=rf"\bCRM[\s/-]*\d{{4,7}}[\s/-]*{UF}\b",
                    score=0.9,
                ),
            ],
            context=["crm", "medico", "médico", "dra", "dr"],
            supported_language="pt",
        )

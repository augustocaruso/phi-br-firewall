from phi_br_core.recognizers.cep import CepRecognizer
from phi_br_core.recognizers.clinical_ids import ClinicalIdRecognizer
from phi_br_core.recognizers.cns import CnsRecognizer
from phi_br_core.recognizers.cpf import CpfRecognizer
from phi_br_core.recognizers.crm import CrmRecognizer
from phi_br_core.recognizers.dates_br import DateBrRecognizer
from phi_br_core.recognizers.institutions import InstitutionRecognizer
from phi_br_core.recognizers.names_context import ClinicalNameContextRecognizer
from phi_br_core.recognizers.phone_br import PhoneBrRecognizer

__all__ = [
    "CepRecognizer",
    "ClinicalIdRecognizer",
    "ClinicalNameContextRecognizer",
    "CnsRecognizer",
    "CpfRecognizer",
    "CrmRecognizer",
    "DateBrRecognizer",
    "InstitutionRecognizer",
    "PhoneBrRecognizer",
]

from phi_br_core.analyzer import build_analyzer
from phi_br_core.policy import PhiPolicy


def entity_types_for(text: str) -> set[str]:
    analyzer = build_analyzer(PhiPolicy())
    results = analyzer.analyze(text=text, language="pt", score_threshold=0.35)
    return {result.entity_type for result in results}


def test_detects_valid_cpf() -> None:
    assert "BR_CPF" in entity_types_for("Paciente com CPF 935.411.347-80.")


def test_rejects_invalid_cpf() -> None:
    assert "BR_CPF" not in entity_types_for("Numero 935.411.347-81.")


def test_detects_cns_with_context() -> None:
    assert "BR_CNS" in entity_types_for("CNS 898001160000000 registrado.")


def test_detects_crm_with_uf_prefix() -> None:
    assert "BR_CRM" in entity_types_for("Atendido pela Dra Ana CRM-DF 12345.")


def test_detects_phone_and_cep() -> None:
    types = entity_types_for("Telefone (61) 99999-9999, CEP 70000-000.")
    assert "BR_PHONE" in types
    assert "BR_CEP" in types


def test_detects_contextual_clinical_ids() -> None:
    types = entity_types_for("Prontuario 123456. Guia 987654321. Laudo 554433.")
    assert "BR_CLINICAL_RECORD_ID" in types
    assert "BR_AUTHORIZATION_ID" in types
    assert "BR_EXAM_ID" in types


def test_does_not_detect_medication_numbers_as_clinical_ids() -> None:
    types = entity_types_for("quetiapina 100 mg, PA 120x80, HbA1c 6,5%.")
    assert "BR_CLINICAL_RECORD_ID" not in types
    assert "BR_VISIT_ID" not in types


def test_detects_patient_and_professional_names_by_context() -> None:
    types = entity_types_for("Paciente Joao da Silva avaliado pela Dra Ana Souza.")
    assert "BR_PATIENT_NAME" in types
    assert "BR_HEALTHCARE_PROFESSIONAL_NAME" in types

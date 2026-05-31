import pytest
from phi_br_core.analyzer import build_analyzer
from phi_br_core.policy import PhiPolicy
from presidio_analyzer import RecognizerResult


def findings_for(text: str) -> list[RecognizerResult]:
    analyzer = build_analyzer(PhiPolicy())
    return analyzer.analyze(text=text, language="pt", score_threshold=0.35)


def entity_types_for(text: str) -> set[str]:
    return {result.entity_type for result in findings_for(text)}


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
    assert "BR_FAMILY_MEMBER_NAME" not in types


def test_detects_uppercase_names_by_context() -> None:
    types = entity_types_for("Paciente MARIA SILVA avaliada pela DRA ANA SOUZA.")

    assert "BR_PATIENT_NAME" in types
    assert "BR_HEALTHCARE_PROFESSIONAL_NAME" in types


def test_detects_names_after_label_separators() -> None:
    patient_types = entity_types_for("Paciente: Maria Silva.")
    professional_types = entity_types_for("Medica - Ana Souza.")

    assert "BR_PATIENT_NAME" in patient_types
    assert "BR_HEALTHCARE_PROFESSIONAL_NAME" in professional_types


def test_detects_patient_name_after_name_label() -> None:
    text = "Nome: Ana Silva Costa\nDN: 10/06/2017."
    findings = findings_for(text)

    patient_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_PATIENT_NAME"
    ]

    assert patient_names == ["Ana Silva Costa"]


def test_detects_family_member_names_by_clinical_context() -> None:
    text = "Acompanhante: Lara (mae). Mae relata piora."
    findings = findings_for(text)

    family_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_FAMILY_MEMBER_NAME"
    ]

    assert family_names == ["Lara"]


def test_detects_intern_name_as_healthcare_professional() -> None:
    text = "Mateus (interno eletivo) sob orientacao de Dra Paula Ramos."
    findings = findings_for(text)

    professional_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_HEALTHCARE_PROFESSIONAL_NAME"
    ]

    assert "Mateus (interno eletivo)" in professional_names
    assert "Dra Paula Ramos" in professional_names


@pytest.mark.parametrize(
    ("leading_context", "title"),
    [
        ("", "Dr"),
        ("", "Dr."),
        ("", "Dra"),
        ("", "Dra."),
        ("", "Drª"),
        ("", "Drª."),
        ("", "Drº"),
        ("", "Dr(a)"),
        ("", "Dr(a)."),
        ("", "Doutor"),
        ("", "Doutora"),
        ("", "Medico"),
        ("", "Médica"),
        ("", "Prof. Dr."),
        ("", "Professora Doutora"),
        ("do ", "Dr."),
        ("da ", "Dra."),
        ("pelo ", "Doutor"),
        ("pela ", "Drª."),
    ],
)
def test_detects_doctor_title_as_part_of_professional_name(
    leading_context: str, title: str
) -> None:
    text = f"Paciente avaliado sob orientacao {leading_context}{title} Carlos Lima."
    findings = findings_for(text)

    professional_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_HEALTHCARE_PROFESSIONAL_NAME"
    ]

    assert professional_names == [f"{leading_context}{title} Carlos Lima"]


def test_name_context_stops_before_next_field_label() -> None:
    text = "Paciente Maria Telefone (61) 99999-9999."
    findings = findings_for(text)

    patient_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_PATIENT_NAME"
    ]

    assert patient_names == ["Maria"]
    assert "BR_PHONE" in {result.entity_type for result in findings}


def test_detects_email_with_project_entity_type() -> None:
    types = entity_types_for("Email maria@example.com registrado.")

    assert "BR_EMAIL" in types
    assert "BR_CONTEXTUAL_IDENTIFIER" not in types
    assert "EMAIL_ADDRESS" not in types


def test_does_not_detect_email_parts_as_contextual_identifiers() -> None:
    texts = [
        "Email maria@portal.hospital.com.br registrado.",
        "Email foo.maria@example.com registrado.",
    ]

    for text in texts:
        findings = findings_for(text)
        assert "BR_EMAIL" in {result.entity_type for result in findings}
        assert [
            text[result.start : result.end]
            for result in findings
            if result.entity_type == "BR_CONTEXTUAL_IDENTIFIER"
        ] == []


def test_institution_context_stops_before_next_field_label() -> None:
    text = "Paciente Maria Hospital Santa Lucia Telefone (61) 99999-9999."
    findings = findings_for(text)

    institutions = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_INSTITUTION"
    ]

    assert institutions == ["Hospital Santa Lucia"]
    assert "BR_PHONE" in {result.entity_type for result in findings}


def test_detects_healthcare_institution_acronym_without_section_acronyms() -> None:
    text = "AMBULATORIO DERMATOLOGIA HCB. QP dermatite. HDA sem febre. BEG."
    findings = findings_for(text)

    institutions = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_INSTITUTION"
    ]

    assert institutions == ["HCB"]


def test_detects_institution_after_label_separator() -> None:
    types = entity_types_for("Encaminhada para Hospital: Santa Lucia.")

    assert "BR_INSTITUTION" in types


def test_detects_address_after_address_label() -> None:
    text = "Endereco: Quadra 10, Rua A, casa 1, Bairro Modelo\nTelefone (61) 99999-9999."
    findings = findings_for(text)

    addresses = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_ADDRESS"
    ]

    assert addresses == ["Quadra 10, Rua A, casa 1, Bairro Modelo"]
    assert "BR_PHONE" in {result.entity_type for result in findings}


def test_detects_residence_neighborhood_by_context() -> None:
    text = "Residentes em Vila Modelo, mae, pai e dois irmaos."
    findings = findings_for(text)

    addresses = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_ADDRESS"
    ]

    assert addresses == ["Vila Modelo"]


def test_detects_url_as_contextual_identifier() -> None:
    types = entity_types_for("Portal https://portal.hospital.com.br/paciente/12345.")

    assert "BR_CONTEXTUAL_IDENTIFIER" in types
    assert "URL" not in types


def test_detects_url_with_email_like_path_as_contextual_identifier() -> None:
    types = entity_types_for("Portal https://portal.hospital.com.br/paciente/maria@example.com.")

    assert "BR_CONTEXTUAL_IDENTIFIER" in types
    assert "BR_EMAIL" in types


def test_detects_pediatric_ages_without_symptom_duration() -> None:
    text = (
        "Paciente: Crianca Teste: 7 anos e 4 meses. "
        "Dermatite ha 3 anos. Quando tinha apenas 1 mes de idade. "
        "Aos 4 anos de idade surgiram lesoes."
    )
    findings = findings_for(text)

    ages = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_AGE"
    ]

    assert "7 anos e 4 meses" in ages
    assert "1 mes de idade" in ages
    assert "4 anos de idade" in ages
    assert "3 anos" not in ages


def test_does_not_detect_prescription_or_followup_duration_as_age() -> None:
    text = (
        "Mantenho medicacoes em uso - deixo receitas para 4 meses. "
        "Retorno em 4 meses. Usar pomada por 2 meses."
    )
    findings = findings_for(text)

    ages = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_AGE"
    ]

    assert ages == []


def test_detects_brazilian_text_month_dates() -> None:
    text = "Em agosto/2023 houve piora. Retorno em dezembro/2024."
    findings = findings_for(text)

    dates = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_DATE"
    ]

    assert "agosto/2023" in dates
    assert "dezembro/2024" in dates

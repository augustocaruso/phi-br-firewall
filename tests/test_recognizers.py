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


def test_detects_rg_with_label() -> None:
    assert "BR_RG" in entity_types_for("RG: 21.392.009-34.")


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
    types = entity_types_for("Prontuario 123456. Guia 987654321. Laudo 554433. Nº SES: 8234636.")
    assert "BR_CLINICAL_RECORD_ID" in types
    assert "BR_AUTHORIZATION_ID" in types
    assert "BR_EXAM_ID" in types
    assert "BR_CONTEXTUAL_IDENTIFIER" in types


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


def test_patient_context_rejects_uppercase_clinical_sentence_without_name() -> None:
    text = "CONFORME ENCAMINHAMENTO, PACIENTE TEM INDICACAO DE INTERNACAO PELA PSIQUIATRIA."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_PATIENT_NAME"
    ] == []


def test_detects_patient_name_after_patient_word_inside_sentence() -> None:
    text = "Dieta via sonda para o Paciente Pedro Willian iniciar as 6h."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_PATIENT_NAME"
    ] == ["Pedro Willian"]


def test_detects_family_member_names_by_clinical_context() -> None:
    text = "Acompanhante: Lara (mae). Contatos: Justino (irmao). Mae relata piora."
    findings = findings_for(text)

    family_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_FAMILY_MEMBER_NAME"
    ]

    assert family_names == ["Lara", "Justino"]


def test_detects_family_names_in_filiation_and_sibling_lists() -> None:
    text = (
        "Filiacao: Eloisio Ficticio da Cunha, Marilda Inventada Braga\n"
        "Irmaos: 3 irmaos - Wilker Ficticio da Cunha, Walas Inventado Braga"
    )
    findings = findings_for(text)

    family_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_FAMILY_MEMBER_NAME"
    ]

    assert family_names == [
        "Eloisio Ficticio da Cunha",
        "Marilda Inventada Braga",
        "Wilker Ficticio da Cunha",
        "Walas Inventado Braga",
    ]


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


def test_institution_context_stops_before_short_date() -> None:
    text = "Hospital Santa Luzia em 18/06."
    findings = findings_for(text)

    institutions = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_INSTITUTION"
    ]

    assert institutions == ["Hospital Santa Luzia"]
    assert "18/06" in [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_DATE"
    ]


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


def test_detects_institute_healthcare_institution() -> None:
    text = "Tratamento no Instituto Castro e Santos (ICS)."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_INSTITUTION"
    ] == ["Instituto Castro e Santos (ICS)"]


def test_detects_healthcare_system_acronyms_and_id_context() -> None:
    text = "Internado no IHBDF. Telemedicina Psiquiatria IGES DF ID: 16142."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_INSTITUTION"
    ] == ["IHBDF", "IGES DF"]
    assert "16142" in [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_CONTEXTUAL_IDENTIFIER"
    ]


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


def test_address_context_ignores_already_redacted_placeholder() -> None:
    text = "Residentes em [ENDERECO_002], mae, pai e dois irmaos."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_ADDRESS"
    ] == []


def test_address_label_does_not_cross_line_after_redacted_value() -> None:
    text = "Endereco:               \nResidentes em               , mae, pai e dois irmaos."
    findings = findings_for(text)

    assert [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_ADDRESS"
    ] == []


def test_detects_naturalidade_and_city_state_context_as_address() -> None:
    text = "Naturalidade: Barra Ficticia-BA. Mudou para Brasilia ha 3 anos."
    findings = findings_for(text)

    addresses = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_ADDRESS"
    ]

    assert "Barra Ficticia-BA" in addresses
    assert "Brasilia" in addresses


def test_detects_url_as_contextual_identifier() -> None:
    types = entity_types_for("Portal https://portal.hospital.com.br/paciente/12345.")

    assert "BR_CONTEXTUAL_IDENTIFIER" in types
    assert "URL" not in types


def test_detects_url_with_email_like_path_as_contextual_identifier() -> None:
    types = entity_types_for("Portal https://portal.hospital.com.br/paciente/maria@example.com.")

    assert "BR_CONTEXTUAL_IDENTIFIER" in types
    assert "BR_EMAIL" in types


def test_detects_protocol_and_password_as_contextual_identifiers() -> None:
    text = "Protocolo: 2290259, Senha: 384715."
    findings = findings_for(text)

    identifiers = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_CONTEXTUAL_IDENTIFIER"
    ]

    assert "2290259" in identifiers
    assert "384715" in identifiers


def test_detects_named_health_system_as_contextual_identifier() -> None:
    text = "Indico internacao e peço leito via Sisleitos."
    findings = findings_for(text)

    identifiers = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_CONTEXTUAL_IDENTIFIER"
    ]

    assert identifiers == ["Sisleitos"]


def test_detects_resident_level_as_professional_identifier() -> None:
    text = "Naiara R1 Psiquiatria sob orientacao do Dr Marcus."
    findings = findings_for(text)

    professional_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_HEALTHCARE_PROFESSIONAL_NAME"
    ]

    assert "Naiara R1 Psiquiatria" in professional_names
    assert "do Dr Marcus" in professional_names


def test_detects_medical_student_year_or_semester_as_professional_identifier() -> None:
    text = (
        "Augusto estudante de medicina do 10o semestre sob orientacao da Dra Paula. "
        "Mateus interno do 6o ano acompanhou."
    )
    findings = findings_for(text)

    professional_names = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_HEALTHCARE_PROFESSIONAL_NAME"
    ]

    assert "Augusto estudante de medicina do 10o semestre" in professional_names
    assert "Mateus interno do 6o ano" in professional_names


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
        "Retorno em 4 meses. Usar pomada por 2 meses. "
        "Ha pelo menos 2 meses com sintomas. Ha aproximadamente 3 meses com sintomas."
    )
    findings = findings_for(text)

    ages = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_AGE"
    ]

    assert ages == []


def test_detects_brazilian_text_month_dates() -> None:
    text = "Em agosto/2023 houve piora. Retorno em dezembro/2024. DI: 18/06. Em 2017."
    findings = findings_for(text)

    dates = [
        text[result.start : result.end]
        for result in findings
        if result.entity_type == "BR_DATE"
    ]

    assert "agosto/2023" in dates
    assert "dezembro/2024" in dates
    assert "18/06" in dates
    assert "2017" in dates

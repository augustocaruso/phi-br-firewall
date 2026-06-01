from phi_br_core import PhiPolicy, restore_text, scan_text, scrub_text


def test_scan_scrub_restore_public_api(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = "Paciente Joao da Silva, CPF 935.411.347-80."

    scan = scan_text(text, policy)
    assert "BR_CPF" in {finding.entity_type for finding in scan.findings}

    scrub = scrub_text(text, policy)
    assert scrub.ok is True
    assert "[CPF_001]" in scrub.scrubbed_text
    assert "935.411.347-80" not in scrub.scrubbed_text

    restored = restore_text(scrub.scrubbed_text, scrub.mapping_path)
    assert restored == text


def test_scrub_repairs_second_pass_residuals_in_same_mapping(tmp_path) -> None:
    policy = PhiPolicy(min_score=0.9, audit_threshold=0.35)
    policy.mapping.base_dir = str(tmp_path)
    text = "Contato (11) 99999-8888. Hospital Santa Luzia."

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "(11) 99999-8888" not in scrub.scrubbed_text
    assert "Hospital Santa Luzia" not in scrub.scrubbed_text
    assert "BR_PHONE" in scrub.summary.entity_types
    assert "BR_INSTITUTION" in scrub.summary.entity_types
    assert restore_text(scrub.scrubbed_text, scrub.mapping_path) == text


def test_scrub_respects_non_persistent_mapping_policy(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    policy.mapping.persist = False
    text = "Paciente Joao da Silva, CPF 935.411.347-80."

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert scrub.mapping_path == ""
    assert scrub.session_id == ""
    assert "[CPF_001]" in scrub.scrubbed_text
    assert "935.411.347-80" not in scrub.scrubbed_text
    assert list(tmp_path.rglob("*")) == []


def test_scrub_covers_clinical_note_leak_patterns(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = """
AMBULATORIO DERMATOLOGIA
Hospital Santa Luzia
Data do atendimento: 20/10/2024
Paciente: Crianca Teste: 7 anos e 4 meses
Data de Nascimento: 10/06/2017
Prontuario: 123456
Acompanhante: Aline (mae)
QP: dermatite ha 3 anos
Quando tinha apenas 1 mes de idade, apresentou lesao.
Aos 4 anos de idade, surgiram lesoes.
Em agosto/2023, apresentou placas.
Retorno em dezembro/2024.
Bruno (interno eletivo) sob orientacao de Dra Renata Alves.
"""

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "Hospital Santa Luzia" not in scrub.scrubbed_text
    assert "20/10/2024" not in scrub.scrubbed_text
    assert "Aline" not in scrub.scrubbed_text
    assert "Bruno" not in scrub.scrubbed_text
    assert "Renata Alves" not in scrub.scrubbed_text
    assert "7 anos e 4 meses" not in scrub.scrubbed_text
    assert "1 mes de idade" not in scrub.scrubbed_text
    assert "4 anos de idade" not in scrub.scrubbed_text
    assert "agosto/2023" not in scrub.scrubbed_text
    assert "dezembro/2024" not in scrub.scrubbed_text
    assert "ha 3 anos" in scrub.scrubbed_text
    assert "[INSTITUICAO_001]" in scrub.scrubbed_text
    assert "[FAMILIAR_001:first/title]" in (
        scrub.scrubbed_text
    )
    assert "[PROFISSIONAL_001:intern/mixed]" in (
        scrub.scrubbed_text
    )
    assert "[IDADE_001:school-age]" in scrub.scrubbed_text
    assert "[IDADE_002:infant]" in scrub.scrubbed_text
    assert "[IDADE_003:preschool]" in scrub.scrubbed_text
    assert "[DATA_001:T0/dd-mm-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_002:birth/dd-mm-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_003:T-14m/month-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_004:T+2m/month-yyyy]" in (
        scrub.scrubbed_text
    )

    restored = restore_text(scrub.scrubbed_text, scrub.mapping_path)

    assert restored == text


def test_date_of_birth_context_does_not_leak_to_following_event_date(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = "Data de Nascimento: 10/06/2017\nEm agosto/2023, apresentou placas."

    scrub = scrub_text(text, policy)

    assert "[DATA_001:birth/dd-mm-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_002:T0/month-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_002:birth" not in scrub.scrubbed_text


def test_date_of_birth_context_does_not_leak_within_same_line(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = "Data de Nascimento: 10/06/2017. Retorno em dezembro/2024."

    scrub = scrub_text(text, policy)

    assert "[DATA_001:birth/dd-mm-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_002:T0/month-yyyy]" in (
        scrub.scrubbed_text
    )
    assert "[DATA_002:birth" not in scrub.scrubbed_text


def test_scrub_covers_identity_address_and_doctor_title_leaks(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = """
Nome: Ana Silva Costa
DN: 10/06/2017
Idade: 8 anos
Prontuario: 123456
Acompanhantes: Bruna (mae)
Endereco: Quadra 10, Rua A, casa 1, Bairro Modelo
Residentes em Vila Modelo, mae, pai e dois irmaos.
Sob orientacao do Dr. Carlos Lima (staff)
"""

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "Ana Silva Costa" not in scrub.scrubbed_text
    assert "Quadra 10" not in scrub.scrubbed_text
    assert "Rua A" not in scrub.scrubbed_text
    assert "Bairro Modelo" not in scrub.scrubbed_text
    assert "Vila Modelo" not in scrub.scrubbed_text
    assert "Dr." not in scrub.scrubbed_text
    assert "Carlos Lima" not in scrub.scrubbed_text
    assert "Sob orientacao do [PROFISSIONAL_001]" not in scrub.scrubbed_text
    assert "Sob orientacao [PROFISSIONAL_001:" in scrub.scrubbed_text
    assert "[PACIENTE_001:" in scrub.scrubbed_text
    assert "[ENDERECO_001]" in scrub.scrubbed_text
    assert "[ENDERECO_002]" in scrub.scrubbed_text
    assert "[PROFISSIONAL_001:" in scrub.scrubbed_text


def test_scrub_preserves_filiation_field_while_redacting_family_names(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = (
        "Naturalidade: Barra Ficticia-BA\n"
        "Filiacao: Eloisio Ficticio da Cunha, Marilda Inventada Braga\n"
        "Escolaridade: Fundamental Completo"
    )

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "Naturalidade: [ENDERECO_001]" in scrub.scrubbed_text
    assert "Filiacao:" in scrub.scrubbed_text
    assert "Escolaridade: Fundamental Completo" in scrub.scrubbed_text
    assert "Eloisio Ficticio da Cunha" not in scrub.scrubbed_text
    assert "Marilda Inventada Braga" not in scrub.scrubbed_text
    assert "[FAMILIAR_001:full/title], [FAMILIAR_002:full/title]" in scrub.scrubbed_text


def test_scrub_formats_partial_dates_and_years_relative_to_anchor(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = (
        "Data do atendimento: 22/10/2025\n"
        "DI: 18/06\n"
        "Quadro iniciou em 2017."
    )

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "[DATA_001:T0/dd-mm-yyyy]" in scrub.scrubbed_text
    assert "[DATA_002:T-4m/dd-mm]" in scrub.scrubbed_text
    assert "[DATA_003:T-8a/yyyy]" in scrub.scrubbed_text


def test_scrub_preserves_uppercase_patient_indication_sentence(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = (
        "Telemedicina Psiquiatria IGES DF ID: 16142.\n"
        "PACIENTE TEM INDICACAO DE INTERNACAO PELA PSIQUIATRIA."
    )

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "Telemedicina Psiquiatria [INSTITUICAO_001] ID: [IDENTIFICADOR_CONTEXTUAL_001]" in (
        scrub.scrubbed_text
    )
    assert "PACIENTE TEM INDICACAO DE INTERNACAO PELA PSIQUIATRIA." in scrub.scrubbed_text
    assert "PACIENTE [INSTITUICAO" not in scrub.scrubbed_text
    assert "[PACIENTE_" not in scrub.scrubbed_text


def test_scrub_redacts_health_system_and_training_level_identifiers(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = (
        "Pedir leito via Sisleitos.\n"
        "Naiara R1 Psiquiatria sob orientacao do Dr Marcus.\n"
        "Augusto estudante de medicina do 10o semestre acompanhou."
    )

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "Sisleitos" not in scrub.scrubbed_text
    assert "Naiara" not in scrub.scrubbed_text
    assert "R1" not in scrub.scrubbed_text
    assert "Dr Marcus" not in scrub.scrubbed_text
    assert "Augusto" not in scrub.scrubbed_text
    assert "10o semestre" not in scrub.scrubbed_text
    assert "[IDENTIFICADOR_CONTEXTUAL_001]" in scrub.scrubbed_text
    assert "[PROFISSIONAL_001:resident/title]" in scrub.scrubbed_text
    assert "[PROFISSIONAL_002:first/title]" in scrub.scrubbed_text
    assert "[PROFISSIONAL_003:student/mixed]" in scrub.scrubbed_text


def test_scrub_preserves_prescription_duration(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = "Mantenho medicacoes em uso - deixo receitas para 4 meses."

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert scrub.scrubbed_text == text
    assert "IDADE" not in scrub.scrubbed_text

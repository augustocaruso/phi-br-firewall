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


def test_scrub_fail_closed_does_not_return_residual_phi(tmp_path) -> None:
    policy = PhiPolicy(min_score=0.9, audit_threshold=0.35)
    policy.mapping.base_dir = str(tmp_path)
    text = "Contato (11) 99999-8888."

    scrub = scrub_text(text, policy)

    assert scrub.ok is False
    assert scrub.scrubbed_text == ""
    assert "(11) 99999-8888" not in scrub.scrubbed_text
    assert "BR_PHONE" in {finding.entity_type for finding in scrub.audit.residual_findings}
    assert "(11) 99999-8888" not in str(scrub.model_dump())


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


def test_scrub_covers_dermatopediatrics_note_leak_patterns(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = """
AMBULATORIO DERMATOPEDIATRIA HUB - 20/10/2024
Paciente: Crianca Teste: 7 anos e 4 meses
Data de Nascimento: 10/06/2017
Prontuario: 123456
Acompanhante: Lara (mae)
QP: dermatite ha 3 anos
Quando tinha apenas 1 mes de idade, apresentou lesao.
Aos 4 anos de idade, surgiram lesoes.
Em agosto/2023, apresentou placas.
Retorno em dezembro/2024.
Mateus (interno eletivo) sob orientacao de Dra Paula Ramos.
"""

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "HUB" not in scrub.scrubbed_text
    assert "Lara" not in scrub.scrubbed_text
    assert "Mateus" not in scrub.scrubbed_text
    assert "Paula Ramos" not in scrub.scrubbed_text
    assert "7 anos e 4 meses" not in scrub.scrubbed_text
    assert "1 mes de idade" not in scrub.scrubbed_text
    assert "4 anos de idade" not in scrub.scrubbed_text
    assert "agosto/2023" not in scrub.scrubbed_text
    assert "dezembro/2024" not in scrub.scrubbed_text
    assert "ha 3 anos" in scrub.scrubbed_text
    assert "[INSTITUICAO_" in scrub.scrubbed_text
    assert "[FAMILIAR_" in scrub.scrubbed_text
    assert "[PROFISSIONAL_" in scrub.scrubbed_text
    assert "[IDADE_" in scrub.scrubbed_text
    assert "[DATA_" in scrub.scrubbed_text

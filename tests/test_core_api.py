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

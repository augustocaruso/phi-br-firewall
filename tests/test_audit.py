from phi_br_core import PhiPolicy, audit_text


def test_audit_blocks_residual_cpf() -> None:
    result = audit_text("Texto ainda contem CPF 935.411.347-80.", PhiPolicy())

    assert result.safe is False
    assert "BR_CPF" in {finding.entity_type for finding in result.residual_findings}


def test_audit_accepts_placeholder_text() -> None:
    result = audit_text("Paciente [PACIENTE_001], CPF [CPF_001].", PhiPolicy())

    assert result.safe is True
    assert result.residual_findings == []


def test_audit_ignores_phi_like_text_inside_placeholders() -> None:
    result = audit_text(
        "Encaminhado para [INSTITUICAO_001: Hospital Santa Luzia].",
        PhiPolicy(),
    )

    assert result.safe is True
    assert result.residual_findings == []


def test_audit_ignores_empty_masked_field_values() -> None:
    result = audit_text(
        "Naturalidade: [ENDERECO_001]\nFiliacao: [FAMILIAR_001]",
        PhiPolicy(),
    )

    assert result.safe is True
    assert result.residual_findings == []

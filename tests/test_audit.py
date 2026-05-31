from phi_br_core import PhiPolicy, audit_text


def test_audit_blocks_residual_cpf() -> None:
    result = audit_text("Texto ainda contem CPF 935.411.347-80.", PhiPolicy())

    assert result.safe is False
    assert "BR_CPF" in {finding.entity_type for finding in result.residual_findings}


def test_audit_accepts_placeholder_text() -> None:
    result = audit_text("Paciente [PACIENTE_001], CPF [CPF_001].", PhiPolicy())

    assert result.safe is True
    assert result.residual_findings == []

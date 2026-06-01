from __future__ import annotations

from phi_br_core import PhiPolicy, audit_text, scrub_text


def test_hardening_scrubs_structured_inpatient_note_leaks(tmp_path) -> None:
    policy = PhiPolicy()
    policy.mapping.base_dir = str(tmp_path)
    text = """
# IDENTIFICACAO
Nome: Paciente Exemplo
RG: 21.392.009-34
Nº SES: 8234636
Prontuario: 123456
Acompanhante: Justino Ficticio (irmao) - (61) 99999-9999

# DADOS BIOGRAFICOS
Naturalidade: Barra Ficticia-BA
Filiacao: Eloisio Ficticio da Cunha, Marilda Inventada Braga
Irmaos: 3 irmaos - Wilker Ficticio da Cunha (25 anos), Walas Inventado Braga
Viveu com os pais na Bahia ate os 20 anos. Mudou para Brasilia ha 3 anos.

# HDA
Historia iniciou em torno de 2013, com piora importante em 2017.
Tratamento iniciado em 18/06 e ajustado em 03/07.
Ha pelo menos 2 meses com recusa alimentar.

# PLANO
Para checar imagens, acessar: https://portal.exemplo.test/laudo
Protocolo: 2290259, Senha: 384715
Dar continuidade ao tratamento no Instituto Castro e Santos (ICS).

Naiara R1 Psiquiatria sob orientacao da Dra Paula Ramos.
"""

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    for leaked in (
        "21.392.009-34",
        "8234636",
        "Justino Ficticio",
        "Barra Ficticia",
        "Eloisio Ficticio",
        "Marilda Inventada",
        "Wilker Ficticio",
        "Walas Inventado",
        "Bahia",
        "Brasilia",
        "2013",
        "2017",
        "18/06",
        "03/07",
        "2290259",
        "384715",
        "Instituto Castro e Santos",
        "Naiara",
    ):
        assert leaked not in scrub.scrubbed_text
    assert "Ha pelo menos 2 meses com recusa alimentar." in scrub.scrubbed_text
    assert "Ha pelo menos [IDADE_" not in scrub.scrubbed_text


def test_strict_audit_blocks_structured_residual_identifiers() -> None:
    result = audit_text(
        """
RG: 21.392.009-34
Nº SES: 8234636
Filiacao: Eloisio Ficticio da Cunha, Marilda Inventada Braga
Protocolo: 2290259, Senha: 384715
Tratamento em 18/06 e em 2017.
""",
        PhiPolicy(),
    )

    assert result.safe is False
    assert {
        "BR_RG",
        "BR_CONTEXTUAL_IDENTIFIER",
        "BR_FAMILY_MEMBER_NAME",
        "BR_DATE",
    } <= {finding.entity_type for finding in result.residual_findings}

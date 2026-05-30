from phi_br_core.entities import (
    BR_CPF,
    BR_CRM,
    BR_DATE,
    BR_ENTITY_TYPES,
    ENTITY_SPECIFICITY,
    ENTITY_SPECIFICITY_ORDER,
    ENTITY_TO_PLACEHOLDER_PREFIX,
)
from phi_br_core.policy import PhiPolicy


def test_policy_defaults_are_safe() -> None:
    policy = PhiPolicy()

    assert policy.mode == "pseudonymize"
    assert policy.fail_closed is True
    assert policy.language == "pt"
    assert policy.min_score == 0.45
    assert policy.audit_threshold == 0.35
    assert policy.mapping.base_dir == ".tmp/phi"
    assert policy.sessions.ttl_hours == 24
    assert policy.sessions.purge_expired_on_start is True


def test_entity_constants_define_placeholders_and_specificity() -> None:
    assert BR_CPF in BR_ENTITY_TYPES
    assert ENTITY_TO_PLACEHOLDER_PREFIX[BR_CPF] == "CPF"
    assert ENTITY_TO_PLACEHOLDER_PREFIX["BR_PATIENT_NAME"] == "PACIENTE"
    assert BR_CRM in ENTITY_SPECIFICITY_ORDER
    assert ENTITY_SPECIFICITY[BR_CRM] > ENTITY_SPECIFICITY[BR_DATE]

import pytest
from phi_br_core.entities import (
    BR_CPF,
    BR_CRM,
    BR_DATE,
    BR_ENTITY_TYPES,
    ENTITY_SPECIFICITY,
    ENTITY_SPECIFICITY_ORDER,
    ENTITY_TO_PLACEHOLDER_PREFIX,
)
from phi_br_core.policy import AgePolicy, DatePolicy, MappingPolicy, PhiPolicy, SessionPolicy
from pydantic import BaseModel, ValidationError


def test_policy_defaults_are_safe() -> None:
    policy = PhiPolicy()

    assert policy.mode == "pseudonymize"
    assert policy.fail_closed is True
    assert policy.language == "pt"
    assert policy.min_score == 0.45
    assert policy.audit_threshold == 0.35
    assert policy.mapping.base_dir == ".tmp/phi"
    assert policy.dates.strategy == "preserve_relative"
    assert policy.ages.strategy == "age_band"
    assert policy.sessions.ttl_hours == 24
    assert policy.sessions.purge_expired_on_start is True


def test_entity_constants_define_placeholders_and_specificity() -> None:
    assert BR_CPF in BR_ENTITY_TYPES
    assert ENTITY_TO_PLACEHOLDER_PREFIX[BR_CPF] == "CPF"
    assert ENTITY_TO_PLACEHOLDER_PREFIX["BR_PATIENT_NAME"] == "PACIENTE"
    assert BR_CRM in ENTITY_SPECIFICITY_ORDER
    assert ENTITY_SPECIFICITY[BR_CRM] > ENTITY_SPECIFICITY[BR_DATE]


@pytest.mark.parametrize(
    "policy_model",
    [MappingPolicy, DatePolicy, AgePolicy, SessionPolicy, PhiPolicy],
)
def test_policy_models_reject_typo_fields(policy_model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError):
        policy_model(unknwon_field=True)


@pytest.mark.parametrize("field_name", ["min_score", "audit_threshold"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_phi_policy_rejects_scores_outside_zero_to_one(
    field_name: str, value: float
) -> None:
    with pytest.raises(ValidationError):
        PhiPolicy(**{field_name: value})


@pytest.mark.parametrize("field_name", ["ttl_hours", "max_sessions"])
@pytest.mark.parametrize("value", [-1, 0])
def test_session_policy_rejects_non_positive_limits(field_name: str, value: int) -> None:
    with pytest.raises(ValidationError):
        SessionPolicy(**{field_name: value})

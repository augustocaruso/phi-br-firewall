import pytest
from phi_br_core.models import PhiFinding
from pydantic import ValidationError


def test_phi_finding_accepts_valid_span_and_score() -> None:
    finding = PhiFinding(
        entity_type="BR_CPF",
        text="935.411.347-80",
        start=4,
        end=18,
        score=0.99,
    )

    assert finding.start == 4
    assert finding.end == 18
    assert finding.score == 0.99


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": -1, "end": 3, "score": 0.5},
        {"start": 3, "end": 3, "score": 0.5},
        {"start": 4, "end": 3, "score": 0.5},
        {"start": 0, "end": 3, "score": -0.01},
        {"start": 0, "end": 3, "score": 1.01},
    ],
)
def test_phi_finding_rejects_invalid_spans_and_scores(kwargs: dict[str, float | int]) -> None:
    with pytest.raises(ValidationError):
        PhiFinding(entity_type="BR_CPF", text="935.411.347-80", **kwargs)

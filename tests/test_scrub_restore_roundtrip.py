from __future__ import annotations

import json
from pathlib import Path

from phi_br_core.anonymizer import StablePlaceholderAnonymizer
from phi_br_core.models import PhiFinding


def test_stable_anonymizer_reuses_placeholder_for_same_value(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    findings = [
        PhiFinding(
            entity_type="BR_PATIENT_NAME", text="Joao da Silva", start=9, end=22, score=0.80
        ),
        PhiFinding(entity_type="BR_CPF", text="935.411.347-80", start=28, end=42, score=0.95),
        PhiFinding(
            entity_type="BR_PATIENT_NAME", text="Joao da Silva", start=53, end=66, score=0.80
        ),
    ]

    result = anonymizer.scrub(
        "Paciente Joao da Silva, CPF 935.411.347-80. Paciente Joao da Silva retornou.",
        findings,
        source="test",
    )

    assert result.scrubbed_text == (
        "Paciente [PACIENTE_001], CPF [CPF_001]. Paciente [PACIENTE_001] retornou."
    )
    assert anonymizer.restore(result.scrubbed_text, result.mapping_path) == (
        "Paciente Joao da Silva, CPF 935.411.347-80. Paciente Joao da Silva retornou."
    )


def test_stable_anonymizer_increments_same_category_values(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    text = "Paciente Ana. Paciente Bia."
    findings = [
        PhiFinding(entity_type="BR_PATIENT_NAME", text="Ana", start=9, end=12, score=0.80),
        PhiFinding(entity_type="BR_PATIENT_NAME", text="Bia", start=23, end=26, score=0.80),
    ]

    result = anonymizer.scrub(text, findings, source="test")

    assert result.scrubbed_text == "Paciente [PACIENTE_001]. Paciente [PACIENTE_002]."


def test_stable_anonymizer_uses_global_placeholder_numbers_across_sessions(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)

    first = anonymizer.scrub(
        "Paciente Ana.",
        [PhiFinding(entity_type="BR_PATIENT_NAME", text="Ana", start=9, end=12, score=0.80)],
        source="test",
    )
    second = anonymizer.scrub(
        "Paciente Bia.",
        [PhiFinding(entity_type="BR_PATIENT_NAME", text="Bia", start=9, end=12, score=0.80)],
        source="test",
    )

    assert first.scrubbed_text == "Paciente [PACIENTE_001]."
    assert second.scrubbed_text == "Paciente [PACIENTE_002]."
    assert anonymizer.index.resolve(["PACIENTE_001", "PACIENTE_002"]) == {
        "PACIENTE_001": first.session_id,
        "PACIENTE_002": second.session_id,
    }


def test_stable_anonymizer_writes_mapping_and_index(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    text = "Paciente Ana, CPF 935.411.347-80."
    findings = [
        PhiFinding(entity_type="BR_PATIENT_NAME", text="Ana", start=9, end=12, score=0.80),
        PhiFinding(entity_type="BR_CPF", text="935.411.347-80", start=18, end=32, score=0.95),
    ]

    result = anonymizer.scrub(text, findings, source="test")
    mapping_path = Path(result.mapping_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))

    assert mapping_path == tmp_path / result.session_id / "mapping.json"
    assert mapping == {
        "session_id": result.session_id,
        "items": {
            "PACIENTE_001": {"value": "Ana", "entity_type": "BR_PATIENT_NAME"},
            "CPF_001": {"value": "935.411.347-80", "entity_type": "BR_CPF"},
        },
    }
    assert index["placeholders"] == {
        "PACIENTE_001": [result.session_id],
        "CPF_001": [result.session_id],
    }


def test_stable_anonymizer_applies_overlap_resolution_before_replacing(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    text = "Registro CRM-DF 12345 confirmado."
    findings = [
        PhiFinding(entity_type="BR_DATE", text="12345", start=16, end=21, score=0.99),
        PhiFinding(entity_type="BR_CRM", text="CRM-DF 12345", start=9, end=21, score=0.85),
    ]

    result = anonymizer.scrub(text, findings, source="test")

    assert result.scrubbed_text == "Registro [CRM_001] confirmado."


def test_stable_anonymizer_uses_containing_phi_span_for_overlaps(tmp_path) -> None:
    anonymizer = StablePlaceholderAnonymizer(base_dir=tmp_path)
    text = "Endereco Rua A, 123, CEP 70000-000 confirmado."
    findings = [
        PhiFinding(
            entity_type="BR_ADDRESS",
            text="Rua A, 123, CEP 70000-000",
            start=9,
            end=34,
            score=0.70,
        ),
        PhiFinding(entity_type="BR_CEP", text="70000-000", start=25, end=34, score=0.95),
    ]

    result = anonymizer.scrub(text, findings, source="test")

    assert result.scrubbed_text == "Endereco [ENDERECO_001] confirmado."

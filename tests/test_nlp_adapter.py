from __future__ import annotations

from dataclasses import dataclass

import pytest
from phi_br_core import PhiPolicy, scrub_text
from phi_br_core.analyzer import clear_analyzer_cache
from phi_br_core.entities import (
    BR_ADDRESS,
    BR_INSTITUTION,
    BR_PERSON_NAME,
)
from phi_br_core.policy import NlpPolicy
from phi_br_core.recognizers.nlp_adapter import NlpEntityRecognizer


@pytest.fixture(autouse=True)
def clear_cached_analyzers() -> None:
    clear_analyzer_cache()
    yield
    clear_analyzer_cache()


@dataclass(frozen=True)
class FakeEntity:
    text: str
    start_char: int
    end_char: int
    label_: str


class FakeDoc:
    def __init__(self, entities: list[FakeEntity]) -> None:
        self.ents = entities


class FakeNlp:
    def __init__(self, entities: list[FakeEntity]) -> None:
        self._entities = entities

    def __call__(self, text: str) -> FakeDoc:
        del text
        return FakeDoc(self._entities)


def fake_entity(text: str, value: str, label: str) -> FakeEntity:
    start = text.index(value)
    return FakeEntity(value, start, start + len(value), label)


def test_nlp_recognizer_maps_person_org_and_location_entities() -> None:
    text = "Mariano foi atendido no Hospital Exemplo em Barra-BA."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True, min_score=0.71),
        nlp=FakeNlp(
            [
                FakeEntity("Mariano", 0, 7, "PER"),
                FakeEntity("Hospital Exemplo", 24, 40, "ORG"),
                FakeEntity("Barra-BA", 44, 52, "LOC"),
            ]
        ),
    )

    results = recognizer.analyze(
        text,
        [BR_PERSON_NAME, BR_INSTITUTION, BR_ADDRESS],
    )

    assert [(item.entity_type, text[item.start : item.end], item.score) for item in results] == [
        (BR_PERSON_NAME, "Mariano", 0.71),
        (BR_INSTITUTION, "Hospital Exemplo", 0.71),
        (BR_ADDRESS, "Barra-BA", 0.71),
    ]


def test_nlp_recognizer_respects_requested_entities() -> None:
    text = "Mariano foi atendido no Hospital Exemplo."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                FakeEntity("Mariano", 0, 7, "PER"),
                FakeEntity("Hospital Exemplo", 24, 40, "ORG"),
            ]
        ),
    )

    results = recognizer.analyze(text, [BR_INSTITUTION])

    assert [(item.entity_type, text[item.start : item.end]) for item in results] == [
        (BR_INSTITUTION, "Hospital Exemplo")
    ]


def test_nlp_recognizer_is_noop_when_policy_is_disabled() -> None:
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=False),
        nlp=FakeNlp([FakeEntity("Mariano", 0, 7, "PER")]),
    )

    assert recognizer.analyze("Mariano", [BR_PERSON_NAME]) == []


def test_nlp_recognizer_skips_placeholders_and_unknown_labels() -> None:
    text = "[PACIENTE_001] foi ao Hospital Exemplo."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                FakeEntity("[PACIENTE_001]", 0, 14, "PER"),
                FakeEntity("foi", 15, 18, "MISC"),
                FakeEntity("Hospital Exemplo", 22, 38, "ORG"),
            ]
        ),
    )

    results = recognizer.analyze(
        text,
        [BR_PERSON_NAME, BR_INSTITUTION],
    )

    assert [(item.entity_type, text[item.start : item.end]) for item in results] == [
        (BR_INSTITUTION, "Hospital Exemplo")
    ]


def test_nlp_recognizer_skips_spans_inside_placeholder_brackets() -> None:
    text = "[ENDERECO_001] mantido."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp([FakeEntity("ENDERECO_001", 1, 13, "ORG")]),
    )

    assert recognizer.analyze(text, [BR_INSTITUTION]) == []


def test_nlp_recognizer_skips_administrative_field_labels() -> None:
    text = "Paciente [PACIENTE_001], CPF [CPF_001]."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                FakeEntity("Paciente", 0, 8, "PER"),
                FakeEntity("CPF", 25, 28, "PER"),
            ]
        ),
    )

    assert recognizer.analyze(text, [BR_PERSON_NAME]) == []


def test_nlp_recognizer_rejects_common_clinical_false_positives() -> None:
    text = "FC 124bpm. Clozapina 25mg. Vitamina B12 5000mg. Glicemia 81."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                FakeEntity("FC", 0, 2, "ORG"),
                FakeEntity("Clozapina", 11, 20, "LOC"),
                FakeEntity("Vitamina B12", 27, 39, "PER"),
                FakeEntity("Glicemia", 48, 56, "ORG"),
            ]
        ),
    )

    assert recognizer.analyze(text, [BR_PERSON_NAME, BR_INSTITUTION, BR_ADDRESS]) == []


def test_nlp_recognizer_rejects_clinical_words_months_and_verbs_as_people() -> None:
    text = (
        "Magnésio e Vitamina B6. Internado no IHBDF de dezembro/2023. "
        "Liquor incolor. Ventrículos de morfologia. Médica relata. "
        "Indico internação. Transtorno obsessivo compulsivo."
    )
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                fake_entity(text, "Magnésio", "PER"),
                fake_entity(text, "Internado", "PER"),
                fake_entity(text, "dezembro/2023", "PER"),
                fake_entity(text, "Liquor", "PER"),
                fake_entity(text, "Ventrículos", "PER"),
                fake_entity(text, "Médica", "PER"),
                fake_entity(text, "Indico", "PER"),
                fake_entity(text, "Transtorno", "PER"),
            ]
        ),
    )

    assert recognizer.analyze(text, [BR_PERSON_NAME]) == []


@pytest.mark.parametrize(
    "value",
    [
        "internacao por Sindrome Catatonica",
        "Sindrome Catatonica",
    ],
)
def test_nlp_recognizer_rejects_diagnosis_phrase_marked_as_person(value: str) -> None:
    text = "Paciente com internacao por Sindrome Catatonica."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp([fake_entity(text, value, "PER")]),
    )

    assert recognizer.analyze(text, [BR_PERSON_NAME]) == []


def test_nlp_recognizer_rejects_spans_crossing_lines_and_admin_labels() -> None:
    text = "Naturalidade: Barra Ficticia-BA\nFiliacao: Eloisio Exemplo, Maria Exemplo"
    value = "Barra Ficticia-BA\nFiliacao"
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp([fake_entity(text, value, "LOC")]),
    )

    assert recognizer.analyze(text, [BR_ADDRESS]) == []


def test_nlp_recognizer_keeps_location_only_with_location_context() -> None:
    text = "Mudou para Brasilia. Uso de Clozapina."
    recognizer = NlpEntityRecognizer(
        NlpPolicy(enabled=True),
        nlp=FakeNlp(
            [
                FakeEntity("Brasilia", 11, 19, "LOC"),
                FakeEntity("Clozapina", 28, 37, "LOC"),
            ]
        ),
    )

    results = recognizer.analyze(text, [BR_ADDRESS])

    assert [(item.entity_type, text[item.start : item.end]) for item in results] == [
        (BR_ADDRESS, "Brasilia")
    ]


def test_scrub_renders_generic_nlp_person_with_safe_name_metadata(
    monkeypatch, tmp_path
) -> None:
    text = "Mariano compareceu."
    monkeypatch.setattr(
        "phi_br_core.recognizers.nlp_adapter.load_spacy_model",
        lambda _policy: FakeNlp([FakeEntity("Mariano", 0, 7, "PER")]),
    )
    policy = PhiPolicy(nlp=NlpPolicy(enabled=True))
    policy.mapping.base_dir = str(tmp_path)

    scrub = scrub_text(text, policy)

    assert scrub.ok is True
    assert "[PESSOA_001:first/title]" in scrub.scrubbed_text

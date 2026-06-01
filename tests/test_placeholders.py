from __future__ import annotations

import pytest
from phi_br_core.placeholders import (
    Placeholder,
    extract_placeholder_keys,
    iter_placeholders,
    parse_placeholder,
    parse_tag_list,
    serialize_placeholder,
)


def test_parse_placeholder_with_metadata_and_render_options() -> None:
    placeholder = parse_placeholder(
        "[DATA_010: kind=date; rel=T-19m; gran=month; src_fmt=month/yyyy|date=long]"
    )

    assert placeholder == Placeholder(
        key="DATA_010",
        public_meta={
            "kind": "date",
            "rel": "T-19m",
            "gran": "month",
            "src_fmt": "month/yyyy",
        },
        render_options={"date": "long"},
    )


def test_parse_placeholder_tolerates_legacy_public_metadata_with_spaces() -> None:
    placeholder = parse_placeholder(
        "[IDADE_059: kind=age; band=adulto jovem; src=exact|case=title]"
    )

    assert placeholder.key == "IDADE_059"
    assert placeholder.public_meta == {}
    assert placeholder.render_options == {"case": "title"}


def test_serialize_placeholder_omits_empty_sections() -> None:
    assert serialize_placeholder(Placeholder(key="PACIENTE_001")) == "[PACIENTE_001]"
    assert (
        serialize_placeholder(
            Placeholder(
                key="PACIENTE_001",
                public_meta={"kind": "name", "case": "upper"},
            )
        )
        == "[PACIENTE_001: kind=name; case=upper]"
    )


def test_parse_tag_list_rejects_unknown_shape() -> None:
    with pytest.raises(ValueError, match="invalid placeholder tag"):
        parse_tag_list("kind=date; free text")


def test_iter_placeholders_reports_spans_and_parsed_values() -> None:
    text = (
        "Paciente [PACIENTE_001: kind=name; role=patient|case=title] "
        "CPF [CPF_001]."
    )

    occurrences = list(iter_placeholders(text))

    assert [(item.placeholder.key, item.start, item.end) for item in occurrences] == [
        ("PACIENTE_001", 9, 59),
        ("CPF_001", 64, 73),
    ]
    assert occurrences[0].placeholder.public_meta == {
        "kind": "name",
        "role": "patient",
    }
    assert occurrences[0].placeholder.render_options == {"case": "title"}


def test_extract_placeholder_keys_deduplicates_in_first_seen_order() -> None:
    text = "[CPF_002] [PACIENTE_001: kind=name] [CPF_002|case=upper]"

    assert extract_placeholder_keys(text) == ["CPF_002", "PACIENTE_001"]

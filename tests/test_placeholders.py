from __future__ import annotations

import pytest
from phi_br_core.placeholders import (
    Placeholder,
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


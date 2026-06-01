from __future__ import annotations

from datetime import date

from phi_br_core.date_formatting import format_date_pt_br, parse_phi_date
from phi_br_core.formatting import detect_text_case, title_case_pt_br


def test_title_case_pt_br_preserves_lowercase_particles() -> None:
    assert title_case_pt_br("MARIANO INACIO MARANHAO GONCALVES") == (
        "Mariano Inacio Maranhao Goncalves"
    )
    assert title_case_pt_br("JOAO DA SILVA E SOUZA") == "Joao da Silva e Souza"
    assert title_case_pt_br("ANA-MARIA DOS SANTOS") == "Ana-Maria dos Santos"


def test_detect_text_case_for_names_and_acronyms() -> None:
    assert detect_text_case("JOAO DA SILVA") == "upper"
    assert detect_text_case("joao da silva") == "lower"
    assert detect_text_case("Joao da Silva") == "title"
    assert detect_text_case("HCB") == "upper"
    assert detect_text_case("Joao DA Silva") == "mixed"


def test_parse_phi_date_tracks_source_format_and_granularity() -> None:
    numeric = parse_phi_date("20/10/2024")
    month_year = parse_phi_date("agosto/2023")

    assert numeric is not None
    assert numeric.value == date(2024, 10, 20)
    assert numeric.granularity == "day"
    assert numeric.source_format == "dd/mm/yyyy"

    assert month_year is not None
    assert month_year.value == date(2023, 8, 1)
    assert month_year.granularity == "month"
    assert month_year.source_format == "month/yyyy"


def test_format_date_pt_br_uses_allowlisted_formats() -> None:
    value = date(2024, 10, 20)

    assert format_date_pt_br(value, "short") == "20/10/2024"
    assert format_date_pt_br(value, "long") == "20 de outubro de 2024"
    assert format_date_pt_br(value, "month_year") == "outubro de 2024"


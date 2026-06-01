from __future__ import annotations

import re
from typing import Literal

TextCase = Literal["none", "upper", "lower", "title", "mixed"]

_PARTICLES = {
    "a",
    "as",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
}


def detect_text_case(value: str) -> TextCase:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return "none"
    if all(char.isupper() for char in letters):
        return "upper"
    if all(char.islower() for char in letters):
        return "lower"
    if value == title_case_pt_br(value):
        return "title"
    return "mixed"


def title_case_pt_br(value: str) -> str:
    words = re.split(r"(\s+)", value.strip().lower())
    return "".join(_title_word(word) if not word.isspace() else word for word in words)


def apply_text_case(value: str, requested_case: str) -> str:
    if requested_case == "original":
        return value
    if requested_case == "upper":
        return value.upper()
    if requested_case == "lower":
        return value.lower()
    if requested_case == "title":
        return title_case_pt_br(value)
    raise ValueError("invalid case render option")


def _title_word(value: str) -> str:
    if value in _PARTICLES:
        return value
    pieces = re.split(r"([-'])", value)
    return "".join(_capitalize_piece(piece) for piece in pieces)


def _capitalize_piece(value: str) -> str:
    if value in {"-", "'"} or value == "":
        return value
    if value in _PARTICLES:
        return value
    return value[0].upper() + value[1:]


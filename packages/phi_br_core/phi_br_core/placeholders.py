from __future__ import annotations

import re
from dataclasses import dataclass, field

_PLACEHOLDER_RE = re.compile(r"^\[(?P<body>[^\[\]]+)\]$")
_KEY_RE = re.compile(r"^[A-Z0-9_]+_\d{3}$")
_TAG_RE = re.compile(r"^[a-z][a-z0-9_]*=[A-Za-z0-9_./:+-]+$")


@dataclass(frozen=True)
class Placeholder:
    key: str
    public_meta: dict[str, str] = field(default_factory=dict)
    render_options: dict[str, str] = field(default_factory=dict)


def parse_placeholder(value: str) -> Placeholder:
    match = _PLACEHOLDER_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("invalid placeholder")

    body = match.group("body")
    left, separator, render_text = body.partition("|")
    key_text, meta_separator, meta_text = left.partition(":")
    key = key_text.strip()
    if not _KEY_RE.fullmatch(key):
        raise ValueError("invalid placeholder key")

    return Placeholder(
        key=key,
        public_meta=parse_tag_list(meta_text) if meta_separator else {},
        render_options=parse_tag_list(render_text) if separator else {},
    )


def serialize_placeholder(placeholder: Placeholder) -> str:
    value = placeholder.key
    if placeholder.public_meta:
        value += f": {serialize_tag_list(placeholder.public_meta)}"
    if placeholder.render_options:
        value += f"|{serialize_tag_list(placeholder.render_options)}"
    return f"[{value}]"


def parse_tag_list(value: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    if value.strip() == "":
        return tags

    for raw_part in value.split(";"):
        part = raw_part.strip()
        if not _TAG_RE.fullmatch(part):
            raise ValueError("invalid placeholder tag")
        key, tag_value = part.split("=", 1)
        tags[key] = tag_value
    return tags


def serialize_tag_list(tags: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in tags.items())


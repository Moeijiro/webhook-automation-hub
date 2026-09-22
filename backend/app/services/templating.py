"""A deliberately small template language: ``{{ path.to.value }}``.

No expressions, no function calls, no attribute access -- a webhook payload is
untrusted input, and a template engine that can evaluate code is the wrong
tool for rendering it. Missing paths render as an empty string and are
reported, so a typo shows up in the execution log instead of silently
producing "None".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.\-\[\]]+)\s*\}\}")
MAX_OUTPUT_CHARS = 8000


@dataclass(slots=True)
class Rendered:
    text: str
    missing: list[str] = field(default_factory=list)


def resolve_path(payload: Any, path: str) -> Any:
    """Walk ``a.b.0.c`` through dicts and lists; return None when it breaks."""
    current = payload
    for part in path.replace("[", ".").replace("]", "").split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render(template: str, payload: Any, *, json_string: bool = False) -> Rendered:
    """Substitute every placeholder.

    ``json_string=True`` escapes each value for insertion inside a JSON string
    literal, so a quote in the payload cannot break the surrounding document.
    """
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        path = match.group(1)
        value = resolve_path(payload, path)
        if value is None:
            missing.append(path)
            return ""
        text = stringify(value)
        return json.dumps(text)[1:-1] if json_string else text

    output = PLACEHOLDER.sub(replace, template)
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "…"
    return Rendered(text=output, missing=missing)


def placeholders(template: str) -> list[str]:
    """Every path a template references -- used to preview a workflow."""
    return sorted({match.group(1) for match in PLACEHOLDER.finditer(template)})

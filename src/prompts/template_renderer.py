"""Small renderable prompt-template helper.

This module only composes prompt text. It does not call LLM providers and does
not parse model output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([^{}]+?)\s*}}")
_VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PromptTemplateError(ValueError):
    """Base error for prompt template rendering failures."""


class PromptTemplateMissingVariableError(PromptTemplateError):
    """Raised when a template references variables the caller did not provide."""


class PromptTemplatePlaceholderError(PromptTemplateError):
    """Raised when a template contains malformed placeholders."""


def render_template(template: str, variables: Mapping[str, object]) -> str:
    """Render `{{variable_name}}` placeholders with stable value serialization.

    Placeholder names must be Python-identifier-like strings. Dict/list/tuple and
    Pydantic model values are serialized as deterministic pretty JSON. Strings
    are inserted as-is so callers may pass pre-rendered prompt fragments.
    """

    placeholder_names = _collect_placeholder_names(template)
    missing_variables = sorted(
        name for name in placeholder_names if name not in variables
    )
    if missing_variables:
        raise PromptTemplateMissingVariableError(
            "missing prompt template variables: " + ", ".join(missing_variables)
        )

    def replace_placeholder(match: re.Match[str]) -> str:
        variable_name = _normalize_placeholder_name(match.group(1))
        return serialize_prompt_value(variables[variable_name])

    return _PLACEHOLDER_PATTERN.sub(replace_placeholder, template)


def render_template_file(path: str | Path, variables: Mapping[str, object]) -> str:
    """Read and render one UTF-8 prompt template file."""

    template_path = Path(path)
    return render_template(
        template_path.read_text(encoding="utf-8"),
        variables,
    )


def serialize_prompt_value(value: object) -> str:
    """Serialize a prompt variable value deterministically."""

    if isinstance(value, str):
        return value

    if isinstance(value, BaseModel):
        return _dumps_json(value.model_dump(mode="json"))

    if isinstance(value, Mapping):
        return _dumps_json(_to_jsonable(value))

    if _is_json_sequence(value):
        return _dumps_json(_to_jsonable(value))

    return str(value)


def _collect_placeholder_names(template: str) -> tuple[str, ...]:
    names: list[str] = []
    placeholder_spans: list[tuple[int, int]] = []

    for match in _PLACEHOLDER_PATTERN.finditer(template):
        names.append(_normalize_placeholder_name(match.group(1)))
        placeholder_spans.append(match.span())

    _raise_for_unmatched_placeholder_delimiters(
        template=template,
        placeholder_spans=tuple(placeholder_spans),
    )

    return tuple(dict.fromkeys(names))


def _normalize_placeholder_name(raw_name: str) -> str:
    name = raw_name.strip()
    if not _VARIABLE_NAME_PATTERN.fullmatch(name):
        raise PromptTemplatePlaceholderError(
            f"malformed prompt template placeholder: {{{{ {raw_name} }}}}"
        )

    return name


def _raise_for_unmatched_placeholder_delimiters(
    *,
    template: str,
    placeholder_spans: tuple[tuple[int, int], ...],
) -> None:
    cursor = 0
    unchecked_parts: list[str] = []

    for start, end in placeholder_spans:
        unchecked_parts.append(template[cursor:start])
        cursor = end

    unchecked_parts.append(template[cursor:])
    unchecked_template_text = "".join(unchecked_parts)

    if "{{" in unchecked_template_text or "}}" in unchecked_template_text:
        raise PromptTemplatePlaceholderError(
            "template contains unresolved or malformed placeholder delimiters"
        )


def _dumps_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _to_jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")

    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}

    if _is_json_sequence(value):
        return [_to_jsonable(item) for item in value]

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime | date):
        return value.isoformat()

    return value


def _is_json_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value,
        str | bytes | bytearray,
    )


__all__ = [
    "PromptTemplateError",
    "PromptTemplateMissingVariableError",
    "PromptTemplatePlaceholderError",
    "render_template",
    "render_template_file",
    "serialize_prompt_value",
]

"""Deterministic JSON schema export helpers for Pydantic models."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def export_pydantic_json_schema(
    model_type: type[BaseModel],
    *,
    title: str | None = None,
) -> dict[str, object]:
    """Export a normalized JSON schema dictionary for one Pydantic model."""

    schema = model_type.model_json_schema()
    if title is not None:
        schema["title"] = title

    return _normalize_schema_object(schema)


def export_pydantic_json_schema_json(
    model_type: type[BaseModel],
    *,
    title: str | None = None,
) -> str:
    """Export one Pydantic model JSON schema as deterministic pretty JSON."""

    schema = export_pydantic_json_schema(model_type, title=title)
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)


def _normalize_schema_object(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize_schema_object(value[key])
            for key in sorted(value, key=str)
        }

    if isinstance(value, list):
        return [_normalize_schema_object(item) for item in value]

    return value


__all__ = [
    "export_pydantic_json_schema",
    "export_pydantic_json_schema_json",
]

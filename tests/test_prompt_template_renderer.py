"""Tests for renderable prompt templates."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from src.prompts.template_renderer import (
    PromptTemplateMissingVariableError,
    PromptTemplatePlaceholderError,
    render_template,
    render_template_file,
    serialize_prompt_value,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "configs" / "prompts" / "v2"


class DemoPromptPayload(BaseModel):
    case_id: str
    created_at: datetime
    values: tuple[int, ...]


def test_render_template_replaces_explicit_placeholders() -> None:
    rendered = render_template(
        "Schema:\n{{output_schema_json}}\nInput:\n{{ input_json }}",
        {
            "output_schema_json": {"type": "object", "required": ["case_id"]},
            "input_json": {"case_id": "case-001", "stage_id": "stage-001"},
        },
    )

    assert "{{" not in rendered
    assert '"required": [' in rendered
    assert '"case_id": "case-001"' in rendered


def test_render_template_rejects_missing_variables() -> None:
    with pytest.raises(PromptTemplateMissingVariableError, match="input_json"):
        render_template("Input:\n{{input_json}}", {})


def test_render_template_rejects_malformed_placeholders() -> None:
    with pytest.raises(PromptTemplatePlaceholderError, match="malformed"):
        render_template("Input:\n{{input-json}}", {"input-json": "value"})


def test_render_template_rejects_unresolved_placeholder_delimiters() -> None:
    with pytest.raises(PromptTemplatePlaceholderError, match="unresolved"):
        render_template("Input:\n{{input_json", {"input_json": "value"})


def test_serialize_prompt_value_stabilizes_dict_and_list_json() -> None:
    serialized = serialize_prompt_value(
        {
            "zeta": [3, {"beta": 2, "alpha": 1}],
            "alpha": "first",
        }
    )

    assert serialized.startswith('{\n  "alpha": "first"')
    assert '"alpha": 1' in serialized
    assert '"beta": 2' in serialized
    assert '"zeta": [' in serialized


def test_serialize_prompt_value_supports_pydantic_models() -> None:
    payload = DemoPromptPayload(
        case_id="case-001",
        created_at=datetime(2026, 4, 28, 9, 30, 0),
        values=(2, 1),
    )

    serialized = serialize_prompt_value(payload)

    assert '"case_id": "case-001"' in serialized
    assert '"created_at": "2026-04-28T09:30:00"' in serialized
    assert '"values": [' in serialized


def test_render_template_file_renders_case_structurer_template() -> None:
    rendered = render_template_file(
        PROMPT_DIR / "case_structurer.md",
        {
            "output_schema_json": {"title": "CaseStructuringDraft"},
            "input_json": {"stage_metadata": {"stage_id": "stage-001"}},
        },
    )

    assert "{{" not in rendered
    assert "Case Structurer" in rendered
    assert '"title": "CaseStructuringDraft"' in rendered
    assert '"stage_id": "stage-001"' in rendered


def test_render_template_file_renders_evidence_atomizer_template() -> None:
    rendered = render_template_file(
        PROMPT_DIR / "evidence_atomizer.md",
        {
            "output_schema_json": {"title": "EvidenceAtomizationDraft"},
            "input_json": {"stage_metadata": {"stage_id": "stage-001"}},
        },
    )

    assert "{{" not in rendered
    assert "Evidence Atomizer" in rendered
    assert '"title": "EvidenceAtomizationDraft"' in rendered
    assert '"stage_id": "stage-001"' in rendered

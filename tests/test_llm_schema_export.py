"""Tests for deterministic Pydantic schema export."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from src.adapters.case_structuring import CaseStructuringDraft
from src.adapters.evidence_atomization import EvidenceAtomizationDraft
from src.llm.schema_export import (
    export_pydantic_json_schema,
    export_pydantic_json_schema_json,
)


class SmallSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zeta: int
    alpha: str


def test_schema_export_returns_deterministic_schema_dict() -> None:
    first = export_pydantic_json_schema(SmallSchemaModel)
    second = export_pydantic_json_schema(SmallSchemaModel)

    assert first == second
    assert list(first) == sorted(first)
    assert first["title"] == "SmallSchemaModel"
    assert "properties" in first


def test_schema_export_json_is_stable_and_parseable() -> None:
    first = export_pydantic_json_schema_json(SmallSchemaModel)
    second = export_pydantic_json_schema_json(SmallSchemaModel)

    assert first == second
    assert json.loads(first)["title"] == "SmallSchemaModel"
    assert first.startswith("{\n")


def test_schema_export_supports_title_override() -> None:
    schema = export_pydantic_json_schema(SmallSchemaModel, title="CustomSchema")

    assert schema["title"] == "CustomSchema"


def test_schema_export_supports_phase1_adapter_drafts() -> None:
    case_schema = export_pydantic_json_schema(CaseStructuringDraft)
    evidence_schema = export_pydantic_json_schema(EvidenceAtomizationDraft)

    assert case_schema["title"] == "CaseStructuringDraft"
    assert evidence_schema["title"] == "EvidenceAtomizationDraft"
    assert "properties" in case_schema
    assert "properties" in evidence_schema

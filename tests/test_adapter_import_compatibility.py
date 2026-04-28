"""Tests for adapter migration import compatibility."""

from __future__ import annotations

from src.adapters.case_structurer_adapter import (
    CaseStructurerInput,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)
from src.adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)
from src.agents.case_structurer import (
    CaseStructurerInput as LegacyCaseStructurerInput,
    build_case_structurer_prompt as legacy_build_case_structurer_prompt,
    parse_case_structurer_payload as legacy_parse_case_structurer_payload,
)
from src.agents.evidence_atomizer import (
    EvidenceAtomizerInput as LegacyEvidenceAtomizerInput,
    build_evidence_atomizer_prompt as legacy_build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload as legacy_parse_evidence_atomizer_payload,
)


def test_case_structurer_new_and_legacy_imports_resolve_same_objects() -> None:
    assert LegacyCaseStructurerInput is CaseStructurerInput
    assert legacy_build_case_structurer_prompt is build_case_structurer_prompt
    assert legacy_parse_case_structurer_payload is parse_case_structurer_payload


def test_evidence_atomizer_new_and_legacy_imports_resolve_same_objects() -> None:
    assert LegacyEvidenceAtomizerInput is EvidenceAtomizerInput
    assert legacy_build_evidence_atomizer_prompt is build_evidence_atomizer_prompt
    assert legacy_parse_evidence_atomizer_payload is parse_evidence_atomizer_payload

"""Tests for Phase 1-4 Evidence Atomizer adapter contract schema."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.adapters.evidence_atomization import EvidenceAtomizationDraft
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.stage import InfoModality


def _base_evidence_atom_payload(
    *, evidence_id: str, source_doc_id: str, atom_index: int, stage_id: str = "stage-001"
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "stage_id": stage_id,
        "source_doc_id": source_doc_id,
        "atom_index": atom_index,
        "category": EvidenceCategory.SYMPTOM,
        "modality": InfoModality.HISTORY,
        "statement": "Chronic cough is present.",
        "raw_excerpt": "Chronic cough for several years.",
        "polarity": EvidencePolarity.PRESENT,
        "certainty": EvidenceCertainty.REPORTED,
        "temporality": EvidenceTemporality.CURRENT,
        "subject": EvidenceSubject.PATIENT,
    }


def _base_extraction_activity_payload(stage_id: str = "stage-001") -> dict[str, object]:
    return {
        "activity_id": "activity-001",
        "stage_id": stage_id,
        "extraction_method": ExtractionMethod.RULE_BASED,
        "extractor_name": "evidence_atomizer_adapter",
        "extractor_version": "0.1.0",
        "occurred_at": datetime(2026, 4, 27, 11, 0, 0),
        "input_source_doc_ids": ("doc-001", "doc-002", "doc-003"),
    }


def _base_evidence_atomization_payload() -> dict[str, object]:
    return {
        "draft_id": "atomization_draft-001",
        "case_id": "case-001",
        "stage_id": "stage-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "evidence_atoms": (
            _base_evidence_atom_payload(
                evidence_id="evd-001",
                source_doc_id="doc-001",
                atom_index=0,
            ),
            _base_evidence_atom_payload(
                evidence_id="evd-002",
                source_doc_id="doc-002",
                atom_index=1,
            ),
        ),
        "extraction_activity": _base_extraction_activity_payload(),
    }


def test_evidence_atomization_draft_valid_construction() -> None:
    draft = EvidenceAtomizationDraft(**_base_evidence_atomization_payload())

    assert draft.kind == "evidence_atomization_draft"
    assert len(draft.evidence_atoms) == 2


def test_evidence_atomization_draft_rejects_empty_evidence_atoms() -> None:
    payload = _base_evidence_atomization_payload()
    payload["evidence_atoms"] = ()

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_duplicate_evidence_ids() -> None:
    payload = _base_evidence_atomization_payload()
    payload["evidence_atoms"][1]["evidence_id"] = "evd-001"

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_evidence_stage_mismatch() -> None:
    payload = _base_evidence_atomization_payload()
    payload["evidence_atoms"][0]["stage_id"] = "stage-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_evidence_source_doc_outside_draft() -> None:
    payload = _base_evidence_atomization_payload()
    payload["evidence_atoms"][0]["source_doc_id"] = "doc-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_extraction_activity_stage_mismatch() -> None:
    payload = _base_evidence_atomization_payload()
    payload["extraction_activity"]["stage_id"] = "stage-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_extraction_activity_doc_coverage_gap() -> None:
    payload = _base_evidence_atomization_payload()
    payload["extraction_activity"]["input_source_doc_ids"] = ("doc-001",)

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)


def test_evidence_atomization_draft_rejects_extra_hypotheses_field() -> None:
    payload = _base_evidence_atomization_payload()
    payload["hypotheses"] = ("hyp-001",)

    with pytest.raises(ValidationError):
        EvidenceAtomizationDraft(**payload)

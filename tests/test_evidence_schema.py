"""Tests for Phase 1-1 EvidenceAtom schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.evidence import (
    EvidenceAtom,
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.stage import InfoModality
from src.schemas.state import EvidenceAtom as ExportedEvidenceAtom


def _base_payload() -> dict[str, object]:
    return {
        "evidence_id": "evd-001",
        "stage_id": "stage-001",
        "source_doc_id": "doc-001",
        "atom_index": 0,
        "category": EvidenceCategory.IMAGING_FINDING,
        "modality": InfoModality.HRCT_TEXT,
        "statement": "Subpleural reticulation in bilateral lower lobes.",
        "raw_excerpt": "HRCT: subpleural reticulation in bilateral lower lobes.",
        "polarity": EvidencePolarity.PRESENT,
        "certainty": EvidenceCertainty.CONFIRMED,
        "temporality": EvidenceTemporality.CURRENT,
        "subject": EvidenceSubject.PATIENT,
        "normalized_key": "  HRCT Reticulation  ",
        "value_text": None,
        "unit": None,
        "body_site": "bilateral lower lobes",
        "source_span_start": 15,
        "source_span_end": 68,
        "extraction_method": "rule_based_v1",
        "non_authoritative_note": "用于人工复核，不参与权威推理。",
    }


def test_evidence_atom_valid_construction() -> None:
    atom = EvidenceAtom(**_base_payload())

    assert atom.evidence_id == "evd-001"
    assert atom.modality is InfoModality.HRCT_TEXT
    assert atom.category is EvidenceCategory.IMAGING_FINDING


def test_evidence_atom_kind_defaults_and_rejects_invalid_value() -> None:
    atom = EvidenceAtom(**_base_payload())
    assert atom.kind == "evidence_atom"

    payload = _base_payload()
    payload["kind"] = "evidence"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_authoritative_field_must_be_non_empty() -> None:
    payload = _base_payload()
    payload["statement"] = "   "

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_evidence_id_pattern_rejected_when_mixed_with_stage_prefix() -> None:
    payload = _base_payload()
    payload["evidence_id"] = "stage_001"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_stage_id_pattern_rejected_when_using_doc_prefix() -> None:
    payload = _base_payload()
    payload["stage_id"] = "doc_001"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_source_doc_id_pattern_rejected_when_using_stage_prefix() -> None:
    payload = _base_payload()
    payload["source_doc_id"] = "stage_001"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_id_patterns_allow_underscore_style() -> None:
    payload = _base_payload()
    payload["evidence_id"] = "ev_001"
    payload["stage_id"] = "stage_001"
    payload["source_doc_id"] = "doc_001"

    atom = EvidenceAtom(**payload)

    assert atom.evidence_id == "ev_001"
    assert atom.stage_id == "stage_001"
    assert atom.source_doc_id == "doc_001"


def test_source_span_must_appear_in_pair() -> None:
    payload = _base_payload()
    payload["source_span_end"] = None

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_source_span_ordering_rejected_when_reversed() -> None:
    payload = _base_payload()
    payload["source_span_start"] = 99
    payload["source_span_end"] = 20

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_source_span_allows_equal_bounds() -> None:
    payload = _base_payload()
    payload["source_span_start"] = 20
    payload["source_span_end"] = 20

    atom = EvidenceAtom(**payload)

    assert atom.source_span_start == atom.source_span_end == 20


def test_category_modality_mismatch_is_rejected() -> None:
    payload = _base_payload()
    payload["category"] = EvidenceCategory.PATHOLOGY_FINDING
    payload["modality"] = InfoModality.PFT

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_other_category_keeps_bootstrap_permissive_behavior() -> None:
    payload = _base_payload()
    payload["category"] = EvidenceCategory.OTHER
    payload["modality"] = InfoModality.PFT

    atom = EvidenceAtom(**payload)

    assert atom.category is EvidenceCategory.OTHER
    assert atom.modality is InfoModality.PFT


def test_normalized_key_is_canonicalized() -> None:
    payload = _base_payload()
    payload["normalized_key"] = "  BALF Cell Count (%)  "

    atom = EvidenceAtom(**payload)

    assert atom.normalized_key == "balf_cell_count"


def test_blank_optional_text_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["value_text"] = "  "
    payload["unit"] = "   "
    payload["extraction_method"] = "\n"

    atom = EvidenceAtom(**payload)

    assert atom.value_text is None
    assert atom.unit is None
    assert atom.extraction_method is None


def test_extra_diagnosis_field_is_forbidden() -> None:
    payload = _base_payload()
    payload["diagnosis"] = "IPF"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_invalid_enum_value_rejected() -> None:
    payload = _base_payload()
    payload["certainty"] = "likely"

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_temporality_taxonomy_contains_revision_friendly_states() -> None:
    expected = {
        "historical",
        "current",
        "newly_observed",
        "persistent",
        "worsening",
        "improving",
        "unspecified",
    }
    actual = {item.value for item in EvidenceTemporality}

    assert actual == expected


def test_subject_taxonomy_uses_subject_semantics() -> None:
    expected = {
        "patient",
        "family_member",
        "environment",
        "external_report",
        "other",
    }
    actual = {item.value for item in EvidenceSubject}

    assert actual == expected


def test_serialization_roundtrip() -> None:
    atom = EvidenceAtom(**_base_payload())

    serialized = atom.model_dump_json()
    restored = EvidenceAtom.model_validate_json(serialized)

    assert restored == atom


def test_state_module_exports_evidence_atom() -> None:
    assert ExportedEvidenceAtom is EvidenceAtom

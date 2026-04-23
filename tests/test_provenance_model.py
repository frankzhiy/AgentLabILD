"""Tests for Phase 1-2 PROV-lite provenance models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.provenance.model import (
    ClaimProvenance,
    EvidenceProvenance,
    ExtractionActivity,
    ExtractionMethod,
    SourceAnchor,
)
from src.schemas.claim import ClaimReference, ClaimRelation, ClaimTargetKind
from src.schemas.evidence import (
    EvidenceAtom,
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.stage import InfoModality


def _base_source_anchor_payload() -> dict[str, object]:
    return {
        "anchor_id": "anchor-001",
        "stage_id": "stage-001",
        "source_doc_id": "doc-001",
        "modality": InfoModality.HRCT_TEXT,
        "raw_excerpt": "HRCT: bilateral subpleural reticulation.",
        "section_label": "Impression",
        "span_start": 6,
        "span_end": 38,
    }


def _base_extraction_activity_payload() -> dict[str, object]:
    return {
        "activity_id": "activity-001",
        "stage_id": "stage-001",
        "extraction_method": ExtractionMethod.LLM_STRUCTURED,
        "extractor_name": "evidence_atomizer",
        "extractor_version": "v1.2.0",
        "occurred_at": datetime(2026, 4, 23, 9, 30, 0),
        "input_source_doc_ids": ["doc-001", "doc-002"],
        "model_name": "gpt-5.3-codex",
        "prompt_template_id": "prompt_v1_evidence_atomizer",
    }


def _base_evidence_provenance_payload() -> dict[str, object]:
    return {
        "evidence_provenance_id": "eprov-001",
        "stage_id": "stage-001",
        "evidence_id": "evd-001",
        "source_anchors": [_base_source_anchor_payload()],
        "extraction_activity": _base_extraction_activity_payload(),
    }


def _base_claim_provenance_payload() -> dict[str, object]:
    return {
        "claim_provenance_id": "cprov-001",
        "stage_id": "stage-001",
        "claim_ref_id": "claim_ref-001",
        "evidence_ids": ["evd-001", "evd-002"],
        "evidence_provenance_ids": ["eprov-001"],
        "derivation_activity": _base_extraction_activity_payload(),
    }


def _base_evidence_atom_payload() -> dict[str, object]:
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
    }


def _base_claim_reference_payload() -> dict[str, object]:
    return {
        "claim_ref_id": "claim_ref-001",
        "stage_id": "stage-001",
        "target_kind": ClaimTargetKind.HYPOTHESIS,
        "target_id": "hyp-001",
        "claim_text": "Reticulation supports fibrotic ILD hypothesis.",
        "relation": ClaimRelation.SUPPORTS,
        "evidence_ids": ["evd-001", "evd-002"],
    }


def test_source_anchor_valid_construction() -> None:
    anchor = SourceAnchor(**_base_source_anchor_payload())

    assert anchor.kind == "source_anchor"
    assert anchor.anchor_id == "anchor-001"


def test_source_anchor_requires_paired_span() -> None:
    payload = _base_source_anchor_payload()
    payload["span_end"] = None

    with pytest.raises(ValidationError):
        SourceAnchor(**payload)


def test_extraction_activity_requires_non_empty_unique_doc_ids() -> None:
    payload = _base_extraction_activity_payload()
    payload["input_source_doc_ids"] = []

    with pytest.raises(ValidationError):
        ExtractionActivity(**payload)

    payload = _base_extraction_activity_payload()
    payload["input_source_doc_ids"] = ["doc-001", "doc-001"]

    with pytest.raises(ValidationError):
        ExtractionActivity(**payload)


def test_evidence_provenance_valid_construction() -> None:
    evidence_provenance = EvidenceProvenance(**_base_evidence_provenance_payload())

    assert evidence_provenance.kind == "evidence_provenance"
    assert evidence_provenance.source_anchors[0].anchor_id == "anchor-001"


def test_evidence_provenance_rejects_stage_mismatch() -> None:
    payload = _base_evidence_provenance_payload()
    payload["source_anchors"][0]["stage_id"] = "stage-002"

    with pytest.raises(ValidationError):
        EvidenceProvenance(**payload)


def test_evidence_provenance_rejects_activity_doc_gap() -> None:
    payload = _base_evidence_provenance_payload()
    payload["extraction_activity"]["input_source_doc_ids"] = ["doc-002"]

    with pytest.raises(ValidationError):
        EvidenceProvenance(**payload)


def test_claim_provenance_valid_construction() -> None:
    claim_provenance = ClaimProvenance(**_base_claim_provenance_payload())

    assert claim_provenance.kind == "claim_provenance"
    assert claim_provenance.claim_ref_id == "claim_ref-001"


def test_claim_provenance_rejects_invalid_evidence_sets() -> None:
    payload = _base_claim_provenance_payload()
    payload["evidence_ids"] = []

    with pytest.raises(ValidationError):
        ClaimProvenance(**payload)

    payload = _base_claim_provenance_payload()
    payload["evidence_provenance_ids"] = ["eprov-001", "eprov-001"]

    with pytest.raises(ValidationError):
        ClaimProvenance(**payload)


def test_evidence_atom_backward_compatible_without_provenance() -> None:
    evidence_atom = EvidenceAtom(**_base_evidence_atom_payload())

    assert evidence_atom.evidence_id == "evd-001"
    assert evidence_atom.provenance is None


def test_evidence_atom_accepts_aligned_provenance() -> None:
    payload = _base_evidence_atom_payload()
    payload["provenance"] = _base_evidence_provenance_payload()

    evidence_atom = EvidenceAtom(**payload)

    assert evidence_atom.provenance is not None
    assert evidence_atom.provenance.evidence_id == evidence_atom.evidence_id


def test_evidence_atom_rejects_misaligned_provenance() -> None:
    payload = _base_evidence_atom_payload()
    provenance = _base_evidence_provenance_payload()
    provenance["evidence_id"] = "evd-999"
    payload["provenance"] = provenance

    with pytest.raises(ValidationError):
        EvidenceAtom(**payload)


def test_claim_reference_backward_compatible_without_provenance() -> None:
    claim_ref = ClaimReference(**_base_claim_reference_payload())

    assert claim_ref.claim_ref_id == "claim_ref-001"
    assert claim_ref.provenance is None


def test_claim_reference_accepts_aligned_provenance() -> None:
    payload = _base_claim_reference_payload()
    payload["provenance"] = _base_claim_provenance_payload()

    claim_ref = ClaimReference(**payload)

    assert claim_ref.provenance is not None
    assert set(claim_ref.provenance.evidence_ids).issubset(set(claim_ref.evidence_ids))


def test_claim_reference_rejects_provenance_evidence_not_subset() -> None:
    payload = _base_claim_reference_payload()
    provenance = _base_claim_provenance_payload()
    provenance["evidence_ids"] = ["evd-001", "evd-999"]
    payload["provenance"] = provenance

    with pytest.raises(ValidationError):
        ClaimReference(**payload)

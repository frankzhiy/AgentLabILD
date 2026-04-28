"""Tests for the Hypothesis Board Bootstrapper adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from src.adapters.evidence_atomization import EvidenceAtomizationDraft
from src.adapters.hypothesis_board_bootstrapper_adapter import (
    HypothesisBoardBootstrapperInput,
    HypothesisBoardBootstrapperStatus,
    build_hypothesis_board_bootstrapper_prompt,
    parse_hypothesis_board_bootstrapper_payload,
)
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.stage import InfoModality, StageContext, StageType, TriggerType


def _stage_context() -> StageContext:
    return StageContext(
        stage_id="stage-001",
        case_id="case-001",
        stage_index=0,
        stage_type=StageType.INITIAL_REVIEW,
        trigger_type=TriggerType.INITIAL_PRESENTATION,
        created_at=datetime(2026, 4, 28, 9, 0, 0),
        available_modalities=(InfoModality.HISTORY, InfoModality.HRCT_TEXT),
        source_doc_ids=("doc-001", "doc-002"),
    )


def _evidence_atom_payload(
    *,
    evidence_id: str,
    source_doc_id: str,
    atom_index: int,
    category: EvidenceCategory,
    modality: InfoModality,
    statement: str,
    raw_excerpt: str,
) -> dict[str, object]:
    return {
        "kind": "evidence_atom",
        "evidence_id": evidence_id,
        "stage_id": "stage-001",
        "source_doc_id": source_doc_id,
        "atom_index": atom_index,
        "category": category.value,
        "modality": modality.value,
        "statement": statement,
        "raw_excerpt": raw_excerpt,
        "polarity": EvidencePolarity.PRESENT.value,
        "certainty": EvidenceCertainty.REPORTED.value,
        "temporality": EvidenceTemporality.CURRENT.value,
        "subject": EvidenceSubject.PATIENT.value,
    }


def _evidence_atomization_draft() -> EvidenceAtomizationDraft:
    return EvidenceAtomizationDraft(
        kind="evidence_atomization_draft",
        draft_id="atomization_draft-001",
        case_id="case-001",
        stage_id="stage-001",
        source_doc_ids=("doc-001", "doc-002"),
        evidence_atoms=(
            _evidence_atom_payload(
                evidence_id="evd-001",
                source_doc_id="doc-001",
                atom_index=0,
                category=EvidenceCategory.SYMPTOM,
                modality=InfoModality.HISTORY,
                statement="Chronic cough is reported.",
                raw_excerpt="chronic cough",
            ),
            _evidence_atom_payload(
                evidence_id="evd-002",
                source_doc_id="doc-002",
                atom_index=1,
                category=EvidenceCategory.IMAGING_FINDING,
                modality=InfoModality.HRCT_TEXT,
                statement="HRCT text reports reticulation.",
                raw_excerpt="reticulation",
            ),
        ),
        extraction_activity={
            "kind": "extraction_activity",
            "activity_id": "activity-001",
            "stage_id": "stage-001",
            "extraction_method": ExtractionMethod.RULE_BASED.value,
            "extractor_name": "test_evidence_atomizer",
            "extractor_version": "0.1.0",
            "occurred_at": datetime(2026, 4, 28, 9, 5, 0),
            "input_source_doc_ids": ("doc-001", "doc-002"),
        },
    )


def _base_input() -> HypothesisBoardBootstrapperInput:
    return HypothesisBoardBootstrapperInput(
        case_id="case-001",
        stage_id="stage-001",
        stage_context=_stage_context(),
        evidence_atomization_draft=_evidence_atomization_draft(),
        board_id="board-001",
        initialized_at=datetime(2026, 4, 28, 9, 10, 0),
    )


def valid_hypothesis_board_bootstrap_payload() -> dict[str, object]:
    initialized_at = datetime(2026, 4, 28, 9, 10, 0)
    return {
        "kind": "hypothesis_board_bootstrap_draft",
        "draft_id": "hypothesis_board_bootstrap_draft-001",
        "case_id": "case-001",
        "stage_id": "stage-001",
        "evidence_ids": ("evd-001", "evd-002"),
        "claim_references": (
            {
                "kind": "claim_reference",
                "claim_ref_id": "claim_ref-001",
                "stage_id": "stage-001",
                "target_kind": "hypothesis",
                "target_id": "hyp-001",
                "claim_text": "Chronic cough supports fibrotic ILD as a candidate.",
                "relation": "supports",
                "evidence_ids": ("evd-001",),
                "strength": "moderate",
            },
            {
                "kind": "claim_reference",
                "claim_ref_id": "claim_ref-002",
                "stage_id": "stage-001",
                "target_kind": "action",
                "target_id": "action-001",
                "claim_text": "HRCT reticulation supports MDT imaging review.",
                "relation": "supports",
                "evidence_ids": ("evd-002",),
                "strength": "moderate",
            },
        ),
        "hypotheses": (
            {
                "kind": "hypothesis_state",
                "hypothesis_id": "hyp-001",
                "hypothesis_key": "fibrotic_ild",
                "stage_id": "stage-001",
                "hypothesis_label": "Fibrotic interstitial lung disease candidate",
                "status": "under_consideration",
                "confidence_level": "low",
                "supporting_claim_ref_ids": ("claim_ref-001",),
                "rank_index": 1,
            },
        ),
        "action_candidates": (
            {
                "kind": "action_candidate",
                "action_candidate_id": "action-001",
                "action_key": "mdt_imaging_review",
                "stage_id": "stage-001",
                "action_type": "request_multidisciplinary_review",
                "action_text": "Review HRCT pattern and clinical history in MDT.",
                "status": "under_consideration",
                "urgency": "routine",
                "linked_hypothesis_ids": ("hyp-001",),
                "supporting_claim_ref_ids": ("claim_ref-002",),
                "rank_index": 1,
            },
        ),
        "board_init": {
            "kind": "hypothesis_board_init",
            "board_id": "board-001",
            "case_id": "case-001",
            "stage_id": "stage-001",
            "board_status": "draft",
            "init_source": "stage_bootstrap",
            "initialized_at": initialized_at,
            "evidence_ids": ("evd-001", "evd-002"),
            "hypothesis_ids": ("hyp-001",),
            "action_candidate_ids": ("action-001",),
            "ranked_hypothesis_ids": ("hyp-001",),
        },
    }


def test_bootstrapper_adapter_accepts_valid_payload() -> None:
    result = parse_hypothesis_board_bootstrapper_payload(
        valid_hypothesis_board_bootstrap_payload(),
        _base_input(),
    )

    assert result.status is HypothesisBoardBootstrapperStatus.ACCEPTED
    assert result.draft is not None
    assert result.draft.board_init.hypothesis_ids == ("hyp-001",)
    assert result.draft.hypotheses[0].supporting_claim_ref_ids == ("claim_ref-001",)
    assert result.draft.claim_references[0].evidence_ids == ("evd-001",)


def test_bootstrapper_adapter_rejects_final_diagnosis_field() -> None:
    payload = valid_hypothesis_board_bootstrap_payload()
    payload["final_diagnosis"] = "IPF"

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert result.draft is None
    assert any("final_diagnosis" in error for error in result.errors)


def test_bootstrapper_adapter_rejects_unknown_evidence_id() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["evidence_ids"] = ("evd-001", "evd-unknown")
    payload["claim_references"][0]["evidence_ids"] = ("evd-unknown",)

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert any("evidence" in error for error in result.errors)


def test_bootstrapper_adapter_rejects_orphan_hypothesis_claim_ref() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["hypotheses"][0]["supporting_claim_ref_ids"] = ("claim_ref-999",)

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert any("HypothesisState claim_ref_id" in error for error in result.errors)


def test_bootstrapper_adapter_rejects_mismatched_claim_target() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["claim_references"][0]["target_id"] = "hyp-999"

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert any("target_id must equal hypothesis_id" in error for error in result.errors)


def test_bootstrapper_adapter_rejects_empty_board_without_changing_board_schema() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["hypotheses"] = ()
    payload["board_init"]["hypothesis_ids"] = ()
    payload["board_init"]["ranked_hypothesis_ids"] = ()

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert any("hypothesis" in error for error in result.errors)


def test_bootstrapper_adapter_rejects_action_linked_to_unknown_hypothesis() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["action_candidates"][0]["linked_hypothesis_ids"] = ("hyp-999",)

    result = parse_hypothesis_board_bootstrapper_payload(payload, _base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert any("linked_hypothesis_ids" in error for error in result.errors)


def test_bootstrapper_prompt_renders_schema_input_and_evidence_ids() -> None:
    prompt = build_hypothesis_board_bootstrapper_prompt(_base_input())

    assert "{{" not in prompt
    assert "}}" not in prompt
    assert "### Input JSON" in prompt
    assert "### Output Schema JSON" in prompt
    assert "HypothesisBoardBootstrapDraft" in prompt
    assert "evd-001" in prompt
    assert "evd-002" in prompt

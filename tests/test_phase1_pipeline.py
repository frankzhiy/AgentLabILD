"""Tests for the full Phase 1 orchestration pipeline."""

from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

import src.orchestration.phase1_pipeline as phase1_pipeline_module
from src.adapters.case_structurer_adapter import (
    CaseStructurerInput,
    CaseStructurerResult,
    CaseStructurerStatus,
)
from src.adapters.case_structuring import CaseStructuringDraft
from src.adapters.evidence_atomization import EvidenceAtomizationDraft
from src.adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerResult,
    EvidenceAtomizerStatus,
)
from src.adapters.hypothesis_board_bootstrapper_adapter import (
    HypothesisBoardBootstrapDraft,
    HypothesisBoardBootstrapperInput,
    HypothesisBoardBootstrapperResult,
    HypothesisBoardBootstrapperStatus,
)
from src.adapters.validation_bridge import AdapterValidationBridgeStatus
from src.orchestration import Phase1Pipeline, Phase1PipelineInput, Phase1PipelineResult
from src.orchestration.phase1_pipeline import Phase1PipelineStatus
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.stage import InfoModality, StageType, TriggerType


@dataclass
class CountingStateSink:
    envelopes: list[object] = field(default_factory=list)

    def persist(self, envelope: object) -> None:
        self.envelopes.append(envelope)


@dataclass
class FakeCaseStructurerAgent:
    result: CaseStructurerResult
    calls: int = 0
    inputs: list[CaseStructurerInput] = field(default_factory=list)

    def run(self, input: CaseStructurerInput) -> CaseStructurerResult:
        self.calls += 1
        self.inputs.append(input)
        return self.result


@dataclass
class FakeEvidenceAtomizerAgent:
    result: EvidenceAtomizerResult
    calls: int = 0
    inputs: list[EvidenceAtomizerInput] = field(default_factory=list)

    def run(self, input: EvidenceAtomizerInput) -> EvidenceAtomizerResult:
        self.calls += 1
        self.inputs.append(input)
        return self.result


@dataclass
class FakeHypothesisBoardBootstrapperAgent:
    result: HypothesisBoardBootstrapperResult
    calls: int = 0
    inputs: list[HypothesisBoardBootstrapperInput] = field(default_factory=list)

    def run(
        self,
        input: HypothesisBoardBootstrapperInput,
    ) -> HypothesisBoardBootstrapperResult:
        self.calls += 1
        self.inputs.append(input)
        return self.result


def _pipeline_input(*, raw_text: str | None = None) -> Phase1PipelineInput:
    return Phase1PipelineInput(
        raw_text=(
            raw_text
            if raw_text is not None
            else "Patient reports chronic cough. HRCT text reports reticulation."
        ),
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        stage_id="stage-001",
        stage_index=0,
        stage_type=StageType.INITIAL_REVIEW,
        trigger_type=TriggerType.INITIAL_PRESENTATION,
        created_at=datetime(2026, 4, 28, 10, 0, 0),
        extraction_activity_id="activity-001",
        evidence_extraction_occurred_at=datetime(2026, 4, 28, 9, 15, 0),
        board_id="board-001",
        board_initialized_at=datetime(2026, 4, 28, 9, 30, 0),
        state_id="state-001",
    )


def _case_structuring_draft() -> CaseStructuringDraft:
    return CaseStructuringDraft(
        kind="case_structuring_draft",
        draft_id="case_struct_draft-001",
        case_id="case-001",
        source_doc_ids=("doc-001",),
        proposed_stage_context={
            "kind": "stage_context",
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW.value,
            "trigger_type": TriggerType.INITIAL_PRESENTATION.value,
            "created_at": datetime(2026, 4, 28, 10, 0, 0),
            "available_modalities": (
                InfoModality.HISTORY.value,
                InfoModality.HRCT_TEXT.value,
            ),
            "source_doc_ids": ("doc-001",),
        },
        timeline_items=(
            {
                "kind": "case_timeline_item",
                "timeline_item_id": "timeline_item-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "event_type": "symptom_onset",
                "event_time_text": "current presentation",
                "description": "Patient reports chronic cough.",
            },
        ),
        normalized_findings=(
            {
                "kind": "normalized_finding",
                "finding_id": "finding-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "finding_key": "chronic cough",
                "finding_text": "Patient reports chronic cough.",
                "modality": InfoModality.HISTORY.value,
            },
        ),
        candidate_clue_groups=(
            {
                "kind": "candidate_clue_group",
                "clue_group_id": "clue_group-001",
                "stage_id": "stage-001",
                "group_key": "respiratory_symptom_clues",
                "finding_ids": ("finding-001",),
                "summary": "Respiratory symptom clue group.",
            },
        ),
    )


def _evidence_atom_payload(
    *,
    evidence_id: str,
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
        "source_doc_id": "doc-001",
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
        source_doc_ids=("doc-001",),
        evidence_atoms=(
            _evidence_atom_payload(
                evidence_id="evd-001",
                atom_index=0,
                category=EvidenceCategory.SYMPTOM,
                modality=InfoModality.HISTORY,
                statement="Patient reports chronic cough.",
                raw_excerpt="chronic cough",
            ),
            _evidence_atom_payload(
                evidence_id="evd-002",
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
            "extractor_name": "fake_evidence_atomizer",
            "extractor_version": "0.1.0",
            "occurred_at": datetime(2026, 4, 28, 9, 15, 0),
            "input_source_doc_ids": ("doc-001",),
        },
    )


def _bootstrap_payload() -> dict[str, object]:
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
                "claim_text": "Reticulation supports MDT imaging review as a next step.",
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
            "initialized_at": datetime(2026, 4, 28, 9, 30, 0),
            "evidence_ids": ("evd-001", "evd-002"),
            "hypothesis_ids": ("hyp-001",),
            "action_candidate_ids": ("action-001",),
            "ranked_hypothesis_ids": ("hyp-001",),
        },
    }


def _accepted_case_result() -> CaseStructurerResult:
    return CaseStructurerResult(
        status=CaseStructurerStatus.ACCEPTED,
        draft=_case_structuring_draft(),
    )


def _accepted_evidence_result() -> EvidenceAtomizerResult:
    return EvidenceAtomizerResult(
        status=EvidenceAtomizerStatus.ACCEPTED,
        draft=_evidence_atomization_draft(),
    )


def _accepted_evidence_result_with_raw_excerpt_mismatch() -> EvidenceAtomizerResult:
    payload = _evidence_atomization_draft().model_dump(mode="python")
    payload["evidence_atoms"][0]["raw_excerpt"] = "ground-glass opacity"
    return EvidenceAtomizerResult(
        status=EvidenceAtomizerStatus.ACCEPTED,
        draft=EvidenceAtomizationDraft.model_validate(payload),
    )


def _accepted_bootstrapper_result(
    payload: dict[str, object] | None = None,
) -> HypothesisBoardBootstrapperResult:
    return HypothesisBoardBootstrapperResult(
        status=HypothesisBoardBootstrapperStatus.ACCEPTED,
        draft=HypothesisBoardBootstrapDraft.model_validate(
            payload if payload is not None else _bootstrap_payload()
        ),
    )


def _pipeline_with(
    *,
    case_result: CaseStructurerResult | None = None,
    evidence_result: EvidenceAtomizerResult | None = None,
    bootstrapper_result: HypothesisBoardBootstrapperResult | None = None,
    sink: CountingStateSink | None = None,
) -> tuple[
    Phase1Pipeline,
    FakeCaseStructurerAgent,
    FakeEvidenceAtomizerAgent,
    FakeHypothesisBoardBootstrapperAgent,
    CountingStateSink,
]:
    resolved_sink = sink or CountingStateSink()
    case_agent = FakeCaseStructurerAgent(case_result or _accepted_case_result())
    evidence_agent = FakeEvidenceAtomizerAgent(
        evidence_result or _accepted_evidence_result()
    )
    bootstrapper_agent = FakeHypothesisBoardBootstrapperAgent(
        bootstrapper_result or _accepted_bootstrapper_result()
    )
    return (
        Phase1Pipeline(
            case_structurer_agent=case_agent,
            evidence_atomizer_agent=evidence_agent,
            hypothesis_board_bootstrapper_agent=bootstrapper_agent,
            sink=resolved_sink,
        ),
        case_agent,
        evidence_agent,
        bootstrapper_agent,
        resolved_sink,
    )


def test_phase1_pipeline_accepted_full_path_builds_and_writes_envelope() -> None:
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with()

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.ACCEPTED
    assert result.candidate_envelope is not None
    assert result.adapter_validation_result is not None
    assert (
        result.adapter_validation_result.status
        is AdapterValidationBridgeStatus.PASSED
    )
    assert result.write_decision is not None
    assert result.write_decision.should_persist is True
    assert len(sink.envelopes) == 1
    assert case_agent.calls == 1
    assert evidence_agent.calls == 1
    assert bootstrapper_agent.calls == 1
    envelope = result.candidate_envelope
    assert envelope.board_init.hypothesis_ids == ("hyp-001",)
    assert envelope.hypotheses
    assert {atom.evidence_id for atom in envelope.evidence_atoms} == {
        "evd-001",
        "evd-002",
    }
    assert envelope.claim_references[0].target_id == envelope.hypotheses[0].hypothesis_id
    assert envelope.action_candidates[0].linked_hypothesis_ids == ("hyp-001",)
    assert case_agent.inputs[0].source_documents[0].source_doc_id == "doc-001"
    assert evidence_agent.inputs[0].case_structuring_draft is not None
    assert bootstrapper_agent.inputs[0].evidence_atomization_draft.draft_id == (
        "atomization_draft-001"
    )


def test_phase1_pipeline_intake_rejected_stops_before_agents_or_write() -> None:
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with()

    result = pipeline.run(_pipeline_input(raw_text="   "))

    assert result.status is Phase1PipelineStatus.REJECTED
    assert result.write_decision is None
    assert result.candidate_envelope is None
    assert case_agent.calls == 0
    assert evidence_agent.calls == 0
    assert bootstrapper_agent.calls == 0
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_case_structurer_rejected_stops_before_downstream_agents() -> None:
    rejected_case_result = CaseStructurerResult(
        status=CaseStructurerStatus.REJECTED,
        draft=None,
        errors=("case structurer rejected",),
    )
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with(
        case_result=rejected_case_result
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.REJECTED
    assert case_agent.calls == 1
    assert evidence_agent.calls == 0
    assert bootstrapper_agent.calls == 0
    assert result.write_decision is None
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_evidence_atomizer_manual_review_stops_before_bootstrapper() -> None:
    manual_evidence_result = EvidenceAtomizerResult(
        status=EvidenceAtomizerStatus.MANUAL_REVIEW,
        draft=None,
        errors=("evidence needs review",),
    )
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with(
        evidence_result=manual_evidence_result
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.MANUAL_REVIEW
    assert case_agent.calls == 1
    assert evidence_agent.calls == 1
    assert bootstrapper_agent.calls == 0
    assert result.write_decision is None
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_bridge_rejects_bad_raw_excerpt_before_bootstrapper() -> None:
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with(
        evidence_result=_accepted_evidence_result_with_raw_excerpt_mismatch()
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.REJECTED
    assert result.adapter_validation_result is not None
    assert (
        result.adapter_validation_result.status
        is AdapterValidationBridgeStatus.FAILED
    )
    assert result.candidate_envelope is None
    assert result.write_decision is None
    assert case_agent.calls == 1
    assert evidence_agent.calls == 1
    assert bootstrapper_agent.calls == 0
    assert len(sink.envelopes) == 0
    assert any("Adapter validation bridge failed" in error for error in result.errors)
    assert result.adapter_validation_result.evidence_atomization_report is not None
    assert any(
        issue.issue_code == "provenance.raw_excerpt_not_found"
        for issue in result.adapter_validation_result.evidence_atomization_report.issues
    )


def test_phase1_pipeline_bootstrapper_rejected_stops_before_write_gate() -> None:
    rejected_bootstrapper_result = HypothesisBoardBootstrapperResult(
        status=HypothesisBoardBootstrapperStatus.REJECTED,
        draft=None,
        errors=("bootstrapper rejected",),
    )
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with(
        bootstrapper_result=rejected_bootstrapper_result
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.REJECTED
    assert case_agent.calls == 1
    assert evidence_agent.calls == 1
    assert bootstrapper_agent.calls == 1
    assert result.write_decision is None
    assert result.candidate_envelope is None
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_rejects_bootstrapper_board_evidence_mismatch_before_write() -> None:
    payload = deepcopy(_bootstrap_payload())
    payload["board_init"]["evidence_ids"] = ("evd-001",)
    pipeline, case_agent, evidence_agent, bootstrapper_agent, sink = _pipeline_with(
        bootstrapper_result=_accepted_bootstrapper_result(payload)
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.REJECTED
    assert result.candidate_envelope is None
    assert result.write_decision is None
    assert any("board_init.evidence_ids" in error for error in result.errors)
    assert case_agent.calls == 1
    assert evidence_agent.calls == 1
    assert bootstrapper_agent.calls == 1
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_does_not_accept_evidence_only_bootstrapper_output() -> None:
    rejected_bootstrapper_result = HypothesisBoardBootstrapperResult(
        status=HypothesisBoardBootstrapperStatus.REJECTED,
        draft=None,
        errors=("hypothesis_ids must contain at least one hypothesis id",),
    )
    pipeline, _, _, _, sink = _pipeline_with(
        bootstrapper_result=rejected_bootstrapper_result
    )

    result = pipeline.run(_pipeline_input())

    assert result.status is Phase1PipelineStatus.REJECTED
    assert result.candidate_envelope is None
    assert result.write_decision is None
    assert len(sink.envelopes) == 0


def test_phase1_pipeline_exports_public_objects() -> None:
    pipeline, _, _, _, _ = _pipeline_with()
    result = pipeline.run(_pipeline_input())

    assert isinstance(pipeline, Phase1Pipeline)
    assert isinstance(result, Phase1PipelineResult)
    assert result.status is Phase1PipelineStatus.ACCEPTED


def test_phase1_pipeline_module_does_not_import_llm_or_provider_clients() -> None:
    module_ast = ast.parse(inspect.getsource(phase1_pipeline_module))
    import_targets: list[str] = []

    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            import_targets.extend(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module_name = node.module or ""
            import_targets.append(f"{prefix}{module_name}")

    forbidden_import_prefixes = (
        "src.llm",
        "..llm",
        "openai",
        "anthropic",
        "google.generativeai",
    )
    for forbidden_prefix in forbidden_import_prefixes:
        assert all(
            not target.startswith(forbidden_prefix) for target in import_targets
        )

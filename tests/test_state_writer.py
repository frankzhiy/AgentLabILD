"""Tests for Phase 1-3 validator-gated state writer layer."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import src.state.state_writer as state_writer_module
from src.schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from src.state import (
    InMemoryStateSink,
    NoOpStateSink,
    WriteDecisionStatus,
    WritePolicy,
    attempt_phase1_write,
)
from src.validators.pipeline import (
    Phase1ValidationPipelineResult,
    SCHEMA_ONLY_EXECUTION_ORDER,
    ValidationPipelinePolicy,
)
from tests.test_provenance_checker import build_valid_envelope


def _build_non_blocking_invalid_report() -> StateValidationReport:
    issue = ValidationIssue(
        issue_id="issue-manual-0001",
        issue_code="provenance.missing_provenance",
        severity=ValidationSeverity.WARNING,
        message="manual review required for non-blocking provenance concern",
        target_kind=ValidationTargetKind.CLAIM_REFERENCE,
        target_id="claim_ref-001",
        blocking=False,
    )

    return StateValidationReport(
        report_id="report-manual-0001",
        case_id="case-abc",
        stage_id="stage-001",
        board_id="board-001",
        generated_at=datetime(2026, 4, 27, 16, 0, 0),
        is_valid=False,
        has_blocking_issue=False,
        issues=(issue,),
        validator_name="phase1_manual_review_simulator",
        validator_version="1.0.0",
        summary="non-blocking but invalid report for manual review path",
    )


def _build_manual_review_pipeline_result() -> Phase1ValidationPipelineResult:
    envelope = build_valid_envelope()

    return Phase1ValidationPipelineResult(
        candidate_state_id=envelope.state_id,
        candidate_envelope=envelope,
        reports=(_build_non_blocking_invalid_report(),),
        has_blocking_issue=False,
        validator_execution_order=SCHEMA_ONLY_EXECUTION_ORDER,
        summary="manual review pipeline fixture",
    )


def test_state_writer_persists_accepted_candidate_to_in_memory_sink() -> None:
    envelope = build_valid_envelope()
    sink = InMemoryStateSink()

    decision = attempt_phase1_write(
        envelope,
        sink=sink,
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    persisted = sink.get(envelope.state_id)

    assert decision.status is WriteDecisionStatus.ACCEPTED
    assert decision.should_persist is True
    assert len(sink) == 1
    assert sink.list_state_ids() == (envelope.state_id,)
    assert persisted is not None
    assert persisted.state_id == envelope.state_id


def test_state_writer_does_not_persist_rejected_candidate() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.created_at = envelope.created_at + timedelta(seconds=1)
    sink = InMemoryStateSink()

    decision = attempt_phase1_write(envelope, sink=sink)

    assert decision.status is WriteDecisionStatus.REJECTED
    assert decision.should_persist is False
    assert decision.accepted_envelope is None
    assert len(sink) == 0


def test_state_writer_manual_review_not_persisted_by_default(
    monkeypatch: object,
) -> None:
    sink = InMemoryStateSink()
    manual_result = _build_manual_review_pipeline_result()

    monkeypatch.setattr(
        state_writer_module,
        "validate_phase1_candidate_pipeline",
        lambda *args, **kwargs: manual_result,
    )

    decision = attempt_phase1_write(build_valid_envelope(), sink=sink)

    assert decision.status is WriteDecisionStatus.MANUAL_REVIEW
    assert decision.should_persist is False
    assert decision.accepted_envelope is not None
    assert len(sink) == 0


def test_state_writer_manual_review_persistence_follows_write_policy(
    monkeypatch: object,
) -> None:
    sink = InMemoryStateSink()
    manual_result = _build_manual_review_pipeline_result()

    monkeypatch.setattr(
        state_writer_module,
        "validate_phase1_candidate_pipeline",
        lambda *args, **kwargs: manual_result,
    )

    decision = attempt_phase1_write(
        build_valid_envelope(),
        sink=sink,
        policy=WritePolicy(allow_manual_review_persist=True),
    )

    assert decision.status is WriteDecisionStatus.MANUAL_REVIEW
    assert decision.should_persist is True
    assert decision.accepted_envelope is not None
    assert len(sink) == 1
    assert sink.list_state_ids() == (decision.candidate_state_id,)


def test_state_writer_raw_invalid_payload_returns_rejected_decision() -> None:
    sink = InMemoryStateSink()
    invalid_payload = {"state_id": "state-raw-001"}

    decision = attempt_phase1_write(invalid_payload, sink=sink)

    assert decision.status is WriteDecisionStatus.REJECTED
    assert decision.should_persist is False
    assert decision.accepted_envelope is None
    assert decision.candidate_state_id == "state-raw-001"
    assert len(sink) == 0


def test_state_writer_preserves_candidate_state_id_and_accepted_envelope_consistency() -> None:
    envelope = build_valid_envelope()

    decision = attempt_phase1_write(
        envelope,
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    assert decision.status is WriteDecisionStatus.ACCEPTED
    assert decision.accepted_envelope is not None
    assert decision.candidate_state_id == envelope.state_id
    assert decision.accepted_envelope.state_id == decision.candidate_state_id


def test_state_writer_noop_sink_keeps_normal_decision_without_persistence() -> None:
    envelope = build_valid_envelope()
    sink = NoOpStateSink()

    decision = attempt_phase1_write(
        envelope,
        sink=sink,
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    assert decision.status is WriteDecisionStatus.ACCEPTED
    assert decision.should_persist is True
    assert sink.persist_call_count == 1
    assert sink.list_state_ids() == ()


def test_state_writer_does_not_mutate_input_envelope_instance() -> None:
    envelope = build_valid_envelope()
    before = deepcopy(envelope.model_dump(mode="python"))

    _ = attempt_phase1_write(
        envelope,
        sink=InMemoryStateSink(),
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    after = envelope.model_dump(mode="python")
    assert after == before

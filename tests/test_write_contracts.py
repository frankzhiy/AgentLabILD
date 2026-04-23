"""Focused tests for Phase 1-3 write-gate contract objects."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import inspect

import pytest
from pydantic import ValidationError

from src.schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from src.state import WriteDecision, WriteDecisionStatus, WritePolicy
import src.state.write_decision as write_decision_module
import src.state.write_policy as write_policy_module
import src.state.write_status as write_status_module
from tests.test_provenance_checker import build_valid_envelope


def _build_report(*, suffix: str, blocking: bool) -> StateValidationReport:
    issue = ValidationIssue(
        issue_id=f"issue-{suffix}",
        issue_code=(
            "provenance.orphan_evidence_provenance_reference"
            if blocking
            else "provenance.missing_provenance"
        ),
        severity=ValidationSeverity.ERROR if blocking else ValidationSeverity.WARNING,
        message="blocking provenance issue" if blocking else "non-blocking provenance note",
        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
        target_id="evd-001",
        blocking=blocking,
    )

    return StateValidationReport(
        report_id=f"report-{suffix}",
        case_id="case-abc",
        stage_id="stage-001",
        board_id="board-001",
        generated_at=datetime(2026, 4, 23, 18, 0, 0),
        is_valid=not blocking,
        has_blocking_issue=blocking,
        issues=(issue,),
        validator_name="phase1_provenance_validator",
        validator_version="1.2.0",
        summary="blocking" if blocking else "non-blocking",
    )


def test_write_decision_status_values() -> None:
    assert WriteDecisionStatus.ACCEPTED.value == "accepted"
    assert WriteDecisionStatus.REJECTED.value == "rejected"
    assert WriteDecisionStatus.MANUAL_REVIEW.value == "manual_review"


def test_write_policy_default_gate_behavior() -> None:
    policy = WritePolicy()

    assert policy.allow_manual_review_persist is False
    assert policy.should_persist(
        status=WriteDecisionStatus.ACCEPTED,
        has_blocking_issue=False,
    ) is True
    assert policy.should_persist(
        status=WriteDecisionStatus.MANUAL_REVIEW,
        has_blocking_issue=False,
    ) is False
    assert policy.should_persist(
        status=WriteDecisionStatus.ACCEPTED,
        has_blocking_issue=True,
    ) is False


def test_write_decision_default_rejected_construction() -> None:
    decision = WriteDecision(
        candidate_state_id="state-001",
        status=WriteDecisionStatus.REJECTED,
    )

    assert decision.has_blocking_issue is False
    assert decision.should_persist is False
    assert decision.reports == ()


def test_write_decision_accepted_semantics() -> None:
    envelope = build_valid_envelope()

    decision = WriteDecision(
        candidate_state_id=envelope.state_id,
        status=WriteDecisionStatus.ACCEPTED,
        accepted_envelope=envelope,
        summary="  accepted by gate  ",
    )

    assert decision.has_blocking_issue is False
    assert decision.should_persist is True
    assert decision.summary == "accepted by gate"


def test_write_decision_rejected_semantics_with_blocking_report() -> None:
    blocking_report = _build_report(suffix="200", blocking=True)

    decision = WriteDecision(
        candidate_state_id="state-001",
        status=WriteDecisionStatus.REJECTED,
        reports=(blocking_report,),
    )

    assert decision.has_blocking_issue is True
    assert decision.should_persist is False
    assert decision.accepted_envelope is None


def test_write_decision_manual_review_semantics_default_and_policy_override() -> None:
    envelope = build_valid_envelope()
    non_blocking_report = _build_report(suffix="201", blocking=False)

    default_decision = WriteDecision(
        candidate_state_id=envelope.state_id,
        status=WriteDecisionStatus.MANUAL_REVIEW,
        reports=(non_blocking_report,),
    )
    assert default_decision.should_persist is False

    override_policy = WritePolicy(allow_manual_review_persist=True)
    override_decision = WriteDecision(
        candidate_state_id=envelope.state_id,
        status=WriteDecisionStatus.MANUAL_REVIEW,
        policy=override_policy,
        accepted_envelope=envelope,
        reports=(non_blocking_report,),
    )
    assert override_decision.should_persist is True


def test_write_decision_rejects_invalid_combinations() -> None:
    envelope = build_valid_envelope()
    blocking_report = _build_report(suffix="202", blocking=True)

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id=envelope.state_id,
            status=WriteDecisionStatus.ACCEPTED,
        )

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id=envelope.state_id,
            status=WriteDecisionStatus.REJECTED,
            accepted_envelope=envelope,
        )

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id=envelope.state_id,
            status=WriteDecisionStatus.ACCEPTED,
            accepted_envelope=envelope,
            reports=(blocking_report,),
        )


def test_write_decision_rejects_consistency_mismatch() -> None:
    envelope = build_valid_envelope()
    non_blocking_report = _build_report(suffix="203", blocking=False)
    blocking_report = _build_report(suffix="204", blocking=True)

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id=envelope.state_id,
            status=WriteDecisionStatus.MANUAL_REVIEW,
            reports=(blocking_report,),
            has_blocking_issue=False,
        )

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id=envelope.state_id,
            status=WriteDecisionStatus.MANUAL_REVIEW,
            reports=(non_blocking_report,),
            should_persist=True,
        )

    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id="state-777",
            status=WriteDecisionStatus.MANUAL_REVIEW,
            policy=WritePolicy(allow_manual_review_persist=True),
            accepted_envelope=envelope,
            reports=(non_blocking_report,),
        )


def test_write_decision_candidate_state_id_pattern_validation() -> None:
    with pytest.raises(ValidationError):
        WriteDecision(
            candidate_state_id="board-001",
            status=WriteDecisionStatus.REJECTED,
        )


def test_write_decision_does_not_mutate_envelope_or_reports() -> None:
    envelope = build_valid_envelope()
    report = _build_report(suffix="205", blocking=False)

    envelope_before = deepcopy(envelope.model_dump(mode="python"))
    report_before = deepcopy(report.model_dump(mode="python"))

    _ = WriteDecision(
        candidate_state_id=envelope.state_id,
        status=WriteDecisionStatus.MANUAL_REVIEW,
        reports=(report,),
    )

    assert envelope.model_dump(mode="python") == envelope_before
    assert report.model_dump(mode="python") == report_before


def test_write_contract_modules_do_not_depend_on_storage_or_event_layers() -> None:
    source = "\n".join(
        inspect.getsource(module)
        for module in (
            write_status_module,
            write_policy_module,
            write_decision_module,
        )
    )

    assert "src.storage" not in source
    assert "src.tracing" not in source
    assert "event_sourcing" not in source

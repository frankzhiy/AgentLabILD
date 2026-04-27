"""Shared helper checks for deterministic Phase 1 metrics."""

from __future__ import annotations

from collections.abc import Sequence

from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import StateValidationReport
from ..validators.pipeline import Phase1ValidationPipelineResult
from ..validators.schema_validator import SCHEMA_VALIDATOR_NAME


def find_report(
    result: Phase1ValidationPipelineResult,
    *,
    validator_name: str,
) -> StateValidationReport | None:
    """Find one validator report by its stable validator_name."""

    for report in result.reports:
        if report.validator_name == validator_name:
            return report
    return None


def is_schema_valid(result: Phase1ValidationPipelineResult) -> bool:
    """Schema validity is derived from schema report blocking status."""

    schema_report = find_report(result, validator_name=SCHEMA_VALIDATOR_NAME)
    if schema_report is None:
        return False
    return not schema_report.has_blocking_issue


def has_schema_stage_alignment_issue(result: Phase1ValidationPipelineResult) -> bool:
    """Identify schema-stage mismatch failures from existing schema issues."""

    schema_report = find_report(result, validator_name=SCHEMA_VALIDATOR_NAME)
    if schema_report is None:
        return False

    return any(
        issue.issue_code.startswith("schema.")
        and "stage_id alignment failed" in issue.message.lower()
        for issue in schema_report.issues
    )


def is_stage_aligned(envelope: Phase1StateEnvelope) -> bool:
    """Check stage_id alignment across all stage-aware envelope objects."""

    stage_id = envelope.stage_context.stage_id

    if envelope.board_init.stage_id != stage_id:
        return False

    if any(evidence_atom.stage_id != stage_id for evidence_atom in envelope.evidence_atoms):
        return False

    if any(
        claim_reference.stage_id != stage_id
        for claim_reference in envelope.claim_references
    ):
        return False

    if any(hypothesis.stage_id != stage_id for hypothesis in envelope.hypotheses):
        return False

    if any(action.stage_id != stage_id for action in envelope.action_candidates):
        return False

    return True


def is_board_complete(envelope: Phase1StateEnvelope) -> bool:
    """Check board_init references against concrete envelope object ids."""

    board = envelope.board_init
    evidence_ids = {evidence_atom.evidence_id for evidence_atom in envelope.evidence_atoms}
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in envelope.hypotheses}
    action_candidate_ids = {
        action.action_candidate_id for action in envelope.action_candidates
    }

    return all(
        (
            bool(board.hypothesis_ids),
            set(board.evidence_ids) == evidence_ids,
            set(board.hypothesis_ids) == hypothesis_ids,
            set(board.action_candidate_ids) == action_candidate_ids,
            set(board.ranked_hypothesis_ids).issubset(hypothesis_ids),
        )
    )


def is_valid_lineage_sequence(
    case_sequence: Sequence[Phase1StateEnvelope],
) -> bool:
    """Apply strict per-case lineage constraints using sequence order."""

    if len(case_sequence) < 2:
        return False

    first_state = case_sequence[0]
    if first_state.state_version != 1:
        return False

    if first_state.parent_state_id is not None:
        return False

    previous_state = first_state
    for current_state in case_sequence[1:]:
        if current_state.case_id != previous_state.case_id:
            return False

        if current_state.state_version != previous_state.state_version + 1:
            return False

        if current_state.parent_state_id != previous_state.state_id:
            return False

        previous_state = current_state

    return True


def collect_blocking_issue_codes(
    result: Phase1ValidationPipelineResult,
) -> tuple[str, ...]:
    """Collect blocking issue codes from all executed validator reports."""

    issue_codes: list[str] = []
    for report in result.reports:
        for issue in report.issues:
            if issue.blocking:
                issue_codes.append(issue.issue_code)

    return tuple(sorted(issue_codes))


def is_stable_rerun_pair(
    first_result: Phase1ValidationPipelineResult,
    second_result: Phase1ValidationPipelineResult,
) -> bool:
    """Check deterministic stability dimensions for one rerun pair."""

    if first_result.candidate_state_id != second_result.candidate_state_id:
        return False

    if is_schema_valid(first_result) != is_schema_valid(second_result):
        return False

    if first_result.validator_execution_order != second_result.validator_execution_order:
        return False

    if collect_blocking_issue_codes(first_result) != collect_blocking_issue_codes(
        second_result
    ):
        return False

    return True


__all__ = [
    "collect_blocking_issue_codes",
    "find_report",
    "has_schema_stage_alignment_issue",
    "is_board_complete",
    "is_schema_valid",
    "is_stable_rerun_pair",
    "is_stage_aligned",
    "is_valid_lineage_sequence",
]

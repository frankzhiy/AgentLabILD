"""Root Phase 1 state envelope and compatibility exports.

Phase 1-1 keeps prior import compatibility while introducing the authoritative
`Phase1StateEnvelope` root object for stage-scoped state persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .action import ActionCandidate, ActionStatus, ActionType, ActionUrgency
from .board import BoardInitSource, BoardStatus, HypothesisBoardInit
from .claim import ClaimReference, ClaimRelation, ClaimStrength, ClaimTargetKind
from .common import (
    CASE_ID_PATTERN,
    STATE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    validate_id_pattern,
)
from .evidence import EvidenceAtom
from .hypothesis import HypothesisConfidenceLevel, HypothesisState, HypothesisStatus
from .stage import (
    InfoModality,
    StageContext,
    StageFocus,
    StageType,
    TriggerType,
    VisibilityPolicyHint,
)
from .validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)


def _collect_hypothesis_claim_ref_links(
    hypotheses: tuple[HypothesisState, ...],
) -> tuple[tuple[str, str], ...]:
    """Collect (hypothesis_id, claim_ref_id) links across all claim buckets."""

    links: list[tuple[str, str]] = []

    for hypothesis in hypotheses:
        for claim_ref_id in (
            *hypothesis.supporting_claim_ref_ids,
            *hypothesis.refuting_claim_ref_ids,
            *hypothesis.missing_information_claim_ref_ids,
        ):
            links.append((hypothesis.hypothesis_id, claim_ref_id))

    return tuple(links)


def _collect_action_claim_ref_links(
    action_candidates: tuple[ActionCandidate, ...],
) -> tuple[tuple[str, str], ...]:
    """Collect (action_candidate_id, claim_ref_id) links across all claim buckets."""

    links: list[tuple[str, str]] = []

    for action in action_candidates:
        for claim_ref_id in (
            *action.supporting_claim_ref_ids,
            *action.refuting_claim_ref_ids,
            *action.missing_information_claim_ref_ids,
            *action.safety_concern_claim_ref_ids,
        ):
            links.append((action.action_candidate_id, claim_ref_id))

    return tuple(links)


def _append_claim_target_mismatch_errors(
    *,
    errors: list[str],
    claim_references_by_id: dict[str, ClaimReference],
    owner_claim_links: tuple[tuple[str, str], ...],
    expected_target_kind: ClaimTargetKind,
    owner_label: str,
) -> None:
    """Validate bidirectional claim-target binding for one owner object type."""

    mismatches: list[str] = []

    for owner_id, claim_ref_id in owner_claim_links:
        claim_ref = claim_references_by_id.get(claim_ref_id)
        if claim_ref is None:
            continue

        if (
            claim_ref.target_kind is not expected_target_kind
            or claim_ref.target_id != owner_id
        ):
            mismatches.append(
                f"{claim_ref_id}=>(target_kind={claim_ref.target_kind.value},target_id={claim_ref.target_id}) "
                f"expected=(target_kind={expected_target_kind.value},target_id={owner_id})"
            )

    if mismatches:
        errors.append(
            f"claim_ref target mismatch for {owner_label}: " + ", ".join(sorted(mismatches))
        )


def _append_board_set_mismatch_error(
    *,
    errors: list[str],
    board_field_name: str,
    board_ids: tuple[str, ...],
    actual_ids: set[str],
) -> None:
    """Validate board id collections as set-equality against envelope objects."""

    board_id_set = set(board_ids)
    if board_id_set == actual_ids:
        return

    details: list[str] = []
    missing_in_board = tuple(sorted(actual_ids - board_id_set))
    unexpected_in_board = tuple(sorted(board_id_set - actual_ids))

    if missing_in_board:
        details.append("missing_in_board=" + ", ".join(missing_in_board))
    if unexpected_in_board:
        details.append("unexpected_in_board=" + ", ".join(unexpected_in_board))

    errors.append(
        f"board_init.{board_field_name} must exactly match envelope ids: "
        + "; ".join(details)
    )


class Phase1StateEnvelope(BaseModel):
    """Authoritative root state envelope for Phase 1-1.

    Envelope-level model validators enforce hard structural integrity. These
    checks intentionally raise exceptions for invalid root construction.

    `validation_report` is an optional external validator/write-gate report for
    accepted or reviewable state packages; it is not used to absorb envelope
    construction failures in this layer.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: NonEmptyStr
    stage_context: StageContext
    board_init: HypothesisBoardInit
    evidence_atoms: tuple[EvidenceAtom, ...] = Field(default_factory=tuple)
    claim_references: tuple[ClaimReference, ...] = Field(default_factory=tuple)
    hypotheses: tuple[HypothesisState, ...] = Field(default_factory=tuple)
    action_candidates: tuple[ActionCandidate, ...] = Field(default_factory=tuple)
    validation_report: StateValidationReport | None = None
    state_id: NonEmptyStr
    state_version: int = Field(ge=1, default=1)
    parent_state_id: str | None = None
    created_at: datetime

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("state_id")
    @classmethod
    def validate_state_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STATE_ID_PATTERN,
            field_name="state_id",
            example="state_001 or state-001",
        )

    @field_validator("parent_state_id", mode="before")
    @classmethod
    def normalize_parent_state_id(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("parent_state_id")
    @classmethod
    def validate_parent_state_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_id_pattern(
            value,
            pattern=STATE_ID_PATTERN,
            field_name="parent_state_id",
            example="state_001 or state-001",
        )

    @model_validator(mode="after")
    def validate_envelope_consistency(self) -> "Phase1StateEnvelope":
        # These checks are hard integrity guards for root-envelope construction.
        errors: list[str] = []
        stage_id = self.stage_context.stage_id

        if self.stage_context.case_id != self.case_id:
            errors.append("case_id mismatch between envelope and stage_context")

        if self.board_init.case_id != self.case_id:
            errors.append("case_id mismatch between envelope and board_init")

        if self.board_init.stage_id != stage_id:
            errors.append("stage_id alignment failed: board_init.stage_id mismatch")

        if self.parent_state_id is not None and self.parent_state_id == self.state_id:
            errors.append("parent_state_id must not equal state_id")

        misaligned_evidence_ids = tuple(
            atom.evidence_id for atom in self.evidence_atoms if atom.stage_id != stage_id
        )
        if misaligned_evidence_ids:
            errors.append(
                "stage_id alignment failed for evidence_atoms: "
                + ", ".join(sorted(misaligned_evidence_ids))
            )

        misaligned_claim_ref_ids = tuple(
            claim_ref.claim_ref_id
            for claim_ref in self.claim_references
            if claim_ref.stage_id != stage_id
        )
        if misaligned_claim_ref_ids:
            errors.append(
                "stage_id alignment failed for claim_references: "
                + ", ".join(sorted(misaligned_claim_ref_ids))
            )

        misaligned_hypothesis_ids = tuple(
            hypothesis.hypothesis_id
            for hypothesis in self.hypotheses
            if hypothesis.stage_id != stage_id
        )
        if misaligned_hypothesis_ids:
            errors.append(
                "stage_id alignment failed for hypotheses: "
                + ", ".join(sorted(misaligned_hypothesis_ids))
            )

        misaligned_action_ids = tuple(
            action.action_candidate_id
            for action in self.action_candidates
            if action.stage_id != stage_id
        )
        if misaligned_action_ids:
            errors.append(
                "stage_id alignment failed for action_candidates: "
                + ", ".join(sorted(misaligned_action_ids))
            )

        duplicate_evidence_ids = find_duplicate_items(
            atom.evidence_id for atom in self.evidence_atoms
        )
        if duplicate_evidence_ids:
            errors.append("duplicate ids in evidence_atoms: " + ", ".join(duplicate_evidence_ids))

        duplicate_claim_ref_ids = find_duplicate_items(
            claim_ref.claim_ref_id for claim_ref in self.claim_references
        )
        if duplicate_claim_ref_ids:
            errors.append(
                "duplicate ids in claim_references: " + ", ".join(duplicate_claim_ref_ids)
            )

        duplicate_hypothesis_ids = find_duplicate_items(
            hypothesis.hypothesis_id for hypothesis in self.hypotheses
        )
        if duplicate_hypothesis_ids:
            errors.append("duplicate ids in hypotheses: " + ", ".join(duplicate_hypothesis_ids))

        duplicate_action_ids = find_duplicate_items(
            action.action_candidate_id for action in self.action_candidates
        )
        if duplicate_action_ids:
            errors.append(
                "duplicate ids in action_candidates: " + ", ".join(duplicate_action_ids)
            )

        claim_ref_ids = {claim_ref.claim_ref_id for claim_ref in self.claim_references}
        claim_references_by_id = {
            claim_ref.claim_ref_id: claim_ref for claim_ref in self.claim_references
        }
        hypothesis_claim_links = _collect_hypothesis_claim_ref_links(self.hypotheses)
        action_claim_links = _collect_action_claim_ref_links(self.action_candidates)
        referenced_claim_ref_ids = {
            claim_ref_id
            for _, claim_ref_id in (*hypothesis_claim_links, *action_claim_links)
        }

        missing_claim_ref_ids = tuple(sorted(referenced_claim_ref_ids - claim_ref_ids))
        if missing_claim_ref_ids:
            errors.append("missing claim references: " + ", ".join(missing_claim_ref_ids))

        _append_claim_target_mismatch_errors(
            errors=errors,
            claim_references_by_id=claim_references_by_id,
            owner_claim_links=hypothesis_claim_links,
            expected_target_kind=ClaimTargetKind.HYPOTHESIS,
            owner_label="hypotheses",
        )
        _append_claim_target_mismatch_errors(
            errors=errors,
            claim_references_by_id=claim_references_by_id,
            owner_claim_links=action_claim_links,
            expected_target_kind=ClaimTargetKind.ACTION,
            owner_label="action_candidates",
        )

        evidence_ids = {atom.evidence_id for atom in self.evidence_atoms}
        referenced_evidence_ids = {
            evidence_id
            for claim_ref in self.claim_references
            for evidence_id in claim_ref.evidence_ids
        }
        missing_evidence_ids = tuple(sorted(referenced_evidence_ids - evidence_ids))
        if missing_evidence_ids:
            errors.append("missing evidence references: " + ", ".join(missing_evidence_ids))

        hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in self.hypotheses}

        _append_board_set_mismatch_error(
            errors=errors,
            board_field_name="evidence_ids",
            board_ids=self.board_init.evidence_ids,
            actual_ids=evidence_ids,
        )
        _append_board_set_mismatch_error(
            errors=errors,
            board_field_name="hypothesis_ids",
            board_ids=self.board_init.hypothesis_ids,
            actual_ids=hypothesis_ids,
        )
        action_candidate_ids = {
            action.action_candidate_id for action in self.action_candidates
        }
        _append_board_set_mismatch_error(
            errors=errors,
            board_field_name="action_candidate_ids",
            board_ids=self.board_init.action_candidate_ids,
            actual_ids=action_candidate_ids,
        )

        ranked_hypothesis_ids = set(self.board_init.ranked_hypothesis_ids)
        board_hypothesis_ids = set(self.board_init.hypothesis_ids)
        ranked_not_in_board = tuple(
            sorted(ranked_hypothesis_ids - board_hypothesis_ids)
        )
        if ranked_not_in_board:
            errors.append(
                "ranked_hypothesis_ids not found in board_init.hypothesis_ids: "
                + ", ".join(ranked_not_in_board)
            )

        ranked_not_in_hypotheses = tuple(sorted(ranked_hypothesis_ids - hypothesis_ids))
        if ranked_not_in_hypotheses:
            errors.append(
                "ranked hypothesis ids not found in hypotheses: "
                + ", ".join(ranked_not_in_hypotheses)
            )

        missing_linked_hypothesis_pairs: list[str] = []
        for action in self.action_candidates:
            for linked_hypothesis_id in action.linked_hypothesis_ids:
                if linked_hypothesis_id not in hypothesis_ids:
                    missing_linked_hypothesis_pairs.append(
                        f"{action.action_candidate_id}:{linked_hypothesis_id}"
                    )

        if missing_linked_hypothesis_pairs:
            errors.append(
                "action linked_hypothesis_ids not found in hypotheses: "
                + ", ".join(sorted(missing_linked_hypothesis_pairs))
            )

        if errors:
            raise ValueError("; ".join(errors))

        return self


class SkeletonState(TypedDict, total=False):
    """Minimal shared-state placeholder used only for import stability."""

    stage_id: str
    note: str


__all__ = [
    "ActionCandidate",
    "ActionStatus",
    "ActionType",
    "ActionUrgency",
    "BoardInitSource",
    "BoardStatus",
    "ClaimReference",
    "ClaimRelation",
    "ClaimStrength",
    "ClaimTargetKind",
    "EvidenceAtom",
    "HypothesisBoardInit",
    "HypothesisConfidenceLevel",
    "HypothesisState",
    "HypothesisStatus",
    "InfoModality",
    "Phase1StateEnvelope",
    "SkeletonState",
    "StateValidationReport",
    "StageContext",
    "StageFocus",
    "StageType",
    "TriggerType",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationTargetKind",
    "VisibilityPolicyHint",
]

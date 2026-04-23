"""Root Phase 1 state envelope and compatibility exports.

Phase 1-1 keeps prior import compatibility while introducing the authoritative
`Phase1StateEnvelope` root object for stage-scoped state persistence.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .action import ActionCandidate, ActionStatus, ActionType, ActionUrgency
from .board import BoardInitSource, BoardStatus, HypothesisBoardInit
from .claim import ClaimReference, ClaimRelation, ClaimStrength, ClaimTargetKind
from .common import NonEmptyStr, find_duplicate_items
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


CASE_ID_PATTERN = re.compile(r"^case[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STATE_ID_PATTERN = re.compile(r"^state[_-][A-Za-z0-9][A-Za-z0-9_-]*$")


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
    state_version: int = Field(ge=1, default=1)
    parent_state_id: str | None = None
    created_at: datetime

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        if not CASE_ID_PATTERN.fullmatch(value):
            raise ValueError("case_id must match pattern like case_001 or case-001")
        return value

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
        if not STATE_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "parent_state_id must match pattern like state_001 or state-001"
            )
        return value

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
        referenced_claim_ref_ids: set[str] = set()

        for hypothesis in self.hypotheses:
            referenced_claim_ref_ids.update(hypothesis.supporting_claim_ref_ids)
            referenced_claim_ref_ids.update(hypothesis.refuting_claim_ref_ids)
            referenced_claim_ref_ids.update(hypothesis.missing_information_claim_ref_ids)

        for action in self.action_candidates:
            referenced_claim_ref_ids.update(action.supporting_claim_ref_ids)
            referenced_claim_ref_ids.update(action.refuting_claim_ref_ids)
            referenced_claim_ref_ids.update(action.missing_information_claim_ref_ids)
            referenced_claim_ref_ids.update(action.safety_concern_claim_ref_ids)

        missing_claim_ref_ids = tuple(sorted(referenced_claim_ref_ids - claim_ref_ids))
        if missing_claim_ref_ids:
            errors.append("missing claim references: " + ", ".join(missing_claim_ref_ids))

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
        missing_ranked_hypothesis_ids = tuple(
            sorted(set(self.board_init.ranked_hypothesis_ids) - hypothesis_ids)
        )
        if missing_ranked_hypothesis_ids:
            errors.append(
                "ranked hypothesis ids not found in hypotheses: "
                + ", ".join(missing_ranked_hypothesis_ids)
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

"""Phase 1 Hypothesis Board Bootstrapper adapter.

This module parses candidate board-bootstrap payloads into explicit Phase 1
candidate objects. It does not persist state and does not create envelopes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from ..prompts import render_template_file
from ..schemas.action import ActionCandidate
from ..schemas.board import HypothesisBoardInit
from ..schemas.claim import ClaimReference, ClaimRelation, ClaimTargetKind
from ..schemas.common import (
    BOARD_ID_PATTERN,
    CASE_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_text,
    validate_id_pattern,
)
from ..schemas.hypothesis import HypothesisState
from ..schemas.stage import StageContext
from .case_structuring import CaseStructuringDraft
from .evidence_atomization import EvidenceAtomizationDraft

HYPOTHESIS_BOARD_BOOTSTRAP_DRAFT_ID_PATTERN = re.compile(
    r"^hypothesis_board_bootstrap_draft[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "prompts"
    / "v2"
    / "hypothesis_board_bootstrapper.md"
)

DEFAULT_PROMPT_CONTRACT = """You are a Hypothesis Board Bootstrapper adapter.
Return only one HypothesisBoardBootstrapDraft-compatible JSON object.
Propose candidate hypotheses, evidence-linked claims, candidate actions, and one board init.
"""

FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "final_diagnosis",
        "arbitration_output",
        "treatment_recommendation",
        "typed_conflicts",
        "belief_revision",
        "update_trace",
        "safety_decision",
        "final_management_plan",
    }
)


class HypothesisBoardBootstrapperStatus(StrEnum):
    """Decision status for one bootstrapper adapter parse attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class HypothesisBoardBootstrapperInput(BaseModel):
    """Input contract for candidate hypothesis board bootstrapping."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    stage_context: StageContext
    evidence_atomization_draft: EvidenceAtomizationDraft
    case_structuring_draft: CaseStructuringDraft | None = None
    board_id: NonEmptyStr
    initialized_at: datetime
    bootstrapper_name: NonEmptyStr = "hypothesis_board_bootstrapper_adapter"
    bootstrapper_version: NonEmptyStr = "0.1.0"

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("board_id")
    @classmethod
    def validate_board_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=BOARD_ID_PATTERN,
            field_name="board_id",
            example="board_001 or board-001",
        )

    @field_validator("bootstrapper_name", "bootstrapper_version", mode="before")
    @classmethod
    def normalize_bootstrapper_text(cls, value: object) -> str:
        cleaned = normalize_optional_text(value)
        if cleaned is None:
            raise ValueError("bootstrapper text fields must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_input_alignment(self) -> "HypothesisBoardBootstrapperInput":
        if self.stage_context.case_id != self.case_id:
            raise ValueError("stage_context.case_id must equal input case_id")

        if self.stage_context.stage_id != self.stage_id:
            raise ValueError("stage_context.stage_id must equal input stage_id")

        evidence_draft = self.evidence_atomization_draft
        if evidence_draft.case_id != self.case_id:
            raise ValueError("evidence_atomization_draft.case_id must equal input case_id")

        if evidence_draft.stage_id != self.stage_id:
            raise ValueError("evidence_atomization_draft.stage_id must equal input stage_id")

        if self.case_structuring_draft is not None:
            case_draft = self.case_structuring_draft
            if case_draft.case_id != self.case_id:
                raise ValueError("case_structuring_draft.case_id must equal input case_id")

            if case_draft.proposed_stage_context.stage_id != self.stage_id:
                raise ValueError(
                    "case_structuring_draft.proposed_stage_context.stage_id must equal input stage_id"
                )

        return self


class HypothesisBoardBootstrapDraft(BaseModel):
    """Candidate board bootstrap output, not authoritative state."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["hypothesis_board_bootstrap_draft"] = (
        "hypothesis_board_bootstrap_draft"
    )
    draft_id: NonEmptyStr
    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...]
    claim_references: tuple[ClaimReference, ...]
    hypotheses: tuple[HypothesisState, ...]
    action_candidates: tuple[ActionCandidate, ...] = Field(default_factory=tuple)
    board_init: HypothesisBoardInit
    non_authoritative_note: str | None = None

    @field_validator("draft_id")
    @classmethod
    def validate_draft_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=HYPOTHESIS_BOARD_BOOTSTRAP_DRAFT_ID_PATTERN,
            field_name="draft_id",
            example=(
                "hypothesis_board_bootstrap_draft_001 or "
                "hypothesis_board_bootstrap_draft-001"
            ),
        )

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence_ids must not be empty")

        duplicates = find_duplicate_items(value)
        if duplicates:
            raise ValueError("evidence_ids must not contain duplicates")

        return value

    @field_validator("claim_references")
    @classmethod
    def validate_claim_references(
        cls, value: tuple[ClaimReference, ...]
    ) -> tuple[ClaimReference, ...]:
        if not value:
            raise ValueError("claim_references must not be empty")

        duplicates = find_duplicate_items(claim.claim_ref_id for claim in value)
        if duplicates:
            raise ValueError("claim_references must not contain duplicate claim_ref_id")

        return value

    @field_validator("hypotheses")
    @classmethod
    def validate_hypotheses(
        cls, value: tuple[HypothesisState, ...]
    ) -> tuple[HypothesisState, ...]:
        if not value:
            raise ValueError("hypotheses must contain at least one candidate hypothesis")

        duplicates = find_duplicate_items(hypothesis.hypothesis_id for hypothesis in value)
        if duplicates:
            raise ValueError("hypotheses must not contain duplicate hypothesis_id")

        return value

    @field_validator("action_candidates")
    @classmethod
    def validate_action_candidates(
        cls, value: tuple[ActionCandidate, ...]
    ) -> tuple[ActionCandidate, ...]:
        duplicates = find_duplicate_items(
            action.action_candidate_id for action in value
        )
        if duplicates:
            raise ValueError(
                "action_candidates must not contain duplicate action_candidate_id"
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_text(value)


class HypothesisBoardBootstrapperResult(BaseModel):
    """Non-authoritative parse result for bootstrapper output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: HypothesisBoardBootstrapperStatus
    draft: HypothesisBoardBootstrapDraft | None = None
    errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "HypothesisBoardBootstrapperResult":
        if self.status is HypothesisBoardBootstrapperStatus.ACCEPTED:
            if self.draft is None:
                raise ValueError("accepted result requires draft")
            if self.errors:
                raise ValueError("accepted result must not include errors")

        if self.status is HypothesisBoardBootstrapperStatus.REJECTED:
            if self.draft is not None:
                raise ValueError("rejected result must not include draft")
            if not self.errors:
                raise ValueError("rejected result must include errors")

        if self.status is HypothesisBoardBootstrapperStatus.MANUAL_REVIEW:
            if self.draft is None and not self.errors and not self.warnings:
                raise ValueError(
                    "manual_review result requires draft, errors, or warnings"
                )

        return self


def build_hypothesis_board_bootstrapper_prompt(
    input: HypothesisBoardBootstrapperInput,
) -> str:
    """Build one Hypothesis Board Bootstrapper prompt."""

    payload: dict[str, object] = {
        "stage_metadata": input.stage_context.model_dump(mode="json"),
        "board_metadata": {
            "board_id": input.board_id,
            "initialized_at": input.initialized_at.isoformat(),
            "bootstrapper_name": input.bootstrapper_name,
            "bootstrapper_version": input.bootstrapper_version,
        },
        "evidence_atomization_draft": input.evidence_atomization_draft.model_dump(
            mode="json"
        ),
    }

    if input.case_structuring_draft is not None:
        payload["case_structuring_draft"] = input.case_structuring_draft.model_dump(
            mode="json"
        )

    if _should_use_fallback_prompt():
        return _build_fallback_prompt(payload)

    return render_template_file(
        DEFAULT_PROMPT_PATH,
        {
            "input_json": payload,
            "output_schema_json": HypothesisBoardBootstrapDraft.model_json_schema(),
        },
    )


def parse_hypothesis_board_bootstrapper_payload(
    payload: Mapping[str, object],
    input: HypothesisBoardBootstrapperInput,
) -> HypothesisBoardBootstrapperResult:
    """Parse bootstrapper payload into candidate board objects."""

    try:
        forbidden_field_errors = _detect_forbidden_payload_fields(payload)
        if forbidden_field_errors:
            return _build_rejected_result(errors=forbidden_field_errors)

        draft = HypothesisBoardBootstrapDraft.model_validate(payload)
        alignment_errors = _validate_draft_alignment(draft=draft, input=input)
        if alignment_errors:
            return _build_rejected_result(errors=alignment_errors)

        return HypothesisBoardBootstrapperResult(
            status=HypothesisBoardBootstrapperStatus.ACCEPTED,
            draft=draft,
            errors=(),
            warnings=(),
        )
    except ValidationError as exc:
        return _build_rejected_result(errors=_extract_validation_errors(exc))
    except Exception as exc:
        return HypothesisBoardBootstrapperResult(
            status=HypothesisBoardBootstrapperStatus.MANUAL_REVIEW,
            draft=None,
            errors=(f"unexpected parser failure: {exc}",),
            warnings=(),
        )


def _should_use_fallback_prompt() -> bool:
    try:
        prompt_contract = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return True

    return not prompt_contract.strip()


def _build_fallback_prompt(payload: dict[str, object]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    schema_json = json.dumps(
        HypothesisBoardBootstrapDraft.model_json_schema(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return (
        f"{DEFAULT_PROMPT_CONTRACT.rstrip()}\n\n"
        f"### Output Schema JSON\n{schema_json}\n\n"
        f"### Input JSON\n{payload_json}\n"
    )


def _detect_forbidden_payload_fields(payload: Mapping[str, object]) -> tuple[str, ...]:
    forbidden_paths = sorted(_find_forbidden_field_paths(payload))
    if not forbidden_paths:
        return ()

    return tuple(
        f"payload contains forbidden field: {field_path}"
        for field_path in forbidden_paths
    )


def _find_forbidden_field_paths(value: object, prefix: str = "") -> set[str]:
    paths: set[str] = set()

    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text in FORBIDDEN_PAYLOAD_FIELDS:
                paths.add(path)
            paths.update(_find_forbidden_field_paths(item, path))
        return paths

    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.update(_find_forbidden_field_paths(item, path))

    return paths


def _validate_draft_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    input: HypothesisBoardBootstrapperInput,
) -> tuple[str, ...]:
    errors: list[str] = []

    _validate_case_stage_alignment(draft=draft, input=input, errors=errors)
    _validate_evidence_alignment(draft=draft, input=input, errors=errors)
    _validate_hypothesis_claim_alignment(draft=draft, errors=errors)
    _validate_action_claim_alignment(draft=draft, errors=errors)
    _validate_board_alignment(draft=draft, input=input, errors=errors)

    return tuple(errors)


def _validate_case_stage_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    input: HypothesisBoardBootstrapperInput,
    errors: list[str],
) -> None:
    if draft.case_id != input.case_id:
        errors.append("draft.case_id must equal input.case_id")

    if draft.stage_id != input.stage_id:
        errors.append("draft.stage_id must equal input.stage_id")

    for claim in draft.claim_references:
        if claim.stage_id != input.stage_id:
            errors.append("every claim_reference.stage_id must equal input.stage_id")
            break

    for hypothesis in draft.hypotheses:
        if hypothesis.stage_id != input.stage_id:
            errors.append("every hypothesis.stage_id must equal input.stage_id")
            break

    for action in draft.action_candidates:
        if action.stage_id != input.stage_id:
            errors.append("every action_candidate.stage_id must equal input.stage_id")
            break

    if draft.board_init.case_id != input.case_id:
        errors.append("board_init.case_id must equal input.case_id")

    if draft.board_init.stage_id != input.stage_id:
        errors.append("board_init.stage_id must equal input.stage_id")

    if draft.board_init.board_id != input.board_id:
        errors.append("board_init.board_id must equal input.board_id")

    if draft.board_init.initialized_at != input.initialized_at:
        errors.append("board_init.initialized_at must equal input.initialized_at")


def _validate_evidence_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    input: HypothesisBoardBootstrapperInput,
    errors: list[str],
) -> None:
    available_evidence_ids = {
        evidence.evidence_id
        for evidence in input.evidence_atomization_draft.evidence_atoms
    }

    unknown_draft_evidence_ids = sorted(set(draft.evidence_ids) - available_evidence_ids)
    if unknown_draft_evidence_ids:
        errors.append(
            "draft.evidence_ids must be a subset of evidence_atomization_draft evidence ids"
        )

    draft_evidence_ids = set(draft.evidence_ids)
    for claim in draft.claim_references:
        unknown_claim_evidence_ids = sorted(
            set(claim.evidence_ids) - available_evidence_ids
        )
        if unknown_claim_evidence_ids:
            errors.append(
                "every claim_reference.evidence_ids value must come from evidence_atomization_draft"
            )
            break

        outside_draft_evidence_ids = sorted(set(claim.evidence_ids) - draft_evidence_ids)
        if outside_draft_evidence_ids:
            errors.append(
                "every claim_reference.evidence_ids value must be included in draft.evidence_ids"
            )
            break


def _validate_hypothesis_claim_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    errors: list[str],
) -> None:
    claim_by_id = {claim.claim_ref_id: claim for claim in draft.claim_references}

    for hypothesis in draft.hypotheses:
        for claim_ref_id, expected_relation in _hypothesis_claim_refs(hypothesis):
            claim = claim_by_id.get(claim_ref_id)
            if claim is None:
                errors.append(
                    "every HypothesisState claim_ref_id must exist in claim_references"
                )
                continue

            if claim.target_kind is not ClaimTargetKind.HYPOTHESIS:
                errors.append(
                    "hypothesis claim references must target ClaimTargetKind.HYPOTHESIS"
                )

            if claim.target_id != hypothesis.hypothesis_id:
                errors.append(
                    "hypothesis claim reference target_id must equal hypothesis_id"
                )

            if claim.relation is not expected_relation:
                errors.append(
                    "hypothesis claim reference relation must align with hypothesis bucket"
                )


def _validate_action_claim_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    errors: list[str],
) -> None:
    claim_by_id = {claim.claim_ref_id: claim for claim in draft.claim_references}
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in draft.hypotheses}

    for action in draft.action_candidates:
        unknown_linked_hypothesis_ids = sorted(
            set(action.linked_hypothesis_ids) - hypothesis_ids
        )
        if unknown_linked_hypothesis_ids:
            errors.append(
                "action_candidate.linked_hypothesis_ids must refer to draft hypotheses"
            )

        for claim_ref_id, expected_relation in _action_claim_refs(action):
            claim = claim_by_id.get(claim_ref_id)
            if claim is None:
                errors.append(
                    "every ActionCandidate claim_ref_id must exist in claim_references"
                )
                continue

            if claim.target_kind is not ClaimTargetKind.ACTION:
                errors.append("action claim references must target ClaimTargetKind.ACTION")

            if claim.target_id != action.action_candidate_id:
                errors.append(
                    "action claim reference target_id must equal action_candidate_id"
                )

            if claim.relation is not expected_relation:
                errors.append(
                    "action claim reference relation must align with action bucket"
                )


def _validate_board_alignment(
    *,
    draft: HypothesisBoardBootstrapDraft,
    input: HypothesisBoardBootstrapperInput,
    errors: list[str],
) -> None:
    board_init = draft.board_init
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in draft.hypotheses}
    action_candidate_ids = {
        action.action_candidate_id for action in draft.action_candidates
    }

    if set(board_init.hypothesis_ids) != hypothesis_ids:
        errors.append("board_init.hypothesis_ids must exactly match draft hypotheses")

    if set(board_init.action_candidate_ids) != action_candidate_ids:
        errors.append(
            "board_init.action_candidate_ids must exactly match draft action candidates"
        )

    if not set(board_init.evidence_ids).issubset(set(draft.evidence_ids)):
        errors.append("board_init.evidence_ids must be drawn from draft.evidence_ids")

    if not set(board_init.ranked_hypothesis_ids).issubset(set(board_init.hypothesis_ids)):
        errors.append(
            "board_init.ranked_hypothesis_ids must be a subset of board_init.hypothesis_ids"
        )

    if board_init.initialized_at != input.initialized_at:
        errors.append("board_init.initialized_at must equal input.initialized_at")


def _hypothesis_claim_refs(
    hypothesis: HypothesisState,
) -> tuple[tuple[str, ClaimRelation], ...]:
    pairs: list[tuple[str, ClaimRelation]] = []
    pairs.extend(
        (claim_ref_id, ClaimRelation.SUPPORTS)
        for claim_ref_id in hypothesis.supporting_claim_ref_ids
    )
    pairs.extend(
        (claim_ref_id, ClaimRelation.REFUTES)
        for claim_ref_id in hypothesis.refuting_claim_ref_ids
    )
    pairs.extend(
        (claim_ref_id, ClaimRelation.INDICATES_MISSING_INFORMATION_FOR)
        for claim_ref_id in hypothesis.missing_information_claim_ref_ids
    )
    return tuple(pairs)


def _action_claim_refs(
    action: ActionCandidate,
) -> tuple[tuple[str, ClaimRelation], ...]:
    pairs: list[tuple[str, ClaimRelation]] = []
    pairs.extend(
        (claim_ref_id, ClaimRelation.SUPPORTS)
        for claim_ref_id in action.supporting_claim_ref_ids
    )
    pairs.extend(
        (claim_ref_id, ClaimRelation.REFUTES)
        for claim_ref_id in action.refuting_claim_ref_ids
    )
    pairs.extend(
        (claim_ref_id, ClaimRelation.INDICATES_MISSING_INFORMATION_FOR)
        for claim_ref_id in action.missing_information_claim_ref_ids
    )
    pairs.extend(
        (claim_ref_id, ClaimRelation.RAISES_SAFETY_CONCERN_FOR)
        for claim_ref_id in action.safety_concern_claim_ref_ids
    )
    return tuple(pairs)


def _extract_validation_errors(exc: ValidationError) -> tuple[str, ...]:
    error_messages: list[str] = []
    for error_item in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error_item.get("loc", ()))
        message = str(error_item.get("msg", "validation error"))
        if location:
            error_messages.append(f"{location}: {message}")
        else:
            error_messages.append(message)

    if error_messages:
        return tuple(error_messages)

    return ("payload validation failed",)


def _build_rejected_result(
    *, errors: tuple[str, ...]
) -> HypothesisBoardBootstrapperResult:
    return HypothesisBoardBootstrapperResult(
        status=HypothesisBoardBootstrapperStatus.REJECTED,
        draft=None,
        errors=errors,
        warnings=(),
    )


__all__ = [
    "HYPOTHESIS_BOARD_BOOTSTRAP_DRAFT_ID_PATTERN",
    "HypothesisBoardBootstrapDraft",
    "HypothesisBoardBootstrapperInput",
    "HypothesisBoardBootstrapperResult",
    "HypothesisBoardBootstrapperStatus",
    "build_hypothesis_board_bootstrapper_prompt",
    "parse_hypothesis_board_bootstrapper_payload",
]

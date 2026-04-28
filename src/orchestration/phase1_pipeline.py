"""Full Phase 1 runtime orchestration pipeline.

The pipeline coordinates existing intake, agent, adapter, validator, and
state-writer boundaries. It does not construct LLM clients and does not perform
medical reasoning.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..adapters.case_structurer_adapter import (
    CaseStructurerInput,
    CaseStructurerResult,
    CaseStructurerStatus,
)
from ..adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerResult,
    EvidenceAtomizerStatus,
)
from ..adapters.hypothesis_board_bootstrapper_adapter import (
    HypothesisBoardBootstrapperInput,
    HypothesisBoardBootstrapperResult,
    HypothesisBoardBootstrapperStatus,
)
from ..adapters.validation_bridge import (
    AdapterValidationBridgeResult,
    AdapterValidationBridgeStatus,
    validate_adapter_drafts_against_sources,
)
from ..intake.free_text import FreeTextIntakeBuilder, FreeTextIntakeResult
from ..schemas.common import NonEmptyStr, normalize_optional_text
from ..schemas.intake import RawIntakeStatus, SourceDocumentType
from ..schemas.stage import StageType, TriggerType
from ..schemas.state import Phase1StateEnvelope
from ..state.sinks import NoOpStateSink, StateSink
from ..state.state_writer import attempt_phase1_write
from ..state.write_decision import WriteDecision
from ..state.write_policy import WritePolicy
from ..state.write_status import WriteDecisionStatus
from ..validators.pipeline import ValidationPipelinePolicy


class Phase1PipelineStatus(StrEnum):
    """Outcome status for Phase 1 orchestration."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class Phase1PipelineInput(BaseModel):
    """Input contract for one complete Phase 1 orchestration run."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    raw_text: str
    case_id: NonEmptyStr
    input_event_id: str | None = None
    source_doc_id: str | None = None
    document_type: SourceDocumentType = SourceDocumentType.FREE_TEXT_CASE_NOTE
    stage_id: NonEmptyStr
    stage_index: int = Field(ge=0)
    stage_type: StageType
    trigger_type: TriggerType
    created_at: datetime
    clinical_time: datetime | None = None
    parent_stage_id: str | None = None
    stage_label: str | None = None
    extraction_activity_id: NonEmptyStr
    evidence_extraction_occurred_at: datetime
    board_id: NonEmptyStr
    board_initialized_at: datetime
    state_id: NonEmptyStr
    state_version: int = Field(default=1, ge=1)
    parent_state_id: str | None = None

    @field_validator(
        "input_event_id",
        "source_doc_id",
        "parent_stage_id",
        "stage_label",
        "parent_state_id",
        mode="before",
    )
    @classmethod
    def normalize_optional_text_fields(cls, value: object) -> str | None:
        return normalize_optional_text(value)


class Phase1PipelineResult(BaseModel):
    """Structured result from one complete Phase 1 pipeline attempt."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: Phase1PipelineStatus
    intake_result: FreeTextIntakeResult | None = None
    case_structurer_result: CaseStructurerResult | None = None
    evidence_atomizer_result: EvidenceAtomizerResult | None = None
    adapter_validation_result: AdapterValidationBridgeResult | None = None
    bootstrapper_result: HypothesisBoardBootstrapperResult | None = None
    candidate_envelope: Phase1StateEnvelope | None = None
    write_decision: WriteDecision | None = None
    errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "Phase1PipelineResult":
        if self.status is Phase1PipelineStatus.ACCEPTED:
            if self.candidate_envelope is None or self.write_decision is None:
                raise ValueError("accepted pipeline result requires envelope and write_decision")
            if self.errors:
                raise ValueError("accepted pipeline result must not include errors")

        if self.status is Phase1PipelineStatus.REJECTED and not self.errors:
            raise ValueError("rejected pipeline result requires errors")

        if self.status is Phase1PipelineStatus.MANUAL_REVIEW:
            if not self.errors and not self.warnings:
                raise ValueError(
                    "manual_review pipeline result requires errors or warnings"
                )

        return self


@runtime_checkable
class CaseStructurerAgentLike(Protocol):
    def run(self, input: CaseStructurerInput) -> CaseStructurerResult:
        """Run the Case Structurer agent."""


@runtime_checkable
class EvidenceAtomizerAgentLike(Protocol):
    def run(self, input: EvidenceAtomizerInput) -> EvidenceAtomizerResult:
        """Run the Evidence Atomizer agent."""


@runtime_checkable
class HypothesisBoardBootstrapperAgentLike(Protocol):
    def run(
        self,
        input: HypothesisBoardBootstrapperInput,
    ) -> HypothesisBoardBootstrapperResult:
        """Run the Hypothesis Board Bootstrapper agent."""


class Phase1Pipeline:
    """Coordinate free text through validator-gated Phase 1 state write."""

    def __init__(
        self,
        *,
        case_structurer_agent: CaseStructurerAgentLike,
        evidence_atomizer_agent: EvidenceAtomizerAgentLike,
        hypothesis_board_bootstrapper_agent: HypothesisBoardBootstrapperAgentLike,
        intake_builder: FreeTextIntakeBuilder | None = None,
        write_policy: WritePolicy | None = None,
        sink: StateSink | None = None,
        validation_policy: ValidationPipelinePolicy | None = None,
        require_provenance: bool | None = None,
    ) -> None:
        self._case_structurer_agent = case_structurer_agent
        self._evidence_atomizer_agent = evidence_atomizer_agent
        self._hypothesis_board_bootstrapper_agent = hypothesis_board_bootstrapper_agent
        self._intake_builder = intake_builder or FreeTextIntakeBuilder()
        self._write_policy = write_policy
        self._sink: StateSink = sink if sink is not None else NoOpStateSink()
        self._validation_policy = validation_policy
        self._require_provenance = require_provenance

    def run(self, input: Phase1PipelineInput) -> Phase1PipelineResult:
        intake_result = self._intake_builder.build(
            raw_text=input.raw_text,
            case_id=input.case_id,
            input_event_id=input.input_event_id,
            source_doc_id=input.source_doc_id,
            document_type=input.document_type,
            created_at=input.created_at,
        )
        if intake_result.status is not RawIntakeStatus.ACCEPTED:
            return _pipeline_result_from_intake_stop(intake_result)

        assert intake_result.source_document is not None
        case_structurer_result = self._case_structurer_agent.run(
            CaseStructurerInput(
                case_id=input.case_id,
                source_documents=(intake_result.source_document,),
                stage_id=input.stage_id,
                stage_index=input.stage_index,
                stage_type=input.stage_type,
                trigger_type=input.trigger_type,
                created_at=input.created_at,
                clinical_time=input.clinical_time,
                parent_stage_id=input.parent_stage_id,
                stage_label=input.stage_label,
            )
        )
        if case_structurer_result.status is not CaseStructurerStatus.ACCEPTED:
            return _pipeline_result_from_case_structurer_stop(
                intake_result=intake_result,
                case_structurer_result=case_structurer_result,
            )

        assert case_structurer_result.draft is not None
        stage_context = case_structurer_result.draft.proposed_stage_context
        evidence_atomizer_result = self._evidence_atomizer_agent.run(
            EvidenceAtomizerInput(
                case_id=input.case_id,
                stage_id=input.stage_id,
                source_documents=(intake_result.source_document,),
                stage_context=stage_context,
                case_structuring_draft=case_structurer_result.draft,
                extraction_activity_id=input.extraction_activity_id,
                occurred_at=input.evidence_extraction_occurred_at,
            )
        )
        if evidence_atomizer_result.status is not EvidenceAtomizerStatus.ACCEPTED:
            return _pipeline_result_from_evidence_atomizer_stop(
                intake_result=intake_result,
                case_structurer_result=case_structurer_result,
                evidence_atomizer_result=evidence_atomizer_result,
            )

        assert evidence_atomizer_result.draft is not None
        adapter_validation_result = validate_adapter_drafts_against_sources(
            case_structuring_draft=case_structurer_result.draft,
            evidence_atomization_draft=evidence_atomizer_result.draft,
            source_documents=(intake_result.source_document,),
        )
        if (
            adapter_validation_result.status
            is not AdapterValidationBridgeStatus.PASSED
        ):
            return _pipeline_result_from_adapter_validation_stop(
                intake_result=intake_result,
                case_structurer_result=case_structurer_result,
                evidence_atomizer_result=evidence_atomizer_result,
                adapter_validation_result=adapter_validation_result,
            )

        bootstrapper_result = self._hypothesis_board_bootstrapper_agent.run(
            HypothesisBoardBootstrapperInput(
                case_id=input.case_id,
                stage_id=input.stage_id,
                stage_context=stage_context,
                evidence_atomization_draft=evidence_atomizer_result.draft,
                case_structuring_draft=case_structurer_result.draft,
                board_id=input.board_id,
                initialized_at=input.board_initialized_at,
            )
        )
        if bootstrapper_result.status is not HypothesisBoardBootstrapperStatus.ACCEPTED:
            return _pipeline_result_from_bootstrapper_stop(
                intake_result=intake_result,
                case_structurer_result=case_structurer_result,
                evidence_atomizer_result=evidence_atomizer_result,
                adapter_validation_result=adapter_validation_result,
                bootstrapper_result=bootstrapper_result,
            )

        try:
            candidate_envelope = _build_candidate_envelope(
                input=input,
                case_structurer_result=case_structurer_result,
                evidence_atomizer_result=evidence_atomizer_result,
                bootstrapper_result=bootstrapper_result,
            )
        except (ValidationError, ValueError) as exc:
            return Phase1PipelineResult(
                status=Phase1PipelineStatus.REJECTED,
                intake_result=intake_result,
                case_structurer_result=case_structurer_result,
                evidence_atomizer_result=evidence_atomizer_result,
                adapter_validation_result=adapter_validation_result,
                bootstrapper_result=bootstrapper_result,
                candidate_envelope=None,
                write_decision=None,
                errors=_extract_errors(exc),
                warnings=(),
            )

        write_decision = attempt_phase1_write(
            candidate_envelope,
            policy=self._write_policy,
            sink=self._sink,
            validation_policy=self._validation_policy,
            require_provenance=self._require_provenance,
        )

        return Phase1PipelineResult(
            status=_pipeline_status_from_write_decision(write_decision),
            intake_result=intake_result,
            case_structurer_result=case_structurer_result,
            evidence_atomizer_result=evidence_atomizer_result,
            adapter_validation_result=adapter_validation_result,
            bootstrapper_result=bootstrapper_result,
            candidate_envelope=candidate_envelope,
            write_decision=write_decision,
            errors=(
                _write_decision_error(write_decision)
                if write_decision.status is WriteDecisionStatus.REJECTED
                else ()
            ),
            warnings=(
                _write_decision_warning(write_decision)
                if write_decision.status is WriteDecisionStatus.MANUAL_REVIEW
                else ()
            ),
        )


def _build_candidate_envelope(
    *,
    input: Phase1PipelineInput,
    case_structurer_result: CaseStructurerResult,
    evidence_atomizer_result: EvidenceAtomizerResult,
    bootstrapper_result: HypothesisBoardBootstrapperResult,
) -> Phase1StateEnvelope:
    assert case_structurer_result.draft is not None
    assert evidence_atomizer_result.draft is not None
    assert bootstrapper_result.draft is not None

    return Phase1StateEnvelope(
        case_id=input.case_id,
        stage_context=case_structurer_result.draft.proposed_stage_context,
        board_init=bootstrapper_result.draft.board_init,
        evidence_atoms=evidence_atomizer_result.draft.evidence_atoms,
        claim_references=bootstrapper_result.draft.claim_references,
        hypotheses=bootstrapper_result.draft.hypotheses,
        action_candidates=bootstrapper_result.draft.action_candidates,
        state_id=input.state_id,
        state_version=input.state_version,
        parent_state_id=input.parent_state_id,
        created_at=input.created_at,
    )


def _pipeline_result_from_intake_stop(
    intake_result: FreeTextIntakeResult,
) -> Phase1PipelineResult:
    status = (
        Phase1PipelineStatus.REJECTED
        if intake_result.status is RawIntakeStatus.REJECTED
        else Phase1PipelineStatus.MANUAL_REVIEW
    )
    return Phase1PipelineResult(
        status=status,
        intake_result=intake_result,
        errors=intake_result.errors if status is Phase1PipelineStatus.REJECTED else (),
        warnings=(
            intake_result.warnings or (intake_result.summary,)
            if status is Phase1PipelineStatus.MANUAL_REVIEW
            else ()
        ),
    )


def _pipeline_result_from_case_structurer_stop(
    *,
    intake_result: FreeTextIntakeResult,
    case_structurer_result: CaseStructurerResult,
) -> Phase1PipelineResult:
    status = _pipeline_status_from_case_structurer_status(case_structurer_result.status)
    return Phase1PipelineResult(
        status=status,
        intake_result=intake_result,
        case_structurer_result=case_structurer_result,
        errors=case_structurer_result.errors
        if status is Phase1PipelineStatus.REJECTED
        else (),
        warnings=_warnings_for_non_rejected_stop(
            errors=case_structurer_result.errors,
            warnings=case_structurer_result.warnings,
        )
        if status is Phase1PipelineStatus.MANUAL_REVIEW
        else (),
    )


def _pipeline_result_from_evidence_atomizer_stop(
    *,
    intake_result: FreeTextIntakeResult,
    case_structurer_result: CaseStructurerResult,
    evidence_atomizer_result: EvidenceAtomizerResult,
) -> Phase1PipelineResult:
    status = _pipeline_status_from_evidence_atomizer_status(
        evidence_atomizer_result.status
    )
    return Phase1PipelineResult(
        status=status,
        intake_result=intake_result,
        case_structurer_result=case_structurer_result,
        evidence_atomizer_result=evidence_atomizer_result,
        errors=evidence_atomizer_result.errors
        if status is Phase1PipelineStatus.REJECTED
        else (),
        warnings=_warnings_for_non_rejected_stop(
            errors=evidence_atomizer_result.errors,
            warnings=evidence_atomizer_result.warnings,
        )
        if status is Phase1PipelineStatus.MANUAL_REVIEW
        else (),
    )


def _pipeline_result_from_adapter_validation_stop(
    *,
    intake_result: FreeTextIntakeResult,
    case_structurer_result: CaseStructurerResult,
    evidence_atomizer_result: EvidenceAtomizerResult,
    adapter_validation_result: AdapterValidationBridgeResult,
) -> Phase1PipelineResult:
    status = _pipeline_status_from_adapter_validation_status(
        adapter_validation_result.status
    )
    return Phase1PipelineResult(
        status=status,
        intake_result=intake_result,
        case_structurer_result=case_structurer_result,
        evidence_atomizer_result=evidence_atomizer_result,
        adapter_validation_result=adapter_validation_result,
        errors=(adapter_validation_result.summary,)
        if status is Phase1PipelineStatus.REJECTED
        else (),
        warnings=(adapter_validation_result.summary,)
        if status is Phase1PipelineStatus.MANUAL_REVIEW
        else (),
    )


def _pipeline_result_from_bootstrapper_stop(
    *,
    intake_result: FreeTextIntakeResult,
    case_structurer_result: CaseStructurerResult,
    evidence_atomizer_result: EvidenceAtomizerResult,
    adapter_validation_result: AdapterValidationBridgeResult,
    bootstrapper_result: HypothesisBoardBootstrapperResult,
) -> Phase1PipelineResult:
    status = _pipeline_status_from_bootstrapper_status(bootstrapper_result.status)
    return Phase1PipelineResult(
        status=status,
        intake_result=intake_result,
        case_structurer_result=case_structurer_result,
        evidence_atomizer_result=evidence_atomizer_result,
        adapter_validation_result=adapter_validation_result,
        bootstrapper_result=bootstrapper_result,
        errors=bootstrapper_result.errors
        if status is Phase1PipelineStatus.REJECTED
        else (),
        warnings=_warnings_for_non_rejected_stop(
            errors=bootstrapper_result.errors,
            warnings=bootstrapper_result.warnings,
        )
        if status is Phase1PipelineStatus.MANUAL_REVIEW
        else (),
    )


def _pipeline_status_from_case_structurer_status(
    status: CaseStructurerStatus,
) -> Phase1PipelineStatus:
    if status is CaseStructurerStatus.ACCEPTED:
        return Phase1PipelineStatus.ACCEPTED
    if status is CaseStructurerStatus.REJECTED:
        return Phase1PipelineStatus.REJECTED
    return Phase1PipelineStatus.MANUAL_REVIEW


def _pipeline_status_from_evidence_atomizer_status(
    status: EvidenceAtomizerStatus,
) -> Phase1PipelineStatus:
    if status is EvidenceAtomizerStatus.ACCEPTED:
        return Phase1PipelineStatus.ACCEPTED
    if status is EvidenceAtomizerStatus.REJECTED:
        return Phase1PipelineStatus.REJECTED
    return Phase1PipelineStatus.MANUAL_REVIEW


def _pipeline_status_from_bootstrapper_status(
    status: HypothesisBoardBootstrapperStatus,
) -> Phase1PipelineStatus:
    if status is HypothesisBoardBootstrapperStatus.ACCEPTED:
        return Phase1PipelineStatus.ACCEPTED
    if status is HypothesisBoardBootstrapperStatus.REJECTED:
        return Phase1PipelineStatus.REJECTED
    return Phase1PipelineStatus.MANUAL_REVIEW


def _pipeline_status_from_adapter_validation_status(
    status: AdapterValidationBridgeStatus,
) -> Phase1PipelineStatus:
    if status is AdapterValidationBridgeStatus.PASSED:
        return Phase1PipelineStatus.ACCEPTED
    if status is AdapterValidationBridgeStatus.FAILED:
        return Phase1PipelineStatus.REJECTED
    return Phase1PipelineStatus.MANUAL_REVIEW


def _pipeline_status_from_write_decision(
    decision: WriteDecision,
) -> Phase1PipelineStatus:
    if decision.status is WriteDecisionStatus.ACCEPTED:
        return Phase1PipelineStatus.ACCEPTED
    if decision.status is WriteDecisionStatus.REJECTED:
        return Phase1PipelineStatus.REJECTED
    return Phase1PipelineStatus.MANUAL_REVIEW


def _warnings_for_non_rejected_stop(
    *,
    errors: tuple[str, ...],
    warnings: tuple[str, ...],
) -> tuple[str, ...]:
    if warnings:
        return warnings
    if errors:
        return errors
    return ("pipeline stopped for manual review",)


def _write_decision_error(decision: WriteDecision) -> tuple[str, ...]:
    if decision.summary:
        return (decision.summary,)
    return ("phase1 write rejected by validation gate",)


def _write_decision_warning(decision: WriteDecision) -> tuple[str, ...]:
    if decision.summary:
        return (decision.summary,)
    return ("phase1 write requires manual review",)


def _extract_errors(exc: ValidationError | ValueError) -> tuple[str, ...]:
    if isinstance(exc, ValidationError):
        error_messages: list[str] = []
        for error_item in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error_item.get("loc", ()))
            message = str(error_item.get("msg", "validation error"))
            error_messages.append(f"{location}: {message}" if location else message)

        if error_messages:
            return tuple(error_messages)

    return (str(exc),)


__all__ = [
    "Phase1Pipeline",
    "Phase1PipelineInput",
    "Phase1PipelineResult",
    "Phase1PipelineStatus",
]

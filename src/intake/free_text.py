"""Free-text intake builder for Phase 1 pre-authoritative source objects."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..schemas.common import NonEmptyStr
from ..schemas.intake import (
    RawInputEvent,
    RawInputMode,
    RawIntakeDecision,
    RawIntakeStatus,
    SourceDocument,
    SourceDocumentType,
)
from ..utils.time import utc_now
from .intake_gate import attempt_raw_intake
from .registry import create_source_document_from_raw_input, register_raw_input_event
from .validators import validate_intake_bundle


class FreeTextIntakeResult(BaseModel):
    """Structured result from one free-text intake build attempt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: RawIntakeStatus
    raw_input_event: RawInputEvent | None
    source_document: SourceDocument | None
    summary: NonEmptyStr
    errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "FreeTextIntakeResult":
        if self.status is RawIntakeStatus.ACCEPTED:
            if self.raw_input_event is None or self.source_document is None:
                raise ValueError(
                    "accepted free-text intake requires raw_input_event and source_document"
                )
            if self.errors:
                raise ValueError("accepted free-text intake must not carry errors")

        if self.status is RawIntakeStatus.REJECTED:
            if self.raw_input_event is not None or self.source_document is not None:
                raise ValueError(
                    "rejected free-text intake must not include intake artifacts"
                )
            if not self.errors:
                raise ValueError("rejected free-text intake requires errors")

        if self.raw_input_event is not None and self.source_document is not None:
            if self.raw_input_event.input_event_id != self.source_document.input_event_id:
                raise ValueError(
                    "raw_input_event and source_document must share input_event_id"
                )
            if self.raw_input_event.case_id != self.source_document.case_id:
                raise ValueError("raw_input_event and source_document must share case_id")

        return self


class FreeTextIntakeBuilder:
    """Convert raw free text into registered intake/source artifacts only."""

    def build(
        self,
        *,
        raw_text: str,
        case_id: str,
        input_event_id: str | None = None,
        source_doc_id: str | None = None,
        document_type: SourceDocumentType = SourceDocumentType.FREE_TEXT_CASE_NOTE,
        created_at: datetime | None = None,
        input_mode: RawInputMode = RawInputMode.INITIAL_SUBMISSION,
        arrival_index: int = 0,
        parent_input_event_id: str | None = None,
        non_authoritative_note: str | None = None,
        chunk_strategy: str | None = None,
    ) -> FreeTextIntakeResult:
        """Build raw intake and source-document objects without state writes."""

        resolved_created_at = created_at if created_at is not None else utc_now()

        if _can_delegate_to_raw_intake_gate(
            input_event_id=input_event_id,
            source_doc_id=source_doc_id,
            non_authoritative_note=non_authoritative_note,
            chunk_strategy=chunk_strategy,
        ):
            return _from_raw_intake_decision(
                attempt_raw_intake(
                    case_id=case_id,
                    raw_text=raw_text,
                    input_mode=input_mode,
                    arrival_index=arrival_index,
                    received_at=resolved_created_at,
                    parent_input_event_id=parent_input_event_id,
                    document_type=document_type,
                )
            )

        return _build_with_registry_helpers(
            raw_text=raw_text,
            case_id=case_id,
            input_event_id=input_event_id,
            source_doc_id=source_doc_id,
            document_type=document_type,
            created_at=resolved_created_at,
            input_mode=input_mode,
            arrival_index=arrival_index,
            parent_input_event_id=parent_input_event_id,
            non_authoritative_note=non_authoritative_note,
            chunk_strategy=chunk_strategy,
        )


def build_free_text_intake(
    *,
    raw_text: str,
    case_id: str,
    input_event_id: str | None = None,
    source_doc_id: str | None = None,
    document_type: SourceDocumentType = SourceDocumentType.FREE_TEXT_CASE_NOTE,
    created_at: datetime | None = None,
    input_mode: RawInputMode = RawInputMode.INITIAL_SUBMISSION,
    arrival_index: int = 0,
    parent_input_event_id: str | None = None,
    non_authoritative_note: str | None = None,
    chunk_strategy: str | None = None,
) -> FreeTextIntakeResult:
    """Convenience function for one free-text intake build."""

    return FreeTextIntakeBuilder().build(
        raw_text=raw_text,
        case_id=case_id,
        input_event_id=input_event_id,
        source_doc_id=source_doc_id,
        document_type=document_type,
        created_at=created_at,
        input_mode=input_mode,
        arrival_index=arrival_index,
        parent_input_event_id=parent_input_event_id,
        non_authoritative_note=non_authoritative_note,
        chunk_strategy=chunk_strategy,
    )


def _can_delegate_to_raw_intake_gate(
    *,
    input_event_id: str | None,
    source_doc_id: str | None,
    non_authoritative_note: str | None,
    chunk_strategy: str | None,
) -> bool:
    return (
        input_event_id is None
        and source_doc_id is None
        and non_authoritative_note is None
        and chunk_strategy is None
    )


def _from_raw_intake_decision(decision: RawIntakeDecision) -> FreeTextIntakeResult:
    if decision.status is RawIntakeStatus.REJECTED:
        return FreeTextIntakeResult(
            status=decision.status,
            raw_input_event=None,
            source_document=None,
            summary=decision.summary,
            errors=decision.blocking_errors,
            warnings=(),
        )

    return FreeTextIntakeResult(
        status=decision.status,
        raw_input_event=decision.raw_input_event,
        source_document=decision.source_document,
        summary=decision.summary,
        errors=(),
        warnings=(
            (decision.summary,)
            if decision.status is RawIntakeStatus.MANUAL_REVIEW
            else ()
        ),
    )


def _build_with_registry_helpers(
    *,
    raw_text: str,
    case_id: str,
    input_event_id: str | None,
    source_doc_id: str | None,
    document_type: SourceDocumentType,
    created_at: datetime,
    input_mode: RawInputMode,
    arrival_index: int,
    parent_input_event_id: str | None,
    non_authoritative_note: str | None,
    chunk_strategy: str | None,
) -> FreeTextIntakeResult:
    if not raw_text.strip():
        return FreeTextIntakeResult(
            status=RawIntakeStatus.REJECTED,
            raw_input_event=None,
            source_document=None,
            summary="Free-text intake rejected: empty raw_text.",
            errors=("raw_text must not be empty",),
            warnings=(),
        )

    try:
        raw_input_event = register_raw_input_event(
            case_id=case_id,
            raw_text=raw_text,
            input_mode=input_mode,
            received_at=created_at,
            arrival_index=arrival_index,
            parent_input_event_id=parent_input_event_id,
            input_event_id=input_event_id,
            non_authoritative_note=non_authoritative_note,
        )
        source_document = create_source_document_from_raw_input(
            raw_input_event,
            document_type,
            source_doc_id=source_doc_id,
            created_at=created_at,
            chunk_strategy=chunk_strategy,
            non_authoritative_note=non_authoritative_note,
        )
        validate_intake_bundle(
            raw_input_events=(raw_input_event,),
            source_documents=(source_document,),
        )
    except (ValidationError, ValueError) as exc:
        return FreeTextIntakeResult(
            status=RawIntakeStatus.REJECTED,
            raw_input_event=None,
            source_document=None,
            summary="Free-text intake rejected: validation failed.",
            errors=_extract_errors(exc),
            warnings=(),
        )

    if (
        input_mode in {RawInputMode.CORRECTION, RawInputMode.REPLACEMENT}
        and parent_input_event_id is None
    ):
        warning = (
            "Free-text intake accepted into source registry but flagged for manual "
            "review due to correction/replacement without parent input event."
        )
        return FreeTextIntakeResult(
            status=RawIntakeStatus.MANUAL_REVIEW,
            raw_input_event=raw_input_event,
            source_document=source_document,
            summary=warning,
            errors=(),
            warnings=(warning,),
        )

    return FreeTextIntakeResult(
        status=RawIntakeStatus.ACCEPTED,
        raw_input_event=raw_input_event,
        source_document=source_document,
        summary=(
            "Free-text intake accepted into source registry. Authoritative clinical "
            "state write remains gated by existing Phase 1 validators."
        ),
        errors=(),
        warnings=(),
    )


def _extract_errors(exc: ValidationError | ValueError) -> tuple[str, ...]:
    if isinstance(exc, ValidationError):
        error_messages: list[str] = []
        for error_item in exc.errors(include_url=False):
            loc = ".".join(str(part) for part in error_item.get("loc", ()))
            message = str(error_item.get("msg", "validation error"))
            error_messages.append(f"{loc}: {message}" if loc else message)

        if error_messages:
            return tuple(error_messages)

    return (str(exc),)


__all__ = [
    "FreeTextIntakeBuilder",
    "FreeTextIntakeResult",
    "build_free_text_intake",
]

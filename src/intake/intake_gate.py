"""Raw intake gate for Phase 1 pre-authoritative intake artifacts."""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from ..schemas.intake import (
    RawInputMode,
    RawIntakeDecision,
    RawIntakeStatus,
    SourceDocumentType,
)
from .registry import (
    create_source_document_from_raw_input,
    register_raw_input_event,
)
from .validators import validate_intake_bundle


def attempt_raw_intake(
    *,
    case_id: str,
    raw_text: str,
    input_mode: RawInputMode,
    arrival_index: int,
    received_at: datetime,
    parent_input_event_id: str | None = None,
    document_type: SourceDocumentType = SourceDocumentType.FREE_TEXT_CASE_NOTE,
) -> RawIntakeDecision:
    """Attempt one raw-text intake write into intake registry artifacts.

    Accepted intake only means source registry admission and does not imply
    authoritative clinical-state write readiness.
    """

    if not raw_text.strip():
        return RawIntakeDecision(
            status=RawIntakeStatus.REJECTED,
            raw_input_event=None,
            source_document=None,
            summary="Raw intake rejected: empty raw_text.",
            blocking_errors=("raw_text must not be empty",),
        )

    try:
        raw_input_event = register_raw_input_event(
            case_id=case_id,
            raw_text=raw_text,
            input_mode=input_mode,
            received_at=received_at,
            arrival_index=arrival_index,
            parent_input_event_id=parent_input_event_id,
        )
        source_document = create_source_document_from_raw_input(
            raw_input_event,
            document_type=document_type,
        )
        validate_intake_bundle(
            raw_input_events=(raw_input_event,),
            source_documents=(source_document,),
        )
    except (ValidationError, ValueError) as exc:
        blocking_errors = _extract_blocking_errors(exc)
        return RawIntakeDecision(
            status=RawIntakeStatus.REJECTED,
            raw_input_event=None,
            source_document=None,
            summary="Raw intake rejected: validation failed.",
            blocking_errors=blocking_errors,
        )

    if (
        input_mode in {RawInputMode.CORRECTION, RawInputMode.REPLACEMENT}
        and parent_input_event_id is None
    ):
        return RawIntakeDecision(
            status=RawIntakeStatus.MANUAL_REVIEW,
            raw_input_event=raw_input_event,
            source_document=source_document,
            summary=(
                "Raw intake accepted into source registry but flagged for manual "
                "review due to correction/replacement without parent input event."
            ),
            blocking_errors=(),
        )

    return RawIntakeDecision(
        status=RawIntakeStatus.ACCEPTED,
        raw_input_event=raw_input_event,
        source_document=source_document,
        summary=(
            "Raw intake accepted into source registry. Authoritative clinical "
            "state write remains gated by existing Phase 1 validators."
        ),
        blocking_errors=(),
    )


def _extract_blocking_errors(exc: ValidationError | ValueError) -> tuple[str, ...]:
    if isinstance(exc, ValidationError):
        error_messages = []
        for error_item in exc.errors(include_url=False):
            loc = ".".join(str(part) for part in error_item.get("loc", ()))
            message = str(error_item.get("msg", "validation error"))
            if loc:
                error_messages.append(f"{loc}: {message}")
            else:
                error_messages.append(message)

        if error_messages:
            return tuple(error_messages)

    return (str(exc),)


__all__ = ["attempt_raw_intake"]

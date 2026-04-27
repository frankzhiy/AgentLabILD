"""Raw-text intake registry helpers.

This module is intentionally lightweight and in-memory only. It does not call
LLM components and does not create authoritative Phase1StateEnvelope objects.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from ..schemas.intake import (
    RawInputEvent,
    RawInputMode,
    SourceDocument,
    SourceDocumentType,
)


def register_raw_input_event(
    *,
    case_id: str,
    raw_text: str,
    input_mode: RawInputMode,
    received_at: datetime,
    arrival_index: int,
    parent_input_event_id: str | None = None,
    input_event_id: str | None = None,
    non_authoritative_note: str | None = None,
) -> RawInputEvent:
    """Register one raw user input event as immutable intake source."""

    resolved_input_event_id = (
        input_event_id
        if input_event_id is not None
        else build_input_event_id(
            case_id=case_id,
            arrival_index=arrival_index,
            received_at=received_at,
            raw_text=raw_text,
        )
    )

    return RawInputEvent(
        input_event_id=resolved_input_event_id,
        case_id=case_id,
        arrival_index=arrival_index,
        raw_text=raw_text,
        received_at=received_at,
        input_mode=input_mode,
        parent_input_event_id=parent_input_event_id,
        non_authoritative_note=non_authoritative_note,
    )


def create_source_document_from_raw_input(
    raw_input_event: RawInputEvent,
    document_type: SourceDocumentType,
    *,
    source_doc_id: str | None = None,
    created_at: datetime | None = None,
    raw_text_subset: str | None = None,
    chunk_strategy: str | None = None,
    non_authoritative_note: str | None = None,
) -> SourceDocument:
    """Create one immutable source document from an intake event.

    By default, source raw_text is copied exactly from the intake event.
    """

    if raw_text_subset is None:
        resolved_raw_text = raw_input_event.raw_text
    else:
        if raw_text_subset not in raw_input_event.raw_text:
            raise ValueError(
                "raw_text_subset must be an exact substring of raw_input_event.raw_text"
            )
        resolved_raw_text = raw_text_subset

    resolved_created_at = (
        created_at if created_at is not None else raw_input_event.received_at
    )

    resolved_source_doc_id = (
        source_doc_id
        if source_doc_id is not None
        else build_source_doc_id(
            input_event_id=raw_input_event.input_event_id,
            document_type=document_type,
            raw_text=resolved_raw_text,
        )
    )

    return SourceDocument(
        source_doc_id=resolved_source_doc_id,
        case_id=raw_input_event.case_id,
        input_event_id=raw_input_event.input_event_id,
        document_type=document_type,
        raw_text=resolved_raw_text,
        created_at=resolved_created_at,
        chunk_strategy=chunk_strategy,
        non_authoritative_note=non_authoritative_note,
    )


def build_input_event_id(
    *,
    case_id: str,
    arrival_index: int,
    received_at: datetime,
    raw_text: str,
) -> str:
    """Build deterministic input_event_id for test-friendly behavior."""

    digest = _stable_digest(
        case_id,
        str(arrival_index),
        received_at.isoformat(),
        raw_text,
    )
    return f"input_event-{arrival_index:04d}-{digest[:8]}"


def build_source_doc_id(
    *,
    input_event_id: str,
    document_type: SourceDocumentType,
    raw_text: str,
) -> str:
    """Build deterministic source_doc_id for test-friendly behavior."""

    digest = _stable_digest(input_event_id, document_type.value, raw_text)
    return f"doc-{digest[:10]}"


def _stable_digest(*parts: str) -> str:
    payload = "||".join(parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


__all__ = [
    "build_input_event_id",
    "build_source_doc_id",
    "create_source_document_from_raw_input",
    "register_raw_input_event",
]

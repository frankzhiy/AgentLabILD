"""Validation helpers for raw-text intake and source documents."""

from __future__ import annotations

from collections.abc import Iterable

from ..schemas.common import find_duplicate_items
from ..schemas.intake import RawInputEvent, SourceDocument


def validate_source_document_contains_excerpt(
    source_document: SourceDocument,
    raw_excerpt: str,
    *,
    source_span_start: int | None = None,
    source_span_end: int | None = None,
) -> bool:
    """Validate whether one excerpt is grounded in the source document text.

    When spans are provided, exact substring equality is required.
    When spans are not provided, raw_excerpt must be a substring.
    """

    if not raw_excerpt:
        raise ValueError("raw_excerpt must not be empty")

    if (source_span_start is None) ^ (source_span_end is None):
        raise ValueError(
            "source_span_start and source_span_end must be provided together"
        )

    if source_span_start is None and source_span_end is None:
        return raw_excerpt in source_document.raw_text

    assert source_span_start is not None
    assert source_span_end is not None

    if source_span_start < 0 or source_span_end < 0:
        raise ValueError("source spans must be non-negative")

    if source_span_start > source_span_end:
        raise ValueError("source_span_start must be <= source_span_end")

    if source_span_end > len(source_document.raw_text):
        raise ValueError("source_span_end exceeds source_document.raw_text length")

    return source_document.raw_text[source_span_start:source_span_end] == raw_excerpt


def validate_intake_bundle(
    *,
    raw_input_events: tuple[RawInputEvent, ...],
    source_documents: tuple[SourceDocument, ...],
) -> None:
    """Validate intake event-source consistency without state writes."""

    _raise_if_duplicates(
        values=(event.input_event_id for event in raw_input_events),
        field_name="raw_input_events.input_event_id",
    )
    _raise_if_duplicates(
        values=(document.source_doc_id for document in source_documents),
        field_name="source_documents.source_doc_id",
    )

    event_by_id = {event.input_event_id: event for event in raw_input_events}

    for source_document in source_documents:
        source_event = event_by_id.get(source_document.input_event_id)
        if source_event is None:
            raise ValueError(
                "source_document.input_event_id must reference an existing RawInputEvent"
            )

        if source_document.case_id != source_event.case_id:
            raise ValueError(
                "source_document.case_id must align with parent RawInputEvent.case_id"
            )

        if source_document.raw_text not in source_event.raw_text:
            raise ValueError(
                "source_document.raw_text must remain immutable from parent RawInputEvent.raw_text"
            )


def _raise_if_duplicates(*, values: Iterable[str], field_name: str) -> None:
    duplicates = find_duplicate_items(values)
    if not duplicates:
        return

    joined = ", ".join(duplicates)
    raise ValueError(f"{field_name} contains duplicate values: {joined}")


__all__ = [
    "validate_intake_bundle",
    "validate_source_document_contains_excerpt",
]

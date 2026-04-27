"""Raw-text intake package exports."""

from .intake_gate import attempt_raw_intake
from .registry import (
    build_input_event_id,
    build_source_doc_id,
    create_source_document_from_raw_input,
    register_raw_input_event,
)
from .validators import (
    validate_intake_bundle,
    validate_source_document_contains_excerpt,
)

__all__ = [
    "attempt_raw_intake",
    "build_input_event_id",
    "build_source_doc_id",
    "create_source_document_from_raw_input",
    "register_raw_input_event",
    "validate_intake_bundle",
    "validate_source_document_contains_excerpt",
]

"""Raw-text intake package exports."""

from .free_text import (
    FreeTextIntakeBuilder,
    FreeTextIntakeResult,
    build_free_text_intake,
)
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
    "FreeTextIntakeBuilder",
    "FreeTextIntakeResult",
    "attempt_raw_intake",
    "build_free_text_intake",
    "build_input_event_id",
    "build_source_doc_id",
    "create_source_document_from_raw_input",
    "register_raw_input_event",
    "validate_intake_bundle",
    "validate_source_document_contains_excerpt",
]

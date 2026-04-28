"""Tests for the free-text intake builder facade."""

from __future__ import annotations

import ast
import inspect
from datetime import datetime

import src.intake.free_text as free_text_module
from src.intake import FreeTextIntakeBuilder, FreeTextIntakeResult, build_free_text_intake
from src.schemas.intake import RawInputMode, RawIntakeStatus, SourceDocumentType


def test_free_text_intake_builder_accepts_valid_explicit_intake_ids() -> None:
    created_at = datetime(2026, 4, 28, 9, 0, 0)
    raw_text = "Patient reports chronic cough and exertional dyspnea."
    builder = FreeTextIntakeBuilder()

    result = builder.build(
        raw_text=raw_text,
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        document_type=SourceDocumentType.FREE_TEXT_CASE_NOTE,
        created_at=created_at,
        arrival_index=0,
        non_authoritative_note="submitted free text",
    )

    assert result.status is RawIntakeStatus.ACCEPTED
    assert result.raw_input_event is not None
    assert result.source_document is not None
    assert result.raw_input_event.input_event_id == "input_event-001"
    assert result.source_document.source_doc_id == "doc-001"
    assert result.source_document.input_event_id == result.raw_input_event.input_event_id
    assert result.source_document.case_id == "case-001"
    assert result.raw_input_event.raw_text == raw_text
    assert result.source_document.raw_text == raw_text
    assert result.raw_input_event.received_at == created_at
    assert result.source_document.created_at == created_at
    assert result.source_document.document_type is SourceDocumentType.FREE_TEXT_CASE_NOTE
    assert result.errors == ()


def test_free_text_intake_builder_generates_deterministic_ids_when_timestamp_is_fixed() -> None:
    created_at = datetime(2026, 4, 28, 9, 0, 0)

    first = build_free_text_intake(
        raw_text="Stable source text.",
        case_id="case-001",
        created_at=created_at,
        arrival_index=7,
    )
    second = build_free_text_intake(
        raw_text="Stable source text.",
        case_id="case-001",
        created_at=created_at,
        arrival_index=7,
    )

    assert first.status is RawIntakeStatus.ACCEPTED
    assert second.status is RawIntakeStatus.ACCEPTED
    assert first.raw_input_event is not None
    assert second.raw_input_event is not None
    assert first.source_document is not None
    assert second.source_document is not None
    assert first.raw_input_event.input_event_id == second.raw_input_event.input_event_id
    assert first.source_document.source_doc_id == second.source_document.source_doc_id


def test_free_text_intake_builder_rejects_empty_raw_text() -> None:
    result = build_free_text_intake(
        raw_text="   ",
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        created_at=datetime(2026, 4, 28, 9, 0, 0),
    )

    assert result.status is RawIntakeStatus.REJECTED
    assert result.raw_input_event is None
    assert result.source_document is None
    assert result.errors == ("raw_text must not be empty",)


def test_free_text_intake_builder_rejects_invalid_case_id() -> None:
    result = build_free_text_intake(
        raw_text="Valid clinical text.",
        case_id="patient-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        created_at=datetime(2026, 4, 28, 9, 0, 0),
    )

    assert result.status is RawIntakeStatus.REJECTED
    assert result.raw_input_event is None
    assert result.source_document is None
    assert any("case_id" in error for error in result.errors)


def test_free_text_intake_builder_rejects_invalid_source_doc_id() -> None:
    result = build_free_text_intake(
        raw_text="Valid clinical text.",
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="source-001",
        created_at=datetime(2026, 4, 28, 9, 0, 0),
    )

    assert result.status is RawIntakeStatus.REJECTED
    assert result.raw_input_event is None
    assert result.source_document is None
    assert any("source_doc_id" in error for error in result.errors)


def test_free_text_intake_builder_preserves_manual_review_gate_semantics() -> None:
    result = build_free_text_intake(
        raw_text="Correction: smoking history was 20 pack-years.",
        case_id="case-001",
        input_mode=RawInputMode.CORRECTION,
        created_at=datetime(2026, 4, 28, 9, 0, 0),
        arrival_index=2,
    )

    assert result.status is RawIntakeStatus.MANUAL_REVIEW
    assert result.raw_input_event is not None
    assert result.source_document is not None
    assert result.errors == ()
    assert result.warnings


def test_free_text_intake_builder_result_does_not_create_stage_or_state_objects() -> None:
    result = build_free_text_intake(
        raw_text="Initial free-text case note.",
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        created_at=datetime(2026, 4, 28, 9, 0, 0),
    )

    assert result.status is RawIntakeStatus.ACCEPTED
    assert not hasattr(result, "stage_context")
    assert not hasattr(result, "case_structurer_input")
    assert not hasattr(result, "evidence_atomizer_input")
    assert not hasattr(result, "phase1_state_envelope")
    assert not hasattr(result, "hypothesis_board_init")
    assert not hasattr(result, "hypothesis_state")
    assert not hasattr(result, "action_candidate")
    assert not hasattr(result, "claim_reference")


def test_free_text_intake_module_has_no_llm_or_state_writer_coupling() -> None:
    source_code = inspect.getsource(free_text_module)
    module_ast = ast.parse(source_code)
    import_targets: list[str] = []

    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            import_targets.extend(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module_name = node.module or ""
            import_targets.append(f"{prefix}{module_name}")

    forbidden_fragments = (
        "llm",
        "StructuredLLMRunner",
        "agents",
        "state_writer",
        "Phase1StateEnvelope",
        "StageContext",
        "HypothesisBoardInit",
        "HypothesisState",
        "ActionCandidate",
        "ClaimReference",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source_code

    forbidden_import_prefixes = ("src.llm", "..llm", "src.state", "..state")
    for forbidden_prefix in forbidden_import_prefixes:
        assert all(
            not target.startswith(forbidden_prefix) for target in import_targets
        )


def test_free_text_intake_exports_builder_and_result_objects() -> None:
    result = build_free_text_intake(
        raw_text="Exported builder path.",
        case_id="case-001",
        input_event_id="input_event-001",
        source_doc_id="doc-001",
        created_at=datetime(2026, 4, 28, 9, 0, 0),
    )

    assert isinstance(FreeTextIntakeBuilder(), FreeTextIntakeBuilder)
    assert isinstance(result, FreeTextIntakeResult)
    assert result.status is RawIntakeStatus.ACCEPTED

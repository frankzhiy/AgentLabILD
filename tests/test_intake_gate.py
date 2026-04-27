"""Tests for Phase 1 raw-text intake gate and registry helpers."""

from __future__ import annotations

import ast
import inspect
from datetime import datetime

from src.intake.intake_gate import attempt_raw_intake
from src.intake.registry import (
    create_source_document_from_raw_input,
    register_raw_input_event,
)
from src.schemas.intake import RawInputMode, RawIntakeStatus, SourceDocumentType


def test_initial_raw_input_creates_raw_input_event_and_source_document() -> None:
    decision = attempt_raw_intake(
        case_id="case-abc",
        raw_text="患者, 女, 77岁, 间断咳嗽咳痰伴胸闷气短8年。",
        input_mode=RawInputMode.INITIAL_SUBMISSION,
        arrival_index=0,
        received_at=datetime(2026, 4, 27, 10, 0, 0),
    )

    assert decision.status is RawIntakeStatus.ACCEPTED
    assert decision.raw_input_event is not None
    assert decision.source_document is not None
    assert decision.source_document.input_event_id == decision.raw_input_event.input_event_id


def test_append_raw_input_can_reference_parent_input_event_id() -> None:
    decision = attempt_raw_intake(
        case_id="case-abc",
        raw_text="追加: 近2月活动后气短明显加重。",
        input_mode=RawInputMode.APPEND,
        arrival_index=1,
        received_at=datetime(2026, 4, 27, 11, 0, 0),
        parent_input_event_id="input_event-0001",
        document_type=SourceDocumentType.FOLLOWUP_NOTE_TEXT,
    )

    assert decision.status is RawIntakeStatus.ACCEPTED
    assert decision.raw_input_event is not None
    assert decision.raw_input_event.parent_input_event_id == "input_event-0001"
    assert decision.source_document is not None
    assert decision.source_document.document_type is SourceDocumentType.FOLLOWUP_NOTE_TEXT


def test_source_document_raw_text_preserves_raw_input_event_text_exactly() -> None:
    raw_input_event = register_raw_input_event(
        case_id="case-abc",
        raw_text="原始文本A\n原始文本B",
        input_mode=RawInputMode.INITIAL_SUBMISSION,
        received_at=datetime(2026, 4, 27, 12, 0, 0),
        arrival_index=0,
    )

    source_document = create_source_document_from_raw_input(
        raw_input_event,
        SourceDocumentType.FREE_TEXT_CASE_NOTE,
    )

    assert source_document.raw_text == raw_input_event.raw_text


def test_empty_raw_text_is_rejected() -> None:
    decision = attempt_raw_intake(
        case_id="case-abc",
        raw_text="   ",
        input_mode=RawInputMode.INITIAL_SUBMISSION,
        arrival_index=0,
        received_at=datetime(2026, 4, 27, 12, 30, 0),
    )

    assert decision.status is RawIntakeStatus.REJECTED
    assert decision.raw_input_event is None
    assert decision.source_document is None
    assert decision.blocking_errors


def test_invalid_case_id_is_rejected() -> None:
    decision = attempt_raw_intake(
        case_id="patient-abc",
        raw_text="有效文本",
        input_mode=RawInputMode.INITIAL_SUBMISSION,
        arrival_index=0,
        received_at=datetime(2026, 4, 27, 13, 0, 0),
    )

    assert decision.status is RawIntakeStatus.REJECTED
    assert decision.raw_input_event is None
    assert decision.source_document is None
    assert any("case_id" in message for message in decision.blocking_errors)


def test_correction_without_parent_enters_manual_review() -> None:
    decision = attempt_raw_intake(
        case_id="case-abc",
        raw_text="更正: 既往吸烟史为20包年。",
        input_mode=RawInputMode.CORRECTION,
        arrival_index=2,
        received_at=datetime(2026, 4, 27, 14, 0, 0),
    )

    assert decision.status is RawIntakeStatus.MANUAL_REVIEW
    assert decision.raw_input_event is not None
    assert decision.source_document is not None


def test_raw_intake_module_does_not_import_or_call_phase1_state_writer() -> None:
    import src.intake.intake_gate as intake_gate_module

    source_code = inspect.getsource(intake_gate_module)
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

    forbidden_prefixes = (
        "src.state",
        "src.state.state_writer",
        "..state",
        "..state.state_writer",
    )

    for forbidden_prefix in forbidden_prefixes:
        assert all(
            not target.startswith(forbidden_prefix) for target in import_targets
        )

    assert "attempt_phase1_write" not in source_code

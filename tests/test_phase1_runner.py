"""Tests for Phase 1 deterministic evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.phase1_runner import (
    evaluate_phase1_fixture_dir,
    evaluate_phase1_payload,
    evaluate_phase1_payloads,
    load_phase1_fixture,
)
from src.validators.pipeline import (
    FULL_VALIDATOR_EXECUTION_ORDER,
    SCHEMA_ONLY_EXECUTION_ORDER,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase1"


def test_evaluate_phase1_payload_returns_valid_result_for_valid_minimal_fixture() -> None:
    payload = load_phase1_fixture(FIXTURE_DIR / "valid_minimal_case.json")

    result = evaluate_phase1_payload(payload, fixture_name="valid_minimal_case.json")

    assert result.fixture_name == "valid_minimal_case.json"
    assert result.case_id == "case-abc"
    assert result.state_id == "state-001"
    assert result.schema_valid is True
    assert result.has_blocking_issue is False
    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER


def test_invalid_missing_evidence_ref_fixture_returns_schema_invalid_without_crash() -> None:
    payload = load_phase1_fixture(FIXTURE_DIR / "invalid_missing_evidence_ref.json")

    result = evaluate_phase1_payload(
        payload,
        fixture_name="invalid_missing_evidence_ref.json",
    )

    assert result.schema_valid is False
    assert result.has_blocking_issue is True
    assert result.validator_execution_order == SCHEMA_ONLY_EXECUTION_ORDER
    assert "schema.model_error" in result.blocking_issue_codes


def test_invalid_unsupported_claim_fixture_exposes_unsupported_claim_issue_code() -> None:
    payload = load_phase1_fixture(FIXTURE_DIR / "invalid_unsupported_claim.json")

    result = evaluate_phase1_payload(
        payload,
        fixture_name="invalid_unsupported_claim.json",
    )

    assert result.schema_valid is True
    assert result.has_blocking_issue is True
    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert "unsupported_claim.invalid_target_binding" in result.blocking_issue_codes


def test_evaluate_phase1_fixture_dir_evaluates_all_phase1_fixture_files() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)

    # 8 fixture files total, with valid_two_stage_version_chain expanding to 2 states.
    assert batch_result.evaluated_count == 9
    assert len(batch_result.results) == 9
    assert batch_result.valid_count + batch_result.invalid_count == 9


def test_two_stage_chain_fixture_returns_lineage_valid_metric() -> None:
    payload = load_phase1_fixture(FIXTURE_DIR / "valid_two_stage_version_chain.json")

    batch_result = evaluate_phase1_payloads((payload,))

    lineage_metric = batch_result.metric_summary.metrics[
        "state_version_lineage_validity_rate"
    ]
    assert batch_result.evaluated_count == 2
    assert lineage_metric.applicable is True
    assert lineage_metric.value == 1.0


def test_runner_output_is_json_serializable() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)

    serialized = json.dumps(batch_result.model_dump(mode="json"))
    assert isinstance(serialized, str)
    assert serialized


def test_runner_preserves_validator_execution_order_without_duplication() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)

    for case_result in batch_result.results:
        execution_order = case_result.validator_execution_order
        assert len(execution_order) == len(set(execution_order))

        if case_result.schema_valid:
            assert execution_order == FULL_VALIDATOR_EXECUTION_ORDER
        else:
            assert execution_order == SCHEMA_ONLY_EXECUTION_ORDER

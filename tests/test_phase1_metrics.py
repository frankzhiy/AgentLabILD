"""Tests for deterministic Phase 1 evaluation metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.phase1_metrics import (
    CLAIM_EVIDENCE_TRACEABILITY_RATE,
    HYPOTHESIS_BOARD_COMPLETENESS_RATE,
    PROVENANCE_COMPLETENESS_RATE,
    SCHEMA_VALIDITY_RATE,
    STAGE_ALIGNMENT_RATE,
    STATE_VERSION_LINEAGE_VALIDITY_RATE,
    UNSUPPORTED_CLAIM_RATE,
    compute_phase1_metrics,
    compute_rerun_stability_metric,
)
from src.evaluation.phase1_runner import load_phase1_fixture
from src.validators.pipeline import (
    Phase1ValidationPipelineResult,
    ValidationPipelinePolicy,
    validate_phase1_candidate_pipeline,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase1"


def _run_fixture_pipeline(
    fixture_name: str,
) -> tuple[Phase1ValidationPipelineResult, ...]:
    payload = load_phase1_fixture(FIXTURE_DIR / fixture_name)
    raw_states = payload.get("states")

    if isinstance(raw_states, list):
        results: list[Phase1ValidationPipelineResult] = []
        for state_payload in raw_states:
            assert isinstance(state_payload, dict)
            results.append(
                validate_phase1_candidate_pipeline(
                    state_payload,
                    policy=ValidationPipelinePolicy(require_provenance=True),
                )
            )
        return tuple(results)

    return (
        validate_phase1_candidate_pipeline(
            payload,
            policy=ValidationPipelinePolicy(require_provenance=True),
        ),
    )


def test_valid_minimal_fixture_has_full_schema_validity_rate() -> None:
    summary = compute_phase1_metrics(_run_fixture_pipeline("valid_minimal_case.json"))

    metric = summary.metrics[SCHEMA_VALIDITY_RATE]
    assert metric.applicable is True
    assert metric.numerator == 1
    assert metric.denominator == 1
    assert metric.value == pytest.approx(1.0)


def test_valid_multihypothesis_fixture_has_complete_board_metric() -> None:
    summary = compute_phase1_metrics(
        _run_fixture_pipeline("valid_multihypothesis_case.json")
    )

    metric = summary.metrics[HYPOTHESIS_BOARD_COMPLETENESS_RATE]
    assert metric.applicable is True
    assert metric.numerator == 1
    assert metric.denominator == 1
    assert metric.value == pytest.approx(1.0)


def test_invalid_missing_evidence_ref_marks_downstream_metrics_not_applicable() -> None:
    summary = compute_phase1_metrics(
        _run_fixture_pipeline("invalid_missing_evidence_ref.json")
    )

    assert summary.metrics[SCHEMA_VALIDITY_RATE].value == pytest.approx(0.0)

    for metric_name in (
        PROVENANCE_COMPLETENESS_RATE,
        CLAIM_EVIDENCE_TRACEABILITY_RATE,
        UNSUPPORTED_CLAIM_RATE,
        STAGE_ALIGNMENT_RATE,
        HYPOTHESIS_BOARD_COMPLETENESS_RATE,
    ):
        assert summary.metrics[metric_name].applicable is False


def test_invalid_unsupported_claim_fixture_keeps_schema_valid_and_raises_rate() -> None:
    summary = compute_phase1_metrics(
        _run_fixture_pipeline("invalid_unsupported_claim.json")
    )

    assert summary.metrics[SCHEMA_VALIDITY_RATE].value == pytest.approx(1.0)

    unsupported_metric = summary.metrics[UNSUPPORTED_CLAIM_RATE]
    assert unsupported_metric.applicable is True
    assert unsupported_metric.value is not None
    assert unsupported_metric.value > 0.0


def test_stage_mismatch_fixture_decreases_schema_and_stage_alignment_rates() -> None:
    combined_results = (
        *_run_fixture_pipeline("valid_minimal_case.json"),
        *_run_fixture_pipeline("invalid_stage_mismatch.json"),
    )
    summary = compute_phase1_metrics(combined_results)

    schema_metric = summary.metrics[SCHEMA_VALIDITY_RATE]
    stage_metric = summary.metrics[STAGE_ALIGNMENT_RATE]

    assert schema_metric.applicable is True
    assert schema_metric.value == pytest.approx(0.5)
    assert stage_metric.applicable is True
    assert stage_metric.value == pytest.approx(0.5)


def test_two_stage_chain_fixture_has_valid_lineage_metric() -> None:
    summary = compute_phase1_metrics(
        _run_fixture_pipeline("valid_two_stage_version_chain.json")
    )

    lineage_metric = summary.metrics[STATE_VERSION_LINEAGE_VALIDITY_RATE]
    assert lineage_metric.applicable is True
    assert lineage_metric.numerator == 1
    assert lineage_metric.denominator == 1
    assert lineage_metric.value == pytest.approx(1.0)


def test_rerun_stability_metric_is_one_for_identical_reruns() -> None:
    first_run = _run_fixture_pipeline("valid_minimal_case.json")
    second_run = _run_fixture_pipeline("valid_minimal_case.json")

    metric = compute_rerun_stability_metric(first_run, second_run)
    assert metric.applicable is True
    assert metric.numerator == 1
    assert metric.denominator == 1
    assert metric.value == pytest.approx(1.0)

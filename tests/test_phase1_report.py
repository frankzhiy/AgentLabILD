"""Tests for Phase 1 deterministic audit report output."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation import phase1_runner
from src.evaluation.phase1_runner import evaluate_phase1_fixture_dir
from src.evaluation.reporting import (
    build_phase1_audit_report,
    build_phase1_markdown_summary,
    phase1_report_to_dict,
    phase1_report_to_json,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase1"


def test_build_phase1_report_from_fixture_dir_output() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)

    report = build_phase1_audit_report(batch_result)

    assert report.phase == "phase1_state_externalization"
    assert report.evaluated_count == batch_result.evaluated_count
    assert report.valid_count == batch_result.valid_count
    assert report.invalid_count == batch_result.invalid_count


def test_report_output_is_json_serializable() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)
    report = build_phase1_audit_report(batch_result)

    report_dict = phase1_report_to_dict(report)
    serialized = phase1_report_to_json(report)

    assert isinstance(report_dict, dict)
    assert isinstance(serialized, str)
    assert json.loads(serialized)["phase"] == "phase1_state_externalization"


def test_blocking_issue_distribution_includes_expected_invalid_fixture_issue_codes() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)
    report = build_phase1_audit_report(batch_result)

    distribution = report.blocking_issue_distribution
    assert distribution.get("schema.model_error", 0) > 0
    assert distribution.get("unsupported_claim.invalid_target_binding", 0) > 0
    assert distribution.get("temporal.stage_after_envelope", 0) > 0


def test_valid_fixtures_do_not_add_blocking_issue_codes() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)
    report = build_phase1_audit_report(batch_result)

    valid_fixture_names = {
        "valid_minimal_case.json",
        "valid_multihypothesis_case.json",
        "valid_two_stage_version_chain.json",
    }

    for case_result in report.per_case_results:
        if case_result.get("fixture_name") in valid_fixture_names:
            assert not case_result.get("blocking_issue_codes")


def test_markdown_summary_contains_key_phase1_metric_labels() -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)
    report = build_phase1_audit_report(batch_result)

    markdown = build_phase1_markdown_summary(report)

    assert "phase1_state_externalization" in markdown
    assert "schema_validity_rate" in markdown
    assert "provenance_completeness_rate" in markdown
    assert "unsupported_claim_rate" in markdown


def test_reporting_only_consumes_runner_output_without_rerunning_pipeline(
    monkeypatch,
) -> None:
    batch_result = evaluate_phase1_fixture_dir(FIXTURE_DIR)

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("validation pipeline should not be called during report build")

    monkeypatch.setattr(
        phase1_runner,
        "validate_phase1_candidate_pipeline",
        _fail_if_called,
    )

    report = build_phase1_audit_report(batch_result)
    assert report.evaluated_count == batch_result.evaluated_count

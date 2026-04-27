"""Phase 1 deterministic evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas.validation import ValidationSeverity
from ..validators.pipeline import (
    Phase1ValidationPipelineResult,
    ValidationPipelinePolicy,
    validate_phase1_candidate_pipeline,
)
from ..validators.schema_validator import SCHEMA_VALIDATOR_NAME
from .phase1_metrics import Phase1MetricSummary, compute_phase1_metrics


class Phase1CaseEvaluationInput(BaseModel):
    """One input unit for Phase 1 candidate evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str | None = None
    fixture_name: str | None = None
    payload: dict[str, object]
    expected_failure_mode: str | None = None


class Phase1CaseEvaluationResult(BaseModel):
    """Structured per-state evaluation result from one pipeline execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str | None = None
    state_id: str
    fixture_name: str | None = None
    schema_valid: bool
    has_blocking_issue: bool
    blocking_issue_codes: tuple[str, ...] = Field(default_factory=tuple)
    warning_issue_codes: tuple[str, ...] = Field(default_factory=tuple)
    validator_execution_order: tuple[str, ...] = Field(default_factory=tuple)
    metric_values: dict[str, object] = Field(default_factory=dict)


class Phase1BatchEvaluationResult(BaseModel):
    """Batch-level Phase 1 evaluation output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    results: tuple[Phase1CaseEvaluationResult, ...]
    metric_summary: Phase1MetricSummary
    evaluated_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_count_consistency(self) -> "Phase1BatchEvaluationResult":
        if self.evaluated_count != len(self.results):
            raise ValueError("evaluated_count must equal len(results)")

        if self.valid_count + self.invalid_count != self.evaluated_count:
            raise ValueError(
                "valid_count + invalid_count must equal evaluated_count"
            )

        if self.metric_summary.evaluated_count != self.evaluated_count:
            raise ValueError(
                "metric_summary.evaluated_count must equal evaluated_count"
            )

        return self


def load_phase1_fixture(path: Path) -> dict[str, object]:
    """Load one JSON fixture payload."""

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if not isinstance(payload, dict):
        raise ValueError("fixture root must be a JSON object")

    return payload


def evaluate_phase1_payload(
    payload: dict[str, object],
    fixture_name: str | None = None,
) -> Phase1CaseEvaluationResult:
    """Evaluate one single-state payload against the existing pipeline."""

    state_payloads = _extract_state_payloads(payload)
    if len(state_payloads) != 1:
        raise ValueError(
            "payload expands to multiple states; use evaluate_phase1_payloads or "
            "evaluate_phase1_fixture_dir"
        )

    case_result, _ = _evaluate_single_state_payload(
        state_payloads[0],
        fixture_name=fixture_name,
    )
    return case_result


def evaluate_phase1_payloads(
    payloads: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> Phase1BatchEvaluationResult:
    """Evaluate in-memory payloads, including multi-state lineage fixtures."""

    case_results: list[Phase1CaseEvaluationResult] = []
    pipeline_results: list[Phase1ValidationPipelineResult] = []

    for payload in payloads:
        for state_payload in _extract_state_payloads(payload):
            case_result, pipeline_result = _evaluate_single_state_payload(
                state_payload,
                fixture_name=None,
            )
            case_results.append(case_result)
            pipeline_results.append(pipeline_result)

    return _build_batch_result(
        case_results=tuple(case_results),
        pipeline_results=tuple(pipeline_results),
    )


def evaluate_phase1_fixture_dir(
    fixture_dir: Path,
) -> Phase1BatchEvaluationResult:
    """Evaluate all JSON fixtures under one directory."""

    case_results: list[Phase1CaseEvaluationResult] = []
    pipeline_results: list[Phase1ValidationPipelineResult] = []

    for fixture_path in sorted(fixture_dir.glob("*.json")):
        payload = load_phase1_fixture(fixture_path)
        for state_payload in _extract_state_payloads(payload):
            case_result, pipeline_result = _evaluate_single_state_payload(
                state_payload,
                fixture_name=fixture_path.name,
            )
            case_results.append(case_result)
            pipeline_results.append(pipeline_result)

    return _build_batch_result(
        case_results=tuple(case_results),
        pipeline_results=tuple(pipeline_results),
    )


def _evaluate_single_state_payload(
    payload: dict[str, object],
    *,
    fixture_name: str | None,
) -> tuple[Phase1CaseEvaluationResult, Phase1ValidationPipelineResult]:
    pipeline_result = validate_phase1_candidate_pipeline(
        payload,
        policy=ValidationPipelinePolicy(require_provenance=True),
    )

    metric_summary = compute_phase1_metrics((pipeline_result,))
    metric_values = {
        metric_name: metric.model_dump(mode="json")
        for metric_name, metric in metric_summary.metrics.items()
    }

    case_result = Phase1CaseEvaluationResult(
        case_id=_resolve_case_id(payload=payload, pipeline_result=pipeline_result),
        state_id=pipeline_result.candidate_state_id,
        fixture_name=fixture_name,
        schema_valid=_is_schema_valid(pipeline_result),
        has_blocking_issue=pipeline_result.has_blocking_issue,
        blocking_issue_codes=_collect_blocking_issue_codes(pipeline_result),
        warning_issue_codes=_collect_warning_issue_codes(pipeline_result),
        validator_execution_order=pipeline_result.validator_execution_order,
        metric_values=metric_values,
    )

    return case_result, pipeline_result


def _extract_state_payloads(payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    raw_states = payload.get("states")
    if not isinstance(raw_states, list):
        return (payload,)

    state_payloads = tuple(item for item in raw_states if isinstance(item, dict))
    if state_payloads:
        return state_payloads

    return (payload,)


def _build_batch_result(
    *,
    case_results: tuple[Phase1CaseEvaluationResult, ...],
    pipeline_results: tuple[Phase1ValidationPipelineResult, ...],
) -> Phase1BatchEvaluationResult:
    metric_summary = compute_phase1_metrics(pipeline_results)
    evaluated_count = len(case_results)
    valid_count = sum(1 for result in case_results if not result.has_blocking_issue)
    invalid_count = evaluated_count - valid_count

    return Phase1BatchEvaluationResult(
        results=case_results,
        metric_summary=metric_summary,
        evaluated_count=evaluated_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
    )


def _resolve_case_id(
    *,
    payload: dict[str, object],
    pipeline_result: Phase1ValidationPipelineResult,
) -> str | None:
    if pipeline_result.candidate_envelope is not None:
        return pipeline_result.candidate_envelope.case_id

    raw_case_id = payload.get("case_id")
    if isinstance(raw_case_id, str):
        cleaned_case_id = raw_case_id.strip()
        if cleaned_case_id:
            return cleaned_case_id

    return None


def _is_schema_valid(pipeline_result: Phase1ValidationPipelineResult) -> bool:
    for report in pipeline_result.reports:
        if report.validator_name == SCHEMA_VALIDATOR_NAME:
            return not report.has_blocking_issue
    return False


def _collect_blocking_issue_codes(
    pipeline_result: Phase1ValidationPipelineResult,
) -> tuple[str, ...]:
    issue_codes: list[str] = []

    for report in pipeline_result.reports:
        for issue in report.issues:
            if issue.blocking:
                issue_codes.append(issue.issue_code)

    return tuple(sorted(issue_codes))


def _collect_warning_issue_codes(
    pipeline_result: Phase1ValidationPipelineResult,
) -> tuple[str, ...]:
    issue_codes: list[str] = []

    for report in pipeline_result.reports:
        for issue in report.issues:
            if issue.severity == ValidationSeverity.WARNING:
                issue_codes.append(issue.issue_code)

    return tuple(sorted(issue_codes))


__all__ = [
    "Phase1BatchEvaluationResult",
    "Phase1CaseEvaluationInput",
    "Phase1CaseEvaluationResult",
    "evaluate_phase1_fixture_dir",
    "evaluate_phase1_payload",
    "evaluate_phase1_payloads",
    "load_phase1_fixture",
]

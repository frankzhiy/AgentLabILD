"""Phase 1 deterministic audit report builders."""

from __future__ import annotations

import json
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .phase1_runner import Phase1BatchEvaluationResult


class Phase1AuditReport(BaseModel):
    """JSON-serializable Phase 1 state externalization audit report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal["phase1_state_externalization"] = "phase1_state_externalization"
    evaluated_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    metric_summary: dict[str, object]
    blocking_issue_distribution: dict[str, int]
    warning_issue_distribution: dict[str, int]
    per_case_results: tuple[dict[str, object], ...]
    notes: tuple[str, ...] = ()


def build_phase1_audit_report(
    batch_result: Phase1BatchEvaluationResult,
) -> Phase1AuditReport:
    """Build one audit report from existing runner output only."""

    metric_summary = {
        metric_name: metric_value.model_dump(mode="json")
        for metric_name, metric_value in batch_result.metric_summary.metrics.items()
    }

    blocking_issue_distribution: Counter[str] = Counter()
    warning_issue_distribution: Counter[str] = Counter()

    per_case_results: list[dict[str, object]] = []
    for case_result in batch_result.results:
        blocking_issue_distribution.update(case_result.blocking_issue_codes)
        warning_issue_distribution.update(case_result.warning_issue_codes)

        per_case_results.append(
            {
                "fixture_name": case_result.fixture_name,
                "case_id": case_result.case_id,
                "state_id": case_result.state_id,
                "schema_valid": case_result.schema_valid,
                "has_blocking_issue": case_result.has_blocking_issue,
                "blocking_issue_codes": case_result.blocking_issue_codes,
                "warning_issue_codes": case_result.warning_issue_codes,
                "validator_execution_order": case_result.validator_execution_order,
                "metric_values": case_result.metric_values,
            }
        )

    notes: list[str] = []
    rerun_metric = metric_summary.get("rerun_stability_rate")
    if isinstance(rerun_metric, dict) and not bool(rerun_metric.get("applicable")):
        notes.append("rerun_stability_rate is not available for single-run evaluation")

    return Phase1AuditReport(
        evaluated_count=batch_result.evaluated_count,
        valid_count=batch_result.valid_count,
        invalid_count=batch_result.invalid_count,
        metric_summary=metric_summary,
        blocking_issue_distribution=dict(sorted(blocking_issue_distribution.items())),
        warning_issue_distribution=dict(sorted(warning_issue_distribution.items())),
        per_case_results=tuple(per_case_results),
        notes=tuple(notes),
    )


def phase1_report_to_dict(
    report: Phase1AuditReport,
) -> dict[str, object]:
    """Convert report model to plain JSON-serializable dict."""

    return report.model_dump(mode="json")


def phase1_report_to_json(
    report: Phase1AuditReport,
    *,
    indent: int = 2,
) -> str:
    """Serialize Phase 1 report to JSON text."""

    return json.dumps(phase1_report_to_dict(report), indent=indent)


def build_phase1_markdown_summary(
    report: Phase1AuditReport,
) -> str:
    """Build a concise markdown summary from an audit report."""

    lines = [
        "# Phase 1 Audit Summary",
        "",
        f"- phase: {report.phase}",
        f"- evaluated_count: {report.evaluated_count}",
        f"- valid_count: {report.valid_count}",
        f"- invalid_count: {report.invalid_count}",
        "",
        "## Metric Summary",
    ]

    required_metric_names = (
        "schema_validity_rate",
        "provenance_completeness_rate",
        "claim_evidence_traceability_rate",
        "unsupported_claim_rate",
        "stage_alignment_rate",
        "hypothesis_board_completeness_rate",
        "state_version_lineage_validity_rate",
    )

    for metric_name in required_metric_names:
        lines.append(
            _format_metric_line(
                metric_name=metric_name,
                metric_payload=report.metric_summary.get(metric_name),
            )
        )

    if "rerun_stability_rate" in report.metric_summary:
        lines.append(
            _format_metric_line(
                metric_name="rerun_stability_rate",
                metric_payload=report.metric_summary.get("rerun_stability_rate"),
            )
        )

    lines.append("")
    lines.append("## Blocking Issue Distribution")
    if report.blocking_issue_distribution:
        for issue_code, count in report.blocking_issue_distribution.items():
            lines.append(f"- {issue_code}: {count}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Warning Issue Distribution")
    if report.warning_issue_distribution:
        for issue_code, count in report.warning_issue_distribution.items():
            lines.append(f"- {issue_code}: {count}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Per-case Results")
    for case_result in report.per_case_results:
        fixture_name = case_result.get("fixture_name")
        state_id = case_result.get("state_id")
        schema_valid = case_result.get("schema_valid")
        has_blocking_issue = case_result.get("has_blocking_issue")
        lines.append(
            "- "
            f"fixture_name={fixture_name}, "
            f"state_id={state_id}, "
            f"schema_valid={schema_valid}, "
            f"has_blocking_issue={has_blocking_issue}"
        )

    return "\n".join(lines)


def _format_metric_line(
    *,
    metric_name: str,
    metric_payload: object,
) -> str:
    if not isinstance(metric_payload, dict):
        return f"- {metric_name}: not_available"

    if bool(metric_payload.get("applicable")):
        value = metric_payload.get("value")
        numerator = metric_payload.get("numerator")
        denominator = metric_payload.get("denominator")
        return (
            f"- {metric_name}: value={value}, "
            f"numerator={numerator}, denominator={denominator}"
        )

    reason = metric_payload.get("reason")
    return f"- {metric_name}: not_applicable ({reason})"


__all__ = [
    "Phase1AuditReport",
    "build_phase1_audit_report",
    "build_phase1_markdown_summary",
    "phase1_report_to_dict",
    "phase1_report_to_json",
]

"""Deterministic Phase 1 state-externalization metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas.state import Phase1StateEnvelope
from ..validators.pipeline import Phase1ValidationPipelineResult
from ..validators.unsupported_claims import UNSUPPORTED_CLAIM_VALIDATOR_NAME
from .phase1_metrics_support import (
    collect_blocking_issue_codes,
    find_report,
    has_schema_stage_alignment_issue,
    is_board_complete,
    is_schema_valid,
    is_stable_rerun_pair,
    is_stage_aligned,
    is_valid_lineage_sequence,
)

SCHEMA_VALIDITY_RATE = "schema_validity_rate"
PROVENANCE_COMPLETENESS_RATE = "provenance_completeness_rate"
CLAIM_EVIDENCE_TRACEABILITY_RATE = "claim_evidence_traceability_rate"
UNSUPPORTED_CLAIM_RATE = "unsupported_claim_rate"
STAGE_ALIGNMENT_RATE = "stage_alignment_rate"
HYPOTHESIS_BOARD_COMPLETENESS_RATE = "hypothesis_board_completeness_rate"
STATE_VERSION_LINEAGE_VALIDITY_RATE = "state_version_lineage_validity_rate"
RERUN_STABILITY_RATE = "rerun_stability_rate"


class Phase1MetricValue(BaseModel):
    """One deterministic metric value with explicit applicability semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: float | None
    numerator: int | None
    denominator: int | None
    applicable: bool
    reason: str | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "Phase1MetricValue":
        if self.applicable:
            if self.value is None:
                raise ValueError("applicable metric must include value")
            if self.numerator is None or self.denominator is None:
                raise ValueError(
                    "applicable metric must include numerator and denominator"
                )
            if self.denominator <= 0:
                raise ValueError("applicable metric denominator must be > 0")
            if not 0.0 <= self.value:
                raise ValueError("metric value must be >= 0")
        else:
            if any(
                item is not None
                for item in (self.value, self.numerator, self.denominator)
            ):
                raise ValueError(
                    "not_applicable metric must not carry value/numerator/denominator"
                )
            if self.reason is None:
                raise ValueError("not_applicable metric must include reason")

        return self


class Phase1MetricSummary(BaseModel):
    """Aggregate deterministic metric summary for one evaluation batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metrics: dict[str, Phase1MetricValue] = Field(default_factory=dict)
    evaluated_count: int = Field(ge=0)


def compute_phase1_metrics(
    results: Sequence[Phase1ValidationPipelineResult],
) -> Phase1MetricSummary:
    """Compute deterministic Phase 1 metrics from existing pipeline results."""

    result_items = tuple(results)
    parsed_envelopes = tuple(
        result.candidate_envelope
        for result in result_items
        if result.candidate_envelope is not None
    )

    metrics = {
        SCHEMA_VALIDITY_RATE: _compute_schema_validity_rate(result_items),
        PROVENANCE_COMPLETENESS_RATE: _compute_provenance_completeness_rate(
            parsed_envelopes
        ),
        CLAIM_EVIDENCE_TRACEABILITY_RATE: _compute_claim_traceability_rate(
            parsed_envelopes
        ),
        UNSUPPORTED_CLAIM_RATE: _compute_unsupported_claim_rate(result_items),
        STAGE_ALIGNMENT_RATE: _compute_stage_alignment_rate(result_items),
        HYPOTHESIS_BOARD_COMPLETENESS_RATE: _compute_board_completeness_rate(
            parsed_envelopes
        ),
        STATE_VERSION_LINEAGE_VALIDITY_RATE: compute_lineage_metric(parsed_envelopes),
        RERUN_STABILITY_RATE: _build_not_applicable_metric(
            name=RERUN_STABILITY_RATE,
            reason="rerun comparison was not provided",
        ),
    }

    return Phase1MetricSummary(metrics=metrics, evaluated_count=len(result_items))


def compute_lineage_metric(
    envelopes: Sequence[Phase1StateEnvelope],
) -> Phase1MetricValue:
    """Check per-case state lineage validity for parsed envelope sequences."""

    envelope_items = tuple(envelopes)
    if not envelope_items:
        return _build_not_applicable_metric(
            name=STATE_VERSION_LINEAGE_VALIDITY_RATE,
            reason="no parsed envelopes available",
        )

    envelopes_by_case: dict[str, list[Phase1StateEnvelope]] = defaultdict(list)
    for envelope in envelope_items:
        envelopes_by_case[envelope.case_id].append(envelope)

    candidate_sequences = [
        tuple(case_envelopes)
        for case_envelopes in envelopes_by_case.values()
        if len(case_envelopes) >= 2
    ]

    if not candidate_sequences:
        return _build_not_applicable_metric(
            name=STATE_VERSION_LINEAGE_VALIDITY_RATE,
            reason="no case has at least two parsed states for lineage evaluation",
        )

    numerator = sum(
        1
        for case_sequence in candidate_sequences
        if is_valid_lineage_sequence(case_sequence)
    )
    denominator = len(candidate_sequences)

    return _build_rate_metric(
        name=STATE_VERSION_LINEAGE_VALIDITY_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def compute_rerun_stability_metric(
    first: Sequence[Phase1ValidationPipelineResult],
    second: Sequence[Phase1ValidationPipelineResult],
) -> Phase1MetricValue:
    """Measure deterministic pipeline stability across two reruns."""

    first_items = tuple(first)
    second_items = tuple(second)

    if not first_items or not second_items:
        return _build_not_applicable_metric(
            name=RERUN_STABILITY_RATE,
            reason="both rerun result sequences are required",
        )

    denominator = max(len(first_items), len(second_items))
    pair_count = min(len(first_items), len(second_items))

    numerator = 0
    for index in range(pair_count):
        if is_stable_rerun_pair(first_items[index], second_items[index]):
            numerator += 1

    return _build_rate_metric(
        name=RERUN_STABILITY_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_schema_validity_rate(
    results: Sequence[Phase1ValidationPipelineResult],
) -> Phase1MetricValue:
    if not results:
        return _build_not_applicable_metric(
            name=SCHEMA_VALIDITY_RATE,
            reason="no candidates were evaluated",
        )

    numerator = sum(1 for result in results if is_schema_valid(result))
    denominator = len(results)

    return _build_rate_metric(
        name=SCHEMA_VALIDITY_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_provenance_completeness_rate(
    envelopes: Sequence[Phase1StateEnvelope],
) -> Phase1MetricValue:
    if not envelopes:
        return _build_not_applicable_metric(
            name=PROVENANCE_COMPLETENESS_RATE,
            reason="schema validation failed for all candidates",
        )

    numerator = 0
    denominator = 0

    for envelope in envelopes:
        denominator += len(envelope.evidence_atoms)
        denominator += len(envelope.claim_references)

        numerator += sum(
            1 for evidence_atom in envelope.evidence_atoms if evidence_atom.provenance is not None
        )
        numerator += sum(
            1
            for claim_reference in envelope.claim_references
            if claim_reference.provenance is not None
        )

    if denominator == 0:
        return _build_not_applicable_metric(
            name=PROVENANCE_COMPLETENESS_RATE,
            reason="parsed envelopes contain no evidence atoms or claim references",
        )

    return _build_rate_metric(
        name=PROVENANCE_COMPLETENESS_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_claim_traceability_rate(
    envelopes: Sequence[Phase1StateEnvelope],
) -> Phase1MetricValue:
    if not envelopes:
        return _build_not_applicable_metric(
            name=CLAIM_EVIDENCE_TRACEABILITY_RATE,
            reason="schema validation failed for all candidates",
        )

    numerator = 0
    denominator = 0

    for envelope in envelopes:
        evidence_ids = {atom.evidence_id for atom in envelope.evidence_atoms}
        for claim_reference in envelope.claim_references:
            if not claim_reference.evidence_ids:
                continue

            denominator += 1
            if all(
                evidence_id in evidence_ids
                for evidence_id in claim_reference.evidence_ids
            ):
                numerator += 1

    if denominator == 0:
        return _build_not_applicable_metric(
            name=CLAIM_EVIDENCE_TRACEABILITY_RATE,
            reason="no claim references with evidence_ids were available",
        )

    return _build_rate_metric(
        name=CLAIM_EVIDENCE_TRACEABILITY_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_unsupported_claim_rate(
    results: Sequence[Phase1ValidationPipelineResult],
) -> Phase1MetricValue:
    numerator = 0
    denominator = 0

    for result in results:
        if result.candidate_envelope is None:
            continue

        denominator += len(result.candidate_envelope.claim_references)

        unsupported_report = find_report(
            result,
            validator_name=UNSUPPORTED_CLAIM_VALIDATOR_NAME,
        )
        if unsupported_report is None:
            continue

        numerator += sum(
            1
            for issue in unsupported_report.issues
            if issue.issue_code.startswith("unsupported_claim.")
        )

    if denominator == 0:
        return _build_not_applicable_metric(
            name=UNSUPPORTED_CLAIM_RATE,
            reason="schema validation failed or no claim references were available",
        )

    return _build_rate_metric(
        name=UNSUPPORTED_CLAIM_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_stage_alignment_rate(
    results: Sequence[Phase1ValidationPipelineResult],
) -> Phase1MetricValue:
    numerator = 0
    denominator = 0

    for result in results:
        if result.candidate_envelope is not None:
            denominator += 1
            if is_stage_aligned(result.candidate_envelope):
                numerator += 1
            continue

        if has_schema_stage_alignment_issue(result):
            denominator += 1

    if denominator == 0:
        return _build_not_applicable_metric(
            name=STAGE_ALIGNMENT_RATE,
            reason=(
                "stage alignment could not be evaluated because parsed envelopes "
                "were unavailable and no stage-alignment schema issues were reported"
            ),
        )

    return _build_rate_metric(
        name=STAGE_ALIGNMENT_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _compute_board_completeness_rate(
    envelopes: Sequence[Phase1StateEnvelope],
) -> Phase1MetricValue:
    if not envelopes:
        return _build_not_applicable_metric(
            name=HYPOTHESIS_BOARD_COMPLETENESS_RATE,
            reason="schema validation failed for all candidates",
        )

    numerator = sum(1 for envelope in envelopes if is_board_complete(envelope))
    denominator = len(envelopes)

    return _build_rate_metric(
        name=HYPOTHESIS_BOARD_COMPLETENESS_RATE,
        numerator=numerator,
        denominator=denominator,
    )


def _build_rate_metric(
    *,
    name: str,
    numerator: int,
    denominator: int,
) -> Phase1MetricValue:
    return Phase1MetricValue(
        name=name,
        value=numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        applicable=True,
        reason=None,
    )


def _build_not_applicable_metric(*, name: str, reason: str) -> Phase1MetricValue:
    return Phase1MetricValue(
        name=name,
        value=None,
        numerator=None,
        denominator=None,
        applicable=False,
        reason=reason,
    )


__all__ = [
    "CLAIM_EVIDENCE_TRACEABILITY_RATE",
    "HYPOTHESIS_BOARD_COMPLETENESS_RATE",
    "PROVENANCE_COMPLETENESS_RATE",
    "Phase1MetricSummary",
    "Phase1MetricValue",
    "RERUN_STABILITY_RATE",
    "SCHEMA_VALIDITY_RATE",
    "STAGE_ALIGNMENT_RATE",
    "STATE_VERSION_LINEAGE_VALIDITY_RATE",
    "UNSUPPORTED_CLAIM_RATE",
    "compute_lineage_metric",
    "compute_phase1_metrics",
    "compute_rerun_stability_metric",
]

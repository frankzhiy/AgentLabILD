"""Deterministic fixtures for Phase 1 benchmark hook inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.evidence import EvidenceAtom
from src.schemas.intake import SourceDocument
from src.storage.state_store import InMemoryStateStore
from src.validators.pipeline import (
    FULL_VALIDATOR_EXECUTION_ORDER,
    SCHEMA_ONLY_EXECUTION_ORDER,
    Phase1ValidationPipelineResult,
    ValidationPipelinePolicy,
    validate_phase1_candidate_pipeline,
)
from src.validators.provenance_validator import (
    SOURCE_ALIGNMENT_VALIDATOR_NAME,
    validate_evidence_atoms_against_sources,
)
from src.validators.schema_validator import SCHEMA_VALIDATOR_NAME
from src.validators.temporal_validator import TEMPORAL_VALIDATOR_NAME
from src.validators.unsupported_claims import UNSUPPORTED_CLAIM_VALIDATOR_NAME

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase1"

# Fixture expectation matrix (all Phase 1-6 Issue 1 fixtures):
# - valid_minimal_case.json: should pass full pipeline.
# - valid_multihypothesis_case.json: should pass full pipeline with multi-entity closure.
# - valid_two_stage_version_chain.json: both states should pass full pipeline and store lineage.
# - invalid_missing_evidence_ref.json: should fail schema closure (missing evidence reference).
# - invalid_unsupported_claim.json: should fail unsupported-claim validator
#   (invalid target binding on detached claim).
# - invalid_stage_mismatch.json: should fail schema stage alignment.
# - invalid_temporal_order.json: should fail temporal validator (stage_after_envelope).
# - invalid_source_alignment.json: should fail source alignment validator
#   (raw_excerpt_not_found).


def _load_json_fixture(file_name: str) -> dict[str, object]:
    fixture_path = FIXTURE_DIR / file_name
    with fixture_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _get_report_by_validator_name(
    result: Phase1ValidationPipelineResult,
    validator_name: str,
):
    matched_reports = [
        report for report in result.reports if report.validator_name == validator_name
    ]
    assert len(matched_reports) == 1
    return matched_reports[0]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "valid_minimal_case.json",
        "valid_multihypothesis_case.json",
    ],
)
def test_valid_fixtures_pass_full_phase1_pipeline(fixture_name: str) -> None:
    payload = _load_json_fixture(fixture_name)

    result = validate_phase1_candidate_pipeline(
        payload,
        policy=ValidationPipelinePolicy(require_provenance=True),
    )

    assert result.candidate_envelope is not None
    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert result.has_blocking_issue is False
    assert all(report.is_valid for report in result.reports)


def test_valid_two_stage_version_chain_is_pipeline_valid_and_persistable() -> None:
    payload = _load_json_fixture("valid_two_stage_version_chain.json")
    states = payload.get("states")

    assert isinstance(states, list)
    assert len(states) == 2

    store = InMemoryStateStore()
    for state_payload in states:
        assert isinstance(state_payload, dict)

        result = validate_phase1_candidate_pipeline(
            state_payload,
            policy=ValidationPipelinePolicy(require_provenance=True),
        )

        assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
        assert result.has_blocking_issue is False
        assert result.candidate_envelope is not None

        store.persist_snapshot(result.candidate_envelope)

    versions = store.list_state_versions("case-chain")
    latest = store.get_latest_state("case-chain")

    assert len(versions) == 2
    assert versions[0].state_id == "state-401"
    assert versions[1].state_id == "state-402"
    assert versions[1].parent_state_id == "state-401"
    assert latest is not None
    assert latest.state_id == "state-402"


# Failure mode: claim references an evidence id not present in envelope,
# so schema closure should fail before downstream validators run.
def test_invalid_missing_evidence_ref_fails_schema_for_missing_reference() -> None:
    payload = _load_json_fixture("invalid_missing_evidence_ref.json")

    result = validate_phase1_candidate_pipeline(payload)
    schema_report = _get_report_by_validator_name(result, SCHEMA_VALIDATOR_NAME)

    assert result.validator_execution_order == SCHEMA_ONLY_EXECUTION_ORDER
    assert result.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in schema_report.issues)
    assert any(
        "missing evidence references" in issue.message for issue in schema_report.issues
    )


# Failure mode: detached claim binds to a non-existent hypothesis target,
# while schema remains valid, so unsupported_claim validator must block it.
def test_invalid_unsupported_claim_fails_unsupported_claim_validator() -> None:
    payload = _load_json_fixture("invalid_unsupported_claim.json")

    result = validate_phase1_candidate_pipeline(
        payload,
        policy=ValidationPipelinePolicy(require_provenance=True),
    )
    schema_report = _get_report_by_validator_name(result, SCHEMA_VALIDATOR_NAME)
    unsupported_report = _get_report_by_validator_name(
        result,
        UNSUPPORTED_CLAIM_VALIDATOR_NAME,
    )

    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert schema_report.is_valid is True
    assert any(
        issue.issue_code == "unsupported_claim.invalid_target_binding"
        and issue.target_id == "claim_ref-099"
        for issue in unsupported_report.issues
    )
    assert result.has_blocking_issue is True


# Failure mode: hypothesis.stage_id does not match stage_context.stage_id,
# which must be blocked by envelope schema consistency checks.
def test_invalid_stage_mismatch_fails_schema_for_stage_alignment() -> None:
    payload = _load_json_fixture("invalid_stage_mismatch.json")

    result = validate_phase1_candidate_pipeline(payload)
    schema_report = _get_report_by_validator_name(result, SCHEMA_VALIDATOR_NAME)

    assert result.validator_execution_order == SCHEMA_ONLY_EXECUTION_ORDER
    assert result.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in schema_report.issues)
    assert any(
        "stage_id alignment failed" in issue.message for issue in schema_report.issues
    )


# Failure mode: stage_context.created_at is later than envelope.created_at,
# so temporal validator should emit temporal.stage_after_envelope.
def test_invalid_temporal_order_fails_temporal_validator() -> None:
    payload = _load_json_fixture("invalid_temporal_order.json")

    result = validate_phase1_candidate_pipeline(
        payload,
        policy=ValidationPipelinePolicy(require_provenance=True),
    )
    schema_report = _get_report_by_validator_name(result, SCHEMA_VALIDATOR_NAME)
    temporal_report = _get_report_by_validator_name(result, TEMPORAL_VALIDATOR_NAME)

    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert schema_report.is_valid is True
    assert temporal_report.has_blocking_issue is True
    assert any(
        issue.issue_code == "temporal.stage_after_envelope"
        for issue in temporal_report.issues
    )
    assert result.has_blocking_issue is True


# Failure mode: evidence.raw_excerpt does not occur in source_document.raw_text,
# so source alignment bridge must report provenance.raw_excerpt_not_found.
def test_invalid_source_alignment_fixture_fails_source_alignment_validator() -> None:
    payload = _load_json_fixture("invalid_source_alignment.json")

    evidence_payload = payload.get("evidence_atoms")
    source_document_payload = payload.get("source_documents")

    assert isinstance(evidence_payload, list)
    assert isinstance(source_document_payload, list)

    evidence_atoms = tuple(
        EvidenceAtom.model_validate(item) for item in evidence_payload
    )
    source_documents = tuple(
        SourceDocument.model_validate(item) for item in source_document_payload
    )

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=evidence_atoms,
        source_documents=source_documents,
    )

    assert report.validator_name == SOURCE_ALIGNMENT_VALIDATOR_NAME
    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.raw_excerpt_not_found" and issue.blocking
        for issue in report.issues
    )

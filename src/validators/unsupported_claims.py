"""Phase 1-3 conservative unsupported-claim validator.

This module only performs structural, state-internal checks on ClaimReference
objects in a fully constructed Phase1StateEnvelope.

Design boundary:
1. This validator is a claim-level review lens over already structured state.
2. It does not replace Phase1StateEnvelope hard closure validation.
3. Some issue codes may partially overlap closure checks, but they are kept
    under unsupported_claim.* for claim-namespace auditability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from ..schemas.claim import ClaimReference, ClaimStrength, ClaimTargetKind
from ..schemas.evidence import EvidenceAtom, EvidenceCertainty, EvidencePolarity
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from ..utils.time import utc_now

UNSUPPORTED_CLAIM_VALIDATOR_NAME = "phase1_unsupported_claim_validator"
UNSUPPORTED_CLAIM_VALIDATOR_VERSION = "1.3.0"

EVIDENCE_USABILITY_POLICY_STRICT_CURRENT_STAGE_ONLY = "strict_current_stage_only"
EVIDENCE_USABILITY_POLICY_ALLOW_HISTORICAL_AUTHORITATIVE_EVIDENCE = (
    "allow_historical_authoritative_evidence"
)

EvidenceUsabilityPolicy = Literal[
    "strict_current_stage_only",
    "allow_historical_authoritative_evidence",
]

_DEFAULT_EVIDENCE_USABILITY_POLICY: EvidenceUsabilityPolicy = (
    EVIDENCE_USABILITY_POLICY_STRICT_CURRENT_STAGE_ONLY
)


def validate_phase1_unsupported_claims(
    envelope: Phase1StateEnvelope,
    *,
    report_id: str | None = None,
    generated_at: datetime | None = None,
    validator_name: str = UNSUPPORTED_CLAIM_VALIDATOR_NAME,
    validator_version: str = UNSUPPORTED_CLAIM_VALIDATOR_VERSION,
) -> StateValidationReport:
    """Validate unsupported-claim risks from current authoritative envelope state.

    Notes:
    1. This is a conservative claim-level lens, not an envelope closure checker.
    2. `unsupported_claim.invalid_target_binding` and
       `unsupported_claim.missing_evidence_reference` can overlap with envelope
       hard validation by design, but are retained for claim-namespace review.
    """

    issues = _collect_unsupported_claim_issues(
        envelope,
        evidence_usability_policy=_DEFAULT_EVIDENCE_USABILITY_POLICY,
    )
    has_blocking_issue = any(issue.blocking for issue in issues)

    if generated_at is None:
        generated_at = utc_now()

    if report_id is None:
        report_id = f"report-unsupported-claim-{envelope.state_id}"

    if issues:
        blocking_issue_count = sum(1 for issue in issues if issue.blocking)
        non_blocking_issue_count = len(issues) - blocking_issue_count
        summary = (
            "Unsupported-claim validation completed: "
            f"total={len(issues)}, blocking={blocking_issue_count}, "
            f"non_blocking={non_blocking_issue_count}."
        )
    else:
        summary = "Unsupported-claim validation passed."

    return StateValidationReport(
        report_id=report_id,
        case_id=envelope.case_id,
        stage_id=envelope.stage_context.stage_id,
        board_id=envelope.board_init.board_id,
        generated_at=generated_at,
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=issues,
        validator_name=validator_name,
        validator_version=validator_version,
        summary=summary,
    )


def _collect_unsupported_claim_issues(
    envelope: Phase1StateEnvelope,
    *,
    evidence_usability_policy: EvidenceUsabilityPolicy,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []

    evidence_by_id: dict[str, EvidenceAtom] = {
        evidence.evidence_id: evidence for evidence in envelope.evidence_atoms
    }
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in envelope.hypotheses}
    action_ids = {
        action.action_candidate_id for action in envelope.action_candidates
    }
    stage_id = envelope.stage_context.stage_id
    visible_source_doc_ids = set(envelope.stage_context.source_doc_ids)

    for claim_index, claim_ref in enumerate(envelope.claim_references):
        field_prefix = f"claim_references[{claim_index}]"

        if not _is_valid_target_binding(
            claim_ref,
            hypothesis_ids=hypothesis_ids,
            action_ids=action_ids,
        ):
            _append_issue(
                issues,
                issue_code="unsupported_claim.invalid_target_binding",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Claim target binding does not resolve in envelope: "
                    f"target_kind={_target_kind_text(claim_ref.target_kind)}, "
                    f"target_id={claim_ref.target_id}."
                ),
                target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                target_id=claim_ref.claim_ref_id,
                field_path=f"{field_prefix}.target_id",
                related_ids=(claim_ref.target_id,),
                blocking=True,
            )

        existing_evidence_ids, missing_evidence_ids = _partition_referenced_evidence_ids(
            claim_ref,
            evidence_by_id=evidence_by_id,
        )

        if missing_evidence_ids:
            _append_issue(
                issues,
                issue_code="unsupported_claim.missing_evidence_reference",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Claim references evidence ids that are not present in envelope: "
                    + ", ".join(missing_evidence_ids)
                    + "."
                ),
                target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                target_id=claim_ref.claim_ref_id,
                field_path=f"{field_prefix}.evidence_ids",
                related_ids=missing_evidence_ids,
                blocking=True,
            )

        usable_evidence_ids = tuple(
            evidence_id
            for evidence_id in existing_evidence_ids
            if _is_evidence_usable_in_current_state(
                evidence_by_id[evidence_id],
                stage_id=stage_id,
                visible_source_doc_ids=visible_source_doc_ids,
                policy=evidence_usability_policy,
            )
        )

        if existing_evidence_ids and not usable_evidence_ids:
            _append_issue(
                issues,
                issue_code="unsupported_claim.unusable_evidence_reference",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Claim references existing evidence ids, but none are usable "
                    "from the current authoritative state view: "
                    + ", ".join(existing_evidence_ids)
                    + "."
                ),
                target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                target_id=claim_ref.claim_ref_id,
                field_path=f"{field_prefix}.evidence_ids",
                related_ids=existing_evidence_ids,
                blocking=True,
            )

        if _has_overstated_strength(
            claim_ref,
            usable_evidence_ids=usable_evidence_ids,
            evidence_by_id=evidence_by_id,
        ):
            _append_issue(
                issues,
                issue_code="unsupported_claim.overstated_strength",
                severity=ValidationSeverity.WARNING,
                message=(
                    "Strong claim is backed only by weak/uncertain/reported "
                    "evidence in current state."
                ),
                target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                target_id=claim_ref.claim_ref_id,
                field_path=f"{field_prefix}.strength",
                related_ids=usable_evidence_ids,
                blocking=False,
            )

    return tuple(issues)


def _partition_referenced_evidence_ids(
    claim_ref: ClaimReference,
    *,
    evidence_by_id: dict[str, EvidenceAtom],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    existing_evidence_ids: list[str] = []
    missing_evidence_ids: list[str] = []

    for evidence_id in claim_ref.evidence_ids:
        if evidence_id in evidence_by_id:
            existing_evidence_ids.append(evidence_id)
            continue
        missing_evidence_ids.append(evidence_id)

    return (
        _to_unique_ordered_ids(existing_evidence_ids),
        _to_unique_ordered_ids(missing_evidence_ids),
    )


def _is_valid_target_binding(
    claim_ref: ClaimReference,
    *,
    hypothesis_ids: set[str],
    action_ids: set[str],
) -> bool:
    if claim_ref.target_kind == ClaimTargetKind.HYPOTHESIS:
        return claim_ref.target_id in hypothesis_ids

    if claim_ref.target_kind == ClaimTargetKind.ACTION:
        return claim_ref.target_id in action_ids

    return False


def _is_evidence_usable_in_current_state(
    evidence: EvidenceAtom,
    *,
    stage_id: str,
    visible_source_doc_ids: set[str],
    policy: EvidenceUsabilityPolicy,
) -> bool:
    if policy == EVIDENCE_USABILITY_POLICY_STRICT_CURRENT_STAGE_ONLY:
        return _is_evidence_usable_strict_current_stage(
            evidence,
            stage_id=stage_id,
            visible_source_doc_ids=visible_source_doc_ids,
        )

    if policy == EVIDENCE_USABILITY_POLICY_ALLOW_HISTORICAL_AUTHORITATIVE_EVIDENCE:
        return _is_evidence_usable_allow_historical_authoritative(
            evidence,
            stage_id=stage_id,
            visible_source_doc_ids=visible_source_doc_ids,
        )

    return False


def _is_evidence_usable_strict_current_stage(
    evidence: EvidenceAtom,
    *,
    stage_id: str,
    visible_source_doc_ids: set[str],
) -> bool:
    if evidence.stage_id != stage_id:
        return False

    if visible_source_doc_ids and evidence.source_doc_id not in visible_source_doc_ids:
        return False

    provenance = evidence.provenance
    if provenance is None:
        return True

    if provenance.stage_id != stage_id:
        return False

    if provenance.evidence_id != evidence.evidence_id:
        return False

    if not provenance.source_anchors:
        return False

    if not visible_source_doc_ids:
        return True

    anchor_doc_ids = {anchor.source_doc_id for anchor in provenance.source_anchors}
    if not (anchor_doc_ids & visible_source_doc_ids):
        return False

    input_doc_ids = set(provenance.extraction_activity.input_source_doc_ids)
    if not (input_doc_ids & visible_source_doc_ids):
        return False

    return True


def _is_evidence_usable_allow_historical_authoritative(
    evidence: EvidenceAtom,
    *,
    stage_id: str,
    visible_source_doc_ids: set[str],
) -> bool:
    # Keep current-stage behavior strict; only historical evidence gets a
    # dedicated authority-path that can be expanded in later phases.
    if evidence.stage_id == stage_id:
        return _is_evidence_usable_strict_current_stage(
            evidence,
            stage_id=stage_id,
            visible_source_doc_ids=visible_source_doc_ids,
        )

    # Fast path: when historical evidence source is still visible in this stage,
    # it is directly usable without requiring stricter historical checks.
    if visible_source_doc_ids and evidence.source_doc_id in visible_source_doc_ids:
        return True

    provenance = evidence.provenance
    if provenance is None:
        return False

    if provenance.evidence_id != evidence.evidence_id:
        return False

    if provenance.stage_id != evidence.stage_id:
        return False

    if not provenance.source_anchors:
        return False

    if any(anchor.stage_id != provenance.stage_id for anchor in provenance.source_anchors):
        return False

    anchor_doc_ids = {anchor.source_doc_id for anchor in provenance.source_anchors}
    input_doc_ids = set(provenance.extraction_activity.input_source_doc_ids)
    if not anchor_doc_ids.issubset(input_doc_ids):
        return False

    return True


def _has_overstated_strength(
    claim_ref: ClaimReference,
    *,
    usable_evidence_ids: tuple[str, ...],
    evidence_by_id: dict[str, EvidenceAtom],
) -> bool:
    if claim_ref.strength != ClaimStrength.STRONG:
        return False

    if not usable_evidence_ids:
        return False

    return all(
        _is_weak_or_uncertain_evidence(evidence_by_id[evidence_id])
        for evidence_id in usable_evidence_ids
    )


def _is_weak_or_uncertain_evidence(evidence: EvidenceAtom) -> bool:
    if evidence.polarity == EvidencePolarity.INDETERMINATE:
        return True

    return evidence.certainty != EvidenceCertainty.CONFIRMED


def _append_issue(
    issues: list[ValidationIssue],
    *,
    issue_code: str,
    severity: ValidationSeverity,
    message: str,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str | None,
    related_ids: tuple[str, ...],
    blocking: bool,
) -> None:
    issues.append(
        ValidationIssue(
            issue_id=f"issue-unsupported-claim-{len(issues) + 1:04d}",
            issue_code=issue_code,
            severity=severity,
            message=message,
            target_kind=target_kind,
            target_id=target_id,
            field_path=field_path,
            related_ids=_to_unique_ordered_ids(related_ids),
            blocking=blocking,
        )
    )


def _to_unique_ordered_ids(ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique_ids: list[str] = []

    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        unique_ids.append(item)

    return tuple(unique_ids)


def _target_kind_text(target_kind: ClaimTargetKind | str) -> str:
    if isinstance(target_kind, ClaimTargetKind):
        return target_kind.value
    return str(target_kind)


__all__ = [
    "UNSUPPORTED_CLAIM_VALIDATOR_NAME",
    "UNSUPPORTED_CLAIM_VALIDATOR_VERSION",
    "validate_phase1_unsupported_claims",
]

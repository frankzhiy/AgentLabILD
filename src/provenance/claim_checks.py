"""Claim-side provenance checks for Phase 1-2 envelope validation."""

from __future__ import annotations

from ..schemas.claim import ClaimReference
from ..schemas.validation import ValidationSeverity, ValidationTargetKind
from .issues import ProvenanceCheckIssue, _make_issue, _missing_provenance_issue


def run_claim_provenance_checks(
    *,
    claim_references: tuple[ClaimReference, ...],
    stage_id: str,
    visible_source_doc_ids: set[str],
    evidence_ids: set[str],
    evidence_provenance_id_to_evidence_id: dict[str, str],
    require_provenance: bool,
) -> tuple[tuple[ProvenanceCheckIssue, ...], set[str]]:
    """Run provenance checks that only target claim references and claim provenance."""

    issues: list[ProvenanceCheckIssue] = []
    claim_provenance_id_to_claim_id: dict[str, str] = {}
    referenced_evidence_provenance_ids: set[str] = set()

    for claim_ref in claim_references:
        if claim_ref.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="claim stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="stage_id",
                    related_ids=(claim_ref.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align claim stage_id with stage_context.stage_id",
                )
            )

        provenance = claim_ref.provenance
        if provenance is None:
            issues.append(
                _missing_provenance_issue(
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance",
                    require_provenance=require_provenance,
                )
            )
            continue

        duplicated_owner = claim_provenance_id_to_claim_id.get(
            provenance.claim_provenance_id
        )
        if duplicated_owner is not None and duplicated_owner != claim_ref.claim_ref_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.duplicate_claim_provenance_id",
                    severity=ValidationSeverity.ERROR,
                    message="claim_provenance_id is reused by multiple claim references",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.claim_provenance_id",
                    related_ids=(
                        provenance.claim_provenance_id,
                        duplicated_owner,
                        claim_ref.claim_ref_id,
                    ),
                    blocking=True,
                    suggested_fix="use globally unique claim_provenance_id values",
                )
            )
        else:
            claim_provenance_id_to_claim_id[provenance.claim_provenance_id] = (
                claim_ref.claim_ref_id
            )

        if provenance.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="claim provenance stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.stage_id",
                    related_ids=(provenance.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align claim provenance stage_id with stage_context.stage_id",
                )
            )

        if provenance.claim_ref_id != claim_ref.claim_ref_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.orphan_provenance_binding",
                    severity=ValidationSeverity.ERROR,
                    message="claim provenance does not bind to owning claim_ref_id",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.claim_ref_id",
                    related_ids=(provenance.claim_ref_id, claim_ref.claim_ref_id),
                    blocking=True,
                    suggested_fix="set claim provenance claim_ref_id equal to owner claim_ref_id",
                )
            )

        if provenance.derivation_activity.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="derivation_activity.stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.derivation_activity.stage_id",
                    related_ids=(provenance.derivation_activity.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align derivation_activity.stage_id with stage_context.stage_id",
                )
            )

        non_visible_activity_docs = tuple(
            sorted(
                set(provenance.derivation_activity.input_source_doc_ids)
                - visible_source_doc_ids
            )
        )
        if non_visible_activity_docs:
            issues.append(
                _make_issue(
                    issue_code="provenance.source_doc_not_visible",
                    severity=ValidationSeverity.ERROR,
                    message="derivation activity references source_doc_id not visible in stage_context",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.derivation_activity.input_source_doc_ids",
                    related_ids=non_visible_activity_docs,
                    blocking=True,
                    suggested_fix="restrict derivation activity docs to stage_context.source_doc_ids",
                )
            )

        claim_evidence_ids = set(claim_ref.evidence_ids)
        claim_provenance_evidence_ids = set(provenance.evidence_ids)
        missing_in_provenance = tuple(
            sorted(claim_evidence_ids - claim_provenance_evidence_ids)
        )
        unexpected_in_provenance = tuple(
            sorted(claim_provenance_evidence_ids - claim_evidence_ids)
        )
        if missing_in_provenance or unexpected_in_provenance:
            related_ids = (
                *missing_in_provenance,
                *unexpected_in_provenance,
            )
            issues.append(
                _make_issue(
                    issue_code="provenance.claim_evidence_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "claim provenance evidence_ids must exactly align with "
                        "ClaimReference.evidence_ids"
                    ),
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.evidence_ids",
                    related_ids=related_ids,
                    blocking=True,
                    suggested_fix="synchronize provenance.evidence_ids and claim evidence_ids",
                )
            )

        orphan_evidence_ids = tuple(
            sorted(claim_provenance_evidence_ids - evidence_ids)
        )
        if orphan_evidence_ids:
            issues.append(
                _make_issue(
                    issue_code="provenance.orphan_evidence_reference",
                    severity=ValidationSeverity.ERROR,
                    message="claim provenance references evidence_id missing in envelope",
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.evidence_ids",
                    related_ids=orphan_evidence_ids,
                    blocking=True,
                    suggested_fix="remove orphan evidence ids or add corresponding EvidenceAtom",
                )
            )

        evidence_provenance_ids = set(provenance.evidence_provenance_ids)
        referenced_evidence_provenance_ids |= evidence_provenance_ids
        orphan_evidence_provenance_ids = tuple(
            sorted(evidence_provenance_ids - set(evidence_provenance_id_to_evidence_id))
        )
        if orphan_evidence_provenance_ids:
            issues.append(
                _make_issue(
                    issue_code="provenance.orphan_evidence_provenance_reference",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "claim provenance references evidence_provenance_id "
                        "that is not attached to any evidence atom"
                    ),
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.evidence_provenance_ids",
                    related_ids=orphan_evidence_provenance_ids,
                    blocking=True,
                    suggested_fix="remove orphan evidence_provenance_ids or attach matching evidence provenance",
                )
            )

        inconsistent_evidence_provenance_bindings: list[str] = []
        for evidence_provenance_id in evidence_provenance_ids:
            evidence_id = evidence_provenance_id_to_evidence_id.get(evidence_provenance_id)
            if evidence_id is None:
                continue
            if evidence_id not in claim_provenance_evidence_ids:
                inconsistent_evidence_provenance_bindings.append(
                    f"{evidence_provenance_id}:{evidence_id}"
                )

        if inconsistent_evidence_provenance_bindings:
            issues.append(
                _make_issue(
                    issue_code="provenance.evidence_provenance_binding_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "claim provenance evidence_provenance_ids do not align with "
                        "claim provenance evidence_ids"
                    ),
                    target_kind=ValidationTargetKind.CLAIM_REFERENCE,
                    target_id=claim_ref.claim_ref_id,
                    field_path="provenance.evidence_provenance_ids",
                    related_ids=tuple(sorted(inconsistent_evidence_provenance_bindings)),
                    blocking=True,
                    suggested_fix="ensure each evidence_provenance_id points to an evidence_id in provenance.evidence_ids",
                )
            )

    return tuple(issues), referenced_evidence_provenance_ids


__all__ = ["run_claim_provenance_checks"]

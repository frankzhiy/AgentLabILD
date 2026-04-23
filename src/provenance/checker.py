"""Phase 1-2 provenance consistency checker.

本模块提供纯检查逻辑：
1. 不做持久化写入，不实现 writer gate。
2. 只返回结构化 issue，供 validator 层转换为 StateValidationReport。
3. 在保持向后兼容前提下，支持可配置的 missing provenance 严格度。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import ValidationSeverity, ValidationTargetKind


@dataclass(frozen=True, slots=True)
class ProvenanceCheckIssue:
    """Structured provenance issue that is directly convertible to ValidationIssue."""

    issue_code: str
    severity: ValidationSeverity
    message: str
    target_kind: ValidationTargetKind
    target_id: str
    field_path: str | None = None
    related_ids: tuple[str, ...] = ()
    blocking: bool = True
    suggested_fix: str | None = None
    non_authoritative_note: str | None = None


def _make_issue(
    *,
    issue_code: str,
    severity: ValidationSeverity,
    message: str,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str | None = None,
    related_ids: tuple[str, ...] = (),
    blocking: bool,
    suggested_fix: str | None = None,
) -> ProvenanceCheckIssue:
    return ProvenanceCheckIssue(
        issue_code=issue_code,
        severity=severity,
        message=message,
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        related_ids=related_ids,
        blocking=blocking,
        suggested_fix=suggested_fix,
    )


def _missing_provenance_issue(
    *,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str,
    require_provenance: bool,
) -> ProvenanceCheckIssue:
    if require_provenance:
        return _make_issue(
            issue_code="provenance.missing_provenance",
            severity=ValidationSeverity.ERROR,
            message="provenance payload is required but missing",
            target_kind=target_kind,
            target_id=target_id,
            field_path=field_path,
            blocking=True,
            suggested_fix="attach structured provenance object for this target",
        )

    return _make_issue(
        issue_code="provenance.missing_provenance",
        severity=ValidationSeverity.WARNING,
        message="provenance payload is missing (backward-compatible warning)",
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        blocking=False,
        suggested_fix="attach structured provenance object for improved traceability",
    )


def check_phase1_provenance(
    envelope: Phase1StateEnvelope,
    *,
    require_provenance: bool = False,
) -> tuple[ProvenanceCheckIssue, ...]:
    """Run provenance-focused checks on one Phase1StateEnvelope.

    The checker intentionally does not raise. It always returns structured issues.
    """

    issues: list[ProvenanceCheckIssue] = []

    stage_context = envelope.stage_context
    stage_id = stage_context.stage_id
    visible_source_doc_ids = set(stage_context.source_doc_ids)

    if envelope.case_id != stage_context.case_id:
        issues.append(
            _make_issue(
                issue_code="provenance.case_alignment_mismatch",
                severity=ValidationSeverity.ERROR,
                message="envelope.case_id does not align with stage_context.case_id",
                target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
                target_id=envelope.state_id,
                field_path="stage_context.case_id",
                related_ids=(envelope.case_id, stage_context.case_id),
                blocking=True,
                suggested_fix="align case identity across envelope and stage_context",
            )
        )

    evidence_ids = {atom.evidence_id for atom in envelope.evidence_atoms}
    evidence_provenance_id_to_evidence_id: dict[str, str] = {}

    for atom in envelope.evidence_atoms:
        if atom.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="evidence stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="stage_id",
                    related_ids=(atom.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align evidence stage_id with stage_context.stage_id",
                )
            )

        provenance = atom.provenance
        if provenance is None:
            issues.append(
                _missing_provenance_issue(
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance",
                    require_provenance=require_provenance,
                )
            )
            continue

        duplicated_owner = evidence_provenance_id_to_evidence_id.get(
            provenance.evidence_provenance_id
        )
        if duplicated_owner is not None and duplicated_owner != atom.evidence_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.duplicate_evidence_provenance_id",
                    severity=ValidationSeverity.ERROR,
                    message="evidence_provenance_id is reused by multiple evidence atoms",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance.evidence_provenance_id",
                    related_ids=(
                        provenance.evidence_provenance_id,
                        duplicated_owner,
                        atom.evidence_id,
                    ),
                    blocking=True,
                    suggested_fix="use globally unique evidence_provenance_id values",
                )
            )
        else:
            evidence_provenance_id_to_evidence_id[provenance.evidence_provenance_id] = (
                atom.evidence_id
            )

        if provenance.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="evidence provenance stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance.stage_id",
                    related_ids=(provenance.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align provenance.stage_id with stage_context.stage_id",
                )
            )

        if provenance.evidence_id != atom.evidence_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.orphan_provenance_binding",
                    severity=ValidationSeverity.ERROR,
                    message="evidence provenance does not bind to owning evidence_id",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance.evidence_id",
                    related_ids=(provenance.evidence_id, atom.evidence_id),
                    blocking=True,
                    suggested_fix="set provenance.evidence_id equal to owner evidence_id",
                )
            )

        if provenance.extraction_activity.stage_id != stage_id:
            issues.append(
                _make_issue(
                    issue_code="provenance.stage_alignment_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message="extraction_activity.stage_id does not align with stage_context.stage_id",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance.extraction_activity.stage_id",
                    related_ids=(provenance.extraction_activity.stage_id, stage_id),
                    blocking=True,
                    suggested_fix="align extraction_activity.stage_id with stage_context.stage_id",
                )
            )

        non_visible_activity_docs = tuple(
            sorted(
                set(provenance.extraction_activity.input_source_doc_ids)
                - visible_source_doc_ids
            )
        )
        if non_visible_activity_docs:
            issues.append(
                _make_issue(
                    issue_code="provenance.source_doc_not_visible",
                    severity=ValidationSeverity.ERROR,
                    message="extraction activity references source_doc_id not visible in stage_context",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="provenance.extraction_activity.input_source_doc_ids",
                    related_ids=non_visible_activity_docs,
                    blocking=True,
                    suggested_fix="restrict activity input_source_doc_ids to stage_context.source_doc_ids",
                )
            )

        activity_source_doc_ids = set(provenance.extraction_activity.input_source_doc_ids)
        for anchor_index, anchor in enumerate(provenance.source_anchors):
            anchor_field = f"provenance.source_anchors[{anchor_index}]"

            if (anchor.span_start is None) ^ (anchor.span_end is None):
                issues.append(
                    _make_issue(
                        issue_code="provenance.source_span_incomplete",
                        severity=ValidationSeverity.ERROR,
                        message="source anchor span_start/span_end must be provided together",
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path=f"{anchor_field}",
                        related_ids=(anchor.anchor_id,),
                        blocking=True,
                        suggested_fix="set both span_start and span_end or leave both empty",
                    )
                )

            if (
                anchor.span_start is not None
                and anchor.span_end is not None
                and anchor.span_start > anchor.span_end
            ):
                issues.append(
                    _make_issue(
                        issue_code="provenance.source_span_order_invalid",
                        severity=ValidationSeverity.ERROR,
                        message="source anchor span_start must be <= span_end",
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path=f"{anchor_field}",
                        related_ids=(anchor.anchor_id,),
                        blocking=True,
                        suggested_fix="swap or correct source span boundaries",
                    )
                )

            if anchor.stage_id != stage_id:
                issues.append(
                    _make_issue(
                        issue_code="provenance.stage_alignment_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message="source anchor stage_id does not align with stage_context.stage_id",
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path=f"{anchor_field}.stage_id",
                        related_ids=(anchor.anchor_id, anchor.stage_id, stage_id),
                        blocking=True,
                        suggested_fix="align source anchor stage_id with stage_context.stage_id",
                    )
                )

            if anchor.source_doc_id not in visible_source_doc_ids:
                issues.append(
                    _make_issue(
                        issue_code="provenance.source_doc_not_visible",
                        severity=ValidationSeverity.ERROR,
                        message="source anchor source_doc_id is not visible in stage_context",
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path=f"{anchor_field}.source_doc_id",
                        related_ids=(anchor.anchor_id, anchor.source_doc_id),
                        blocking=True,
                        suggested_fix="restrict source anchors to stage_context.source_doc_ids",
                    )
                )

            if anchor.source_doc_id not in activity_source_doc_ids:
                issues.append(
                    _make_issue(
                        issue_code="provenance.source_doc_not_in_activity",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            "source anchor source_doc_id is missing from "
                            "extraction_activity.input_source_doc_ids"
                        ),
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path=f"{anchor_field}.source_doc_id",
                        related_ids=(anchor.anchor_id, anchor.source_doc_id),
                        blocking=True,
                        suggested_fix="add source_doc_id into extraction_activity.input_source_doc_ids",
                    )
                )

    claim_provenance_id_to_claim_id: dict[str, str] = {}
    referenced_evidence_provenance_ids: set[str] = set()

    for claim_ref in envelope.claim_references:
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

    unreferenced_evidence_provenance_ids = tuple(
        sorted(
            set(evidence_provenance_id_to_evidence_id)
            - referenced_evidence_provenance_ids
        )
    )
    if unreferenced_evidence_provenance_ids:
        issues.append(
            _make_issue(
                issue_code="provenance.orphan_provenance",
                severity=ValidationSeverity.WARNING,
                message="some evidence provenance objects are not referenced by any claim provenance",
                target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
                target_id=envelope.state_id,
                field_path="evidence_atoms[].provenance",
                related_ids=unreferenced_evidence_provenance_ids,
                blocking=False,
                suggested_fix="link orphan evidence provenance ids in claim provenance where appropriate",
            )
        )

    return tuple(issues)


__all__ = [
    "ProvenanceCheckIssue",
    "check_phase1_provenance",
]

"""Evidence-side provenance checks for Phase 1-2 envelope validation."""

from __future__ import annotations

from ..schemas.evidence import EvidenceAtom
from ..schemas.validation import ValidationSeverity, ValidationTargetKind
from .issues import (
    ProvenanceCheckIssue,
    _make_issue,
    _missing_provenance_issue,
    _normalize_extraction_method,
)


def run_evidence_provenance_checks(
    *,
    evidence_atoms: tuple[EvidenceAtom, ...],
    stage_id: str,
    visible_source_doc_ids: set[str],
    require_provenance: bool,
) -> tuple[tuple[ProvenanceCheckIssue, ...], dict[str, str]]:
    """Run provenance checks that only target evidence atoms and evidence provenance."""

    issues: list[ProvenanceCheckIssue] = []
    evidence_provenance_id_to_evidence_id: dict[str, str] = {}

    for atom in evidence_atoms:
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

        source_anchors = provenance.source_anchors
        if len(source_anchors) == 1:
            anchor = source_anchors[0]

            if atom.source_doc_id != anchor.source_doc_id:
                issues.append(
                    _make_issue(
                        issue_code="provenance.evidence_flat_source_doc_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            "flat source_doc_id must align with provenance source anchor "
                            "when exactly one source anchor is present"
                        ),
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path="source_doc_id",
                        related_ids=(atom.source_doc_id, anchor.source_doc_id),
                        blocking=True,
                        suggested_fix=(
                            "set evidence source_doc_id equal to "
                            "provenance.source_anchors[0].source_doc_id"
                        ),
                    )
                )

            if atom.raw_excerpt != anchor.raw_excerpt:
                issues.append(
                    _make_issue(
                        issue_code="provenance.evidence_flat_excerpt_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            "flat raw_excerpt must align with provenance source anchor "
                            "when exactly one source anchor is present"
                        ),
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path="raw_excerpt",
                        related_ids=(anchor.anchor_id,),
                        blocking=True,
                        suggested_fix=(
                            "set evidence raw_excerpt equal to "
                            "provenance.source_anchors[0].raw_excerpt"
                        ),
                    )
                )

            if (
                atom.source_span_start != anchor.span_start
                or atom.source_span_end != anchor.span_end
            ):
                issues.append(
                    _make_issue(
                        issue_code="provenance.evidence_flat_span_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            "flat source span must align with provenance source anchor "
                            "when exactly one source anchor is present"
                        ),
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path="source_span_start",
                        related_ids=(anchor.anchor_id,),
                        blocking=True,
                        suggested_fix=(
                            "set source_span_start/source_span_end equal to "
                            "provenance.source_anchors[0].span_start/span_end"
                        ),
                    )
                )
        else:
            anchor_source_doc_ids = {anchor.source_doc_id for anchor in source_anchors}
            if atom.source_doc_id not in anchor_source_doc_ids:
                issues.append(
                    _make_issue(
                        issue_code="provenance.evidence_flat_source_doc_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            "flat source_doc_id must belong to provenance source anchor "
                            "source_doc_id set in multi-anchor mode"
                        ),
                        target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                        target_id=atom.evidence_id,
                        field_path="source_doc_id",
                        related_ids=(atom.source_doc_id, *tuple(sorted(anchor_source_doc_ids))),
                        blocking=True,
                        suggested_fix=(
                            "set evidence source_doc_id to one of provenance source anchor "
                            "source_doc_id values"
                        ),
                    )
                )
            else:
                candidate_anchors = [
                    anchor
                    for anchor in source_anchors
                    if anchor.source_doc_id == atom.source_doc_id
                ]
                matched_anchors = [
                    anchor
                    for anchor in candidate_anchors
                    if anchor.raw_excerpt == atom.raw_excerpt
                ]

                if atom.source_span_start is not None and atom.source_span_end is not None:
                    matched_anchors = [
                        anchor
                        for anchor in matched_anchors
                        if (
                            anchor.span_start == atom.source_span_start
                            and anchor.span_end == atom.source_span_end
                        )
                    ]
                elif (atom.source_span_start is None) ^ (atom.source_span_end is None):
                    matched_anchors = []

                if len(matched_anchors) != 1:
                    issues.append(
                        _make_issue(
                            issue_code="provenance.evidence_flat_multi_anchor_ambiguous",
                            severity=ValidationSeverity.WARNING,
                            message=(
                                "flat raw_excerpt/source_span cannot be safely mapped to "
                                "a unique provenance source anchor in multi-anchor mode"
                            ),
                            target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                            target_id=atom.evidence_id,
                            field_path="raw_excerpt",
                            related_ids=tuple(
                                sorted(anchor.anchor_id for anchor in candidate_anchors)
                            ),
                            blocking=False,
                            suggested_fix=(
                                "keep provenance as authority and make flat raw_excerpt/source_span "
                                "match one unique anchor for compatibility"
                            ),
                        )
                    )

        normalized_flat_extraction_method = _normalize_extraction_method(
            atom.extraction_method
        )
        normalized_activity_extraction_method = _normalize_extraction_method(
            provenance.extraction_activity.extraction_method
        )
        if (
            normalized_flat_extraction_method is not None
            and normalized_flat_extraction_method != normalized_activity_extraction_method
        ):
            issues.append(
                _make_issue(
                    issue_code="provenance.evidence_flat_extraction_method_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "flat extraction_method must align with provenance "
                        "extraction_activity.extraction_method when provided"
                    ),
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=atom.evidence_id,
                    field_path="extraction_method",
                    related_ids=(
                        atom.extraction_method,
                        provenance.extraction_activity.extraction_method.value,
                    ),
                    blocking=True,
                    suggested_fix=(
                        "set flat extraction_method to the same method as "
                        "provenance.extraction_activity.extraction_method"
                    ),
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

    return tuple(issues), evidence_provenance_id_to_evidence_id


__all__ = ["run_evidence_provenance_checks"]

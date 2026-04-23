"""Phase 1-2 provenance consistency checker orchestrator.

本模块仅负责编排：
1. 准备共享上下文。
2. 调用 evidence/claim 分域检查模块。
3. 追加 envelope 级汇总检查并返回结构化 issue。
"""

from __future__ import annotations

from .claim_checks import run_claim_provenance_checks
from .evidence_checks import run_evidence_provenance_checks
from .issues import ProvenanceCheckIssue, _make_issue
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import ValidationSeverity, ValidationTargetKind


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

    evidence_issues, evidence_provenance_id_to_evidence_id = run_evidence_provenance_checks(
        evidence_atoms=envelope.evidence_atoms,
        stage_id=stage_id,
        visible_source_doc_ids=visible_source_doc_ids,
        require_provenance=require_provenance,
    )
    issues.extend(evidence_issues)

    claim_issues, referenced_evidence_provenance_ids = run_claim_provenance_checks(
        claim_references=envelope.claim_references,
        stage_id=stage_id,
        visible_source_doc_ids=visible_source_doc_ids,
        evidence_ids=evidence_ids,
        evidence_provenance_id_to_evidence_id=evidence_provenance_id_to_evidence_id,
        require_provenance=require_provenance,
    )
    issues.extend(claim_issues)

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

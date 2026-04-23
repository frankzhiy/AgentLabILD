"""Compatibility exports for shared state schema modules.

Phase 1-1 introduces typed StageContext / EvidenceAtom / ClaimReference /
HypothesisState exports while keeping
legacy import stability for shallow skeleton state references.
"""

from __future__ import annotations

from typing import TypedDict

from .action import ActionCandidate, ActionStatus, ActionType, ActionUrgency
from .claim import ClaimReference, ClaimRelation, ClaimStrength, ClaimTargetKind
from .evidence import EvidenceAtom
from .hypothesis import HypothesisConfidenceLevel, HypothesisState, HypothesisStatus
from .stage import (
    InfoModality,
    StageContext,
    StageFocus,
    StageType,
    TriggerType,
    VisibilityPolicyHint,
)


class SkeletonState(TypedDict, total=False):
    """Minimal shared-state placeholder used only for import stability."""

    stage_id: str
    note: str


__all__ = [
    "ActionCandidate",
    "ActionStatus",
    "ActionType",
    "ActionUrgency",
    "ClaimReference",
    "ClaimRelation",
    "ClaimStrength",
    "ClaimTargetKind",
    "EvidenceAtom",
    "HypothesisConfidenceLevel",
    "HypothesisState",
    "HypothesisStatus",
    "InfoModality",
    "SkeletonState",
    "StageContext",
    "StageFocus",
    "StageType",
    "TriggerType",
    "VisibilityPolicyHint",
]

"""Compatibility exports for shared state schema modules.

Phase 1-1 introduces typed StageContext / EvidenceAtom exports while keeping
legacy import stability for shallow skeleton state references.
"""

from __future__ import annotations

from typing import TypedDict

from .evidence import EvidenceAtom
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
    "EvidenceAtom",
    "InfoModality",
    "SkeletonState",
    "StageContext",
    "StageFocus",
    "StageType",
    "TriggerType",
    "VisibilityPolicyHint",
]

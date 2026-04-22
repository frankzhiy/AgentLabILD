"""State schema placeholders for future ILD-MDT mechanism phases.

This module intentionally avoids implementing Phase 1 logic.
"""

from __future__ import annotations

from typing import TypedDict


class SkeletonState(TypedDict, total=False):
    """Minimal shared-state placeholder used only for import stability."""

    stage_id: str
    note: str

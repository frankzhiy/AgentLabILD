"""Shared constants for validator modules."""

from __future__ import annotations

# Keep these values pattern-safe for StateValidationReport construction.
FALLBACK_CASE_ID = "case-unknown"
FALLBACK_STAGE_ID = "stage-unknown"
FALLBACK_STATE_ID = "state-unknown"
FALLBACK_BOARD_ID = "board-unknown"


__all__ = [
    "FALLBACK_BOARD_ID",
    "FALLBACK_CASE_ID",
    "FALLBACK_STAGE_ID",
    "FALLBACK_STATE_ID",
]
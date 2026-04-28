"""Backward-compatible Case Structurer adapter exports.

The implementation lives in ``src.adapters.case_structurer_adapter``.
"""

from __future__ import annotations

from ..adapters.case_structurer_adapter import (
    CaseStructurerInput,
    CaseStructurerResult,
    CaseStructurerStatus,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)

__all__ = [
    "CaseStructurerInput",
    "CaseStructurerResult",
    "CaseStructurerStatus",
    "build_case_structurer_prompt",
    "parse_case_structurer_payload",
]

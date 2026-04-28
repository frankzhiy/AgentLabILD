"""Backward-compatible Evidence Atomizer adapter exports.

The implementation lives in ``src.adapters.evidence_atomizer_adapter``.
"""

from __future__ import annotations

from ..adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerResult,
    EvidenceAtomizerStatus,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)

__all__ = [
    "EvidenceAtomizerInput",
    "EvidenceAtomizerResult",
    "EvidenceAtomizerStatus",
    "build_evidence_atomizer_prompt",
    "parse_evidence_atomizer_payload",
]

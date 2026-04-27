"""Adapter-agent package boundary for Phase 1.

Agents in this package are non-authoritative adapters that produce structured
drafts. They must not bypass validator-gated write mechanisms.
"""

from .case_structurer import (
	CaseStructurerInput,
	CaseStructurerResult,
	CaseStructurerStatus,
	build_case_structurer_prompt,
	parse_case_structurer_payload,
)
from .evidence_atomizer import (
	EvidenceAtomizerInput,
	EvidenceAtomizerResult,
	EvidenceAtomizerStatus,
	build_evidence_atomizer_prompt,
	parse_evidence_atomizer_payload,
)

__all__ = [
	"CaseStructurerInput",
	"CaseStructurerResult",
	"CaseStructurerStatus",
	"build_case_structurer_prompt",
	"parse_case_structurer_payload",
	"EvidenceAtomizerInput",
	"EvidenceAtomizerResult",
	"EvidenceAtomizerStatus",
	"build_evidence_atomizer_prompt",
	"parse_evidence_atomizer_payload",
]

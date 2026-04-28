"""Backward-compatible adapter export package for Phase 1.

True LLM agents are introduced separately. Current names re-export adapter
contracts for old import paths.
"""

from .case_structurer import (
	CaseStructurerInput,
	CaseStructurerResult,
	CaseStructurerStatus,
	build_case_structurer_prompt,
	parse_case_structurer_payload,
)
from .case_structurer_agent import CaseStructurerAgent
from .evidence_atomizer import (
	EvidenceAtomizerInput,
	EvidenceAtomizerResult,
	EvidenceAtomizerStatus,
	build_evidence_atomizer_prompt,
	parse_evidence_atomizer_payload,
)
from .evidence_atomizer_agent import EvidenceAtomizerAgent
from .hypothesis_board_bootstrapper_agent import HypothesisBoardBootstrapperAgent

__all__ = [
	"CaseStructurerInput",
	"CaseStructurerResult",
	"CaseStructurerStatus",
	"CaseStructurerAgent",
	"build_case_structurer_prompt",
	"parse_case_structurer_payload",
	"EvidenceAtomizerInput",
	"EvidenceAtomizerResult",
	"EvidenceAtomizerStatus",
	"EvidenceAtomizerAgent",
	"HypothesisBoardBootstrapperAgent",
	"build_evidence_atomizer_prompt",
	"parse_evidence_atomizer_payload",
]

"""Phase 1-4 adapter contract exports."""

from .case_structuring import (
    CandidateClueGroup,
    CandidateClueGroupKey,
    CaseStructuringDraft,
    CaseTimelineEventType,
    CaseTimelineItem,
    NormalizedFinding,
)
from .case_structurer_adapter import (
    CaseStructurerInput,
    CaseStructurerResult,
    CaseStructurerStatus,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)
from .evidence_atomization import EvidenceAtomizationDraft
from .evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerResult,
    EvidenceAtomizerStatus,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)
from .hypothesis_board_bootstrapper_adapter import (
    HypothesisBoardBootstrapDraft,
    HypothesisBoardBootstrapperInput,
    HypothesisBoardBootstrapperResult,
    HypothesisBoardBootstrapperStatus,
    build_hypothesis_board_bootstrapper_prompt,
    parse_hypothesis_board_bootstrapper_payload,
)
from .validation_bridge import (
    AdapterValidationBridgeResult,
    AdapterValidationBridgeStatus,
    validate_adapter_drafts_against_sources,
    validate_case_structuring_draft_against_sources,
    validate_evidence_atomization_draft_against_sources,
)

__all__ = [
    "CandidateClueGroup",
    "CandidateClueGroupKey",
    "CaseStructuringDraft",
    "CaseTimelineEventType",
    "CaseTimelineItem",
    "CaseStructurerInput",
    "CaseStructurerResult",
    "CaseStructurerStatus",
    "EvidenceAtomizationDraft",
    "EvidenceAtomizerInput",
    "EvidenceAtomizerResult",
    "EvidenceAtomizerStatus",
    "HypothesisBoardBootstrapDraft",
    "HypothesisBoardBootstrapperInput",
    "HypothesisBoardBootstrapperResult",
    "HypothesisBoardBootstrapperStatus",
    "NormalizedFinding",
    "AdapterValidationBridgeResult",
    "AdapterValidationBridgeStatus",
    "build_case_structurer_prompt",
    "parse_case_structurer_payload",
    "build_evidence_atomizer_prompt",
    "parse_evidence_atomizer_payload",
    "build_hypothesis_board_bootstrapper_prompt",
    "parse_hypothesis_board_bootstrapper_payload",
    "validate_adapter_drafts_against_sources",
    "validate_case_structuring_draft_against_sources",
    "validate_evidence_atomization_draft_against_sources",
]

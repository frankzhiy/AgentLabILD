"""Tests for explicit adapter and agent import locations."""

from __future__ import annotations

from src.adapters.case_structurer_adapter import (
    CaseStructurerInput,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)
from src.adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)
from src.agents import (
    CaseStructurerAgent,
    EvidenceAtomizerAgent,
    HypothesisBoardBootstrapperAgent,
)
from src.agents.case_structurer_agent import (
    CaseStructurerAgent as DirectCaseStructurerAgent,
)
from src.agents.evidence_atomizer_agent import (
    EvidenceAtomizerAgent as DirectEvidenceAtomizerAgent,
)
from src.agents.hypothesis_board_bootstrapper_agent import (
    HypothesisBoardBootstrapperAgent as DirectHypothesisBoardBootstrapperAgent,
)


def test_case_structurer_adapter_imports_resolve() -> None:
    assert CaseStructurerInput.__name__ == "CaseStructurerInput"
    assert callable(build_case_structurer_prompt)
    assert callable(parse_case_structurer_payload)


def test_evidence_atomizer_adapter_imports_resolve() -> None:
    assert EvidenceAtomizerInput.__name__ == "EvidenceAtomizerInput"
    assert callable(build_evidence_atomizer_prompt)
    assert callable(parse_evidence_atomizer_payload)


def test_agent_package_exports_real_agent_classes_only() -> None:
    assert CaseStructurerAgent is DirectCaseStructurerAgent
    assert EvidenceAtomizerAgent is DirectEvidenceAtomizerAgent
    assert HypothesisBoardBootstrapperAgent is DirectHypothesisBoardBootstrapperAgent

"""Tests for the LLM-backed Evidence Atomizer agent coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerStatus,
)
from src.adapters.case_structuring import CaseStructuringDraft
from src.agents.evidence_atomizer_agent import (
    EVIDENCE_ATOMIZATION_SCHEMA_NAME,
    EVIDENCE_ATOMIZER_AGENT_NAME,
    EvidenceAtomizerAgent,
)
from src.llm.retry_policy import StructuredLLMFailureKind
from src.llm.structured_runner import StructuredLLMRunnerResult, StructuredLLMStatus
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.intake import SourceDocumentType
from src.schemas.stage import InfoModality, StageType, TriggerType


@dataclass
class FakeStructuredRunner:
    result: StructuredLLMRunnerResult

    def __post_init__(self) -> None:
        self.prompts: list[str] = []
        self.output_schemas: list[dict[str, object] | None] = []
        self.metadata: list[dict[str, object] | None] = []

    def run_prompt(
        self,
        prompt: str,
        *,
        output_schema: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> StructuredLLMRunnerResult:
        self.prompts.append(prompt)
        self.output_schemas.append(output_schema)
        self.metadata.append(metadata)
        return self.result


def _base_case_structuring_draft_payload() -> dict[str, object]:
    return {
        "draft_id": "case_struct_draft-001",
        "case_id": "case-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "proposed_stage_context": {
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": datetime(2026, 4, 27, 10, 0, 0),
            "available_modalities": (InfoModality.HISTORY, InfoModality.HRCT_TEXT),
            "source_doc_ids": ("doc-001", "doc-002"),
        },
        "timeline_items": (
            {
                "timeline_item_id": "timeline_item-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "event_type": "symptom_onset",
                "event_time_text": "8 years ago",
                "description": "Chronic cough began.",
                "source_span_start": 0,
                "source_span_end": 25,
            },
        ),
        "normalized_findings": (
            {
                "finding_id": "finding-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-002",
                "finding_key": "reticulation pattern",
                "finding_text": "Reticulation with traction bronchiectasis.",
                "modality": InfoModality.HRCT_TEXT,
                "source_span_start": 0,
                "source_span_end": 43,
            },
        ),
        "candidate_clue_groups": (
            {
                "clue_group_id": "clue_group-001",
                "stage_id": "stage-001",
                "group_key": "disease_course_clues",
                "finding_ids": ("finding-001",),
                "summary": "Findings suggest chronic progressive course clues.",
            },
        ),
    }


def _base_input(*, with_case_structuring_draft: bool = True) -> EvidenceAtomizerInput:
    payload: dict[str, object] = {
        "case_id": "case-001",
        "stage_id": "stage-001",
        "source_documents": (
            {
                "source_doc_id": "doc-001",
                "case_id": "case-001",
                "input_event_id": "input_event-001",
                "document_type": SourceDocumentType.FREE_TEXT_CASE_NOTE,
                "raw_text": "Patient has chronic cough for 8 years.",
                "created_at": datetime(2026, 4, 27, 9, 0, 0),
            },
            {
                "source_doc_id": "doc-002",
                "case_id": "case-001",
                "input_event_id": "input_event-002",
                "document_type": SourceDocumentType.HRCT_REPORT_TEXT,
                "raw_text": "HRCT text mentions reticulation and traction bronchiectasis.",
                "created_at": datetime(2026, 4, 27, 9, 30, 0),
            },
        ),
        "stage_context": {
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": datetime(2026, 4, 27, 10, 0, 0),
            "available_modalities": (InfoModality.HISTORY, InfoModality.HRCT_TEXT),
            "source_doc_ids": ("doc-001", "doc-002"),
        },
        "extraction_activity_id": "activity-001",
        "occurred_at": datetime(2026, 4, 27, 10, 5, 0),
    }

    if with_case_structuring_draft:
        payload["case_structuring_draft"] = CaseStructuringDraft(
            **_base_case_structuring_draft_payload()
        )

    return EvidenceAtomizerInput(**payload)


def _base_evidence_atom_payload(
    *, evidence_id: str, source_doc_id: str, atom_index: int
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "stage_id": "stage-001",
        "source_doc_id": source_doc_id,
        "atom_index": atom_index,
        "category": EvidenceCategory.SYMPTOM,
        "modality": InfoModality.HISTORY,
        "statement": "Chronic cough is present.",
        "raw_excerpt": "Chronic cough for several years.",
        "polarity": EvidencePolarity.PRESENT,
        "certainty": EvidenceCertainty.REPORTED,
        "temporality": EvidenceTemporality.CURRENT,
        "subject": EvidenceSubject.PATIENT,
    }


def _valid_evidence_atomization_payload() -> dict[str, object]:
    return {
        "draft_id": "atomization_draft-001",
        "case_id": "case-001",
        "stage_id": "stage-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "evidence_atoms": (
            _base_evidence_atom_payload(
                evidence_id="evd-001",
                source_doc_id="doc-001",
                atom_index=0,
            ),
            _base_evidence_atom_payload(
                evidence_id="evd-002",
                source_doc_id="doc-002",
                atom_index=1,
            ),
        ),
        "extraction_activity": {
            "activity_id": "activity-001",
            "stage_id": "stage-001",
            "extraction_method": ExtractionMethod.RULE_BASED,
            "extractor_name": "evidence_atomizer_adapter",
            "extractor_version": "0.1.0",
            "occurred_at": datetime(2026, 4, 27, 10, 5, 0),
            "input_source_doc_ids": ("doc-001", "doc-002"),
        },
    }


def test_evidence_atomizer_agent_success_path_calls_runner_and_adapter_parser() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.SUCCESS,
            parsed=_valid_evidence_atomization_payload(),
            attempts=1,
        )
    )
    agent = EvidenceAtomizerAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is EvidenceAtomizerStatus.ACCEPTED
    assert result.draft is not None
    assert "{{" not in fake_runner.prompts[0]
    assert "}}" not in fake_runner.prompts[0]
    assert fake_runner.output_schemas[0] is not None
    assert fake_runner.output_schemas[0]["title"] == "EvidenceAtomizationDraft"
    assert fake_runner.metadata[0] == {
        "agent_name": EVIDENCE_ATOMIZER_AGENT_NAME,
        "case_id": "case-001",
        "stage_id": "stage-001",
        "schema_name": EVIDENCE_ATOMIZATION_SCHEMA_NAME,
    }


def test_evidence_atomizer_agent_returns_adapter_rejection_without_exception() -> None:
    payload = _valid_evidence_atomization_payload()
    payload["hypotheses"] = ("hyp-001",)
    payload["claim_references"] = ("claim_ref-001",)
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.SUCCESS,
            parsed=payload,
            attempts=1,
        )
    )
    agent = EvidenceAtomizerAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("hypotheses" in error for error in result.errors)
    assert any("claim_references" in error for error in result.errors)


def test_evidence_atomizer_agent_runner_failure_returns_manual_review_without_draft() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.FAILURE,
            parsed=None,
            attempts=1,
            errors=("runner failed",),
            failure_kind=StructuredLLMFailureKind.TRANSPORT,
        )
    )
    agent = EvidenceAtomizerAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is EvidenceAtomizerStatus.MANUAL_REVIEW
    assert result.draft is None
    assert result.errors == ("runner failed",)


def test_evidence_atomizer_agent_runner_manual_review_returns_manual_review_without_draft() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.MANUAL_REVIEW,
            parsed=None,
            attempts=1,
            errors=("needs review",),
            failure_kind=StructuredLLMFailureKind.EMPTY_RESPONSE,
        )
    )
    agent = EvidenceAtomizerAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is EvidenceAtomizerStatus.MANUAL_REVIEW
    assert result.draft is None
    assert result.errors == ("needs review",)

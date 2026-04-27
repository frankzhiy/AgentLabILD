"""Tests for EvidenceAtom and SourceDocument alignment bridge validation."""

from __future__ import annotations

from datetime import datetime

from src.schemas.evidence import (
    EvidenceAtom,
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.intake import SourceDocument, SourceDocumentType
from src.schemas.stage import InfoModality
from src.validators.provenance_validator import validate_evidence_atoms_against_sources


def _build_source_document(raw_text: str) -> SourceDocument:
    return SourceDocument(
        source_doc_id="doc-001",
        case_id="case-abc",
        input_event_id="input_event-0001",
        document_type=SourceDocumentType.FREE_TEXT_CASE_NOTE,
        raw_text=raw_text,
        created_at=datetime(2026, 4, 27, 15, 0, 0),
    )


def _build_evidence_atom(
    *,
    raw_excerpt: str,
    source_span_start: int | None = None,
    source_span_end: int | None = None,
) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id="evd-001",
        stage_id="stage-001",
        source_doc_id="doc-001",
        atom_index=0,
        category=EvidenceCategory.SYMPTOM,
        modality=InfoModality.HISTORY,
        statement="Patient reports chronic cough.",
        raw_excerpt=raw_excerpt,
        polarity=EvidencePolarity.PRESENT,
        certainty=EvidenceCertainty.REPORTED,
        temporality=EvidenceTemporality.CURRENT,
        subject=EvidenceSubject.PATIENT,
        source_span_start=source_span_start,
        source_span_end=source_span_end,
    )


def test_evidence_excerpt_must_exist_in_source_document_raw_text() -> None:
    source_document = _build_source_document("患者诉慢性咳嗽并气短。")
    evidence_atom = _build_evidence_atom(raw_excerpt="慢性咳嗽")

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=(evidence_atom,),
        source_documents=(source_document,),
    )

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()


def test_evidence_excerpt_not_found_is_blocking() -> None:
    source_document = _build_source_document("患者诉慢性咳嗽并气短。")
    evidence_atom = _build_evidence_atom(raw_excerpt="胸痛")

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=(evidence_atom,),
        source_documents=(source_document,),
    )

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.raw_excerpt_not_found" and issue.blocking
        for issue in report.issues
    )


def test_invalid_source_span_is_rejected() -> None:
    source_document = _build_source_document("患者诉慢性咳嗽并气短。")
    evidence_atom = _build_evidence_atom(
        raw_excerpt="慢性咳嗽",
        source_span_start=0,
        source_span_end=99,
    )

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=(evidence_atom,),
        source_documents=(source_document,),
    )

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.source_span_invalid" and issue.blocking
        for issue in report.issues
    )


def test_source_span_mismatch_is_blocking() -> None:
    source_document = _build_source_document("患者诉慢性咳嗽并气短。")
    evidence_atom = _build_evidence_atom(
        raw_excerpt="慢性咳嗽",
        source_span_start=0,
        source_span_end=4,
    )

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=(evidence_atom,),
        source_documents=(source_document,),
    )

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.source_span_excerpt_mismatch" and issue.blocking
        for issue in report.issues
    )


def test_missing_source_doc_registration_is_blocking() -> None:
    source_document = _build_source_document("患者诉慢性咳嗽并气短。")
    evidence_atom = _build_evidence_atom(raw_excerpt="慢性咳嗽")
    evidence_atom.source_doc_id = "doc-999"

    report = validate_evidence_atoms_against_sources(
        evidence_atoms=(evidence_atom,),
        source_documents=(source_document,),
    )

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.source_doc_not_registered" and issue.blocking
        for issue in report.issues
    )

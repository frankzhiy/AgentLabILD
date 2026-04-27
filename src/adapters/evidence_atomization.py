"""Phase 1-4 adapter contract schema for Evidence Atomizer.

This model is a non-authoritative extraction draft boundary.
It does not perform diagnosis or hypothesis synthesis.
"""

from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..provenance.model import ExtractionActivity
from ..schemas.common import (
    CASE_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    validate_id_pattern,
)
from ..schemas.evidence import EvidenceAtom

EVIDENCE_ATOMIZATION_DRAFT_ID_PATTERN = re.compile(
    r"^atomization_draft[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)


class EvidenceAtomizationDraft(BaseModel):
    """Non-authoritative draft contract for Evidence Atomizer output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["evidence_atomization_draft"] = "evidence_atomization_draft"
    draft_id: NonEmptyStr
    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_doc_ids: tuple[NonEmptyStr, ...]
    evidence_atoms: tuple[EvidenceAtom, ...]
    extraction_activity: ExtractionActivity
    non_authoritative_note: str | None = None

    @field_validator("draft_id")
    @classmethod
    def validate_draft_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EVIDENCE_ATOMIZATION_DRAFT_ID_PATTERN,
            field_name="draft_id",
            example="atomization_draft_001 or atomization_draft-001",
        )

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("source_doc_ids")
    @classmethod
    def validate_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("source_doc_ids must not be empty")

        duplicate_ids = find_duplicate_items(value)
        if duplicate_ids:
            raise ValueError("source_doc_ids must not contain duplicates")

        for source_doc_id in value:
            validate_id_pattern(
                source_doc_id,
                pattern=SOURCE_DOC_ID_PATTERN,
                field_name="source_doc_ids[]",
                example="doc_001 or doc-001",
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_cross_object_alignment(self) -> "EvidenceAtomizationDraft":
        if not self.evidence_atoms:
            raise ValueError("evidence_atoms must not be empty")

        duplicate_evidence_ids = find_duplicate_items(
            evidence_atom.evidence_id for evidence_atom in self.evidence_atoms
        )
        if duplicate_evidence_ids:
            raise ValueError("evidence_atoms must not contain duplicate evidence_id values")

        allowed_source_doc_ids = set(self.source_doc_ids)
        for evidence_atom in self.evidence_atoms:
            if evidence_atom.stage_id != self.stage_id:
                raise ValueError("every evidence atom must align to draft stage_id")
            if evidence_atom.source_doc_id not in allowed_source_doc_ids:
                raise ValueError(
                    "every evidence atom source_doc_id must be included in draft source_doc_ids"
                )

        if self.extraction_activity.stage_id != self.stage_id:
            raise ValueError("extraction_activity.stage_id must equal draft stage_id")

        activity_source_doc_ids = set(self.extraction_activity.input_source_doc_ids)
        if not allowed_source_doc_ids.issubset(activity_source_doc_ids):
            raise ValueError(
                "extraction_activity.input_source_doc_ids must cover draft source_doc_ids"
            )

        return self


__all__ = [
    "EVIDENCE_ATOMIZATION_DRAFT_ID_PATTERN",
    "EvidenceAtomizationDraft",
]

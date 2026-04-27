"""Shared primitive schema types for Phase 1 state models."""

from __future__ import annotations

import re
from collections.abc import Iterable
from re import Pattern
from typing import Annotated

from pydantic import Field


NonEmptyStr = Annotated[str, Field(min_length=1)]


CASE_ID_PATTERN = re.compile(r"^case[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_ID_PATTERN = re.compile(r"^stage[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
SOURCE_DOC_ID_PATTERN = re.compile(r"^doc[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
EVENT_ID_PATTERN = re.compile(r"^event[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
EVIDENCE_ID_PATTERN = re.compile(r"^(ev|evd)[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
CLAIM_REF_ID_PATTERN = re.compile(r"^claim_ref[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
HYPOTHESIS_ID_PATTERN = re.compile(r"^hyp(?:othesis)?[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
ACTION_CANDIDATE_ID_PATTERN = re.compile(
	r"^action(?:_candidate)?[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)
BOARD_ID_PATTERN = re.compile(r"^board[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STATE_ID_PATTERN = re.compile(r"^state[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
REPORT_ID_PATTERN = re.compile(r"^report[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
ISSUE_ID_PATTERN = re.compile(r"^issue[_-][A-Za-z0-9][A-Za-z0-9_-]*$")


def validate_id_pattern(
	value: str,
	*,
	pattern: Pattern[str],
	field_name: str,
	example: str,
) -> str:
	"""Validate one id value against a shared regex pattern."""

	if not pattern.fullmatch(value):
		raise ValueError(f"{field_name} must match pattern like {example}")

	return value


def normalize_optional_text(value: object) -> str | None:
	"""Normalize optional text-like values to stripped string or None."""

	if value is None:
		return None

	cleaned = str(value).strip()
	return cleaned or None


def normalize_optional_note(value: object) -> str | None:
	"""Normalize optional non-authoritative note values."""

	return normalize_optional_text(value)


def find_duplicate_items(values: Iterable[str]) -> tuple[str, ...]:
	"""Return sorted duplicates from an iterable of ids/keys."""

	seen: set[str] = set()
	duplicates: set[str] = set()

	for value in values:
		if value in seen:
			duplicates.add(value)
			continue
		seen.add(value)

	return tuple(sorted(duplicates))


__all__ = [
	"ACTION_CANDIDATE_ID_PATTERN",
	"BOARD_ID_PATTERN",
	"CASE_ID_PATTERN",
	"CLAIM_REF_ID_PATTERN",
	"EVIDENCE_ID_PATTERN",
	"EVENT_ID_PATTERN",
	"HYPOTHESIS_ID_PATTERN",
	"ISSUE_ID_PATTERN",
	"NonEmptyStr",
	"REPORT_ID_PATTERN",
	"SOURCE_DOC_ID_PATTERN",
	"STAGE_ID_PATTERN",
	"STATE_ID_PATTERN",
	"find_duplicate_items",
	"normalize_optional_note",
	"normalize_optional_text",
	"validate_id_pattern",
]

"""Shared primitive schema types for Phase 1 state models."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from pydantic import Field


NonEmptyStr = Annotated[str, Field(min_length=1)]


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
	"NonEmptyStr",
	"find_duplicate_items",
	"normalize_optional_note",
	"normalize_optional_text",
]

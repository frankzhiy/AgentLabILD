"""Shared primitive schema types for Phase 1 state models."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field


NonEmptyStr = Annotated[str, Field(min_length=1)]


__all__ = ["NonEmptyStr"]

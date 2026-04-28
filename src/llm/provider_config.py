"""Provider configuration contracts for structured LLM calls.

This module only models provider-call configuration. It does not instantiate
provider SDK clients and does not read API keys.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMProvider(StrEnum):
    """Supported provider identifiers for future runtime integration."""

    CUSTOM = "custom"
    OPENAI = "openai"
    TEST = "test"


class LLMProviderConfig(BaseModel):
    """Small provider/model configuration object for structured calls."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider: LLMProvider = LLMProvider.CUSTOM
    model: str = Field(min_length=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    timeout_seconds: float | None = Field(default=None, gt=0)
    response_format: str = Field(default="json_object", min_length=1)
    api_key_env_var: str | None = None

    @field_validator("api_key_env_var", mode="before")
    @classmethod
    def normalize_api_key_env_var(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None


__all__ = ["LLMProvider", "LLMProviderConfig"]

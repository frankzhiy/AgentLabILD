"""LLM-backed Case Structurer agent coordinator.

This layer coordinates prompt rendering, structured runner invocation, and
adapter parsing. It does not persist state and does not run validators.
"""

from __future__ import annotations

from ..adapters.case_structurer_adapter import (
    CaseStructurerInput,
    CaseStructurerResult,
    CaseStructurerStatus,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)
from ..adapters.case_structuring import CaseStructuringDraft
from ..llm.schema_export import export_pydantic_json_schema
from ..llm.structured_runner import StructuredLLMRunner, StructuredLLMStatus

CASE_STRUCTURER_AGENT_NAME = "case_structurer_agent"
CASE_STRUCTURING_SCHEMA_NAME = "CaseStructuringDraft"


class CaseStructurerAgent:
    """Coordinate Case Structurer prompt -> runner -> adapter parser."""

    def __init__(self, runner: StructuredLLMRunner) -> None:
        self._runner = runner

    def run(self, input: CaseStructurerInput) -> CaseStructurerResult:
        rendered_prompt = build_case_structurer_prompt(input)
        output_schema = export_pydantic_json_schema(CaseStructuringDraft)
        runner_result = self._runner.run_prompt(
            rendered_prompt,
            output_schema=output_schema,
            metadata={
                "agent_name": CASE_STRUCTURER_AGENT_NAME,
                "case_id": input.case_id,
                "stage_id": input.stage_id,
                "schema_name": CASE_STRUCTURING_SCHEMA_NAME,
            },
        )

        if (
            runner_result.status is StructuredLLMStatus.SUCCESS
            and runner_result.parsed is not None
        ):
            return parse_case_structurer_payload(runner_result.parsed, input)

        return CaseStructurerResult(
            status=CaseStructurerStatus.MANUAL_REVIEW,
            draft=None,
            errors=_runner_errors_or_fallback(runner_result.errors),
            warnings=(),
        )


def _runner_errors_or_fallback(errors: tuple[str, ...]) -> tuple[str, ...]:
    if errors:
        return errors

    return ("structured runner did not return parsed CaseStructuringDraft payload",)


__all__ = [
    "CASE_STRUCTURER_AGENT_NAME",
    "CASE_STRUCTURING_SCHEMA_NAME",
    "CaseStructurerAgent",
]

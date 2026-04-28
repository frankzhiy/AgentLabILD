"""LLM-backed Evidence Atomizer agent coordinator.

This layer coordinates prompt rendering, structured runner invocation, and
adapter parsing. It does not persist state and does not run validators.
"""

from __future__ import annotations

from ..adapters.evidence_atomization import EvidenceAtomizationDraft
from ..adapters.evidence_atomizer_adapter import (
    EvidenceAtomizerInput,
    EvidenceAtomizerResult,
    EvidenceAtomizerStatus,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)
from ..llm.schema_export import export_pydantic_json_schema
from ..llm.structured_runner import StructuredLLMRunner, StructuredLLMStatus

EVIDENCE_ATOMIZER_AGENT_NAME = "evidence_atomizer_agent"
EVIDENCE_ATOMIZATION_SCHEMA_NAME = "EvidenceAtomizationDraft"


class EvidenceAtomizerAgent:
    """Coordinate Evidence Atomizer prompt -> runner -> adapter parser."""

    def __init__(self, runner: StructuredLLMRunner) -> None:
        self._runner = runner

    def run(self, input: EvidenceAtomizerInput) -> EvidenceAtomizerResult:
        rendered_prompt = build_evidence_atomizer_prompt(input)
        output_schema = export_pydantic_json_schema(EvidenceAtomizationDraft)
        runner_result = self._runner.run_prompt(
            rendered_prompt,
            output_schema=output_schema,
            metadata={
                "agent_name": EVIDENCE_ATOMIZER_AGENT_NAME,
                "case_id": input.case_id,
                "stage_id": input.stage_id,
                "schema_name": EVIDENCE_ATOMIZATION_SCHEMA_NAME,
            },
        )

        if (
            runner_result.status is StructuredLLMStatus.SUCCESS
            and runner_result.parsed is not None
        ):
            return parse_evidence_atomizer_payload(runner_result.parsed, input)

        return EvidenceAtomizerResult(
            status=EvidenceAtomizerStatus.MANUAL_REVIEW,
            draft=None,
            errors=_runner_errors_or_fallback(runner_result.errors),
            warnings=(),
        )


def _runner_errors_or_fallback(errors: tuple[str, ...]) -> tuple[str, ...]:
    if errors:
        return errors

    return ("structured runner did not return parsed EvidenceAtomizationDraft payload",)


__all__ = [
    "EVIDENCE_ATOMIZATION_SCHEMA_NAME",
    "EVIDENCE_ATOMIZER_AGENT_NAME",
    "EvidenceAtomizerAgent",
]

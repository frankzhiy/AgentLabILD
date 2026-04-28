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
from ..tracing.phase1_trace import (
    Phase1TraceRecorder,
    Phase1TraceStatus,
    Phase1TraceStep,
    hash_text_artifact,
    safe_record_phase1_event,
)

CASE_STRUCTURER_AGENT_NAME = "case_structurer_agent"
CASE_STRUCTURING_SCHEMA_NAME = "CaseStructuringDraft"


class CaseStructurerAgent:
    """Coordinate Case Structurer prompt -> runner -> adapter parser."""

    def __init__(
        self,
        runner: StructuredLLMRunner,
        *,
        trace_recorder: Phase1TraceRecorder | None = None,
    ) -> None:
        self._runner = runner
        self._trace_recorder = trace_recorder

    def run(self, input: CaseStructurerInput) -> CaseStructurerResult:
        rendered_prompt = build_case_structurer_prompt(input)
        output_schema = export_pydantic_json_schema(CaseStructuringDraft)
        safe_record_phase1_event(
            self._trace_recorder,
            step_name=Phase1TraceStep.PROMPT_HANDOFF,
            case_id=input.case_id,
            stage_id=input.stage_id,
            status=Phase1TraceStatus.HANDED_OFF,
            agent_name=CASE_STRUCTURER_AGENT_NAME,
            schema_name=CASE_STRUCTURING_SCHEMA_NAME,
            artifact_hashes=(
                hash_text_artifact(label="prompt", text=rendered_prompt),
            ),
        )
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
        safe_record_phase1_event(
            self._trace_recorder,
            step_name=Phase1TraceStep.RUNNER_RESULT,
            case_id=input.case_id,
            stage_id=input.stage_id,
            status=_runner_status_to_trace_status(runner_result.status),
            agent_name=CASE_STRUCTURER_AGENT_NAME,
            schema_name=CASE_STRUCTURING_SCHEMA_NAME,
            attempt_count=runner_result.attempts,
            model_name=runner_result.model,
            error_messages=runner_result.errors,
            artifact_ids=(
                (runner_result.raw_response_id,)
                if runner_result.raw_response_id is not None
                else ()
            ),
        )

        if (
            runner_result.status is StructuredLLMStatus.SUCCESS
            and runner_result.parsed is not None
        ):
            adapter_result = parse_case_structurer_payload(runner_result.parsed, input)
            safe_record_phase1_event(
                self._trace_recorder,
                step_name=Phase1TraceStep.ADAPTER_RESULT,
                case_id=input.case_id,
                stage_id=input.stage_id,
                status=_adapter_status_to_trace_status(adapter_result.status),
                agent_name=CASE_STRUCTURER_AGENT_NAME,
                schema_name=CASE_STRUCTURING_SCHEMA_NAME,
                error_messages=adapter_result.errors,
                warning_messages=adapter_result.warnings,
                artifact_ids=(
                    (adapter_result.draft.draft_id,)
                    if adapter_result.draft is not None
                    else ()
                ),
            )
            return adapter_result

        result = CaseStructurerResult(
            status=CaseStructurerStatus.MANUAL_REVIEW,
            draft=None,
            errors=_runner_errors_or_fallback(runner_result.errors),
            warnings=(),
        )
        safe_record_phase1_event(
            self._trace_recorder,
            step_name=Phase1TraceStep.MANUAL_REVIEW_DECISION,
            case_id=input.case_id,
            stage_id=input.stage_id,
            status=Phase1TraceStatus.MANUAL_REVIEW,
            agent_name=CASE_STRUCTURER_AGENT_NAME,
            schema_name=CASE_STRUCTURING_SCHEMA_NAME,
            attempt_count=runner_result.attempts,
            model_name=runner_result.model,
            error_messages=result.errors,
        )
        return result


def _runner_errors_or_fallback(errors: tuple[str, ...]) -> tuple[str, ...]:
    if errors:
        return errors

    return ("structured runner did not return parsed CaseStructuringDraft payload",)


def _runner_status_to_trace_status(
    status: StructuredLLMStatus,
) -> Phase1TraceStatus:
    if status is StructuredLLMStatus.SUCCESS:
        return Phase1TraceStatus.SUCCESS

    if status is StructuredLLMStatus.FAILURE:
        return Phase1TraceStatus.FAILURE

    return Phase1TraceStatus.MANUAL_REVIEW


def _adapter_status_to_trace_status(
    status: CaseStructurerStatus,
) -> Phase1TraceStatus:
    if status is CaseStructurerStatus.ACCEPTED:
        return Phase1TraceStatus.SUCCESS

    if status is CaseStructurerStatus.REJECTED:
        return Phase1TraceStatus.REJECTED

    return Phase1TraceStatus.MANUAL_REVIEW


__all__ = [
    "CASE_STRUCTURER_AGENT_NAME",
    "CASE_STRUCTURING_SCHEMA_NAME",
    "CaseStructurerAgent",
]

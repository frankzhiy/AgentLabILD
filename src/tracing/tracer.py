"""实验追踪器

收集 agent 级、通信级、冲突级的完整 trace 数据。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.schemas.trace import (
    AgentTrace,
    ConflictTrace,
    LLMCallTrace,
    MessageTrace,
    PipelineTrace,
    TokenUsage,
)


class Tracer:
    """收集单个病例运行过程中的所有 trace"""

    def __init__(self, case_id: str, experiment_name: str):
        self._pipeline_trace = PipelineTrace(
            case_id=case_id,
            experiment_name=experiment_name,
            start_time=datetime.now(timezone.utc),
        )

    # ── Agent 追踪 ──────────────────────────────────────────

    def start_agent(self, agent_id: str, node_id: str, input_data: dict) -> AgentTrace:
        """开始追踪一个 agent 的执行"""
        trace = AgentTrace(
            agent_id=agent_id,
            node_id=node_id,
            input_data=input_data,
            start_time=datetime.now(timezone.utc),
        )
        return trace

    def finish_agent(self, trace: AgentTrace, output_content: str,
                     output_metadata: dict | None = None,
                     llm_calls: list[LLMCallTrace] | None = None,
                     error: str | None = None) -> None:
        """完成一个 agent 的追踪并记录"""
        trace.end_time = datetime.now(timezone.utc)
        trace.output_content = output_content
        trace.output_metadata = output_metadata or {}
        trace.llm_calls = llm_calls or []
        trace.error = error
        self._pipeline_trace.agent_traces.append(trace)
        self._pipeline_trace.node_execution_order.append(
            f"{trace.node_id}/{trace.agent_id}"
        )

    # ── 消息追踪 ────────────────────────────────────────────

    def log_message(self, from_agent: str, to_agent: str, content: Any) -> None:
        self._pipeline_trace.message_traces.append(
            MessageTrace(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                timestamp=datetime.now(timezone.utc),
            )
        )

    # ── 冲突追踪 ────────────────────────────────────────────

    def set_conflict_trace(self, conflict_trace: ConflictTrace) -> None:
        self._pipeline_trace.conflict_trace = conflict_trace

    # ── 获取结果 ────────────────────────────────────────────

    def finalize(self) -> PipelineTrace:
        """结束追踪，汇总 token 消耗，返回完整 PipelineTrace"""
        self._pipeline_trace.end_time = datetime.now(timezone.utc)
        # 汇总 token
        total = TokenUsage()
        for at in self._pipeline_trace.agent_traces:
            for call in at.llm_calls:
                total.prompt_tokens += call.token_usage.prompt_tokens
                total.completion_tokens += call.token_usage.completion_tokens
                total.total_tokens += call.token_usage.total_tokens
        self._pipeline_trace.total_token_usage = total
        return self._pipeline_trace

"""Trace 数据结构

记录实验运行过程中各层级的完整追踪信息。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """单次 LLM 调用的 token 消耗"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMCallTrace(BaseModel):
    """一次 LLM 调用的完整记录"""

    model: str
    messages: list[dict[str, str]] = Field(description="发送给 LLM 的完整消息列表")
    response: str = Field(description="LLM 原始响应文本")
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    temperature: float = 0.0
    cached: bool = False


class AgentTrace(BaseModel):
    """单个 agent 的执行追踪"""

    agent_id: str
    node_id: str = Field(description="所在 pipeline 节点 id")
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_content: str = ""
    output_metadata: dict[str, Any] = Field(default_factory=dict)
    llm_calls: list[LLMCallTrace] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None


class MessageTrace(BaseModel):
    """agent 间消息传递记录"""

    from_agent: str
    to_agent: str
    content: Any
    timestamp: datetime | None = None


class ConflictTrace(BaseModel):
    """冲突检测与仲裁追踪"""

    conflicts_detected: list[dict[str, Any]] = Field(default_factory=list)
    arbitration_steps: list[dict[str, Any]] = Field(default_factory=list)
    final_decision: dict[str, Any] = Field(default_factory=dict)


class PipelineTrace(BaseModel):
    """Pipeline 级别执行追踪"""

    case_id: str
    experiment_name: str
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    message_traces: list[MessageTrace] = Field(default_factory=list)
    conflict_trace: ConflictTrace | None = None
    node_execution_order: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    total_token_usage: TokenUsage = Field(default_factory=TokenUsage)

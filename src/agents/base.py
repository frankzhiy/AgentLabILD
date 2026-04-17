"""Agent 抽象基类与上下文定义"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from src.schemas.trace import LLMCallTrace

if TYPE_CHECKING:
    from src.llm.client import LLMClient
    from src.tracing.tracer import Tracer


class AgentOutput(BaseModel):
    """Agent 执行结果"""

    content: str = Field(..., description="Agent 的输出文本")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    llm_calls: list[LLMCallTrace] = Field(default_factory=list, description="本次执行的 LLM 调用记录")


@dataclass
class AgentContext:
    """Agent 执行时注入的运行上下文"""

    llm_client: LLMClient
    tracer: Tracer | None = None
    agent_config: dict = field(default_factory=dict)
    node_id: str = ""


class BaseAgent(ABC):
    """所有 agent 的抽象基类"""

    def __init__(self, agent_id: str, config: dict | None = None):
        self.agent_id = agent_id
        self.config = config or {}

    @abstractmethod
    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
        """
        执行 agent 核心逻辑。

        Args:
            input_data: 该 agent 在当前 pipeline 节点接收到的输入
            context: 运行上下文（llm_client, tracer 等注入依赖）

        Returns:
            AgentOutput: 输出内容 + 元数据 + LLM 调用记录
        """
        ...

"""编排策略抽象基类与注册表

编排策略决定 agent 之间如何协作：谁先谁后、并行还是串行、
是否有循环、是否由某个 agent 动态调度。

每种编排策略是一个独立的 .py 文件，定义如何将 agent 组装成 LangGraph。
YAML 通过 strategy 名引用，不涉及具体拓扑细节。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Type

from src.agents.base import BaseAgent
from src.communication.base import CommunicationProtocol
from src.llm.client import LLMClient
from src.tracing.tracer import Tracer

# ── 注册表 ──────────────────────────────────────────────────

ORCHESTRATION_REGISTRY: dict[str, Type["BaseOrchestration"]] = {}


def register_orchestration(name: str):
    """装饰器：将编排策略注册到全局注册表

    使用方式：
        @register_orchestration("sequential_then_synthesize")
        class SequentialThenSynthesize(BaseOrchestration):
            ...
    """
    def decorator(cls: Type[BaseOrchestration]) -> Type[BaseOrchestration]:
        if name in ORCHESTRATION_REGISTRY:
            raise ValueError(f"Orchestration '{name}' 已注册，不能重复注册")
        ORCHESTRATION_REGISTRY[name] = cls
        return cls
    return decorator


def get_orchestration_class(name: str) -> Type["BaseOrchestration"]:
    """根据注册名获取编排策略类"""
    if name not in ORCHESTRATION_REGISTRY:
        available = ", ".join(ORCHESTRATION_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Orchestration '{name}' 未注册。可用: {available}")
    return ORCHESTRATION_REGISTRY[name]


# ── 抽象基类 ────────────────────────────────────────────────

class BaseOrchestration(ABC):
    """编排策略抽象基类

    子类通过实现 build_graph 方法，定义 agent 之间的协作拓扑。
    """

    def __init__(self, parameters: dict | None = None):
        self.parameters = parameters or {}

    @abstractmethod
    def build_graph(
        self,
        agents: dict[str, BaseAgent],
        protocol: CommunicationProtocol,
        llm_client: LLMClient,
        tracer_factory: Callable[[], Tracer | None],
    ) -> Any:
        """构建并编译 LangGraph StateGraph

        Args:
            agents: {agent_id: agent_instance} 所有可用 agent
            protocol: 通信协议实例
            llm_client: LLM 客户端
            tracer_factory: 返回当前 Tracer 的可调用对象

        Returns:
            编译后的 LangGraph CompiledGraph
        """
        ...

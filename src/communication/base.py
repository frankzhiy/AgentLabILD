"""通信协议抽象基类与注册表"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from src.agents.base import AgentOutput
from src.schemas.state import GraphState

# ── 抽象接口 ────────────────────────────────────────────────

class CommunicationProtocol(ABC):
    """定义 agent 间如何交换信息"""

    def __init__(self, parameters: dict | None = None):
        self.parameters = parameters or {}

    @abstractmethod
    def prepare_input(self, agent_id: str, state: GraphState) -> dict:
        """从当前 state 中提取该 agent 需要的输入信息"""
        ...

    @abstractmethod
    def process_output(self, agent_id: str, output: AgentOutput, state: GraphState) -> dict:
        """将 agent 的输出写回 state，返回 state 更新 dict"""
        ...


# ── 注册表 ──────────────────────────────────────────────────

PROTOCOL_REGISTRY: dict[str, Type[CommunicationProtocol]] = {}


def register_protocol(name: str):
    """装饰器：注册通信协议"""
    def decorator(cls: Type[CommunicationProtocol]) -> Type[CommunicationProtocol]:
        if name in PROTOCOL_REGISTRY:
            raise ValueError(f"Protocol '{name}' 已注册")
        PROTOCOL_REGISTRY[name] = cls
        return cls
    return decorator


def get_protocol_class(name: str) -> Type[CommunicationProtocol]:
    if name not in PROTOCOL_REGISTRY:
        available = ", ".join(PROTOCOL_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Protocol '{name}' 未注册。可用: {available}")
    return PROTOCOL_REGISTRY[name]

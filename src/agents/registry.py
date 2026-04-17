"""Agent 注册表（Registry Pattern）"""

from __future__ import annotations

from typing import Type

from src.agents.base import BaseAgent

# 全局 agent 注册表：name → class
AGENT_REGISTRY: dict[str, Type[BaseAgent]] = {}


def register_agent(name: str):
    """装饰器：将 agent 类注册到全局注册表

    使用方式：
        @register_agent("pulmonologist")
        class PulmonologistAgent(LLMAgent):
            ...
    """
    def decorator(cls: Type[BaseAgent]) -> Type[BaseAgent]:
        if name in AGENT_REGISTRY:
            raise ValueError(f"Agent '{name}' 已注册，不能重复注册")
        AGENT_REGISTRY[name] = cls
        return cls
    return decorator


def get_agent_class(name: str) -> Type[BaseAgent]:
    """根据注册名获取 agent 类"""
    if name not in AGENT_REGISTRY:
        available = ", ".join(AGENT_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Agent '{name}' 未注册。可用: {available}")
    return AGENT_REGISTRY[name]

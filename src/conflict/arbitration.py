"""仲裁策略抽象基类与注册表"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel, Field

from src.agents.base import AgentOutput
from src.conflict.detection import Conflict


class ArbitrationResult(BaseModel):
    """仲裁结果"""

    decision: str = Field(description="最终决策")
    reasoning: str = Field(default="", description="决策理由")
    trace: list[dict[str, Any]] = Field(default_factory=list, description="仲裁过程追踪")


@dataclass
class ArbitrationContext:
    """仲裁的运行上下文"""

    config: dict = field(default_factory=dict)


class ArbitrationStrategy(ABC):
    """仲裁策略抽象接口"""

    def __init__(self, parameters: dict | None = None):
        self.parameters = parameters or {}

    @abstractmethod
    def arbitrate(
        self,
        conflicts: list[Conflict],
        agent_outputs: dict[str, AgentOutput],
        context: ArbitrationContext,
    ) -> ArbitrationResult:
        """解决检测到的冲突，返回仲裁结果"""
        ...


# ── 注册表 ──────────────────────────────────────────────────

ARBITRATION_REGISTRY: dict[str, Type[ArbitrationStrategy]] = {}


def register_arbitration(name: str):
    def decorator(cls: Type[ArbitrationStrategy]) -> Type[ArbitrationStrategy]:
        if name in ARBITRATION_REGISTRY:
            raise ValueError(f"Arbitration '{name}' 已注册")
        ARBITRATION_REGISTRY[name] = cls
        return cls
    return decorator


def get_arbitration_class(name: str) -> Type[ArbitrationStrategy]:
    if name not in ARBITRATION_REGISTRY:
        available = ", ".join(ARBITRATION_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Arbitration '{name}' 未注册。可用: {available}")
    return ARBITRATION_REGISTRY[name]

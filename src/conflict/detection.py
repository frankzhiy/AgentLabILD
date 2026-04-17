"""冲突检测抽象基类与注册表"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel, Field

from src.agents.base import AgentOutput


class Conflict(BaseModel):
    """检测到的一个冲突"""

    agents_involved: list[str] = Field(description="冲突涉及的 agent id 列表")
    description: str = Field(description="冲突描述")
    evidence: dict[str, Any] = Field(default_factory=dict, description="支撑冲突判定的证据")


@dataclass
class DetectionContext:
    """冲突检测的运行上下文"""

    config: dict = field(default_factory=dict)


class ConflictDetector(ABC):
    """冲突检测抽象接口"""

    def __init__(self, parameters: dict | None = None):
        self.parameters = parameters or {}

    @abstractmethod
    def detect(
        self,
        agent_outputs: dict[str, AgentOutput],
        context: DetectionContext,
    ) -> list[Conflict]:
        """检测 agent 输出中的冲突"""
        ...


# ── 注册表 ──────────────────────────────────────────────────

DETECTOR_REGISTRY: dict[str, Type[ConflictDetector]] = {}


def register_detector(name: str):
    def decorator(cls: Type[ConflictDetector]) -> Type[ConflictDetector]:
        if name in DETECTOR_REGISTRY:
            raise ValueError(f"Detector '{name}' 已注册")
        DETECTOR_REGISTRY[name] = cls
        return cls
    return decorator


def get_detector_class(name: str) -> Type[ConflictDetector]:
    if name not in DETECTOR_REGISTRY:
        available = ", ".join(DETECTOR_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Detector '{name}' 未注册。可用: {available}")
    return DETECTOR_REGISTRY[name]

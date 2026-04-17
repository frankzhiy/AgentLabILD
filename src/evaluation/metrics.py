"""评估指标抽象接口与注册表"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from src.schemas.results import CaseResult


class BaseMetric(ABC):
    """评估指标抽象基类"""

    @abstractmethod
    def compute(self, results: list[CaseResult]) -> dict[str, Any]:
        """计算评估指标，返回 {指标名: 值} 字典"""
        ...


# ── 注册表 ──────────────────────────────────────────────────

METRIC_REGISTRY: dict[str, Type[BaseMetric]] = {}


def register_metric(name: str):
    def decorator(cls: Type[BaseMetric]) -> Type[BaseMetric]:
        if name in METRIC_REGISTRY:
            raise ValueError(f"Metric '{name}' 已注册")
        METRIC_REGISTRY[name] = cls
        return cls
    return decorator


def get_metric_class(name: str) -> Type[BaseMetric]:
    if name not in METRIC_REGISTRY:
        available = ", ".join(METRIC_REGISTRY.keys()) or "(空)"
        raise KeyError(f"Metric '{name}' 未注册。可用: {available}")
    return METRIC_REGISTRY[name]

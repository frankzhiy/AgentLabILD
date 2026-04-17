"""实验结果与评估结果数据结构"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.trace import PipelineTrace, TokenUsage


class CaseResult(BaseModel):
    """单个病例的运行结果"""

    case_id: str
    final_output: str = ""
    ground_truth_diagnosis: str | None = None
    trace: PipelineTrace | None = None


class ExperimentResult(BaseModel):
    """一次完整实验的结果"""

    experiment_name: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict, description="实验配置快照")
    case_results: list[CaseResult] = Field(default_factory=list)
    total_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    metrics: dict[str, Any] = Field(default_factory=dict, description="汇总评估指标")

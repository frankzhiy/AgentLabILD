"""实验配置数据模型

对应 configs/experiments/ 下的 YAML 文件，完整描述一次实验的所有参数。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── 编排策略配置 ────────────────────────────────────────────
class OrchestrationConfig(BaseModel):
    """编排策略配置：决定 agent 之间如何协作"""

    strategy: str = Field(..., description="注册表中的编排策略名，如 'sequential_then_synthesize'")
    parameters: dict = Field(default_factory=dict, description="传递给编排策略的参数")


# ── 通信协议配置 ────────────────────────────────────────────
class CommunicationConfig(BaseModel):
    protocol: str = Field("blackboard", description="注册表中的协议名")
    parameters: dict = Field(default_factory=dict)


# ── 冲突与仲裁配置 ──────────────────────────────────────────
class DetectionConfig(BaseModel):
    strategy: str = Field("none", description="注册表中的冲突检测策略名")
    parameters: dict = Field(default_factory=dict)


class ArbitrationConfig(BaseModel):
    strategy: str = Field("none", description="注册表中的仲裁策略名")
    parameters: dict = Field(default_factory=dict)


class ConflictConfig(BaseModel):
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    arbitration: ArbitrationConfig = Field(default_factory=ArbitrationConfig)


# ── 评估配置 ────────────────────────────────────────────────
class EvaluationConfig(BaseModel):
    metrics: list[str] = Field(default_factory=list)


# ── 追踪配置 ────────────────────────────────────────────────
class TrackingConfig(BaseModel):
    save_full_traces: bool = True
    save_token_usage: bool = True
    cache_llm_responses: bool = True


# ── 数据配置 ────────────────────────────────────────────────
class DataConfig(BaseModel):
    cases: str = Field(..., description="病例数据集 JSONL 路径")
    ground_truth: str | None = Field(None, description="金标准标注 JSONL 路径（可选）")


# ── 顶层实验配置 ────────────────────────────────────────────
class ExperimentMeta(BaseModel):
    name: str
    description: str = ""
    seed: int = 42


class ExperimentConfig(BaseModel):
    """一个完整实验的配置——对应一个 YAML 文件"""

    experiment: ExperimentMeta
    data: DataConfig
    agents: list[str] = Field(..., description="注册表中的 agent 名列表，如 ['pulmonologist', 'radiologist', 'moderator']")
    orchestration: OrchestrationConfig
    communication: CommunicationConfig = Field(default_factory=CommunicationConfig)
    conflict: ConflictConfig = Field(default_factory=ConflictConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)

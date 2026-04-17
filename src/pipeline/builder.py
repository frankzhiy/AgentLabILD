"""从实验配置构建 LangGraph 运行图

核心函数：build_graph_from_config(config, llm_client, tracer_factory) → CompiledGraph

图的拓扑结构由编排策略（orchestration strategy）决定，
本模块负责实例化 agent、通信协议和编排策略，然后委托编排策略构建图。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.agents.base import BaseAgent
from src.agents.registry import get_agent_class
from src.communication.base import get_protocol_class
from src.llm.client import LLMClient
from src.orchestration.base import get_orchestration_class
from src.schemas.experiment import ExperimentConfig
from src.tracing.tracer import Tracer

logger = logging.getLogger(__name__)


# ── 实例化 Agent ────────────────────────────────────────────

def _build_agents(config: ExperimentConfig) -> dict[str, BaseAgent]:
    """根据配置实例化所有 agent，返回 {agent_id: agent_instance}

    agent 名即注册表中的 key，每个 agent 的配置（model、temperature 等）
    由其自身 .py 文件中的 AGENT_CONFIG 管理，不再由 YAML 传入。
    """
    agents: dict[str, BaseAgent] = {}
    for agent_name in config.agents:
        agent_cls = get_agent_class(agent_name)
        agent = agent_cls(agent_id=agent_name)
        agents[agent_name] = agent
    return agents


# ── 构建图 ──────────────────────────────────────────────────

def build_graph_from_config(
    config: ExperimentConfig,
    llm_client: LLMClient,
    tracer_factory: Callable[[], Tracer | None],
) -> Any:
    """从实验配置构建编译后的 LangGraph

    流程：
        1. 实例化所有 agent
        2. 实例化通信协议
        3. 实例化编排策略
        4. 委托编排策略构建图拓扑

    Args:
        config: 完整实验配置
        llm_client: LLM 客户端实例
        tracer_factory: 返回当前 Tracer 的可调用对象

    Returns:
        编译后的 LangGraph CompiledGraph，可通过 .invoke(initial_state) 运行
    """
    # 1. 实例化所有 agent
    agents = _build_agents(config)

    # 2. 实例化通信协议
    import src.communication.blackboard  # noqa: F401  # 触发 @register_protocol
    protocol_cls = get_protocol_class(config.communication.protocol)
    protocol = protocol_cls(parameters=config.communication.parameters)

    # 3. 实例化编排策略并构建图
    import src.orchestration.sequential  # noqa: F401  # 触发 @register_orchestration
    orchestration_cls = get_orchestration_class(config.orchestration.strategy)
    orchestration = orchestration_cls(parameters=config.orchestration.parameters)

    compiled = orchestration.build_graph(
        agents=agents,
        protocol=protocol,
        llm_client=llm_client,
        tracer_factory=tracer_factory,
    )

    logger.info("Pipeline 构建完成（编排策略: %s）", config.orchestration.strategy)
    return compiled

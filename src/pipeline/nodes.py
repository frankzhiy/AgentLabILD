"""通用节点工厂：将 Agent 实例包装为 LangGraph 节点函数

# -------------------------------------------------------
# 设计说明：
#   每个 pipeline 节点可以包含 1~N 个 agent。
#   - 单 agent 节点：直接执行 agent 并更新 state
#   - 多 agent 节点：通过 LangGraph Send API 并行 fan-out，
#     每个 agent 独立执行后合并结果
#
# TODO（后续研究扩展点）：
#   1. 当前 fan-out 后每个 agent 子节点独立执行完返回。
#      如需 agent 间在同一节点内交互（如辩论），需要不同的节点实现
#   2. 当前通过 CommunicationProtocol.prepare_input 获取输入。
#      如果切换通信协议，节点逻辑不需要改——只需注册新 protocol
#   3. 错误处理：当前 agent 执行异常会记录到 trace 并继续。
#      如需 fail-fast 或重试策略，修改 _execute_single_agent
# -------------------------------------------------------
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import AgentContext, AgentOutput, BaseAgent
from src.communication.base import CommunicationProtocol
from src.llm.client import LLMClient
from src.schemas.state import GraphState
from src.tracing.tracer import Tracer

logger = logging.getLogger(__name__)


def _execute_single_agent(
    agent: BaseAgent,
    protocol: CommunicationProtocol,
    llm_client: LLMClient,
    tracer: Tracer | None,
    node_id: str,
    state: GraphState,
) -> dict[str, Any]:
    """执行单个 agent 并返回 state 更新 dict

    这是所有节点执行的原子操作。
    """
    # 1. 通信协议：从 state 提取输入
    input_data = protocol.prepare_input(agent.agent_id, state)

    # 2. 追踪：记录开始
    agent_trace = None
    if tracer:
        agent_trace = tracer.start_agent(agent.agent_id, node_id, input_data)

    # 3. 执行 agent
    context = AgentContext(
        llm_client=llm_client,
        tracer=tracer,
        agent_config=agent.config,
        node_id=node_id,
    )
    error_msg = None
    output: AgentOutput | None = None
    try:
        output = agent.execute(input_data, context)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error("Agent '%s' 执行失败: %s", agent.agent_id, error_msg)
        output = AgentOutput(content=f"[ERROR] {error_msg}")

    # 4. 追踪：记录完成
    if tracer and agent_trace:
        tracer.finish_agent(
            agent_trace,
            output_content=output.content,
            output_metadata=output.metadata,
            llm_calls=output.llm_calls,
            error=error_msg,
        )

    # 5. 通信协议：将输出写回 state
    state_update = protocol.process_output(agent.agent_id, output, state)

    # 附加 agent trace 到 state（供 pipeline 汇总）
    if agent_trace:
        state_update["agent_traces"] = [agent_trace]

    return state_update


def make_node_function(
    agents: list[BaseAgent],
    protocol: CommunicationProtocol,
    llm_client: LLMClient,
    tracer_factory,
    node_id: str,
):
    """为一个 pipeline 节点创建 LangGraph 节点函数

    Args:
        agents: 该节点包含的 agent 列表（多个则顺序执行，并行通过 fan-out 在 builder 层处理）
        protocol: 通信协议实例
        llm_client: LLM 客户端
        tracer_factory: 返回当前 Tracer 的可调用对象（lambda: tracer）
        node_id: 节点 id

    Returns:
        一个接受 GraphState 返回 state 更新 dict 的函数

    # -------------------------------------------------------
    # TODO（后续研究扩展点）：
    #   当前多 agent 节点通过 builder 层的 Send fan-out 并行执行。
    #   如果需要节点内的 agent 串行依赖（如 A 的输出喂给 B），
    #   可以在这里实现串行链逻辑。
    # -------------------------------------------------------
    """

    def node_fn(state: GraphState) -> dict[str, Any]:
        tracer = tracer_factory()
        merged_update: dict[str, Any] = {}
        for agent in agents:
            update = _execute_single_agent(
                agent, protocol, llm_client, tracer, node_id, state,
            )
            # 合并多个 agent 的 state 更新
            for key, value in update.items():
                if key in merged_update and isinstance(value, dict):
                    merged_update[key] = {**merged_update[key], **value}
                elif key in merged_update and isinstance(value, list):
                    merged_update[key] = merged_update[key] + value
                else:
                    merged_update[key] = value
        return merged_update

    return node_fn

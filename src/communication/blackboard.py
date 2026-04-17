"""Blackboard 通信协议（baseline 参考实现）

所有 agent 共享同一个"黑板"（即 GraphState），每个 agent 可以看到：
  - 原始病例文本
  - 所有已完成 agent 的输出

这是最简单的通信方式。后续研究中你可以实现其他协议替换它：
  - 点对点消息协议（agent 之间定向通信）
  - 约束式结构化通信（只传递特定格式的信息）
  - 迭代辩论协议（多轮交换）

# -------------------------------------------------------
# TODO（后续研究扩展点）：
#   1. prepare_input 当前将全部 agent_outputs 传给每个 agent。
#      如需信息隔离（如某些 agent 只能看到特定 agent 的输出），在这里过滤
#   2. process_output 当前只写入文本 content。
#      如需结构化输出（如 claim-evidence 对），修改写入逻辑
# -------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

from src.agents.base import AgentOutput
from src.communication.base import CommunicationProtocol, register_protocol
from src.schemas.state import GraphState


@register_protocol("blackboard")
class BlackboardProtocol(CommunicationProtocol):
    """黑板通信协议：所有 agent 共享全部信息"""

    def prepare_input(self, agent_id: str, state: GraphState) -> dict:
        """从 state 中提取该 agent 的输入

        返回的 dict 将作为 agent.execute(input_data, ...) 的 input_data。
        """
        return {
            "case_text": state.get("case_text", ""),
            "case_id": state.get("case_id", ""),
            "agent_outputs": dict(state.get("agent_outputs", {})),
        }

    def process_output(self, agent_id: str, output: AgentOutput, state: GraphState) -> dict:
        """将 agent 输出写回 state

        返回的 dict 会被 LangGraph reducer 合并进 state。
        """
        return {
            "agent_outputs": {agent_id: output.content},
        }

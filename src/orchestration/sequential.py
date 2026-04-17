"""顺序分析 → 综合 编排策略

最基础的 MDT 编排：先让专科 agent 分析病例，再由综合者汇总。

YAML 使用方式：
    orchestration:
      strategy: "sequential_then_synthesize"
      parameters:
        specialists: ["pulmonologist", "radiologist"]
        synthesizer: "moderator"

如果不提供 synthesizer，则所有 agent 在同一步执行，没有综合步骤。
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from src.orchestration.base import BaseOrchestration, register_orchestration
from src.pipeline.nodes import make_node_function
from src.schemas.state import GraphState

logger = logging.getLogger(__name__)


@register_orchestration("sequential_then_synthesize")
class SequentialThenSynthesize(BaseOrchestration):
    """先专科分析，再综合诊断

    参数（通过 self.parameters 传入）：
        specialists: list[str] — 专科 agent 注册名列表
        synthesizer: str       — 综合分析 agent 注册名（可选，为空则无综合步骤）
    """

    def build_graph(self, agents, protocol, llm_client, tracer_factory):
        specialists = self.parameters.get("specialists", [])
        synthesizer = self.parameters.get("synthesizer", "")

        graph = StateGraph(GraphState)

        # 专科分析节点
        specialist_agents = [agents[aid] for aid in specialists]
        specialist_fn = make_node_function(
            agents=specialist_agents,
            protocol=protocol,
            llm_client=llm_client,
            tracer_factory=tracer_factory,
            node_id="specialist_analysis",
        )
        graph.add_node("specialist_analysis", specialist_fn)
        graph.add_edge(START, "specialist_analysis")

        # 如果有综合者，添加综合节点
        if synthesizer:
            synth_agent = agents[synthesizer]
            synth_fn = make_node_function(
                agents=[synth_agent],
                protocol=protocol,
                llm_client=llm_client,
                tracer_factory=tracer_factory,
                node_id="final_synthesis",
            )
            graph.add_node("final_synthesis", synth_fn)
            graph.add_edge("specialist_analysis", "final_synthesis")
            graph.add_edge("final_synthesis", END)
        else:
            graph.add_edge("specialist_analysis", END)

        compiled = graph.compile()
        node_count = 2 if synthesizer else 1
        logger.info("编排策略 sequential_then_synthesize：%d 个节点", node_count)
        return compiled

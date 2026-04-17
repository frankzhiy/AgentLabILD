"""MDT 主持人 Agent

综合各专科意见，推动达成诊断共识。
"""

from __future__ import annotations

from src.agents.llm_agent import LLMAgent
from src.agents.registry import register_agent

# ── Agent 配置 ──────────────────────────────────────────────
AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/moderator_synthesis.md",
    "model": "gpt-4o",
    "temperature": 0.2,
}


@register_agent("moderator")
class ModeratorAgent(LLMAgent):
    """MDT 主持人：综合各专科分析，形成最终诊断共识"""

    def __init__(self, agent_id: str, config: dict | None = None):
        merged = {**AGENT_CONFIG, **(config or {})}
        super().__init__(agent_id, merged)

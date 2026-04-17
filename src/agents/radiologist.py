"""影像科医生 Agent

基于 HRCT 文字报告分析影像学模式和特征。
"""

from __future__ import annotations

from src.agents.llm_agent import LLMAgent
from src.agents.registry import register_agent

# ── Agent 配置 ──────────────────────────────────────────────
AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/radiologist_analysis.md",
    "model": "gpt-4o",
    "temperature": 0.3,
}


@register_agent("radiologist")
class RadiologistAgent(LLMAgent):
    """影像科医生：分析 HRCT 模式、病变分布、特征性征象"""

    def __init__(self, agent_id: str, config: dict | None = None):
        merged = {**AGENT_CONFIG, **(config or {})}
        super().__init__(agent_id, merged)

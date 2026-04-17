"""呼吸科医生 Agent

基于临床症状、肺功能、暴露史等综合分析 ILD 病例。
"""

from __future__ import annotations

from src.agents.llm_agent import LLMAgent
from src.agents.registry import register_agent

# ── Agent 配置 ──────────────────────────────────────────────
AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/pulmonologist_analysis.md",
    "model": "gpt-4o",
    "temperature": 0.3,
}


@register_agent("pulmonologist")
class PulmonologistAgent(LLMAgent):
    """呼吸科医生：分析临床症状、吸烟史、职业暴露、肺功能等"""

    def __init__(self, agent_id: str, config: dict | None = None):
        merged = {**AGENT_CONFIG, **(config or {})}
        super().__init__(agent_id, merged)

"""测试 Agent 注册表"""

import pytest

from src.agents.base import BaseAgent, AgentContext, AgentOutput
from src.agents.registry import AGENT_REGISTRY, register_agent, get_agent_class


def test_register_and_retrieve():
    """注册一个 agent 并通过名字取回"""

    @register_agent("_test_dummy")
    class DummyAgent(BaseAgent):
        def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
            return AgentOutput(content="dummy")

    cls = get_agent_class("_test_dummy")
    assert cls is DummyAgent

    # 清理
    del AGENT_REGISTRY["_test_dummy"]


def test_get_unregistered_raises():
    with pytest.raises(KeyError, match="未注册"):
        get_agent_class("nonexistent_agent_xyz")

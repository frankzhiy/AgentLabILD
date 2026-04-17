"""测试 Pipeline Builder：从 YAML 配置构建 LangGraph 图

使用 mock LLM client，不产生真实 API 调用。
"""

import yaml

from src.agents.base import AgentContext, AgentOutput, BaseAgent
from src.agents.registry import AGENT_REGISTRY, register_agent
from src.llm.client import LLMClient
from src.pipeline.builder import build_graph_from_config
from src.schemas.experiment import ExperimentConfig
from src.tracing.tracer import Tracer


# ── 用于测试的 mock agent ─────────────────────────────────
# 注意：这是专门为跑通 pipeline 测试而写的 mock。
# 注册三个独立的测试 agent 名，模拟实际 agent 各自有独立注册名的模式。

for _name in ("_test_agent_a", "_test_agent_b", "_test_agent_c", "_test_solo_agent"):
    if _name not in AGENT_REGISTRY:
        def _make_cls(name):
            @register_agent(name)
            class _EchoAgent(BaseAgent):
                """测试用 echo agent：直接返回收到的 case_text 摘要"""
                def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
                    prior = input_data.get("agent_outputs", {})
                    summary = f"[{self.agent_id}] analyzed case. Prior agents: {list(prior.keys())}"
                    return AgentOutput(content=summary)
            return _EchoAgent
        _make_cls(_name)


# ── 测试用最小配置 ─────────────────────────────────────────

MINIMAL_CONFIG_YAML = """
experiment:
  name: test_pipeline
  seed: 42

data:
  cases: "data/cases/demo_2cases.jsonl"

agents:
  - "_test_agent_a"
  - "_test_agent_b"
  - "_test_agent_c"

orchestration:
  strategy: "sequential_then_synthesize"
  parameters:
    specialists: ["_test_agent_a", "_test_agent_b"]
    synthesizer: "_test_agent_c"
"""


def _make_dummy_llm_client() -> LLMClient:
    """创建一个不会真正调用 API 的 LLM client（测试中 echo agent 不使用它）"""
    return LLMClient(api_key="test-key", cache=None)


def test_build_graph_from_config():
    """验证能从配置成功构建 LangGraph 并编译"""
    raw = yaml.safe_load(MINIMAL_CONFIG_YAML)
    config = ExperimentConfig(**raw)
    client = _make_dummy_llm_client()

    compiled = build_graph_from_config(
        config=config,
        llm_client=client,
        tracer_factory=lambda: None,
    )
    # 编译后的图应该有 invoke 方法
    assert hasattr(compiled, "invoke")


def test_pipeline_execution():
    """验证 pipeline 能端到端运行并产出正确的 state"""
    raw = yaml.safe_load(MINIMAL_CONFIG_YAML)
    config = ExperimentConfig(**raw)
    client = _make_dummy_llm_client()
    tracer = Tracer(case_id="test", experiment_name="test")

    compiled = build_graph_from_config(
        config=config,
        llm_client=client,
        tracer_factory=lambda: tracer,
    )

    # 运行
    initial_state = {
        "case_text": "Test patient: 65yo male with dyspnea",
        "case_id": "test_001",
        "agent_outputs": {},
        "agent_traces": [],
        "message_traces": [],
    }
    final_state = compiled.invoke(initial_state)

    # 验证：3 个 agent 都产出了输出
    outputs = final_state.get("agent_outputs", {})
    assert "_test_agent_a" in outputs
    assert "_test_agent_b" in outputs
    assert "_test_agent_c" in outputs

    # 验证：step2 的 _test_agent_c 应该能看到 step1 的输出
    assert "_test_agent_a" in outputs["_test_agent_c"] or "_test_agent_b" in outputs["_test_agent_c"]


def test_pipeline_with_single_agent_nodes():
    """测试每个节点只有一个 agent 的简单串行拓扑"""
    config_yaml = """
experiment:
  name: test_serial
  seed: 42
data:
  cases: "data/cases/demo_2cases.jsonl"
agents:
  - "_test_solo_agent"
orchestration:
  strategy: "sequential_then_synthesize"
  parameters:
    specialists: ["_test_solo_agent"]
"""
    raw = yaml.safe_load(config_yaml)
    config = ExperimentConfig(**raw)
    client = _make_dummy_llm_client()

    compiled = build_graph_from_config(
        config=config,
        llm_client=client,
        tracer_factory=lambda: None,
    )

    result = compiled.invoke({
        "case_text": "Simple test case",
        "case_id": "simple_001",
        "agent_outputs": {},
        "agent_traces": [],
        "message_traces": [],
    })
    assert "_test_solo_agent" in result.get("agent_outputs", {})

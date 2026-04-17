"""端到端测试：Runner + 数据加载 + Pipeline

使用 mock agent 代替真实 LLM 调用，验证整个流程能跑通。
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.runner import ExperimentRunner, load_cases, load_ground_truth, load_experiment_config
from src.schemas.case import CaseData, GroundTruth


# ── 数据加载测试 ────────────────────────────────────────────

def test_load_cases():
    """加载 demo 病例数据"""
    cases = load_cases("data/cases/demo_2cases.jsonl")
    assert len(cases) == 2
    assert cases[0].case_id == "demo_001"
    assert cases[1].case_id == "demo_002"
    assert cases[0].basic_clinical_background.age == "65"


def test_load_ground_truth():
    """加载 demo 金标准"""
    gt = load_ground_truth("data/ground_truth/demo_2cases_labels.jsonl")
    assert "demo_001" in gt
    assert gt["demo_001"].diagnosis == "IPF"
    assert gt["demo_002"].diagnosis == "RA-ILD"


def test_load_experiment_config():
    """加载 baseline 实验配置"""
    config = load_experiment_config("configs/experiments/baseline_3agent.yaml")
    assert config.experiment.name == "baseline_3agent"
    assert len(config.agents) == 3
    assert config.orchestration.strategy == "sequential_then_synthesize"


# ── 端到端测试（使用 mock agent） ───────────────────────────

def _make_mock_config(tmp_path: Path) -> Path:
    """创建一个使用 echo agent 的临时实验配置"""
    # 确保 echo agent 已注册
    from src.agents.registry import AGENT_REGISTRY
    from src.agents.base import BaseAgent, AgentContext, AgentOutput
    from src.agents.registry import register_agent

    for _name in ("_test_runner_agent_x", "_test_runner_agent_y"):
        if _name not in AGENT_REGISTRY:
            def _make_cls(name):
                @register_agent(name)
                class _EchoAgent(BaseAgent):
                    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
                        prior = input_data.get("agent_outputs", {})
                        return AgentOutput(
                            content=f"[{self.agent_id}] output. Prior: {list(prior.keys())}"
                        )
                return _EchoAgent
            _make_cls(_name)

    config = {
        "experiment": {"name": "e2e_test", "seed": 42},
        "data": {"cases": "data/cases/demo_2cases.jsonl",
                 "ground_truth": "data/ground_truth/demo_2cases_labels.jsonl"},
        "agents": ["_test_runner_agent_x", "_test_runner_agent_y"],
        "orchestration": {
            "strategy": "sequential_then_synthesize",
            "parameters": {
                "specialists": ["_test_runner_agent_x"],
                "synthesizer": "_test_runner_agent_y",
            },
        },
        "tracking": {"save_full_traces": True, "save_token_usage": True,
                      "cache_llm_responses": False},
    }
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(yaml.dump(config, allow_unicode=True), "utf-8")
    return config_path


def test_runner_end_to_end(tmp_path: Path):
    """端到端运行：加载配置 → 构建 pipeline → 运行 2 个病例 → 保存结果"""
    config_path = _make_mock_config(tmp_path)
    output_dir = tmp_path / "output"

    runner = ExperimentRunner(
        config_path=str(config_path),
        output_dir=str(output_dir),
        api_key="test-key",  # echo agent 不使用 API
    )

    result = runner.run()

    # 验证结果
    assert result.experiment_name == "e2e_test"
    assert len(result.case_results) == 2

    # 每个病例都应该有输出
    for cr in result.case_results:
        assert cr.final_output != ""
        assert cr.case_id in ("demo_001", "demo_002")

    # 金标准应该被附加
    assert result.case_results[0].ground_truth_diagnosis == "IPF"
    assert result.case_results[1].ground_truth_diagnosis == "RA-ILD"

    # 每个病例都应该有 trace
    for cr in result.case_results:
        assert cr.trace is not None
        assert len(cr.trace.agent_traces) == 2  # _test_runner_agent_x + _test_runner_agent_y

    # 输出文件应该存在
    run_dirs = list(output_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "config_snapshot.yaml").exists()
    assert (run_dir / "raw_outputs.jsonl").exists()
    assert (run_dir / "traces").is_dir()

    # 验证 raw_outputs.jsonl 内容
    lines = (run_dir / "raw_outputs.jsonl").read_text("utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["case_id"] == "demo_001"
    assert first["ground_truth_diagnosis"] == "IPF"

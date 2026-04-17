"""测试所有核心 schemas 的基本功能"""

import json
import yaml

from src.schemas.case import CaseData, GroundTruth
from src.schemas.experiment import ExperimentConfig
from src.schemas.trace import AgentTrace, PipelineTrace, TokenUsage
from src.schemas.results import CaseResult, ExperimentResult


# ── Case ────────────────────────────────────────────────────

def test_case_data_minimal():
    """最小字段创建"""
    case = CaseData(case_id="test_001")
    assert case.case_id == "test_001"
    assert case.basic_clinical_background is None


def test_case_data_full():
    """嵌套字段创建与 to_text"""
    case = CaseData(
        case_id="test_002",
        basic_clinical_background={
            "age": "65",
            "sex": "male",
            "smoking_history": {
                "smoking_status": "Former smoker",
                "smoking_description": "30 pack-years, quit 5 years ago",
            },
        },
        symptoms_and_disease_course={
            "chief_complaint": "Progressive dyspnea for 2 years",
        },
        imaging={
            "summary_of_chest_ct_or_hrct": "Bilateral subpleural reticulation with honeycombing",
            "imaging_pattern_tendency": {
                "uip_pattern_tendency": "Definite UIP pattern",
            },
        },
    )
    assert case.basic_clinical_background.age == "65"
    text = case.to_text()
    assert "Basic Clinical Background" in text
    assert "Imaging" in text
    assert "65" in text


def test_ground_truth():
    gt = GroundTruth(case_id="test_001", diagnosis="IPF", confidence=0.9)
    assert gt.diagnosis == "IPF"


# ── ExperimentConfig ────────────────────────────────────────

MINIMAL_EXPERIMENT_YAML = """
experiment:
  name: test_exp
  description: "unit test"
  seed: 42

data:
  cases: "data/cases/test.jsonl"

agents:
  - "pulmonologist"

orchestration:
  strategy: "sequential_then_synthesize"
  parameters:
    specialists: ["pulmonologist"]
"""


def test_experiment_config_from_yaml():
    """从 YAML 解析实验配置"""
    raw = yaml.safe_load(MINIMAL_EXPERIMENT_YAML)
    config = ExperimentConfig(**raw)
    assert config.experiment.name == "test_exp"
    assert len(config.agents) == 1
    assert config.agents[0] == "pulmonologist"
    assert config.orchestration.strategy == "sequential_then_synthesize"
    assert config.orchestration.parameters["specialists"] == ["pulmonologist"]


def test_experiment_config_defaults():
    """默认值填充"""
    raw = yaml.safe_load(MINIMAL_EXPERIMENT_YAML)
    config = ExperimentConfig(**raw)
    # 通信协议默认 blackboard
    assert config.communication.protocol == "blackboard"
    # 冲突检测默认 none
    assert config.conflict.detection.strategy == "none"
    # 追踪默认开启
    assert config.tracking.save_full_traces is True


# ── Trace ───────────────────────────────────────────────────

def test_token_usage():
    t = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert t.total_tokens == 150


def test_pipeline_trace_serialization():
    """验证 PipelineTrace 可序列化为 JSON"""
    trace = PipelineTrace(case_id="t1", experiment_name="exp1")
    data = trace.model_dump(mode="json")
    json_str = json.dumps(data)
    assert "t1" in json_str


# ── Results ─────────────────────────────────────────────────

def test_case_result():
    r = CaseResult(case_id="c1", final_output="IPF")
    assert r.final_output == "IPF"


def test_experiment_result():
    r = ExperimentResult(experiment_name="exp1")
    assert r.case_results == []

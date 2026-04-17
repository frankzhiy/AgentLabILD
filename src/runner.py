"""实验运行器

加载配置 → 构建 pipeline → 遍历病例 → 保存 trace 和原始输出

# -------------------------------------------------------
# 设计说明：
#   Runner 是实验的顶层入口。它负责：
#   1. 解析 YAML 配置文件
#   2. 初始化 LLM 客户端（含缓存）
#   3. 加载病例数据集
#   4. 对每个病例：构建 Tracer → 运行 pipeline → 收集结果
#   5. 保存所有输出（trace、raw outputs、config snapshot）
#
# TODO（后续研究扩展点）：
#   1. 评估集成：当前只保存原始输出，不计算评估指标。
#      Phase 2 实现评估指标后，在 run() 末尾添加评估逻辑
#   2. 批量并行：当前逐病例串行运行。如需并行处理多个病例
#      （如用 asyncio 或 multiprocessing），修改 _run_single_case 的调用方式
#   3. 断点续跑：当前不支持断点续跑。如需支持（如大批量运行中断后恢复），
#      可以检查已有结果文件跳过已完成的病例
#   4. 进度报告：当前用 logging 输出进度。如需更丰富的进度条，
#      可以集成 tqdm
# -------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.llm.cache import LLMCache
from src.llm.client import LLMClient
from src.pipeline.builder import build_graph_from_config
from src.schemas.case import CaseData, GroundTruth
from src.schemas.experiment import ExperimentConfig
from src.schemas.results import CaseResult, ExperimentResult
from src.schemas.state import GraphState
from src.schemas.trace import TokenUsage
from src.tracing.tracer import Tracer

# 确保所有 Agent 被注册（导入模块即触发 @register_agent 装饰器）
import src.agents.pulmonologist  # noqa: F401
import src.agents.radiologist  # noqa: F401
import src.agents.moderator  # noqa: F401
import src.agents.case_analyst  # noqa: F401

logger = logging.getLogger(__name__)


# ── 数据加载 ────────────────────────────────────────────────

def load_cases(path: str) -> list[CaseData]:
    """从 JSONL 文件加载病例数据"""
    cases = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"病例数据文件不存在: {p}")
    for line in p.read_text("utf-8").strip().splitlines():
        if line.strip():
            cases.append(CaseData(**json.loads(line)))
    return cases


def load_ground_truth(path: str) -> dict[str, GroundTruth]:
    """从 JSONL 文件加载金标准，返回 {case_id: GroundTruth}"""
    gt_map: dict[str, GroundTruth] = {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"金标准文件不存在: {p}")
    for line in p.read_text("utf-8").strip().splitlines():
        if line.strip():
            gt = GroundTruth(**json.loads(line))
            gt_map[gt.case_id] = gt
    return gt_map


def load_experiment_config(path: str) -> ExperimentConfig:
    """从 YAML 文件加载实验配置"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"实验配置文件不存在: {p}")
    raw = yaml.safe_load(p.read_text("utf-8"))
    return ExperimentConfig(**raw)


# ── 实验运行器 ──────────────────────────────────────────────

class ExperimentRunner:
    """实验运行器

    Args:
        config_path: 实验配置 YAML 文件路径
        output_dir: 实验输出根目录（默认 results/）
        api_key: OpenAI API Key（优先使用，否则从 .env 读取）
        base_url: OpenAI 兼容 API 的 base URL
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str = "results",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        # 加载 .env（API keys 等）
        load_dotenv()

        self.config = load_experiment_config(config_path)
        self.output_dir = Path(output_dir)

        # 初始化 LLM 客户端
        import os
        _api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        _base_url = base_url or os.getenv("OPENAI_BASE_URL")

        cache = LLMCache() if self.config.tracking.cache_llm_responses else None
        self.llm_client = LLMClient(
            api_key=_api_key,
            base_url=_base_url,
            cache=cache,
        )

        # 当前病例的 tracer（每个病例重新创建）
        self._current_tracer: Tracer | None = None

    def _tracer_factory(self) -> Tracer | None:
        """返回当前 tracer 实例，供节点函数使用"""
        return self._current_tracer

    def _run_single_case(self, case: CaseData, compiled_graph: Any) -> CaseResult:
        """运行单个病例

        # TODO（后续研究扩展点）：
        #   1. 当前 final_output 从 state["final_output"] 获取。
        #      如果 pipeline 最后一个节点的 agent 没有写 final_output，
        #      则回退到取最后一个 agent 的 output。你的实验可能需要
        #      更精确的输出提取逻辑
        #   2. 错误恢复：当前单个病例失败会记录错误并继续下一个。
        #      如需更细致的错误处理策略，修改这里
        """
        # 创建 tracer
        if self.config.tracking.save_full_traces:
            self._current_tracer = Tracer(
                case_id=case.case_id,
                experiment_name=self.config.experiment.name,
            )
        else:
            self._current_tracer = None

        # 构建初始 state
        initial_state: GraphState = {
            "case_text": case.to_text(),
            "case_id": case.case_id,
            "agent_outputs": {},
            "agent_traces": [],
            "message_traces": [],
        }

        # 运行 pipeline
        final_state = compiled_graph.invoke(initial_state)

        # 提取最终输出
        # 优先取 state 中的 final_output，否则取最后一个 agent 的输出
        final_output = final_state.get("final_output", "")
        if not final_output:
            agent_outputs = final_state.get("agent_outputs", {})
            if agent_outputs:
                # 取最后写入的 agent 输出作为 final_output
                final_output = list(agent_outputs.values())[-1]

        # 获取 trace
        trace = self._current_tracer.finalize() if self._current_tracer else None

        return CaseResult(
            case_id=case.case_id,
            final_output=str(final_output),
            trace=trace,
        )

    def run(self) -> ExperimentResult:
        """运行完整实验：遍历所有病例，收集结果

        Returns:
            ExperimentResult: 包含所有病例结果和汇总信息
        """
        logger.info("开始实验: %s", self.config.experiment.name)

        # 加载数据
        cases = load_cases(self.config.data.cases)
        gt_map: dict[str, GroundTruth] = {}
        if self.config.data.ground_truth:
            gt_map = load_ground_truth(self.config.data.ground_truth)
        logger.info("加载了 %d 个病例", len(cases))

        # 构建 pipeline（只构建一次，所有病例共享同一个编译后的图）
        compiled_graph = build_graph_from_config(
            config=self.config,
            llm_client=self.llm_client,
            tracer_factory=self._tracer_factory,
        )

        # 逐病例运行
        case_results: list[CaseResult] = []
        total_tokens = TokenUsage()

        for i, case in enumerate(cases, 1):
            logger.info("运行病例 [%d/%d]: %s", i, len(cases), case.case_id)
            try:
                result = self._run_single_case(case, compiled_graph)
                # 附加金标准
                if case.case_id in gt_map:
                    result.ground_truth_diagnosis = gt_map[case.case_id].diagnosis
                # 汇总 token
                if result.trace:
                    t = result.trace.total_token_usage
                    total_tokens.prompt_tokens += t.prompt_tokens
                    total_tokens.completion_tokens += t.completion_tokens
                    total_tokens.total_tokens += t.total_tokens
                case_results.append(result)
            except Exception as e:
                logger.error("病例 %s 运行失败: %s", case.case_id, e)
                case_results.append(CaseResult(
                    case_id=case.case_id,
                    final_output=f"[ERROR] {e}",
                ))

        # 构建实验结果
        experiment_result = ExperimentResult(
            experiment_name=self.config.experiment.name,
            config_snapshot=self.config.model_dump(mode="json"),
            case_results=case_results,
            total_token_usage=total_tokens,
        )

        # 保存结果
        self._save_results(experiment_result)

        logger.info("实验完成: %d 个病例, 总 token: %d",
                     len(case_results), total_tokens.total_tokens)
        return experiment_result

    def _save_results(self, result: ExperimentResult) -> Path:
        """保存实验结果到文件

        输出目录结构：
            results/{experiment_name}_{timestamp}/
                config_snapshot.yaml
                raw_outputs.jsonl
                traces/{case_id}.json  （如果开启了 trace）
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"{result.experiment_name}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # 保存配置快照
        config_path = run_dir / "config_snapshot.yaml"
        config_path.write_text(
            yaml.dump(result.config_snapshot, allow_unicode=True, default_flow_style=False),
            "utf-8",
        )

        # 保存原始输出（JSONL）
        outputs_path = run_dir / "raw_outputs.jsonl"
        with outputs_path.open("w", encoding="utf-8") as f:
            for cr in result.case_results:
                line = json.dumps({
                    "case_id": cr.case_id,
                    "final_output": cr.final_output,
                    "ground_truth_diagnosis": cr.ground_truth_diagnosis,
                }, ensure_ascii=False)
                f.write(line + "\n")

        # 保存 traces
        if self.config.tracking.save_full_traces:
            traces_dir = run_dir / "traces"
            traces_dir.mkdir(exist_ok=True)
            for cr in result.case_results:
                if cr.trace:
                    trace_path = traces_dir / f"{cr.case_id}.json"
                    trace_path.write_text(
                        json.dumps(cr.trace.model_dump(mode="json"), ensure_ascii=False, indent=2),
                        "utf-8",
                    )

        logger.info("结果已保存到: %s", run_dir)
        return run_dir

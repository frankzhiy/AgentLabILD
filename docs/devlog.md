# ILD-MDT 实验平台开发日志

---

## 2026-03-17 — Phase 1 基础设施搭建（步骤 1-4）

**做了什么**：完成项目初始化 + 核心 schemas + LLM Client/Cache + Prompt Loader

**改动文件**：
- `pyproject.toml` — 项目元数据与依赖（openai, pydantic, langgraph, pyyaml, python-dotenv）
- `.github/copilot-instructions.md` — Copilot 上下文指引（领域知识、设计原则、技术栈、约束）
- `src/schemas/case.py` — CaseData, GroundTruth 数据模型
- `src/schemas/experiment.py` — ExperimentConfig 全链路配置模型（agent、pipeline、通信、冲突、评估）
- `src/schemas/state.py` — LangGraph GraphState（TypedDict + Annotated reducers）
- `src/schemas/trace.py` — 多层级追踪结构（LLMCallTrace, AgentTrace, PipelineTrace 等）
- `src/schemas/results.py` — CaseResult, ExperimentResult
- `src/agents/base.py` — BaseAgent ABC + AgentOutput + AgentContext
- `src/agents/registry.py` — Agent 注册表（Registry Pattern + 装饰器）
- `src/communication/base.py` — CommunicationProtocol ABC + 注册表
- `src/conflict/detection.py` — ConflictDetector ABC + Conflict 模型 + 注册表
- `src/conflict/arbitration.py` — ArbitrationStrategy ABC + ArbitrationResult + 注册表
- `src/evaluation/metrics.py` — BaseMetric ABC + 注册表
- `src/tracing/tracer.py` — Tracer 类（收集 agent/消息/冲突 trace，汇总 token）
- `src/llm/cache.py` — LLMCache（基于 SHA-256 hash 的文件缓存）
- `src/llm/client.py` — LLMClient（OpenAI 兼容接口封装，集成缓存）
- `src/llm/prompt_loader.py` — PromptLoader（Markdown 模板加载 + $variable 替换）
- `configs/prompts/v1/pulmonologist_analysis.md` — 呼吸科医生 prompt 模板
- `configs/prompts/v1/radiologist_analysis.md` — 影像科医生 prompt 模板
- `tests/test_schemas.py` — 11 个 schema 单元测试
- `tests/test_agents.py` — 2 个注册表测试
- `tests/test_llm.py` — 5 个 cache/client 测试
- `tests/test_prompt_loader.py` — 6 个 prompt loader 测试

**设计决策**：
1. Prompt 模板使用 `string.Template`（`$var` 语法）而非 `str.format`（`{var}` 语法），因为 prompt 中大括号常见（JSON 示例等），`$` 冲突概率低
2. LLM Cache 按 hash 前两位分子目录，避免单目录文件过多
3. ExperimentConfig 的 `EdgeConfig` 使用 `alias="from"` / `alias="to"` 映射 YAML 中的 `from`/`to` 字段（Python 保留字）
4. GraphState 使用 Annotated reducers 而非简单覆盖，支持并行节点同时写入 agent_outputs
5. 所有注册表都带重复注册检查，避免静默覆盖

**待办**：
- ~~Phase 1 剩余：LLMAgent 具体实现、Pipeline Builder、Runner、参考实验配置、测试病例~~ ✅

---

## 2026-03-17 — Phase 1 完成：LLMAgent + Pipeline + Runner + 端到端验证

**做了什么**：实现了 Phase 1 所有剩余模块，平台可以端到端运行实验

**改动文件**：
- `src/agents/llm_agent.py` — LLMAgent 实现（从 prompt 模板 + LLM 调用生成分析）
- `src/communication/blackboard.py` — Blackboard 通信协议 baseline（所有 agent 共享全部信息）
- `src/pipeline/nodes.py` — 节点工厂（将 Agent 包装为 LangGraph 节点函数）
- `src/pipeline/builder.py` — Pipeline Builder（从 YAML 配置动态构建 LangGraph StateGraph）
- `src/runner.py` — ExperimentRunner（加载配置 → 构建 pipeline → 遍历病例 → 保存结果）
- `configs/prompts/v1/moderator_synthesis.md` — MDT 主持人综合分析 prompt 模板
- `configs/experiments/baseline_3agent.yaml` — 参考实验配置（3-agent baseline）
- `data/cases/demo_2cases.jsonl` — 2 个 demo 测试病例（IPF + RA-ILD）
- `data/ground_truth/demo_2cases_labels.jsonl` — 对应金标准
- `tests/test_pipeline_builder.py` — Pipeline 构建与执行测试（3 个）
- `tests/test_runner.py` — Runner 端到端测试（4 个，含数据加载 + 完整流程）

**设计决策**：
1. LLMAgent 中标注了多处 `TODO（后续研究扩展点）`——这些是后续研究中最可能需要修改的位置（输出格式解析、消息编排、多轮对话等）
2. Blackboard 协议是最简实现：每个 agent 能看到所有已有 agent 的输出。后续需要信息隔离实验时，实现新 protocol 并注册
3. Pipeline Builder 中多 agent 节点当前在单节点内顺序执行（非真正并行）。如需利用 LangGraph Send API 做真正并行 fan-out，需要将多 agent 节点拆成子节点 + fan-out/fan-in 边
4. 条件路由的条件函数注册表（`CONDITION_REGISTRY`）当前为空。实现冲突检测后需注册如 `has_conflicts` 等条件
5. Runner 当前不计算评估指标，只保存原始输出和 trace。评估在 Phase 2 集成
6. 所有临时/baseline 实现都用注释标明了 "后续研究扩展点"

**测试状态**：29 个测试全部通过（schemas 11 + agents 2 + cache/client 5 + prompt 6 + pipeline 3 + runner 4）

**待办**：
- Phase 2：选择第一个研究切入点（建议冲突协商与仲裁），实现具体策略
- 用真实 LLM API 跑通 baseline 实验验证完整链路
- 实现评估指标（如 diagnostic_accuracy）

---

## 2026-03-17 — 项目文档编写

**做了什么**：编写三份核心文档，帮助快速理解和上手项目

**新增文件**：
- `docs/architecture.md` — 代码架构与核心机制详解：覆盖 ABC、Registry Pattern、Trace 框架、LangGraph 状态图、通信协议、Prompt 模板、LLM 缓存等机制，并给出"添加新 agent / 冲突检测 / 通信协议"的实操步骤
- `docs/getting_started.md` — 新手上路指南：从打开 VSCode → 激活环境 → 安装依赖 → 配置 API Key → 运行实验 → 查看结果 → 跑测试 → 修改参数，完整的 step-by-step 教程
- `docs/config_reference.md` — 实验配置速查手册：逐字段解释 YAML 配置含义，附带 4 个常用配置模板（最简 2-agent、完整 4-agent MDT、两轮讨论、模型对比）

---

## 2026-03-18 — 编排策略模块重构

**做了什么**：将 YAML 从"拓扑决策者"重构为纯"选择器"。YAML 不再定义 pipeline 的 nodes/edges，改为引用编排策略名。

**核心改变**：
- 删除了 `PipelineConfig`、`PipelineNodeConfig`、`EdgeConfig`、`ConditionalEdgeConfig` 等 schema
- 新增 `OrchestrationConfig`（strategy + parameters），`ExperimentConfig.pipeline` → `ExperimentConfig.orchestration`
- 新建 `src/orchestration/` 模块：`base.py`（ABC + 注册表）、`sequential.py`（baseline 策略）
- `pipeline/builder.py` 不再手动建图，改为委托编排策略的 `build_graph()` 方法
- 29 个测试全部通过

**新增文件**：
- `src/orchestration/__init__.py`、`base.py`、`sequential.py`
- `teach/refactor_orchestration_module.md`

**修改文件**：
- `src/schemas/experiment.py`、`src/pipeline/builder.py`、`configs/experiments/baseline_3agent.yaml`
- `src/runner.py`、`tests/test_pipeline_builder.py`、`tests/test_runner.py`、`tests/test_schemas.py`

---

## 2026-03-20 — CaseData 重构为嵌套结构 + case_analyst 实测

**做了什么**：

1. **重写 `CaseData` 数据模型**：从扁平 ~15 字段重构为与 `assets/case_schema.json` 对齐的嵌套结构，包含 9 大临床板块（Basic Clinical Background / Symptoms / Autoimmune / Imaging / Pulmonary Function / Laboratory / BAL & Pathology / Integrated Assessment / Treatment）共 20+ 子模型。`to_text()` 改为递归遍历嵌套结构生成 Markdown。

2. **更新 case_analyst prompt 模板**：提取规则适配嵌套结构，增加 9 大板块说明，明确 snake_case 字段名和值类型要求。

3. **更新 demo 数据**：`data/cases/demo_2cases.jsonl` 从旧扁平格式迁移到新嵌套格式。

4. **创建手动测试脚本**：`scripts/test_case_analyst.py`，支持内置示例 / 文件读取 / stdin 输入三种方式，结果保存到 `tempfile/casefile/`。

5. **实测通过**：用真实中文病例文本成功跑通 case_analyst → 结构化 JSON 全链路。

**新增文件**：
- `scripts/test_case_analyst.py` — case_analyst 手动测试脚本
- `tempfile/test_input/case_chinese_01.txt` — 中文测试病例文本

**修改文件**：
- `src/schemas/case.py` — 核心改动，CaseData 重写为嵌套结构
- `configs/prompts/v1/case_analyst_parsing.md` — prompt 模板适配新 schema
- `data/cases/demo_2cases.jsonl` — demo 数据迁移到新格式
- `tests/test_schemas.py`、`tests/test_runner.py` — 断言适配新结构

**未改动**：
- `src/agents/case_analyst.py` — 无需改动（`CaseData.model_json_schema()` 动态反映新结构）

**测试**：29/29 通过

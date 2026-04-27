# Phase 1-6 Issue 2-4: Evaluation Harness（2026-04-27）

## 1. Analysis path

本次按“既有机制入口 -> 评估接口设计 -> 输出报告分层”顺序分析：

1. `src/validators/pipeline.py`
- 确认唯一验证入口是 `validate_phase1_candidate_pipeline`。
- 确认 schema-only 短路与 full validator 执行顺序（schema/provenance/temporal/unsupported_claim）。

2. `src/schemas/state.py`、`src/schemas/validation.py`
- 确认 `Phase1StateEnvelope` 的结构闭环约束与 `StateValidationReport` 的 issue 结构。

3. `src/storage/state_store.py`
- 以既有 `persist_snapshot` 语义作为 lineage 指标参考来源（首版本/parent/version 递增规则）。

4. `tests/test_phase1_fixtures.py` 与 `tests/fixtures/phase1/*.json`
- 复用 deterministic fixtures，确保 runner/metrics/report 三层都使用同一输入边界。

这样做的原因：
- 先锁定“已有机制源头”，再做评估层，避免在评估代码里重复实现 validator 逻辑。
- 先锁定 fixture 失败模式，再写指标口径，确保 metric 的 not_applicable 与 schema short-circuit 行为一致。

## 2. Change list

### 新增代码文件

1. `src/evaluation/phase1_metrics.py`
- 新增 `Phase1MetricValue`、`Phase1MetricSummary`。
- 新增 deterministic 指标函数：
  - `compute_phase1_metrics`
  - `compute_lineage_metric`
  - `compute_rerun_stability_metric`
- 指标覆盖：
  - schema_validity_rate
  - provenance_completeness_rate
  - claim_evidence_traceability_rate
  - unsupported_claim_rate
  - stage_alignment_rate
  - hypothesis_board_completeness_rate
  - state_version_lineage_validity_rate
  - rerun_stability_rate（默认 not_applicable，需成对 rerun 输入）

2. `src/evaluation/phase1_metrics_support.py`
- 抽离 stage/board/lineage/rerun 判定辅助函数，保持 `phase1_metrics.py` 规模可维护。
- 该文件仅提供纯函数检查，不做 I/O、不做状态写入。

3. `src/evaluation/phase1_runner.py`
- 新增 runner 输入/输出模型：
  - `Phase1CaseEvaluationInput`
  - `Phase1CaseEvaluationResult`
  - `Phase1BatchEvaluationResult`
- 新增执行函数：
  - `load_phase1_fixture`
  - `evaluate_phase1_payload`
  - `evaluate_phase1_payloads`
  - `evaluate_phase1_fixture_dir`
- 支持 top-level `states` 链式 fixture 展开并逐 state 验证。

4. `src/evaluation/reporting.py`
- 新增报告模型与输出函数：
  - `Phase1AuditReport`
  - `build_phase1_audit_report`
  - `phase1_report_to_dict`
  - `phase1_report_to_json`
  - `build_phase1_markdown_summary`
- 报告层只消费 runner 输出，不重跑 pipeline。

5. `src/evaluation/__init__.py`
- 导出 metrics/runner/report 公开接口。

### 新增测试文件

1. `tests/test_phase1_metrics.py`
- 覆盖单 fixture 与混合 fixture 下的指标行为。
- 覆盖 not_applicable、lineage、rerun stability。

2. `tests/test_phase1_runner.py`
- 覆盖 payload/fixture-dir 两种输入。
- 覆盖无崩溃失败输出、`states` 链式展开、JSON 可序列化、validator 顺序稳定性。

3. `tests/test_phase1_report.py`
- 覆盖 report 构建、序列化、issue 分布、markdown 摘要、以及“不重跑验证流水线”。

## 3. Connection mechanism

### 为什么 Phase 1 需要先做 metrics，再进入 Phase 2

- Phase 1 的研究对象是“状态外化机制是否成立”，不是 agent 对话质量。
- 没有 deterministic 指标，Phase 2（冲突/修订/仲裁）缺少可审计基线，无法判断机制改动是变好还是退化。

### 为什么这些指标评估的是 state externalization，而不是诊断准确率

- 指标全部围绕结构化状态对象和 validator 产物：schema、provenance、claim-evidence 链路、stage 对齐、board 闭环、lineage、rerun 稳定性。
- 指标不涉及最终诊断正确率、治疗方案优劣、临床结局评分。

### 为什么 runner 复用既有 validator，而不复制逻辑

- `phase1_runner` 统一调用 `validate_phase1_candidate_pipeline(...)`。
- validator 仍是唯一语义真源；runner 仅做编排、聚合与结构化输出。

### 为什么 report 与 metrics/runner 分离

- metrics 层负责“如何算”；runner 层负责“算什么输入”；report 层负责“如何呈现”。
- 分层后可单独复用：
  - 可在 notebook/脚本直接消费 `Phase1BatchEvaluationResult` 生成不同输出。
  - 不会因为报告格式变化而影响验证与指标计算行为。

### 为什么本次明确不做 ablation

- 当前任务目标是稳定基线审计层。
- ablation toggle 会引入额外实验维度与控制面，增加解释成本，不属于本 issue 的最小交付边界。

## 4. Runtime data flow

### 4.1 runner 执行流

1. 输入 payload（内存对象或 fixture 文件）。
2. 如存在 top-level `states`，先展开为逐 state payload。
3. 每个 state 调用：
- `validate_phase1_candidate_pipeline(payload, policy=ValidationPipelinePolicy(require_provenance=True))`
4. 收集 per-state 结果：
- `schema_valid`
- `blocking_issue_codes`
- `warning_issue_codes`
- `validator_execution_order`
- `metric_values`（单 state 视角）
5. 对全部 pipeline results 计算 batch `metric_summary`。

### 4.2 reporting 执行流

1. 输入 `Phase1BatchEvaluationResult`。
2. 提取已有 `metric_summary`，不重算低层指标。
3. 汇总 blocking/warning issue code 分布。
4. 生成 per-case（实际是 per-state）摘要与 JSON/Markdown 输出。

## 5. Self-service modification guide

后续若需扩展，可按以下入口修改：

1. 新增 Phase 1 机制指标
- 修改 `src/evaluation/phase1_metrics.py`。
- 保持纯函数、无 I/O、无状态写入、无 validator 语义复制。

2. 新增输入来源（例如 API 入参）
- 修改 `src/evaluation/phase1_runner.py`。
- 保持对 `validate_phase1_candidate_pipeline` 的单入口复用。

3. 新增报告格式（例如 CSV 或 HTML）
- 在 `src/evaluation/reporting.py` 增加纯输出函数。
- 不要在 report 层重跑 pipeline 或重算底层 validator 逻辑。

4. 调整 not_applicable 口径
- 优先在 `phase1_metrics.py` 内单点调整。
- 同步更新对应测试断言，避免口径漂移。

## 6. Validation method

建议执行：

```bash
python -m pytest -q tests/test_phase1_fixtures.py
python -m pytest -q tests/test_phase1_metrics.py
python -m pytest -q tests/test_phase1_runner.py
python -m pytest -q tests/test_phase1_report.py
python -m pytest -q
```

预期：
- 以上测试均通过。
- 无需新增 agent/prompt/诊断评分机制。

常见失败排查：

1. `states` fixture 未展开，导致 lineage 指标一直 not_applicable。
2. 报告层误调用 pipeline，破坏“只消费 runner 输出”边界。
3. schema-fail 样本被错误纳入 provenance/traceability 分母，导致口径失真。

## 7. Concept notes

1. Deterministic metric
- 同一输入应得到同一输出，不依赖 LLM 随机性。

2. Validator as source of truth
- 评估层读取 validator 报告，不复制 validator 规则。

3. not_applicable first-class
- 当 schema 未通过且指标无法计算时，显式返回 not_applicable，而不是伪造 0 分。

4. Mechanism boundary
- 本次仅构建 Phase 1 状态外化评估 harness，不引入冲突检测、belief revision、仲裁、安全门或诊断准确率评分。

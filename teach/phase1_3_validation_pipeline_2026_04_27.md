# Phase 1-3：Unified Validation Pipeline（2026-04-27）

## 1. Analysis path

本次先阅读并对齐以下文件，再开始编码：

- src/state/write_policy.py
- src/state/write_decision.py
- src/validators/schema_validator.py
- src/validators/provenance_validator.py
- src/validators/temporal_validator.py
- src/validators/unsupported_claims.py
- tests/test_write_contracts.py
- tests/test_schema_validator.py
- tests/test_provenance_validator.py
- tests/test_temporal_validator.py
- tests/test_unsupported_claims.py

这样做的原因：

1. 先确认 write-gate 合同层当前仅负责“决策建模”，避免在本任务误实现 writer。
2. 对齐四个现有 validator 的输入输出契约，确保 pipeline 是编排层而不是替换层。
3. 复用已有测试风格与夹具，保证 Phase 1-3 行为边界一致。

## 2. Change list

- src/validators/pipeline.py
  - 新增 `validate_phase1_candidate_pipeline(...)` 入口。
  - 支持输入类型：
    - `dict[str, object]`
    - `Phase1StateEnvelope`
  - 固定执行顺序：
    1. schema
    2. provenance
    3. temporal
    4. unsupported_claim
  - 实现 schema 失败短路：raw payload schema 失败时仅返回 schema report，不执行下游。
  - 新增 `Phase1ValidationPipelineResult`：
    - `candidate_envelope`
    - `reports`
    - `has_blocking_issue`
    - `validator_execution_order`
    - `summary`
  - 保持 report 粒度：不合并 issue，不改 issue_code namespace。

- src/validators/__init__.py
  - 导出 pipeline 入口、结果对象和执行顺序常量。

- tests/test_validation_pipeline.py
  - 新增 7 个测试，覆盖：
    1. raw payload schema 失败仅返回 schema
    2. provenance 问题场景下游报告保留
    3. temporal 问题场景下游报告保留
    4. unsupported-claim 问题场景下游报告保留
    5. fully valid 场景全报告 valid
    6. 顺序稳定性断言
    7. 报告粒度与 namespace 保留断言

## 3. Connection mechanism

连接方式如下：

- 外部通过 validators 包调用：
  - `from src.validators import validate_phase1_candidate_pipeline`
- pipeline 内部调用现有四个 validator：
  - `validate_phase1_schema`
  - `validate_phase1_provenance`
  - `validate_phase1_temporal`
  - `validate_phase1_unsupported_claims`
- pipeline 返回聚合元数据供后续 write-gate / writer 读取，但不执行写入。

## 4. Runtime data flow

1. 输入 candidate（raw payload 或 envelope）。
2. schema 先执行：
  - raw payload schema fail -> 仅产出 schema report 并短路。
  - raw payload schema pass -> 构造一次 envelope，并将 envelope 传给下游 validator。
  - envelope 输入 -> 直接走 pass-through schema report 后进入下游。
3. provenance/temporal/unsupported_claim 按固定顺序执行。
4. 汇总 `Phase1ValidationPipelineResult`：
  - 保留每个 validator 的独立 `StateValidationReport`
  - 计算 `has_blocking_issue`
  - 记录 `validator_execution_order`
  - 输出可审计 summary

## 5. Self-service modification guide

后续扩展建议：

1. 若新增 validator，优先在 `src/validators/pipeline.py` 中扩展固定顺序常量和 `_run_full_pipeline`。
2. 不要在 pipeline 内改写 validator issue；保持各命名空间独立。
3. 若要切换 provenance 策略（如 `require_provenance`），仅通过 pipeline 参数传递，不在 pipeline 内硬编码分支逻辑。
4. 若未来接入 writer，请在 writer 层消费 `Phase1ValidationPipelineResult`，不要把写入行为回塞到 pipeline。
5. 若要做 accept/reject/manual_review 计算，应在 write-gate 合同层扩展，而不是在 validator pipeline 里做持久化决策。

## 6. Validation method

执行：

```bash
python -m pytest -q tests/test_validation_pipeline.py tests/test_schema_validator.py tests/test_provenance_validator.py tests/test_temporal_validator.py tests/test_unsupported_claims.py tests/test_write_contracts.py
```

预期：

- 全部通过。
- 本次结果：`48 passed`。

常见失败与排查：

1. 如果 `validator_execution_order` 断言失败：检查 pipeline 执行顺序常量与 `_run_full_pipeline` 调用顺序是否一致。
2. 如果 schema fail 没有短路：检查 raw payload 失败分支是否提前 return。
3. 如果 envelope 输入报重建/重校验错误：检查 pipeline result 是否保持 envelope pass-through（不做二次构造）。

## 7. Concept notes

1. 为什么 pipeline 存在：
  - 单个 validator 只回答一个维度（schema/provenance/temporal/unsupported_claim）。
  - 写门禁和未来 writer 需要“有序、可审计、可复用”的多报告结果，因此需要统一编排层。

2. 为什么 schema 必须先跑：
  - schema 是结构边界，失败时下游报告没有可靠对象语义基础。
  - 先 schema 再下游可避免把结构失败误解释为 provenance/temporal/unsupported_claim 失败。

3. 为什么这仍不是 state writer：
  - pipeline 只做“验证编排 + 聚合元数据”。
  - 不做持久化，不写 blackboard，不落 storage，不产生命令式 accept/reject 行为。
  - 下一步 state writer 只应消费 pipeline 结果并执行写入策略，而非反向侵入 validator 逻辑。

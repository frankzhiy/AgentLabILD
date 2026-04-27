# Phase 1-3：State Writer Gate（2026-04-27）

## 1. Analysis path

本次按以下顺序检查并实现：

- src/state/write_status.py
- src/state/write_policy.py
- src/state/write_decision.py
- src/validators/pipeline.py
- src/state/__init__.py
- tests/test_write_contracts.py
- tests/test_validation_pipeline.py

选择这条路径的原因：

1. 先确认已有写门禁合同（status/policy/decision）语义已经稳定。
2. 再在其上叠加 writer orchestration，避免重复定义决策语义。
3. 最后补 sink 抽象和测试，确保“可选持久化”与“不改写状态”边界同时成立。

## 2. Change list

- src/state/sinks.py
  - 新增 `StateSink` 协议（最小 persist 接口）。
  - 新增 `NoOpStateSink`（不落盘，仅吞掉写入请求）。
  - 新增 `InMemoryStateSink`（用于测试/本地实验的内存持久化）。

- src/state/state_writer.py
  - 新增 `attempt_phase1_write(...)` 公开入口。
  - 统一流程：
    1. 调用 `validate_phase1_candidate_pipeline(...)`
    2. 推导 `WriteDecisionStatus`
    3. 构造 `WriteDecision`
    4. 在 `should_persist=True` 且有 `accepted_envelope` 时调用 sink.persist
  - 不做自动修复、不做 schema 重写、不做事件日志。

- src/state/__init__.py
  - 导出 `attempt_phase1_write`、`StateSink`、`NoOpStateSink`、`InMemoryStateSink`。

- tests/test_state_writer.py
  - 新增 8 条用例，覆盖接受/拒绝/manual_review/策略持久化/原始无效 payload/no-op sink/非变异边界。

## 3. Connection mechanism

连接关系：

- 上游输入：raw dict 或 `Phase1StateEnvelope`。
- writer 调用：`src.validators.validate_phase1_candidate_pipeline`。
- writer 产出：`WriteDecision`（复用已有合同对象）。
- sink 层：只接收 `accepted_envelope` 并执行 `persist`。

因此，writer 只是把“验证结果”连接到“门禁决策与可选持久化”，不替代 validator 本身。

## 4. Runtime data flow

1. 调用 `attempt_phase1_write(candidate, ...)`。
2. writer 先运行 validation pipeline，获得：
  - `candidate_state_id`
  - `reports`
  - `has_blocking_issue`
  - `candidate_envelope`
3. 按规则推导状态：
  - blocking -> `REJECTED`
  - 无 blocking 且全 valid -> `ACCEPTED`
  - 无 blocking 但存在 invalid(non-blocking) -> `MANUAL_REVIEW`
4. 构造 `WriteDecision`（由合同层自动推导 `should_persist`）。
5. 若 `should_persist=True` 且有 `accepted_envelope`，调用 sink.persist。
6. 返回 `WriteDecision` 给调用方。

## 5. Self-service modification guide

后续扩展建议：

1. 若增加 sink 类型（文件/远程服务），仅实现 `StateSink.persist`，不要在 writer 内加入 sink-specific 分支。
2. 若调整“accept/reject/manual_review”逻辑，优先修改 writer 内状态推导 helper，保持 `WriteDecision` 合同不变。
3. 若新增 pipeline 策略字段（如 temporal strictness），通过 `ValidationPipelinePolicy` 传入，不要把策略散落到 writer 参数。
4. 若后续引入 event log，请在新模块实现，不要回写到当前 `state_writer.py`。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_state_writer.py tests/test_write_contracts.py tests/test_validation_pipeline.py tests/test_skeleton_imports.py
```

预期：

- 全部通过。
- 本次结果：`30 passed`。

常见失败排查：

1. `WriteDecision` 构造失败：通常是 `status` 与 `accepted_envelope` / `should_persist` 不一致。
2. manual_review 持久化失败：检查 `WritePolicy(allow_manual_review_persist=True)` 是否显式开启。
3. rejected 仍被持久化：检查 writer 是否在 sink.persist 前先依赖 `decision.should_persist`。

## 7. Concept notes

1. writer-gate 语义
  - writer 的核心职责是“执行门禁”，不是“修复候选状态”。
  - 它消费 validator 输出并给出结构化决策，保证行为可审计。

2. 为什么这是 Issue5 的关键
  - 之前只有验证报告；现在形成了可执行写路径。
  - 调用方可以一次调用获得统一 `WriteDecision`，并触发可控持久化。

3. 这仍不是最终 state_writer 终态
  - 目前没有 event sourcing/replay/version lineage storage。
  - 目前没有数据库事务与并发控制。
  - 目前没有自动修复/重试策略。
  - 这些属于后续阶段，不在本 issue 范围内。

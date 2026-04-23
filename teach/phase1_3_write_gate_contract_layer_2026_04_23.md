# Phase 1-3：Write-Gate Contract Layer（2026-04-23）

## 1. Analysis path

先读以下文件以锁定不可破坏边界与当前行为：

- `src/schemas/state.py`：确认 `Phase1StateEnvelope` 仍执行硬结构校验并在构造期失败。
- `src/schemas/validation.py`：确认 `StateValidationReport`/`ValidationIssue` 的 blocking 语义。
- `src/validators/provenance_validator.py`：确认外部 validator 只产出报告，不做写入。
- `tests/test_phase1_state_envelope.py`、`tests/test_provenance_validator.py`：确认 Direction A 现有行为与测试断言。

这些文件是正确起点，因为 Phase 1-3 write gate 必须建立在现有 envelope + report 语义之上，且不能反向改变 Direction A。

## 2. Change list

- `src/state/write_status.py`
  - 新增 `WriteDecisionStatus`，仅表达写判定状态：`accepted` / `rejected` / `manual_review`。
- `src/state/write_policy.py`
  - 新增 `WritePolicy`，仅表达写门禁策略参数与 `should_persist` 计算逻辑。
  - 默认策略：`blocking` 阻断写入；`accepted` 可写；`manual_review` 默认不可写。
- `src/state/write_decision.py`
  - 新增 `WriteDecision`，汇总一次候选状态写入尝试的门禁结果。
  - 关键字段：`candidate_state_id`、`accepted_envelope`、`reports`、`has_blocking_issue`、`should_persist`、`summary`。
  - 关键一致性校验：
    - `accepted` 必须有 `accepted_envelope` 且不能带 blocking。
    - `rejected` 不能带 `accepted_envelope`。
    - `candidate_state_id` 必须与 `accepted_envelope.state_id` 一致（若 envelope 存在）。
    - `has_blocking_issue` 与 `reports` 的 blocking 聚合保持一致。
    - `should_persist` 必须与 policy 计算一致。
- `src/state/__init__.py`
  - 导出 `WriteDecisionStatus`、`WritePolicy`、`WriteDecision`。
- `tests/test_write_contracts.py`
  - 新增聚焦测试：默认行为、三态语义、不变量、输入不变异、轻量依赖边界。
- `docs/devlog.md`
  - 追加本次任务记录。

## 3. Connection mechanism

当前连接机制保持最小：

- 外部模块通过 `src.state` 直接导入合同对象：
  - `from src.state import WriteDecisionStatus, WritePolicy, WriteDecision`
- 本次未接入 writer/orchestrator/storage。
- 后续 state writer 只需消费：
  - 候选 `Phase1StateEnvelope`
  - 外部 validators 输出的 `StateValidationReport`
  - `WritePolicy`
  - 产出 `WriteDecision`

## 4. Runtime data flow

一次典型运行链路（仍是合同层，不含真实持久化）：

1. 上游生成候选 `Phase1StateEnvelope`（构造时先过 envelope 硬校验）。
2. 外部 validators 生成一个或多个 `StateValidationReport`。
3. 写门禁（未来 writer）读取 reports 的 blocking 聚合，并结合 `WritePolicy`。
4. 构造 `WriteDecision`：
   - `status` 表示结论（accepted/rejected/manual_review）。
   - `has_blocking_issue` 与 `should_persist` 被规范化并校验一致性。
5. 后续持久化层（未来实现）只根据 `WriteDecision.should_persist` 决定是否落库。

## 5. Self-service modification guide

如果你要继续扩展：

1. 调整状态枚举：编辑 `src/state/write_status.py`。
2. 调整策略参数或门禁规则：编辑 `src/state/write_policy.py` 的字段与 `should_persist`。
3. 调整 decision 不变量：编辑 `src/state/write_decision.py` 的 `validate_write_decision`。
4. 调整对外 API：编辑 `src/state/__init__.py`。
5. 每次规则变化都要同步 `tests/test_write_contracts.py`。

## 6. Validation method

建议先跑聚焦回归：

```bash
python -m pytest -q tests/test_write_contracts.py tests/test_phase1_state_envelope.py tests/test_provenance_validator.py
```

预期：

- `tests/test_write_contracts.py` 全通过。
- 既有 envelope 与 provenance validator 测试不回归。

常见失败优先排查：

1. `accepted` 缺 `accepted_envelope`。
2. `candidate_state_id` 与 `accepted_envelope.state_id` 不一致。
3. 手工传入 `has_blocking_issue` 或 `should_persist` 与自动推导不一致。

## 7. Concept notes

- `WriteDecisionStatus`：判定语义层（结论）。
- `WritePolicy`：门禁策略层（规则）。
- `WriteDecision`：执行前合同层（结构化写入决议），不是 validator 也不是 writer。

该拆分保持“机制先于 agent”：

- validator 负责“报告事实”；
- gate contract 负责“表达可审计判定”；
- writer（未来）负责“执行持久化动作”。

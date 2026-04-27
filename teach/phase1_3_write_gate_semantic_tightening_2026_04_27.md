# Phase 1-3：Write Gate 语义收紧（2026-04-27）

## 1. Analysis path

本次 refinement 按以下顺序分析：

1. `src/state/write_policy.py`：确认 manual_review 落库是否可被策略放开。
2. `src/state/write_decision.py`：确认 `accepted_envelope` 的合法状态范围。
3. `src/state/state_writer.py`：确认 writer 是否会将 MANUAL_REVIEW 送入 sink。
4. `src/state/sinks.py`：确认 `NoOpStateSink` 的语义表述是否足够清晰。
5. `tests/test_write_contracts.py` 与 `tests/test_state_writer.py`：确认已有测试是否与“保守权威语义”一致。

该路径优先覆盖门禁合同对象，再覆盖编排和测试，避免“只改 writer、不改合同约束”造成语义漂移。

## 2. Change list

- `src/state/write_policy.py`
  - 将 `allow_manual_review_persist` 冻结为 `Literal[False]`（兼容字段保留、行为不可开启）。
  - `should_persist` 对 `MANUAL_REVIEW` 固定返回 `False`。

- `src/state/write_decision.py`
  - 收紧约束：`accepted_envelope` 仅允许在 `status == ACCEPTED` 时存在。
  - 对 `REJECTED` 与 `MANUAL_REVIEW` 统一要求 `accepted_envelope is None`。
  - 增加说明：`WriteDecision` 表达 validation-gate 判定，不保证持久化副作用已成功。

- `src/state/state_writer.py`
  - 文档改为“仅 accepted 可进入持久化路径”。
  - `_derive_accepted_envelope` 改为仅在 `ACCEPTED` 返回 envelope。
  - 明确保留异常传播：sink 持久化异常不吞掉，直接 bubble up。

- `src/state/sinks.py`
  - 澄清 `NoOpStateSink` 语义：接收 `persist` 调用但明确丢弃状态。
  - `list_state_ids()` 文档改为“始终为空”。

- `tests/test_write_contracts.py`
  - 新增：禁止 `WritePolicy(allow_manual_review_persist=True)`。
  - manual_review 相关断言改为始终不持久化且不允许 `accepted_envelope`。

- `tests/test_state_writer.py`
  - manual_review 测试改为 `accepted_envelope is None`。
  - 新增：manual_review 不触发 sink.persist 调用。
  - NoOp 测试重命名为 `noop_sink_receives_persist_call_but_discards_state` 语义。
  - 新增：持久化异常向上抛出测试。

## 3. Connection mechanism

连接方式保持不变：

1. `attempt_phase1_write` 调用 `validate_phase1_candidate_pipeline`。
2. writer 根据 report 推导 `WriteDecisionStatus`。
3. writer 构造 `WriteDecision`（合同层强校验）。
4. 仅当 `WriteDecision` 判定可持久化时调用 sink。

本次仅收紧语义，不新增组件，不改 pipeline 拓扑。

## 4. Runtime data flow

1. 输入 candidate（raw dict 或 `Phase1StateEnvelope`）。
2. pipeline 产出 candidate identity + reports + blocking 聚合。
3. writer 推导状态：
   - blocking -> `REJECTED`
   - all valid and non-blocking -> `ACCEPTED`
   - non-blocking but invalid -> `MANUAL_REVIEW`
4. `accepted_envelope` 仅在 `ACCEPTED` 设置。
5. 若 sink 在持久化阶段抛错，异常直接传给调用方。

## 5. Self-service modification guide

若未来要调整本语义，请优先在以下位置修改：

1. `src/state/write_policy.py`：变更“哪种状态可持久化”。
2. `src/state/write_decision.py`：变更 `accepted_envelope` 的状态约束。
3. `src/state/state_writer.py`：变更编排顺序或异常传播策略。

若要引入审计级持久化成功报告，请新建机制层对象，不要把 writer 改成吞异常或隐式修复。

## 6. Validation method

运行：

```bash
python -m pytest -q tests/test_write_contracts.py tests/test_state_writer.py tests/test_validation_pipeline.py tests/test_skeleton_imports.py
```

期望：

- 全部通过。
- manual_review 路径不会触发 sink.persist。
- accepted 以外状态不允许携带 `accepted_envelope`。

常见失败优先检查：

1. 测试仍假设 manual_review 可通过策略持久化。
2. writer helper 仍把 manual_review envelope 透传给 `WriteDecision`。
3. NoOp 测试误把“空存储”理解成“未尝试 persist 调用”。

## 7. Concept notes

1. **验证门禁结果** 与 **持久化副作用结果** 是两层语义。
2. `WriteDecision` 属于第一层：表达 gate decision（接受/拒绝/人工复核）。
3. sink 异常属于第二层：表达 side-effect 失败，当前策略是显式抛出，不做吞错。
4. 这种分层可以保持 writer 轻量且可审计，符合 Phase 1-3 的保守机制边界。

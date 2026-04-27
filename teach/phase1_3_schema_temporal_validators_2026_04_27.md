# Phase 1-3：Schema Validator 与 Conservative Temporal Validator（2026-04-27）

## 1. Analysis path

本次先阅读以下文件并确定边界后再实现：

- `src/schemas/state.py`
  - 确认 `Phase1StateEnvelope` 的结构闭环仍由模型构造期强约束负责（Direction A 不变）。
- `src/schemas/validation.py`
  - 确认 `ValidationIssue` / `StateValidationReport` 字段与 blocking 语义，保证新 validator 输出可直接被 write-gate 消费。
- `src/validators/provenance_validator.py`
  - 复用现有 validator 的 API 风格与报告构造模式，保持模块可组合。
- `tests/test_phase1_state_envelope.py`、`tests/test_provenance_validator.py`
  - 对齐现有测试断言风格，避免引入命名或行为漂移。

这些文件是正确入口，因为任务目标是“把结构校验外化为可复用机制模块”，而不是改写 schema 本体或编排层。

## 2. Change list

- `src/validators/schema_validator.py`
  - 新增 `validate_phase1_schema(candidate)` 对外入口。
  - 支持两类输入：
    - 原始 payload `dict[str, object]`
    - 已构造 `Phase1StateEnvelope`
  - payload 构造失败时捕获 `ValidationError` 并转换为 `StateValidationReport`。
  - 引入 issue_code：
    - `schema.invalid_payload`
    - `schema.field_error`
    - `schema.model_error`
  - 尽量保留 `ValidationError.loc` 到 `field_path`（如 `evidence_atoms[0].stage_id`）。
  - 所有 schema 失败统一 `blocking=True`。

- `src/validators/temporal_validator.py`
  - 新增 `validate_phase1_temporal(envelope)` 对外入口。
  - 实现 Phase 1-3 保守时序检查：
    1. `stage_context.created_at <= envelope.created_at`
    2. `board_init.initialized_at <= envelope.created_at`
    3. `stage_index == 0 -> parent_state_id is None`
    4. `parent_state_id is not None -> state_version >= 2`
  - 明确不检查 `clinical_time >= created_at`，允许临床事件早于系统建档时间。
  - 使用 issue_code：
    - `temporal.stage_after_envelope`
    - `temporal.board_after_envelope`
    - `temporal.invalid_root_parent`
    - `temporal.invalid_state_version`

- `src/validators/__init__.py`
  - 导出 schema/temporal validator 入口与常量，不破坏现有 provenance 导出。

- `tests/test_schema_validator.py`
  - 覆盖：有效 raw payload、非 dict malformed payload、缺失必填字段、嵌套对象非法、envelope-level model error、已构造 envelope。

- `tests/test_temporal_validator.py`
  - 覆盖：valid baseline、stage 时间晚于 envelope、board 时间晚于 envelope、root parent 非法、parent+低版本非法。
  - 增加一条保守性测试：`clinical_time` 早于 `created_at` 不报错。

- `docs/devlog.md`
  - 追加本次任务记录。

## 3. Connection mechanism

连接方式保持最小、可组合：

- 外部可直接调用：
  - `from src.validators import validate_phase1_schema`
  - `from src.validators import validate_phase1_temporal`
- 两个 validator 都返回 `StateValidationReport`，因此后续 write-gate 可以按 tuple 组合多个报告统一决策。
- 本次未改 pipeline、writer、storage、event-sourcing。

## 4. Runtime data flow

### 4.1 Schema validator 流程

1. 输入候选对象（payload 或 envelope）。
2. 若是 envelope：直接返回 valid report（不重复 envelope 级逻辑）。
3. 若是 payload：尝试构造 `Phase1StateEnvelope`。
4. 构造失败时捕获 `ValidationError`，逐条转成 `ValidationIssue`。
5. 产出 `StateValidationReport`（blocking issue 会让 `is_valid=False`）。

### 4.2 Temporal validator 流程

1. 输入已构造 envelope。
2. 执行 4 条保守时序规则。
3. 仅在“明确非法”时生成 blocking issue。
4. 产出 `StateValidationReport`，供后续 write-gate 聚合。

## 5. Self-service modification guide

后续若你要扩展该能力，建议按以下顺序：

1. 新增 schema 失败分类：编辑 `src/validators/schema_validator.py` 的 issue_code 映射与 target_kind 推断。
2. 新增 temporal 规则：编辑 `src/validators/temporal_validator.py`，每条规则保持独立 issue_code。
3. 若新增目标类型：先在 `src/schemas/validation.py` 扩展 `ValidationTargetKind`，再修改 validator 映射。
4. 任何规则变化都要同步更新：
   - `tests/test_schema_validator.py`
   - `tests/test_temporal_validator.py`
5. 若接入 write-gate，只消费 report，不在 validator 内做写入动作。

## 6. Validation method

建议运行以下命令：

```bash
python -m pytest -q tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py
```

预期：

- 两个新增测试文件全部通过。
- provenance validator 测试不回归。

常见失败排查：

1. `issue_id` 不符合 `issue_*` / `issue-*` 模式。
2. fallback `case_id` / `stage_id` 不符合 id pattern，导致 report 本身构造失败。
3. temporal 场景构造时触发了多个规则，导致断言应改为“包含某 issue_code”而非“仅一条 issue”。

## 7. Concept notes

### 7.1 为什么 schema validation 要与 model construction 分离

- 模型构造异常（`ValidationError`）适合做“硬边界阻断”，但不适合直接进入审计流水。
- write-gate 需要结构化、可归档的报告对象，而不是异常栈。
- 因此保留 `Phase1StateEnvelope` 的硬构造边界，同时新增外部 schema validator 把失败“翻译”为 `StateValidationReport`，实现：
  - 机制可组合
  - 审计可追踪
  - 与后续 gate 策略解耦

### 7.2 为什么 temporal validation 在 Phase 1-3 要保守

- 当前阶段目标是“最小可验证约束”，不是完整纵向病程重建。
- 过早引入跨阶段回放/事件日志推理，会把问题从机制层扩展到 orchestration 层，超出本 issue 范围。
- 所以仅保留明确、低歧义的 envelope 内规则，并把 `clinical_time` 视为可早于系统时间的临床事实时间，避免误判。

这个选择确保了：

- 规则可解释
- 阻断条件清晰
- 与未来事件源/跨阶段时序扩展兼容

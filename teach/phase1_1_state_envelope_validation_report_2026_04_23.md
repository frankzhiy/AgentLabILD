# Phase 1-1 StateValidationReport + Phase1StateEnvelope 教学说明（2026-04-23）

## 1. Analysis path

本次改动先读以下文件，再确定实现边界：

- src/schemas/stage.py
  - 确认 StageContext 的 stage-aware 约束风格（id pattern、extra forbid、阶段边界）。
- src/schemas/evidence.py
  - 确认 evidence_id/stage_id/source_doc_id 的命名与溯源约束，作为 envelope 的 evidence 侧引用基准。
- src/schemas/claim.py
  - 确认 ClaimReference 只负责 claim-to-evidence 链接，作为 envelope 的 claim 引用源。
- src/schemas/hypothesis.py
  - 确认 hypothesis 只消费 claim_ref_id，不绕过到 evidence_ids。
- src/schemas/action.py
  - 确认 action candidate 同样以 claim_ref_id 为依据输入。
- src/schemas/board.py
  - 确认 board root 的 ranked_hypothesis_ids 语义边界，并在 envelope 层补齐“ranked id 必须存在于 hypotheses”的跨对象校验。
- src/schemas/state.py
  - 确认当前仅是兼容导出层，需要在不破坏既有导出的前提下引入根 envelope。
- tests/* 既有 schema 测试
  - 复用当前测试风格：成功、失败、边界、导出兼容、序列化。

这些入口是正确起点，因为本任务是机制层状态收口，不是 agent 行为扩展。

## 2. Change list

### 新增 src/schemas/common.py

- 新增 `NonEmptyStr` 共享类型，避免在新增 schema 中重复定义同类基础约束。

### 新增 src/schemas/validation.py

- 新增 `ValidationSeverity`：`info` / `warning` / `error`。
- 新增 `ValidationIssue`：
  - `issue_code`
  - `severity`
  - `message`
  - `field_path`
  - `related_ids`
  - `non_authoritative_note`
- 新增 `StateValidationReport`：
  - `generated_at`
  - `is_valid`
  - `issues`
  - `validator_name`
  - `validator_version`
  - `summary`
- 报告内部一致性约束：
  - 若 `is_valid=True`，不允许出现 `error` 级 issue。
  - 若 `is_valid=False`，必须至少包含 1 条 issue。

### 修改 src/schemas/state.py

- 在保留原有兼容导出的基础上新增根对象 `Phase1StateEnvelope`。
- `Phase1StateEnvelope` 字段：
  - `case_id`
  - `stage_context`
  - `board_init`
  - `evidence_atoms`
  - `claim_references`
  - `hypotheses`
  - `action_candidates`
  - `validation_report`
  - `state_version`
  - `parent_state_id`
  - `created_at`
- envelope-level 一致性校验（本次任务核心）：
  - `stage_id` 对齐（board/evidence/claim/hypothesis/action 均需对齐 stage_context.stage_id）
  - 重复 id 检查（evidence/claim/hypothesis/action）
  - 缺失 claim 引用（hypothesis/action 引用的 claim_ref_id 必须存在）
  - 缺失 evidence 引用（claim 引用的 evidence_id 必须存在）
  - ranked hypothesis 存在性（board_init.ranked_hypothesis_ids 必须在 hypotheses 中存在）
- 兼容性保留：
  - `SkeletonState` 保留。
  - 既有导出项（StageContext/EvidenceAtom/ClaimReference/HypothesisState/ActionCandidate/HypothesisBoardInit）保留。
  - 新增导出 `ValidationSeverity`、`ValidationIssue`、`StateValidationReport`、`Phase1StateEnvelope`。

### 新增 tests/test_phase1_state_envelope.py

- 覆盖 `StateValidationReport` 成功/失败构造。
- 覆盖 `Phase1StateEnvelope` 成功构造。
- 覆盖 5 类要求中的失败场景：
  - stage_id 不对齐
  - duplicate ids
  - missing claim references
  - missing evidence references
  - ranked hypothesis ids not found in hypotheses
- 覆盖 state 模块新导出类型兼容。

### 修改 docs/devlog.md

- 追加本次任务记录、变更文件、动机与验证结果。

## 3. Connection mechanism

本次实现保持“机制对象可复用、集成由上层决定”的连接方式：

1. 各子对象仍可独立构建：`StageContext` / `EvidenceAtom` / `ClaimReference` / `HypothesisState` / `ActionCandidate` / `HypothesisBoardInit`。
2. `Phase1StateEnvelope` 作为根对象在写入前做跨对象一致性聚合校验。
3. 业务侧仍可通过 `src.schemas.state` 统一导入，避免调用方大面积改 import。
4. 没有改 pipeline 拓扑、仲裁器、冲突逻辑、更新管理或编排逻辑。

## 4. Runtime data flow

运行时从输入到输出的数据流：

1. 上游先准备阶段对象与各子对象（board/evidence/claim/hypothesis/action）。
2. 构建 `StateValidationReport`（仅作为结构化报告对象，不执行完整引擎逻辑）。
3. 将上述对象装入 `Phase1StateEnvelope`。
4. envelope 执行跨对象校验：
   - 检查 stage_id 对齐。
   - 检查重复对象 id。
   - 检查 claim 引用闭包。
   - 检查 evidence 引用闭包。
   - 检查 ranked hypothesis 的存在性。
5. 若任一规则失败，抛出 `ValidationError`，阻断状态进入可持久化层。
6. 若全部通过，得到可审计、可追溯、阶段化兼容的根状态对象。

## 5. Self-service modification guide

后续若要扩展，请按下面路径修改：

- 扩展严重级别：修改 `src/schemas/validation.py` 的 `ValidationSeverity`，并同步新增测试。
- 扩展 issue 字段：在 `ValidationIssue` 增加字段，并补 `extra=forbid` 下的兼容测试。
- 调整 envelope 一致性规则：在 `src/schemas/state.py` 的 `validate_envelope_consistency` 中增加明确规则与错误信息。
- 增加跨对象引用规则（例如 board_init.action_candidate_ids 闭包）：
  - 在 envelope validator 新增集合比较。
  - 增加一条失败单测 + 一条成功单测。
- 若要放宽规则以兼容历史数据：
  - 优先加可控兼容字段或迁移辅助函数。
  - 避免直接删除现有机制约束。

## 6. Validation method

建议命令：

```bash
python -m pytest -q tests/test_phase1_state_envelope.py
python -m pytest -q
```

本次实测结果：

- `tests/test_phase1_state_envelope.py`: 10 passed
- 全量测试: 109 passed

若失败，优先检查：

1. id 前缀是否混用（如 stage/doc/claim_ref/evd/hyp/action）。
2. 是否出现跨对象 stage_id 不一致。
3. hypothesis/action 的 claim_ref 引用是否缺失。
4. claim 的 evidence_ids 是否在 evidence_atoms 中存在。
5. board 的 ranked_hypothesis_ids 是否真的在 hypotheses 列表中出现。

## 7. Concept notes

涉及的核心概念：

- Pydantic v2 的“字段校验 + 模型校验”分层。
- 根状态封装（root envelope）用于跨对象一致性约束。
- 可追溯引用闭包（claim -> evidence，hypothesis/action -> claim）。
- 机制与报告分离：
  - `StateValidationReport` 是报告结构。
  - envelope validator 是结构一致性 gate。
- backward compatibility：
  - 在 `state.py` 保留既有导出并增量扩展，不打断旧调用路径。

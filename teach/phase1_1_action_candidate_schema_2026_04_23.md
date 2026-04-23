# Phase 1-1 ActionCandidate Schema 教学说明（2026-04-23）

## 1. Analysis path

优先阅读并对齐以下文件：
- src/schemas/stage.py：确认 stage-aware 对象的一致建模风格（`stage_id` 模式校验、`extra="forbid"`、去重规则）。
- src/schemas/claim.py：确认 claim 引用边界（`claim_ref_id` 是唯一权威桥接，不能被 free-text 或 direct evidence 替代）。
- src/schemas/hypothesis.py：复用 claim_ref 分桶、桶间重叠禁止、至少一条依据等关键机制模式。
- src/schemas/state.py：确认统一导出入口，避免调用方导入路径碎片化。
- tests/test_claim_reference_schema.py、tests/test_hypothesis_state_schema.py：对齐测试风格（成功/失败/边界/导出/序列化回环）。

这些文件是本任务的正确起点，因为本任务是“机制层 schema 补全”，而不是 agent 行为扩展。

## 2. Change list

- 新增 src/schemas/action.py
  - 新增枚举：
    - `ActionType`
    - `ActionStatus`
    - `ActionUrgency`
  - 新增 `ActionCandidate` 模型，包含字段：
    - `action_candidate_id`
    - `action_key`
    - `stage_id`
    - `action_type`
    - `action_text`
    - `status`
    - `urgency`
    - `linked_hypothesis_ids`
    - `supporting_claim_ref_ids`
    - `refuting_claim_ref_ids`
    - `missing_information_claim_ref_ids`
    - `safety_concern_claim_ref_ids`
    - `rank_index`
    - `non_authoritative_note`
  - 关键校验：
    - `action_candidate_id/stage_id/linked_hypothesis_ids/claim_ref_ids` pattern 校验。
    - 桶内去重。
    - 四个 claim_ref 桶间禁止交叉。
    - 四个 claim_ref 桶合计至少 1 条。
    - `blocked` 状态必须至少包含 1 条 `refuting` 或 `safety_concern` claim_ref。
    - `action_key` 归一化为 snake_case。
- 修改 src/schemas/state.py
  - 导出 `ActionCandidate`、`ActionType`、`ActionStatus`、`ActionUrgency`。
- 新增 tests/test_action_candidate_schema.py
  - 覆盖成功构造、id pattern 失败、重复失败、跨桶重叠失败、空依据失败、`blocked` 约束失败、禁止 direct `evidence_ids`、序列化回环、导出路径。
- 修改 docs/devlog.md
  - 追加本次任务记录与验证命令。

## 3. Connection mechanism

当前连接机制保持“显式导出 + 外部组装”，不改变 pipeline：
1. 上游先生成 `ClaimReference`（claim 与 evidence 的权威链接对象）。
2. `ActionCandidate` 只通过四类 `claim_ref_id` 分桶引用依据。
3. 调用方通过 `src.schemas.state` 统一导入 `ActionCandidate` 及其枚举。

本次没有引入仲裁、更新管理、最终管理计划逻辑，也没有修改实验配置或 pipeline 拓扑。

## 4. Runtime data flow

运行时从 payload 到权威对象的路径：
1. 输入 payload 进入 `ActionCandidate`。
2. 字段级校验：
   - `action_candidate_id`、`stage_id`、`linked_hypothesis_ids`、claim_ref 桶逐项校验 pattern。
   - `linked_hypothesis_ids` 与各 claim_ref 桶执行桶内去重。
   - `action_key` 归一化。
   - `rank_index` 做正整数边界校验。
3. 模型级校验：
   - 四类 claim_ref 桶至少有一条。
   - 四类 claim_ref 桶两两不重叠。
   - 若 `status=blocked`，必须有 `refuting` 或 `safety_concern` 依据。
4. 校验通过后产出可持久化候选行动对象；失败则抛出 `ValidationError`，供后续 gate/validator 拦截。

## 5. Self-service modification guide

若后续需要扩展，请按以下路径修改：
- 新增行动类型：扩展 `ActionType` 并补测试（枚举合法值、非法值）。
- 调整 blocked 规则：只改 `validate_claim_ref_boundaries`，并补充对应失败测试。
- 增加新的 claim_ref 桶：
  - 新增字段与 field validator。
  - 在模型级校验中加入“至少一条 + 桶间互斥”规则。
  - 增补跨桶冲突测试。
- 若后续需要可执行计划细节：应新增独立机制对象，不要把详细计划文本直接塞入 `action_text`。

## 6. Validation method

建议命令：
- `python -m pytest -q tests/test_action_candidate_schema.py`
- `python -m pytest -q`

预期结果：
- 新增 `ActionCandidate` 测试全部通过。
- 既有 StageContext/EvidenceAtom/ClaimReference/HypothesisState 测试无回归。

常见失败排查：
- `action_candidate_id` 是否符合 `action_*` / `action-*` / `action_candidate_*` / `action_candidate-*`。
- `stage_id` 是否使用 `stage` 前缀。
- claim 桶中是否误填 `evd-*` 或其他非 `claim_ref-*` id。
- `blocked` 状态是否缺少 `refuting` 或 `safety_concern` 依据。

## 7. Concept notes

涉及编程概念：
- Pydantic v2 的字段级校验与模型级校验协作。
- `StrEnum` 固化状态空间，避免自由文本状态漂移。
- `extra="forbid"` 约束 schema 表面，阻断未声明字段写入。

涉及机制设计概念：
- claim-reference-based：行动依据通过 claim 层显式连接证据，不允许 direct evidence shortcut。
- stage-aware：每个候选行动都要有 `stage_id` 锚点，保证阶段可追溯性。
- 候选对象边界：`ActionCandidate` 仅表达候选行动，不承担最终计划和仲裁职责。

## 8. Refinement note（same day）

- ActionStatus 已与 HypothesisStatus 对齐到同一优先级语义轴：
  - `under_consideration`
  - `prioritized`
  - `deprioritized`
  - 另保留动作层特有状态 `blocked`
- ActionType 已移除 `defer_pending_information`，避免与状态层 `deprioritized` 形成语义重叠。
- `start_or_adjust_treatment_trial` 已重命名为 `start_or_adjust_treatment`，保持候选动作层的中性表达，减少过早引入 trial 语义的风险。
- 测试新增 taxonomy 防回归断言，确保后续修改不会重新引入 status/type 维度混淆。

# Phase 1-1 结构闭环修复教学说明（2026-04-23）

## 1. Analysis path

本次任务先按“根状态一致性优先”的顺序分析：

1. src/schemas/state.py
- 先确认当前 envelope 只做了 claim_id 存在性校验，没有校验 claim 的 target 回指关系，也没有 board 与真实对象集合闭环。

2. src/schemas/claim.py / src/schemas/hypothesis.py / src/schemas/action.py
- 确认 HypothesisState 和 ActionCandidate 都是通过 claim_ref_ids 间接引用依据，适合把“反向 target 绑定”放在 envelope 层集中校验。

3. src/schemas/board.py
- 确认已有 ranked_hypothesis_ids ⊆ hypothesis_ids 规则，但没有验证 board 三组 ids 与 envelope 实体集合完全匹配。

4. src/schemas/common.py 与其他 schema
- 确认 id pattern 在多个文件重复定义，存在分散维护风险，适合统一到 common 并提供共享校验函数。

5. tests/test_phase1_state_envelope.py 与相关 schema tests
- 确认可在现有测试风格中补齐正/负例，不需要改 pipeline、agent 或 orchestrator。

## 2. Change list

### 修改 src/schemas/common.py
- 集中新增并导出共享 id pattern：
  - CASE_ID_PATTERN
  - STAGE_ID_PATTERN
  - EVIDENCE_ID_PATTERN
  - CLAIM_REF_ID_PATTERN
  - HYPOTHESIS_ID_PATTERN
  - ACTION_CANDIDATE_ID_PATTERN
  - BOARD_ID_PATTERN
  - STATE_ID_PATTERN
- 同步新增 SOURCE_DOC_ID_PATTERN / REPORT_ID_PATTERN / ISSUE_ID_PATTERN，供既有 schema 复用。
- 新增 `validate_id_pattern(...)`，把重复的 fullmatch+报错逻辑收敛为共享帮助函数。

### 修改 src/schemas/stage.py
- StageContext 新增 stage_id/case_id pattern 校验，且使用 common 的共享 pattern 与 helper。

### 修改 src/schemas/evidence.py
- evidence_id/stage_id/source_doc_id 校验改为复用 common 的共享 pattern 与 helper。

### 修改 src/schemas/claim.py
- claim_ref_id/stage_id 校验改为复用 common。
- ClaimTargetKind 的 action 目标规范化为 `"action"`。
- 新增 backward-aware 兼容：输入历史值 `"action_candidate"` 时自动归一化为 `"action"`。

### 修改 src/schemas/hypothesis.py
- hypothesis_id/stage_id/claim_ref_id 相关 pattern 校验改为复用 common。

### 修改 src/schemas/action.py
- action_candidate_id/stage_id/hypothesis_id/claim_ref_id 相关 pattern 校验改为复用 common。

### 修改 src/schemas/board.py
- board/case/stage/evidence/hypothesis/action id 的 pattern 校验改为复用 common。

### 修改 src/schemas/validation.py
- report/case/stage/board/issue id 的 pattern 校验改为复用 common。

### 修改 src/schemas/state.py
- `Phase1StateEnvelope` 新增必填字段 `state_id`（pattern 校验）。
- 保留 `parent_state_id` 可空规则，并新增：`parent_state_id != state_id`。
- 新增 envelope-level 结构闭环校验：
  1. Claim 双向绑定校验
  - Hypothesis 使用的每个 claim_ref_id，必须回指 `(target_kind=hypothesis, target_id=<hypothesis_id>)`
  - ActionCandidate 使用的每个 claim_ref_id，必须回指 `(target_kind=action, target_id=<action_candidate_id>)`
  - 阻断“借用他人 claim”

  2. board_init 与 envelope 实体集合闭环
  - board_init.evidence_ids 与 evidence_atoms ids 做集合相等
  - board_init.hypothesis_ids 与 hypotheses ids 做集合相等
  - board_init.action_candidate_ids 与 action_candidates ids 做集合相等
  - 采用 set equality（顺序无关，语义是成员闭环一致）

  3. ranked_hypothesis_ids 双重子集校验
  - 仍要求 ranked ⊆ board_init.hypothesis_ids
  - 并要求 ranked ⊆ envelope hypotheses ids

  4. linked_hypothesis_ids 实体存在性校验
  - 每个 ActionCandidate 的 linked_hypothesis_ids 必须都能在 hypotheses 中找到

- 把 envelope 内复杂逻辑拆成小 helper（claim link 收集、target mismatch 校验、board set mismatch 校验），避免巨型 validator。

### 修改 tests/test_claim_reference_schema.py
- 更新 action target 语义到 `ClaimTargetKind.ACTION`。
- 新增历史值 `"action_candidate"` 归一化测试。

### 修改 tests/test_phase1_state_envelope.py
- 基础 payload 增加 state_id。
- 基础 payload 让 hypothesis/action 各自使用对应 target 的 claim，形成“合法双向绑定”正例。
- 新增失败测试：
  - borrowed claim reference（action 借 hypothesis claim）
  - board 三组 id 与 envelope mismatch
  - missing linked_hypothesis_ids
  - parent_state_id == state_id
  - invalid state_id pattern
- 保留并兼容既有 stage 对齐/重复 id/缺失引用/ranked 校验测试。

### 新增 tests/test_common_id_patterns.py
- 覆盖共享 pattern 的正反例。
- 断言多个 schema 模块复用了 common 中同一 pattern 对象，验证“中心化规则被一致使用”。

## 3. Connection mechanism

本次改动保持“机制层可组合，不强耦合组装”：

1. 各子对象 schema（stage/evidence/claim/hypothesis/action/board/validation）仍可独立构建。
2. Phase1StateEnvelope 作为唯一根对象，在装配阶段做跨对象结构闭环校验。
3. 业务侧继续通过 `src.schemas.state` 导入，不需要改动 pipeline 或 agent 注册。
4. 没有新增 agent、orchestration、conflict、update-manager 逻辑。

## 4. Runtime data flow

运行时状态装配流程：

1. 上游构建 StageContext、EvidenceAtom、ClaimReference、HypothesisState、ActionCandidate、HypothesisBoardInit。
2. 构建 Phase1StateEnvelope（携带 state_id / parent_state_id / state_version）。
3. envelope 执行模型级校验：
- stage/case 对齐
- 对象 id 重复检测
- claim/evidence 引用存在性
- claim 双向 target 回指
- board 三组 ids 与真实对象集合闭环
- ranked 子集双重校验
- action linked_hypothesis_ids 实体存在性
- parent_state_id 与 state_id 自环阻断
4. 任一失败即抛 ValidationError，阻断持久化写入。
5. 全部通过后得到结构闭环的可写状态对象。

## 5. Self-service modification guide

后续若要扩展，可按以下位置修改：

1. 增加新 id 类型 pattern
- 修改 src/schemas/common.py，新增 pattern 常量并导出。
- 对应 schema 的字段校验统一调用 `validate_id_pattern(...)`。

2. 增加新的 envelope 闭环规则
- 修改 src/schemas/state.py：
  - 优先新增小 helper
  - 在 `validate_envelope_consistency` 调用 helper 并追加结构化错误文本

3. 调整 board 比较语义
- 若需从“集合相等”改为“顺序敏感”，仅需替换 `_append_board_set_mismatch_error` 内比较策略并更新测试。

4. 调整 claim target 词表
- 修改 src/schemas/claim.py 的 ClaimTargetKind。
- 同步更新 state.py 的 `_append_claim_target_mismatch_errors` 调用参数与测试。

## 6. Validation method

建议命令：

```bash
python -m pytest -q tests/test_claim_reference_schema.py tests/test_phase1_state_envelope.py tests/test_common_id_patterns.py
python -m pytest -q
```

本次实际验证结果：

- 目标测试集：51 passed
- 全量测试：144 passed

若出现失败，优先检查：

1. ClaimReference.target_kind 是否仍为 `action_candidate` 且未被归一化。
2. action/hypothesis 是否复用了不属于自己的 claim_ref。
3. board_init 三组 ids 是否与 envelope 实体集合完全一致。
4. linked_hypothesis_ids 是否引用了不存在 hypothesis。
5. state_id / parent_state_id 是否违反 pattern 或自环约束。

## 7. Concept notes

本次改动涉及的关键设计概念：

1. 双向引用完整性（bidirectional referential integrity）
- 不是只验证“被引用对象存在”，还要验证“被引用对象声明你是合法拥有者”。

2. 集合闭包（set closure）
- board 作为 root index，必须与 envelope 中真实对象集合一致，避免索引漂移。

3. 机制优先于提示词
- 所有关键约束落在可执行 schema validator，而不是 prompt 约定。

4. 中央规则源（single source of truth）
- id pattern 与基础校验规则集中到 common，降低规则分叉和维护成本。

5. 向后兼容中的“规范化输入”
- 对历史值做受控归一化（`action_candidate` -> `action`），同时把输出语义收敛到新的规范值。

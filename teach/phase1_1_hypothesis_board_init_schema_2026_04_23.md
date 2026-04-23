# Phase 1-1 HypothesisBoardInit Schema 教学说明（2026-04-23）

## 1. Analysis path

本次先阅读并对齐这些文件：
- src/schemas/stage.py：确认 stage-aware 对象的基础风格（`stage_id` 校验、`extra="forbid"`、去重校验）。
- src/schemas/evidence.py：复用 evidence id pattern（`ev_*` / `evd-*`）与“对象分层、不跨层混用 id”原则。
- src/schemas/claim.py：参考 id-only 关联和 strict schema boundary 的写法。
- src/schemas/hypothesis.py：对齐 hypothesis id pattern、去重与边界校验表达。
- src/schemas/action.py：复用 action id pattern 与非权威备注归一化策略。
- src/schemas/state.py：确认统一导出入口，避免调用方导入路径分裂。
- tests/test_*.py（stage/evidence/claim/hypothesis/action）：复用测试组织方式（成功 + 失败 + 边界 + 导出 + 序列化回环）。

这些文件是正确起点，因为本任务是 Phase 1 的“机制层 schema 落地”，不是 agent 扩展或仲裁逻辑开发。

## 2. Change list

- 新增 src/schemas/board.py
  - 新增枚举：
    - `BoardStatus`（当前仅 `initialized`）
    - `BoardInitSource`（`stage_bootstrap` / `parent_board_propagation` / `manual_structured_entry` / `migration`）
  - 新增模型：`HypothesisBoardInit`
  - 字段：
    - `board_id`
    - `case_id`
    - `stage_id`
    - `board_status`
    - `init_source`
    - `initialized_at`
    - `evidence_ids`
    - `hypothesis_ids`
    - `action_candidate_ids`
    - `ranked_hypothesis_ids`
    - `parent_board_id`
    - `non_authoritative_note`
  - 关键校验：
    - `hypothesis_ids` 必须非空。
    - `ranked_hypothesis_ids` 必须是 `hypothesis_ids` 子集。
    - `parent_board_id` 不得等于 `board_id`。
    - `evidence_ids` / `hypothesis_ids` / `action_candidate_ids` / `ranked_hypothesis_ids` 都做去重与 pattern 校验。
    - `extra="forbid"` + `str_strip_whitespace=True`。

- 修改 src/schemas/state.py
  - 新增导出：
    - `HypothesisBoardInit`
    - `BoardStatus`
    - `BoardInitSource`

- 新增 tests/test_hypothesis_board_init.py
  - 覆盖成功构造、核心失败路径、id pattern、去重、额外字段阻断、序列化回环、state 导出。

- 修改 docs/devlog.md
  - 追加本次任务的变更与验证记录。

## 3. Connection mechanism

当前连接机制是“显式 schema + 统一导出，不改 pipeline 拓扑”：
1. 上游机制产生 evidence/hypothesis/action 对象。
2. `HypothesisBoardInit` 只接收这些对象的 id 引用，不嵌入对象正文。
3. 调用方通过 `src.schemas.state` 统一导入 `HypothesisBoardInit`。

本次没有接入 conflict、arbitration、update manager，也没有修改实验 YAML 或 pipeline graph。

## 4. Runtime data flow

输入 payload 到权威对象的路径：
1. payload 进入 `HypothesisBoardInit`。
2. 字段级校验执行：
   - `board_id` / `stage_id` / 各 id 列表做 pattern 校验。
   - 各 id 列表执行去重。
   - `parent_board_id` 与 `non_authoritative_note` 做空白归一化。
3. 模型级校验执行：
   - `ranked_hypothesis_ids ⊆ hypothesis_ids`。
   - `parent_board_id != board_id`。
4. 校验通过后输出可持久化的阶段 board 根对象；失败则抛出 `ValidationError` 供后续 gate/validator 拦截。

## 5. Self-service modification guide

后续如果需要扩展，请按以下方式改：
- 增加 board 生命周期状态：扩展 `BoardStatus`，并补充枚举合法值和非法值测试。
- 增加初始化来源：扩展 `BoardInitSource`，并补充 parser/validation 测试。
- 增加新的 id 引用集合（例如 claim_ref 聚合）：
  - 新增字段 + pattern/去重校验。
  - 视需要在 model validator 增加跨字段一致性规则。
- 如果将来需要“跨阶段 board 演进逻辑”：建议新增独立 update/event schema，不要把状态迁移逻辑塞进 `HypothesisBoardInit`。

## 6. Validation method

执行命令：
- `python -m pytest -q tests/test_hypothesis_board_init.py`
- `python -m pytest -q`

本次结果：
- `tests/test_hypothesis_board_init.py`：16 passed
- 全量：94 passed

常见失败排查：
- `hypothesis_ids` 是否为空。
- `ranked_hypothesis_ids` 是否包含未出现在 `hypothesis_ids` 的 id。
- `parent_board_id` 是否与 `board_id` 相同。
- id 列表中是否误填了不匹配前缀（如把 `claim_ref-*` 填进 `evidence_ids`）。

## 7. Concept notes

涉及编程概念：
- Pydantic v2 的字段级校验与模型级校验组合。
- `StrEnum` 固化受控字段，避免自由文本漂移。
- `extra="forbid"` 约束 schema 表面，阻断未声明字段。

涉及机制设计概念：
- stage-scoped root object：board 是阶段容器入口，不是诊断结论容器。
- id-only reference boundary：board 只做对象引用层，保持轻量与可审计。
- mechanism-first：把约束放到可执行 schema 校验，而不是依赖提示词约定。

## 8. Refinement note（same day）

根据后续边界审查，本文件完成三项机制强化：

1. `case_id` 模式校验补齐
- 新增 `CASE_ID_PATTERN = ^case[_-]...`。
- 新增 `case_id` 字段级校验，避免 `case-001` / `patient_78` / `78-IPF` 等混用导致 board 根对象先失真。

2. `BoardStatus` 扩展为最小生命周期
- 从单值 `initialized` 扩展为：
  - `draft`
  - `initialized`
  - `ready_for_review`
- 这样既保留 `HypothesisBoardInit` 的初始化语义，也为后续阶段共享/审阅衔接提供最小状态空间。

3. `init_source` 与 `parent_board_id` 联动约束
- 当 `init_source=parent_board_propagation` 时，`parent_board_id` 必填。
- 当 `init_source=stage_bootstrap` 时，`parent_board_id` 必须为空。
- 该联动约束确保来源语义与父板关系一致，避免“有来源无父板”或“bootstrap 却带父板”的结构化脏数据进入状态层。

对应测试也已补齐：
- `case_id` pattern 失败路径。
- `BoardStatus` taxonomy 断言。
- `init_source` 与 `parent_board_id` 的正反例联动断言。

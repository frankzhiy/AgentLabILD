# Phase 1-1 ClaimReference Schema 教学说明（2026-04-23）

## 1. Analysis path

优先检查 src/schemas/stage.py、src/schemas/evidence.py、src/schemas/state.py，原因如下：
- stage.py 提供 stage_id 的语义锚点与 schema 风格（extra forbid、strip whitespace、显式 validator）。
- evidence.py 已实现 id pattern 防混用与 snake_case 归一化逻辑，可直接复用机制设计原则。
- state.py 是当前兼容导出的入口，需要同步暴露 ClaimReference 以避免后续导入断裂。

随后检查 tests/test_evidence_schema.py 与 tests/test_stage_context.py，确认测试风格为：
- happy path + failure path 并重
- 明确断言结构化字段
- 明确覆盖边界条件与兼容导出

## 2. Change list

- 新增 src/schemas/claim.py
  - 增加枚举：
    - ClaimTargetKind：hypothesis、action_candidate
    - ClaimRelation：supports、refutes、indicates_missing_information_for、raises_safety_concern_for
    - ClaimStrength：weak、moderate、strong
  - 增加 Pydantic 模型 ClaimReference，字段：
    - claim_ref_id, stage_id, target_kind, target_id, claim_text, relation, evidence_ids
    - claim_key (optional), strength (optional), non_authoritative_note (optional)
  - 增加严格校验：
    - extra="forbid"
    - str_strip_whitespace=True
    - evidence_ids 非空且不可重复
    - claim_key 归一化为 snake_case
    - target_id 不能等于 claim_ref_id
    - claim_ref_id/stage_id/target_id 的 pattern 边界校验
    - claim_text 限制最大长度 300，防止长段解释文本回流到 ClaimReference
  - 明确语义边界：
    - strength = claim-to-target relation strength，不是诊断置信度
    - claim_ref_id = 对象实例唯一 id
    - claim_key = 语义对齐/去重键，不是对象身份
- 修改 src/schemas/state.py
  - 兼容导出 ClaimReference 与相关枚举，便于从 shared state 统一入口导入。
- 新增 tests/test_claim_reference_schema.py
  - 覆盖 valid construction、duplicate evidence_ids、empty evidence_ids、claim_key normalization、id pattern failure、自引用 failure、target_kind 与 target_id 不匹配 failure。
- 新增 teach/phase1_1_claim_reference_schema_2026_04_23.md
  - 记录分析路径、改动点、连接机制、运行时数据流与自助修改指南。
- 修改 docs/devlog.md
  - 追加 2026-04-23 的 ClaimReference 变更条目与验证命令。

## 3. Connection mechanism

当前连接机制是显式导出而非隐式注入：
1. 上游机制构造 ClaimReference 对象（通常在 extraction/validation 之后）。
2. 下游通过 src.schemas.state 的兼容导出读取 ClaimReference 类型。
3. 后续 HypothesisState / ActionCandidate 只需要消费 claim_ref_id 与 evidence_ids，即可建立可追溯桥接。

本次没有改动 orchestration、experiment YAML、pipeline topology，保持“机制部件先独立可用”的 Lego 式交付。

## 4. Runtime data flow

运行时数据流（ClaimReference 创建路径）：
1. 输入 payload 进入 ClaimReference。
2. 字段级处理执行：
   - 去首尾空白（str_strip_whitespace）。
   - claim_key 归一化为 snake_case。
   - non_authoritative_note 空白归一化为 None。
3. 字段级校验执行：
   - claim_ref_id/stage_id pattern。
  - claim_text 长度上限（300）。
   - evidence_ids 非空与去重校验。
4. 模型级校验执行：
   - target_id != claim_ref_id。
   - target_kind 与 target_id pattern 一致性。
5. 通过后产出权威 claim-to-evidence 链接对象；失败则抛出 ValidationError，由后续 gate 处理。

## 5. Self-service modification guide

若后续需要扩展：
- 新增 relation 类型：
  - 在 ClaimRelation 增加枚举值。
  - 补充对应失败/成功测试，防止词表漂移。
- 新增 target_kind：
  - 在 ClaimTargetKind 增加值。
  - 在 model_validator 中补 target_id pattern 分支。
  - 添加至少 1 个成功 + 1 个失败测试。
- 调整 id 规范：
  - 只修改 regex 常量与测试，不要用“跨字段不相等”替代字段语义校验。
- 若需更强 claim_key 约束：
  - 在 normalize_claim_key 之后增加长度或字符集规则，并同步测试。
- 若需更强“原子性”保障：
  - 建议在 validator 层增加规则（例如并列连接词数量、句号数量、跨段落检测），不要在 schema 层引入复杂 NLP 逻辑。

## 6. Validation method

建议验证命令：
- python -m pytest -q tests/test_claim_reference_schema.py
- python -m pytest -q

预期结果：
- 新增测试全部通过。
- 旧有 StageContext 与 EvidenceAtom 测试不回归。

常见失败优先检查：
- claim_ref_id 是否符合 claim_ref_*/claim_ref-*。
- target_kind 与 target_id 前缀是否匹配（hypothesis vs action_candidate）。
- evidence_ids 是否为空或包含重复项。
- claim_text 是否超过 300 字符。

## 7. Concept notes

已实现事实：
- ClaimReference 已成为独立、强约束、可追溯的 schema 机制对象。
- 通过 state 兼容导出可被后续状态层直接消费。
- strength 已明确定义为关系强度，不与 HypothesisState.confidence 混用。

合理推断：
- 该对象可作为未来 HypothesisState / ActionCandidate 的统一证据引用桥，不需要复制证据内容。

可选扩展：
- 未来可增加 claim 版本字段或事件日志绑定字段，但应在 Phase 1-1 之后、并由 validator/gate 一并治理。

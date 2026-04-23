# Phase 1-1 HypothesisState Schema 教学说明（2026-04-23）

## 1. Analysis path

优先阅读以下文件，并据此确定新增对象边界：
- src/schemas/stage.py：确认 stage-aware 对象的一致字段风格（stage_id 模式、extra forbid、去重校验）。
- src/schemas/evidence.py：确认证据层与 id pattern 防混用策略，避免在 HypothesisState 直接复用 evidence_id。
- src/schemas/claim.py：确认 claim_ref_id 与 evidence_id 的桥接责任，保证 HypothesisState 不绕过 ClaimReference。
- src/schemas/state.py：确认兼容导出入口，后续统一从 state 模块对外暴露新 schema。
- tests/test_stage_context.py、tests/test_evidence_schema.py、tests/test_claim_reference_schema.py：复用现有测试风格（成功/失败/边界/序列化/导出覆盖）。

这些文件是正确起点，因为本次任务本质是“状态层机制补全”，而不是 agent 行为扩展。

## 2. Change list

- 新增 src/schemas/hypothesis.py
  - 新增枚举：
    - HypothesisStatus：under_consideration、prioritized、deprioritized、ruled_out。
    - HypothesisConfidenceLevel：very_low、low、moderate、high、very_high。
  - 新增 HypothesisState 模型，关键字段：
    - hypothesis_id（当前对象实例 id）
    - hypothesis_key（跨阶段语义对齐键，可为空）
    - stage_id（阶段锚点）
    - hypothesis_label（短标签，非长文本诊断）
    - status / confidence_level
    - supporting_claim_ref_ids / refuting_claim_ref_ids / missing_information_claim_ref_ids
    - rank_index（可选）
    - next_best_test（可选）
    - non_authoritative_note（可选）
  - 关键校验：
    - hypothesis_id / stage_id / claim_ref_id pattern 校验。
    - hypothesis_key 归一化为 snake_case。
    - 三个 claim_ref 分桶各自去重。
    - 三个 claim_ref 分桶之间禁止交叉复用。
    - 至少存在 1 条 claim_ref_id，阻断“无依据候选假设”。
    - next_best_test 与 non_authoritative_note 空白归一化。
- 修改 src/schemas/state.py
  - 导出 HypothesisState、HypothesisStatus、HypothesisConfidenceLevel，保持兼容统一入口。
- 新增 tests/test_hypothesis_state_schema.py
  - 覆盖：有效构造、id 模式失败、分桶重复失败、分桶交叉失败、空桶失败、direct evidence 绕过失败、rank 边界、可选文本归一化、枚举失败、序列化回环、state 导出校验。
- 修改 docs/devlog.md
  - 追加本次任务记录和验证命令。

## 3. Connection mechanism

连接机制保持“显式导出 + 外部组装”：
1. 上游先产出 ClaimReference（claim 与 evidence 的链接对象）。
2. HypothesisState 只引用 claim_ref_id（按支持/反驳/缺失信息分桶）。
3. 业务模块通过 src.schemas.state 统一导入 HypothesisState。

本次没有修改 pipeline 拓扑、实验 YAML、仲裁器或 action 规划，符合最小交付边界。

## 4. Runtime data flow

运行时从 payload 到对象的流转如下：
1. payload 进入 HypothesisState。
2. 字段级校验执行：
   - hypothesis_id、stage_id、claim_ref_ids 模式校验。
   - 三类 claim_ref_ids 桶内去重。
   - rank_index 边界校验（>=1）。
   - next_best_test/non_authoritative_note 空白归一化。
3. 模型级校验执行：
   - 至少存在 1 个 claim_ref_id。
   - supporting/refuting/missing_information 三桶之间禁止交叉。
4. 校验通过后产出权威候选假设对象；失败时抛 ValidationError 供后续 gate/validator 处理。

## 5. Self-service modification guide

如需后续扩展，建议按以下方式修改：
- 增加状态枚举：修改 HypothesisStatus，并补充状态相关失败测试。
- 增加置信度等级：修改 HypothesisConfidenceLevel，并补充枚举非法值测试。
- 若需跨阶段语义对齐：优先设置 hypothesis_key，不要复用 hypothesis_id 承担语义身份。
- 调整 id 规范：仅改 regex 常量与测试，不要用松散字符串判断替代。
- 新增 claim 分桶：
  - 先新增字段，再在 model_validator 明确跨桶互斥规则。
  - 同步补“桶间冲突失败”测试。
- 若 next_best_test 需要结构化：优先新增独立对象字段（例如 test_code / intent），不要扩展成长文本计划。

## 6. Validation method

建议命令：
- python -m pytest -q tests/test_hypothesis_state_schema.py
- python -m pytest -q

预期结果：
- HypothesisState 新增测试通过。
- StageContext / EvidenceAtom / ClaimReference 旧测试无回归。

常见失败排查：
- hypothesis_id 是否符合 hyp_*/hyp-* 或 hypothesis_*/hypothesis-*。
- stage_id 是否符合 stage_*/stage-*。
- claim_ref id 是否误填 evd/doc/stage 前缀。
- claim_ref 是否在多个桶重复出现。

## 7. Concept notes

涉及的编程概念：
- Pydantic v2 字段级与模型级校验协作。
- 受控枚举（StrEnum）确保状态空间可审计。
- extra="forbid" 约束 schema 表面，阻断未声明字段（包括暂不启用的 kind）。

涉及的框架概念：
- state.py 作为兼容导出层，避免调用方散落导入路径。
- “claim_ref 先行、hypothesis 后挂载”的机制分层，防止证据链绕行。

涉及的设计概念：
- 机制优先：结构化约束先于 prompt 文本解释。
- 审计优先：每个候选假设必须可追溯到 claim_ref，而非自由文本结论。

## 8. Refinement note（same day）

- 当前版本将 hypothesis_id 与 hypothesis_key 解耦：
  - hypothesis_id = 对象实例 id
  - hypothesis_key = 跨阶段语义对齐键
- 当前版本已将 ACTIVE 移除，改为 UNDER_CONSIDERATION/PRIORITIZED 词表，降低与疾病活动性语义混淆风险。

## 9. Refinement note（same day）

- 当前版本已移除 HypothesisState.kind。
- 原因：在尚未引入多类型联合状态容器前，保持与 StageContext/EvidenceAtom/ClaimReference 一致的窄 schema 风格。
- 若未来确实进入混合记录容器（需要 discriminator），应在同一批次统一评估并引入 kind，而不是仅在单个对象先行添加。

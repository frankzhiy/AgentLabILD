# Phase 1-1 EvidenceAtom Schema 教学说明（2026-04-22）

## 1. Analysis path

首先阅读 src/schemas/stage.py，确认现有 Phase 1-1 的建模风格（StrEnum、Pydantic v2 validator、extra forbid、中文模块边界说明）。
然后阅读 src/schemas/state.py，确认兼容导出入口应放在 state 兼容层而不是直接改 pipeline。
接着阅读 .github/copilot-instructions.md、.github/instructions/schemas.instructions.md、AGENTS.md，锁定机制优先、最小交付、不可混入诊断逻辑等硬约束。
最后阅读 tests/test_stage_context.py 与 tests.instructions.md，对齐测试结构与失败用例覆盖风格。

## 2. Change list

- 新增 src/schemas/evidence.py
  - 新增 EvidenceAtom 模型与 5 个受控枚举：EvidenceCategory、EvidencePolarity、EvidenceCertainty、EvidenceTemporality、EvidenceSubject。
  - 复用 InfoModality 作为 modality 字段类型，确保 stage 层和 evidence 层模态字典一致。
  - 增加校验器：
    - 权威字段非空（通过 NonEmptyStr + str_strip_whitespace）。
    - 关键标识去重别名校验（evidence_id、stage_id、source_doc_id 不允许同值）。
    - source span 成对与顺序校验（start/end 同时存在且 start <= end）。
    - normalized_key 归一化（小写、非字母数字转下划线、连续下划线折叠）。
- 修改 src/schemas/state.py
  - 兼容导出 EvidenceAtom，保持浅层导入路径稳定。
- 新增 tests/test_evidence_schema.py
  - 覆盖成功构造、枚举失败、空字段失败、id 别名冲突失败、source span 边界失败、归一化行为、额外字段拒绝、序列化回环、兼容导出检查。
- 修改 docs/devlog.md
  - 追加本次任务记录与验证方式。

## 3. Connection mechanism

本次没有修改 pipeline、实验配置或注册表。
连接机制是“兼容导出 + 按需导入”：
- 业务方可直接从 src.schemas.evidence 导入 EvidenceAtom。
- 兼容路径可从 src.schemas.state 导入 EvidenceAtom，保持历史浅层引用不破坏。

## 4. Runtime data flow

运行时数据流如下：
1. 上游抽取器产生证据候选字段（包含 stage_id、source_doc_id、statement、raw_excerpt 等）。
2. 构造 EvidenceAtom 时先执行字段级归一化：可选文本清洗、normalized_key 规范化。
3. 执行模型级校验：
   - 标识字段不允许别名冲突。
   - source_span_start/source_span_end 必须成对且顺序合法。
4. 校验通过后输出可序列化的 EvidenceAtom，用于后续 ClaimReference 或 HypothesisState 的证据引用。
5. 校验失败时抛出 ValidationError，供后续 writer gate 阻断持久化写入。

## 5. Self-service modification guide

后续如需扩展，请优先在 src/schemas/evidence.py 做局部改动：
- 增加证据类型：扩展 EvidenceCategory，但不要引入诊断结论类别。
- 调整 certainty 或 temporality 粒度：修改对应枚举并补测试。
- 修改 normalized_key 规则：仅改 normalize_normalized_key，保持结果可审计、可预测。
- 若新增列表字段：补充去重校验，避免状态内重复元素。

## 6. Validation method

验证命令：
- python -m pytest -q

本次预期结果：
- 25 passed

常见失败排查：
- 枚举值拼写不在受控集合内。
- source_span_start/source_span_end 只给了一个端点。
- source_span_start 大于 source_span_end。
- evidence_id、stage_id、source_doc_id 出现同值别名冲突。

## 7. Concept notes

- Pydantic v2 校验分层：field_validator 适合单字段归一化，model_validator 适合跨字段约束。
- StrEnum 的价值：保证受控词表稳定，降低自由文本漂移带来的不可审计风险。
- 机制边界思想：EvidenceAtom 只表达“事实证据单元”，不承担诊断、仲裁、行动规划职责。
- 阶段可追溯思想：证据必须锚定 stage_id 与 source_doc_id，为后续局部修订与审计回放提供基础。

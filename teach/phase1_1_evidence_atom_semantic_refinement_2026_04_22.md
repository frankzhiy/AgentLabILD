# Phase 1-1 EvidenceAtom 语义重构教学说明（2026-04-22）

## 1. Analysis path

首先检查 src/schemas/evidence.py，定位现有风险点：
- 使用“evidence_id/stage_id/source_doc_id 三字段不能相等”作为防混用规则，语义过强且可能误伤。
- category 粒度混杂来源维度与语义维度。
- temporality 对纵向变化拆分不足。
- subject 中 EXPOSURE_SOURCE 与 subject 字段语义层级不一致。

然后检查 tests/test_evidence_schema.py，确认需要同步替换失败用例与枚举断言。
最后确认 state 兼容导出不需要改动结构，仅需保证 EvidenceAtom API 稳定。

## 2. Change list

- 修改 src/schemas/evidence.py
  - 删除 validate_id_alias_collision。
  - 新增 id 命名模式校验：
    - evidence_id: ev_/evd_ 前缀（兼容连字符）。
    - stage_id: stage_ 前缀（兼容连字符）。
    - source_doc_id: doc_ 前缀（兼容连字符）。
  - 重构 EvidenceCategory 为临床语义优先：
    - demographic/exposure/symptom/sign/lab_finding/pulmonary_function_finding/imaging_finding/pathology_finding/treatment_history/disease_course/family_history/other。
  - 调整 EvidenceCertainty：
    - asserted/reported/suspected/confirmed。
  - 扩展 EvidenceTemporality：
    - historical/current/newly_observed/persistent/worsening/improving/unspecified。
  - 调整 EvidenceSubject：
    - patient/family_member/environment/external_report/other。
  - 新增 category-modality 一致性校验（轻量白名单映射）。
- 修改 tests/test_evidence_schema.py
  - 替换旧别名冲突用例为 id pattern 防混用用例。
  - 新增 category-modality 冲突阻断测试。
  - 新增 temporality 与 subject 枚举集合断言。
  - 保留既有边界测试（source span、normalized_key、extra forbid、序列化回环、兼容导出）。

## 3. Connection mechanism

这次修改仍然是纯 schema 层机制强化：
- 上游抽取器不需要知道内部 validator 细节，只要按字段约定构造 EvidenceAtom。
- 下游 ClaimReference/HypothesisState 继续引用 evidence_id，不受本次接口重构影响。
- src.schemas.state 中 EvidenceAtom 兼容导出仍有效。

## 4. Runtime data flow

运行时流程：
1. 上游传入 EvidenceAtom 原始字段。
2. 字段级归一化执行（可选文本去空、normalized_key 归一化）。
3. id pattern 校验执行，阻断 stage/doc/evidence 字段混填。
4. source span 边界校验执行（成对出现且 start <= end）。
5. category-modality 一致性校验执行，阻断语义冲突组合。
6. 通过校验后输出可持久化的证据原子；失败则抛出 ValidationError 交给 gate 处理。

## 5. Self-service modification guide

后续若需要扩展：
- 增加 category：先加枚举值，再补 ALLOWED_MODALITIES_BY_CATEGORY，再加正反测试。
- 调整 id 规范：只改三个 PATTERN 常量与对应测试，不要回到“字段值互斥相等”替代规则。
- 若要收紧 OTHER：把 OTHER 的允许模态从空集合（放行）改成显式集合并补回归测试。
- 若上游已有旧 certainty 词表（如 likely/possible）：可在适配层转换，不建议在状态 schema 内做隐式兼容。

## 6. Validation method

命令：
- python -m pytest -q

本次结果：
- 32 passed

若失败，优先检查：
- id 前缀是否与字段角色一致。
- category 与 modality 是否组合冲突（例如 pathology_finding + pft）。
- temporality/certainty 是否仍使用旧词表。

## 7. Concept notes

- 替代规则风险：
  “三字段不相等”并不等价于“字段不混用”，容易误杀合法样例，也难解释错误意图。
- 命名模式校验的价值：
  直接对齐字段角色，错误定位清晰，且便于后续迁移适配。
- 语义分层原则：
  category 表达临床语义，modality 表达来源渠道，二者通过轻量一致性规则耦合，避免自由组合漂移。
- 纵向修订友好：
  temporality 提前细分 newly_observed/persistent/worsening/improving，为后续 staged revision 与冲突检测保留信息分辨率。

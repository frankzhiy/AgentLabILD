# Phase 1-2 provenance 包教学说明（2026-04-23）

## 1. Analysis path

本次任务先按“边界不破坏 + 可追溯增强”的顺序分析：

1. src/schemas/evidence.py / src/schemas/claim.py
- 先确认 EvidenceAtom 与 ClaimReference 当前字段边界、id pattern 与模型校验方式，保证新增 provenance 不会破坏既有 payload。

2. src/schemas/stage.py / src/schemas/common.py
- 复用已有 stage_id、source_doc_id、evidence_id、claim_ref_id 的命名模式校验，保持 schema 风格一致。

3. docs/devlog.md 与既有 tests
- 对齐已有记录与测试风格，确保新增机制对象具备 success/failure/boundary 测试，不仅覆盖 happy path。

4. src/provenance/
- 将 provenance 能力独立在 package 内实现，避免直接侵入 orchestrator、writer gate 或 pipeline。

## 2. Change list

### 新增 src/provenance/model.py
- 新增四个最小 PROV-lite 模型：
  - SourceAnchor
  - ExtractionActivity
  - EvidenceProvenance
  - ClaimProvenance
- 设计要点：
  - 所有对象均为显式 id（pattern 校验）
  - 全部 stage-aware（含 stage_id，并做跨对象 stage 对齐校验）
  - 不使用自由文本 provenance blob，采用结构化字段（source anchor、activity、id 列表）
  - extra="forbid" + str_strip_whitespace=True
  - 对重复 id、空集合、span 边界、来源文档覆盖关系进行显式校验

### 修改 src/provenance/__init__.py
- 导出 PROV-lite 公开对象：
  - SourceAnchor
  - ExtractionActivity
  - ExtractionMethod
  - EvidenceProvenance
  - ClaimProvenance

### 修改 src/schemas/evidence.py
- 给 EvidenceAtom 增加可选字段：
  - provenance: EvidenceProvenance | None = None
- 新增一致性校验：
  - provenance.stage_id 必须等于 evidence.stage_id
  - provenance.evidence_id 必须等于 evidence_id
- 向后兼容：旧 payload 不传 provenance 时行为不变。

### 修改 src/schemas/claim.py
- 给 ClaimReference 增加可选字段：
  - provenance: ClaimProvenance | None = None
- 新增一致性校验：
  - provenance.stage_id 必须等于 claim.stage_id
  - provenance.claim_ref_id 必须等于 claim_ref_id
  - provenance.evidence_ids 必须是 claim.evidence_ids 的子集
- 向后兼容：旧 payload 不传 provenance 时行为不变。

### 新增 tests/test_provenance_model.py
- 覆盖内容：
  - SourceAnchor 的合法构造与 span 边界失败
  - ExtractionActivity 的输入文档列表非空/去重失败
  - EvidenceProvenance 的 stage 对齐与来源文档覆盖失败
  - ClaimProvenance 的证据列表失败与重复 provenance id 失败
  - EvidenceAtom/ClaimReference 的无 provenance 向后兼容
  - EvidenceAtom/ClaimReference 的 provenance 对齐成功与失败

### 修改 docs/devlog.md
- 追加本次任务记录、变更文件与验证命令结果。

## 3. Connection mechanism

本次改动采用“独立机制对象 + 可选挂接”的连接方式：

1. provenance 模型位于 src/provenance/model.py，作为独立 package 能力。
2. EvidenceAtom 与 ClaimReference 仅新增可选 provenance 字段，不替换现有核心字段。
3. 现有调用方可分阶段接入：
- 不传 provenance：完全走旧路径。
- 传 provenance：自动触发额外一致性校验。
4. 未改动 writer gate、pipeline、orchestration、experiment YAML。

## 4. Runtime data flow

运行时数据流（本次范围内）：

1. 上游构造 SourceAnchor（文档锚点）与 ExtractionActivity（抽取活动）。
2. 用上述对象构造 EvidenceProvenance，并绑定 evidence_id + stage_id。
3. 可选地把 EvidenceProvenance 挂到 EvidenceAtom.provenance。
4. 上游构造 ClaimProvenance（claim_ref_id + evidence_ids + derivation_activity）。
5. 可选地把 ClaimProvenance 挂到 ClaimReference.provenance。
6. Pydantic 校验阶段执行：
- id pattern
- stage 对齐
- 来源文档覆盖关系
- evidence 子集关系
7. 任一失败抛 ValidationError，阻断无效对象进入共享状态。

## 5. Self-service modification guide

后续若需要扩展 provenance，可按以下路径修改：

1. 增加 provenance id 词表/前缀
- 修改 src/provenance/model.py 内 pattern 常量。
- 同步补充 tests/test_provenance_model.py 的正反例。

2. 增加 extraction_method 类型
- 修改 ExtractionMethod 枚举。
- 增加合法值与非法值测试。

3. 强化 claim 与 evidence provenance 的联动
- 在 ClaimProvenance 增加跨字段校验（例如要求 evidence_provenance_ids 非空）。
- 同步更新 ClaimReference 的 provenance 对齐规则。

4. 未来演进到 id-only 引用
- 先在 schema 中保持兼容字段并新增 adapter。
- 在明确迁移窗口前，不直接移除 EvidenceAtom/ClaimReference 现有结构字段。

## 6. Validation method

建议验证命令：

```bash
python -m pytest -q tests/test_provenance_model.py tests/test_evidence_schema.py tests/test_claim_reference_schema.py
python -m pytest -q
```

本次实际结果：

- 定向测试：46 passed
- 全量测试：158 passed

若失败，优先检查：

1. provenance 与宿主对象 stage_id 是否一致。
2. provenance 与宿主对象主键（evidence_id / claim_ref_id）是否一致。
3. source_anchors 的 source_doc_id 是否被 extraction_activity.input_source_doc_ids 覆盖。
4. claim provenance 的 evidence_ids 是否超出 claim.evidence_ids。

## 7. Concept notes

本次涉及的关键概念：

1. PROV-lite
- 使用最小必要结构表达“谁从哪里抽取了什么”，避免过度工程化。

2. Stage-aware traceability
- provenance 不仅要能追到 source，还要绑定 stage 以支持分阶段修订。

3. Backward-compatible augmentation
- 通过可选字段扩展而非替换旧字段，降低集成成本。

4. Mechanism-first constraints
- 关键边界由可执行 schema validator 保证，而非依赖 prompt 约定。

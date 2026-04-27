# Phase 1：Raw Text Intake Layer（2026-04-27）

## 1. Analysis path

本次实现按以下顺序分析：

1. 先读现有状态层核心模型与边界：
   - src/schemas/common.py
   - src/schemas/stage.py
   - src/schemas/evidence.py
   - src/schemas/validation.py
   - src/schemas/state.py
2. 再读现有 validator 与写门控：
   - src/validators/provenance_validator.py
   - src/validators/pipeline.py
   - src/state/state_writer.py
3. 最后对齐测试与文档风格：
   - tests/test_state_writer.py
   - tests/test_validation_pipeline.py
   - docs/devlog.md

这样做的原因是先锁定 Phase1StateEnvelope 与 attempt_phase1_write 的既有不变边界，再把 intake 作为前置层接入，避免把 raw 文本直接写入 authoritative state。

## 2. Change list

新增与修改如下：

1. 新增 intake schema：
   - src/schemas/intake.py
   - 定义 RawInputEvent、SourceDocument、StageResolutionReport
   - 追加 RawIntakeDecision、RawIntakeStatus（用于 intake gate 决策返回）

2. 新增 schema 导出：
   - src/schemas/__init__.py

3. 新增 intake 运行时工具：
   - src/intake/registry.py
   - src/intake/validators.py
   - src/intake/intake_gate.py
   - src/intake/__init__.py

4. 扩展 provenance bridge 校验：
   - src/validators/provenance_validator.py
   - src/validators/__init__.py
   - 新增 validate_evidence_atoms_against_sources(...)

5. 新增测试：
   - tests/test_intake_schemas.py
   - tests/test_intake_gate.py
   - tests/test_source_document_evidence_alignment.py

## 3. Connection mechanism

连接关系是显式分层的：

1. 外部输入 raw 文本先进入 RawInputEvent。
2. RawInputEvent 再转换为 SourceDocument（可被 EvidenceAtom.source_doc_id 引用）。
3. 之后才允许做 source/evidence 对齐校验。
4. 后续阶段才会进入 EvidenceAtom / ClaimReference / HypothesisState / ActionCandidate 候选构造。
5. authoritative 写入仍由原有 attempt_phase1_write 与 validator pipeline 决定。

本次没有把 RawInputEvent/SourceDocument 并入 Phase1StateEnvelope。

## 4. Runtime data flow

当前新增的数据流是：

1. 调用 attempt_raw_intake(...)。
2. gate 内部执行 register_raw_input_event(...)，得到 RawInputEvent。
3. 通过 create_source_document_from_raw_input(...) 生成 SourceDocument。
4. 运行 validate_intake_bundle(...) 做 intake 层一致性检查。
5. 输出 RawIntakeDecision（accepted/rejected/manual_review）。
6. 如需校验证据锚定，调用 validate_evidence_atoms_against_sources(...) 生成 StateValidationReport。

注意：该流程不触发 attempt_phase1_write，不产生 authoritative Phase1StateEnvelope 持久化行为。

## 5. Self-service modification guide

后续你若要扩展本层，可以按以下方式自助修改：

1. 若要增加 intake 模式或 source 类型：
   - 修改 src/schemas/intake.py 中 RawInputMode 或 SourceDocumentType。

2. 若要调整 id 规则：
   - 修改 src/schemas/intake.py 中 INPUT_EVENT_ID_PATTERN 或 STAGE_RESOLUTION_ID_PATTERN。

3. 若要改变 intake gate 的人工复核策略：
   - 修改 src/intake/intake_gate.py 中 manual_review 判定分支。

4. 若要扩展 source/evidence 对齐策略：
   - 修改 src/validators/provenance_validator.py 中 validate_evidence_atoms_against_sources。

5. 若要把 StageResolutionReport 纳入后续编排：
   - 在 orchestration 层引入，不要直接改写 Phase1StateEnvelope 结构边界。

## 6. Validation method

建议命令：

```bash
python -m pytest -q tests/test_intake_schemas.py tests/test_intake_gate.py tests/test_source_document_evidence_alignment.py
```

全量回归命令：

```bash
python -m pytest -q
```

常见失败排查：

1. case_id 不匹配 pattern（应为 case_... 或 case-...）。
2. initial_submission 误传 parent_input_event_id。
3. EvidenceAtom 的 raw_excerpt 与 SourceDocument.raw_text 对不上。
4. source span 越界或与 excerpt 不一致。

## 7. Concept notes

1. 为什么 RawInputEvent 不是 StageContext：
   - RawInputEvent 只表示“输入事件到达”，StageContext 表示“临床阶段边界”。
   - 输入事件与临床阶段不是同一语义层。

2. 为什么 append 输入不自动等于新阶段：
   - append 可能只是补充、纠错、替换，不一定触发阶段迁移。
   - 阶段迁移需要独立的 stage resolution 机制，不应由输入动作隐式决定。

3. 为什么 EvidenceAtom 前必须有 SourceDocument：
   - 没有 immutable source document，就无法稳定校验 source_doc_id、raw_excerpt、source_span。
   - provenance 可追溯性需要先有可引用的文本源对象。

4. 为什么 raw intake gate 与 authoritative write gate 必须分离：
   - 前者负责输入登记与基础一致性；后者负责临床权威状态写入。
   - 分离后可避免 raw free-text 直接进入 authoritative state。

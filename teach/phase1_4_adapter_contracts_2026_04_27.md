# Phase 1-4 Adapter Contracts（2026-04-27）

## 1. Analysis path

本次先阅读以下文件，目的都是先对齐边界再写代码：

1. `.github/copilot-instructions.md`
2. `AGENTS.md`
3. `.github/instructions/agents.instructions.md`
4. `.github/instructions/schemas.instructions.md`
5. `.github/instructions/tests.instructions.md`
6. `src/schemas/intake.py`
7. `src/schemas/stage.py`
8. `src/schemas/evidence.py`
9. `src/provenance/model.py`
10. `src/validators/schema_validator.py`
11. `docs/devlog.md`

这样做的原因：

1. 先确认 Phase 1 的机制优先和硬边界（禁止诊断越权、禁止写入绕过 gate）。
2. 复用已有 id pattern、`extra="forbid"`、跨字段 `model_validator` 的建模风格。
3. 保证新增 adapter contract 与既有 `StageContext` / `EvidenceAtom` / `ExtractionActivity` 对齐。

## 2. Change list

新增或修改文件如下：

1. `src/adapters/__init__.py`
   - 新增 adapters 导出入口。
2. `src/adapters/case_structuring.py`
   - 新增 `CaseTimelineEventType`、`CaseTimelineItem`、`NormalizedFinding`、`CandidateClueGroup`、`CaseStructuringDraft`。
   - 实现 source doc 去重、stage/source 对齐、finding 引用闭环、snake_case 归一化等校验。
3. `src/adapters/evidence_atomization.py`
   - 新增 `EvidenceAtomizationDraft`。
   - 实现 evidence 非空、evidence_id 唯一、stage/source 对齐、activity 覆盖 source doc 校验。
4. `tests/test_case_structuring_adapter_contract.py`
   - 覆盖 valid/invalid 构造、case/stage/source 不一致、clue->finding 失配、诊断型 group_key 拒绝、extra field 拒绝。
5. `tests/test_evidence_atomization_adapter_contract.py`
   - 覆盖 valid/invalid 构造、empty evidence、重复 evidence_id、stage/source/activity 不一致、extra field 拒绝。
6. `docs/devlog.md`
   - 追加本次任务记录。

## 3. Connection mechanism

本次实现仅提供可复用的 adapter contract 模型，不做自动接线：

1. 通过 `src/adapters/__init__.py` 暴露类型，供后续调用方按需 import。
2. 未修改 orchestration、pipeline graph、experiment YAML。
3. 未修改既有 validator 组合与 writer gate 入口。

也就是说，本次是“可被接入”的契约层，不是“已接入”的流程层。

## 4. Runtime data flow

### 4.1 Case Structurer draft

1. 输入：上游调用方提供 `case_id`、`source_doc_ids`、`proposed_stage_context` 和结构化条目。
2. 过程：`CaseStructuringDraft` 在构造时执行字段级与跨对象级校验。
3. 输出：得到一个非权威草稿对象（draft），仅用于后续机制消费。

### 4.2 Evidence Atomizer draft

1. 输入：上游调用方提供 `stage_id`、`source_doc_ids`、`evidence_atoms`、`extraction_activity`。
2. 过程：`EvidenceAtomizationDraft` 在构造时执行 evidence 集合与 provenance 活动一致性校验。
3. 输出：得到一个非权威草稿对象（draft），后续仍需进入既有验证与写入机制。

## 5. Self-service modification guide

后续若要扩展本模块，优先改以下点：

1. 新增时间线事件类型：编辑 `CaseTimelineEventType`。
2. 新增线索分组键：编辑 `CandidateClueGroupKey`（仍应保持非诊断语义）。
3. 调整 finding_key 归一化策略：编辑 `case_structuring.py` 的 `_normalize_to_snake_case`。
4. 调整 atomization 草稿 id 规则：编辑 `evidence_atomization.py` 的 `EVIDENCE_ATOMIZATION_DRAFT_ID_PATTERN`。
5. 新增约束后，请同步补测试，避免只改 happy path。

## 6. Validation method

建议执行：

```bash
python -m pytest -q tests/test_case_structuring_adapter_contract.py tests/test_evidence_atomization_adapter_contract.py
```

期望结果：

1. 两个测试文件全部通过。
2. 失败场景应由 `ValidationError` 明确阻断，而不是 silent coercion。

常见失败原因：

1. `draft_id` / `finding_id` / `clue_group_id` 与 pattern 不匹配。
2. `proposed_stage_context` 与 draft 的 `case_id`、`source_doc_ids` 或 `stage_id` 不一致。
3. `extraction_activity.input_source_doc_ids` 未覆盖草稿 `source_doc_ids`。

## 7. Concept notes

本次必须明确的研究边界：

1. Phase 1-4 adapters 不是研究主对象，研究主对象仍是机制层（schema + validator + gate）。
2. Draft 不是 authoritative state，不能替代 `Phase1StateEnvelope`。
3. Case Structurer 只能做结构化整理，不能产出 final diagnosis。
4. Evidence Atomizer 只能做证据原子抽取，不能综合生成 hypotheses。
5. 既有 validators 与 state writer gate 仍是唯一权威写入边界。

# Phase 1-4 Adapter Validation Bridge（2026-04-27）

## 1. Analysis path

本次实现按以下顺序分析：

1. `AGENTS.md`
2. `.github/copilot-instructions.md`
3. `.github/instructions/agents.instructions.md`
4. `.github/instructions/schemas.instructions.md`
5. `.github/instructions/tests.instructions.md`
6. `.github/instructions/validators.instructions.md`
7. `src/adapters/case_structuring.py`
8. `src/adapters/evidence_atomization.py`
9. `src/agents/case_structurer.py`
10. `src/agents/evidence_atomizer.py`
11. `src/schemas/intake.py`
12. `src/schemas/validation.py`
13. `src/intake/validators.py`
14. `src/validators/provenance_validator.py`
15. `tests/test_case_structuring_adapter_contract.py`
16. `tests/test_evidence_atomization_adapter_contract.py`
17. `tests/test_case_structurer_adapter.py`
18. `tests/test_evidence_atomizer_adapter.py`
19. `tests/test_source_document_evidence_alignment.py`
20. `docs/devlog.md`

这样做的目的：

1. 先锁定 Phase 1 的机制边界，避免桥接层越权写入或触发编排。
2. 复用现有 `StateValidationReport` / `ValidationIssue` 语义与断言风格。
3. 复用 `validate_evidence_atoms_against_sources`，避免重复实现 evidence-grounding 规则。

## 2. Change list

本次新增/修改文件：

1. `src/adapters/validation_bridge.py`
- 新增 `AdapterValidationBridgeStatus`（`passed` / `failed` / `manual_review`）。
- 新增 `AdapterValidationBridgeResult`（含两类报告、阻断标志、汇总摘要）。
- 新增 `validate_case_structuring_draft_against_sources`：
  - source registry 重复 id 检查。
  - draft/source_doc_ids 覆盖检查。
  - timeline/finding 的 source_doc_id 注册检查。
  - timeline/finding span 成对、边界、越界检查。
- 新增 `validate_evidence_atomization_draft_against_sources`：
  - 复用 `validate_evidence_atoms_against_sources` 做 raw_excerpt/span grounding。
  - 增加 draft/source_doc_ids 覆盖检查。
  - 增加 extraction_activity 对 draft/source_doc_ids 的覆盖检查。
- 新增 `validate_adapter_drafts_against_sources` 组合入口（无 draft 时直接 failed）。

2. `src/adapters/__init__.py`
- 导出 bridge API，供上游按需显式调用。

3. `tests/test_adapter_validation_bridge.py`
- 新增 13 条用例，覆盖题目要求的通过/阻断/组合状态场景。

4. `docs/devlog.md`
- 追加本次任务记录。

5. `teach/phase1_4_validation_bridge_2026_04_27.md`
- 新增本教学文档。

## 3. Connection mechanism

本次桥接层是“可复用组件”，不自动接入 orchestration。

调用方式：

1. Case draft 单独校验：
- `validate_case_structuring_draft_against_sources(draft, source_documents)`

2. Evidence draft 单独校验：
- `validate_evidence_atomization_draft_against_sources(draft, source_documents)`

3. 组合校验：
- `validate_adapter_drafts_against_sources(...)`

导出路径：

1. `src.adapters.validation_bridge`
2. `src.adapters`（经 `__init__.py` 统一导出）

## 4. Runtime data flow

运行时数据流如下：

1. 上游先获得 adapter 草稿（`CaseStructuringDraft` 或 `EvidenceAtomizationDraft`）。
2. 上游传入当前注册的 `SourceDocument` 集合。
3. bridge 执行纯确定性规则检查：
- 不调用 LLM。
- 不调用 `attempt_phase1_write`。
- 不落库，不持久化。
4. bridge 产出 `StateValidationReport`（单草稿）或 `AdapterValidationBridgeResult`（组合）。
5. 上游根据 `has_blocking_issue` 决定是否继续后续“权威状态构造”路径。

## 5. Self-service modification guide

后续若要扩展桥接规则，可按以下位置修改：

1. 调整 case draft 规则：
- 编辑 `validate_case_structuring_draft_against_sources`。

2. 调整 evidence draft 规则：
- 编辑 `validate_evidence_atomization_draft_against_sources`。

3. 调整 issue 编码/消息模板：
- 编辑 `_build_issue` 和各规则分支中的 `issue_code` / `message`。

4. 调整组合状态策略：
- 编辑 `validate_adapter_drafts_against_sources` 与 `_build_bridge_summary`。

5. 修改后同步更新测试：
- 优先更新 `tests/test_adapter_validation_bridge.py`，保持“成功 + 阻断 + 组合失败”三类覆盖。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_adapter_validation_bridge.py tests/test_case_structurer_adapter.py tests/test_evidence_atomizer_adapter.py tests/test_case_structuring_adapter_contract.py tests/test_evidence_atomization_adapter_contract.py
```

预期结果：

1. 新增 bridge 测试全部通过。
2. 既有 adapter 合同与行为测试无回归。

常见失败原因：

1. 使用了不符合 `ValidationIssue.issue_code` 正则的编码。
2. 组合函数在“无草稿”场景返回了非阻断状态。
3. 手工突变对象后未覆盖 span 成对/越界场景，导致断言与规则不一致。

## 7. Concept notes

关键概念说明：

1. **Bridge 是“前置校验”，不是“状态写入”**
- bridge 只回答“草稿是否被已登记 source 文档支持”。
- bridge 不生成权威状态对象，不修改 state writer/pipeline/storage。

2. **Non-authoritative draft 保持非权威属性**
- `CaseStructuringDraft` 和 `EvidenceAtomizationDraft` 仍是 adapter 草稿。
- 即使 bridge 通过，也仅表示“可进入下一步机制”，不等于“已成为权威状态”。

3. **Mechanism-first deterministic control**
- 控制逻辑在可执行 Python 规则中，不依赖 prompt 文案保证。
- 校验结果以结构化 report 返回，便于审计与后续 gate 组合。
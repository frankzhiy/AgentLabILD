# Phase 1-4 Evidence Atomizer Adapter（2026-04-27）

## 1. Analysis path

本次实现先阅读以下文件，再开始编码：

1. `AGENTS.md`
2. `.github/copilot-instructions.md`
3. `.github/instructions/agents.instructions.md`
4. `.github/instructions/schemas.instructions.md`
5. `src/adapters/evidence_atomization.py`
6. `src/adapters/case_structuring.py`
7. `src/agents/case_structurer.py`
8. `src/schemas/evidence.py`
9. `src/schemas/intake.py`
10. `src/schemas/stage.py`
11. `src/provenance/model.py`
12. `configs/prompts/v2/case_structurer.md`
13. `tests/test_evidence_atomization_adapter_contract.py`
14. `tests/test_case_structurer_adapter.py`
15. `docs/devlog.md`
16. `teach/phase1_4_case_structurer_adapter_2026_04_27.md`

这样做的目的：

1. 先锁定 Phase 1 机制边界，确保 Evidence Atomizer 只做非权威草稿适配。
2. 镜像 `Case Structurer` 的实现风格、错误结构与测试组织方式。
3. 复用 `EvidenceAtomizationDraft` 契约，不新建平行 schema。

## 2. Change list

本次新增与修改如下：

1. `src/agents/evidence_atomizer.py`
- 新增 `EvidenceAtomizerInput`、`EvidenceAtomizerResult`、`EvidenceAtomizerStatus`。
- 新增 `build_evidence_atomizer_prompt`：仅序列化 stage metadata、source documents、可选 case structuring draft guidance（timeline/findings/clue groups）。
- 新增 `parse_evidence_atomizer_payload`：执行输入边界重检、forbidden 字段拦截、`EvidenceAtomizationDraft` 解析、输入对齐校验。
- 新增 forbidden 顶层字段拦截：诊断、假设、claim/action、仲裁、冲突、安全、belief revision 等。
- 明确不做持久化，不调用 write gate，不触发 LLM 客户端。

2. `configs/prompts/v2/evidence_atomizer.md`
- 新增 v2 提示词契约，明确角色是 adapter，不是 diagnostician。
- 明确只输出 `EvidenceAtomizationDraft` 兼容 JSON。
- 明确只提取 evidence atom 所需字段。
- 明确禁止输出 diagnosis/hypothesis/claim/action/conflict/arbitration/safety/belief-revision 等字段。
- 明确 case structuring draft 仅作提取引导，不能作为诊断证据。

3. `tests/test_evidence_atomizer_adapter.py`
- 新增适配器行为测试，覆盖 prompt 构建、forbidden 拦截、payload 解析成功与失败、输入边界构造失败、异常兜底错误结构。
- 包含题目要求的全部关键失败用例（`final_diagnosis`、`hypotheses`、`claim_references`、`action_candidates`、stage/source/extraction_activity 对齐失败）。

4. `src/agents/__init__.py`
- 导出 Evidence Atomizer 对外 API：
  - `EvidenceAtomizerInput`
  - `EvidenceAtomizerResult`
  - `EvidenceAtomizerStatus`
  - `build_evidence_atomizer_prompt`
  - `parse_evidence_atomizer_payload`

5. `docs/devlog.md`
- 追加本次任务记录、变更文件、原因、验证方式与边界说明。

## 3. Connection mechanism

本次实现是可复用 adapter 组件，不自动接入 pipeline。

1. 调用方通过 `src.agents.evidence_atomizer` 直接使用：
- `build_evidence_atomizer_prompt(input_model)`
- `parse_evidence_atomizer_payload(payload, input_model)`

2. `parse_evidence_atomizer_payload` 返回 `EvidenceAtomizerResult`，其中 `draft` 类型是 `EvidenceAtomizationDraft`。

3. 本次没有修改：
- orchestration
- experiment YAML
- validators pipeline
- state writer
- storage

## 4. Runtime data flow

运行时数据流如下：

1. 上游准备 `EvidenceAtomizerInput`：
- `case_id`
- `stage_id`
- `source_documents`
- `stage_context`
- 可选 `case_structuring_draft`
- extraction activity 元信息（`extraction_activity_id`、`extractor_name`、`extractor_version`、`occurred_at`）

2. 调用 `build_evidence_atomizer_prompt`：
- 读取 `configs/prompts/v2/evidence_atomizer.md`（若不可读则回落到内置 fallback）。
- 序列化 stage metadata + source documents + 可选 case structuring draft guidance。
- 返回给 LLM 的 prompt 字符串。

3. LLM 返回 payload 后，调用 `parse_evidence_atomizer_payload`：
- 先做输入边界重检（避免 `model_copy(update=...)` 绕过构造校验）。
- 再做 forbidden 字段拦截。
- 再 `EvidenceAtomizationDraft.model_validate(payload)`。
- 最后做输入对齐校验：`case_id` / `stage_id` / `source_doc_ids` / extraction_activity stage 与文档覆盖。

4. 输出 `EvidenceAtomizerResult`：
- `accepted`：携带 `draft`。
- `rejected`：不携带 `draft`，返回结构化错误。
- `manual_review`：仅用于兜底异常，避免未捕获异常泄漏。

## 5. Self-service modification guide

后续若要扩展本模块，建议按以下位置修改：

1. 调整 forbidden 策略：
- 编辑 `src/agents/evidence_atomizer.py` 中 `FORBIDDEN_PAYLOAD_FIELDS`。

2. 调整 prompt 合同文案：
- 编辑 `configs/prompts/v2/evidence_atomizer.md`。

3. 调整输入/草稿对齐规则：
- 编辑 `src/agents/evidence_atomizer.py` 中 `_validate_input_boundary` 与 `_validate_draft_alignment`。

4. 调整 prompt 序列化范围：
- 编辑 `_serialize_stage_metadata`、`_serialize_source_document`、`_serialize_case_structuring_draft_guidance`。

5. 增加规则后同步测试：
- 更新 `tests/test_evidence_atomizer_adapter.py`，至少保留成功、失败、边界和异常兜底四类覆盖。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_evidence_atomizer_adapter.py tests/test_evidence_atomization_adapter_contract.py tests/test_case_structurer_adapter.py tests/test_case_structuring_adapter_contract.py
```

本次实际结果：

1. 54 passed。
2. 无未捕获异常。
3. Case Structurer 相关测试无回归。

常见失败原因：

1. payload 顶层包含 forbidden 字段（如 `final_diagnosis`、`hypotheses`）。
2. draft/source 与输入 source_documents 不对齐。
3. extraction_activity 文档覆盖不足（未覆盖输入文档集合）。

## 7. Concept notes

本次实现涉及的核心概念：

1. **Adapter 非权威边界**
- Evidence Atomizer 只生成 `EvidenceAtomizationDraft` 候选，不做权威写入。

2. **Schema-first + deterministic parsing**
- 先执行 forbidden 拦截，再走 Pydantic schema 校验，再做输入对齐检查。

3. **输入边界重检**
- 构造期校验之外，解析期再次做 boundary check，防止运行时对象突变导致绕过。

4. **Prompt 仅做辅助，不做控制机制**
- 真正约束依赖外部可执行校验（schema + boundary），不是靠提示词文本保证。
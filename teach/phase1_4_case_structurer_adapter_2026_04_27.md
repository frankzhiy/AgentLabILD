# Phase 1-4 Case Structurer Adapter（2026-04-27）

> 更新：2026-04-27（Issue 2 hardening）

## 1. Analysis path

本次实现先阅读以下文件，再开始编码：

1. `AGENTS.md`
2. `.github/copilot-instructions.md`
3. `.github/instructions/agents.instructions.md`
4. `.github/instructions/schemas.instructions.md`
5. `src/adapters/case_structuring.py`
6. `src/schemas/intake.py`
7. `src/schemas/stage.py`
8. `docs/devlog.md`
9. `teach/phase1_4_adapter_contracts_2026_04_27.md`

这样做的目的：

1. 先锁定 Phase 1 的机制边界，确保 Case Structurer 只做适配，不做诊断。
2. 复用已有 `CaseStructuringDraft` 契约，避免新建平行 schema。
3. 保持与 intake/stage 对象一致的输入边界与 id 规范。

## 2. Change list

本次新增与修改如下：

1. `src/agents/case_structurer.py`
- 新增 `CaseStructurerInput`、`CaseStructurerResult`、`CaseStructurerStatus`。
- 新增 `build_case_structurer_prompt`：只拼装 stage metadata + source documents。
- 新增 `parse_case_structurer_payload`：只解析为 `CaseStructuringDraft`，并做输入对齐与边界拦截。
- 新增越权字段拦截（如 `final_diagnosis`、`hypotheses`、`action_plan`、`arbitration_output` 等）。
- Issue 2 hardening：`CaseStructurerInput.source_documents` 在构造期强制非空。
- Issue 2 hardening：解析阶段新增 `StageContext` 强对齐（`stage_index` / `stage_type` / `trigger_type` / `parent_stage_id`，以及条件字段 `clinical_time` / `stage_label`）。

2. `configs/prompts/v2/case_structurer.md`
- 新增 v2 提示词契约，明确“Case Structurer 是 adapter，不是 diagnostician”。
- 明确输出范围、禁止输出范围、溯源要求和输出格式要求。
- Issue 2 hardening：明确 `previous_stage_summary_non_authoritative` 只能用于阶段连续性，不得用于诊断、假设、治疗、仲裁与安全决策推断。

3. `tests/test_case_structurer_adapter.py`
- 新增 9 个测试，覆盖 prompt 内容边界、解析成功、解析失败与异常兜底行为。
- Issue 2 hardening：新增构造期空 source 文档失败测试与 StageContext 对齐失败测试。
- Issue 2 hardening：新增 previous summary 含诊断字样时 forbidden 字段仍拒绝的回归测试。

4. `src/agents/__init__.py`
- 将旧 skeleton TODO 替换为 adapter-agent 边界说明。
- 导出 Case Structurer 输入/输出模型与核心函数，供后续集成复用。

5. `docs/devlog.md`
- 追加本次任务记录、验证命令与边界说明。

## 3. Connection mechanism

本次实现是可复用 adapter 组件，不自动接入 pipeline。

1. 调用方通过 `src.agents.case_structurer` 直接使用：
- `build_case_structurer_prompt(input_model)`
- `parse_case_structurer_payload(payload, input_model)`

2. `parse_case_structurer_payload` 输出 `CaseStructurerResult`，其中 `draft` 类型是 `CaseStructuringDraft`。

3. 本次没有修改：
- orchestration
- experiment YAML
- validators pipeline
- state writer
- storage

## 4. Runtime data flow

运行时数据流如下：

1. 上游准备 `CaseStructurerInput`：
- `case_id`
- `source_documents`
- stage metadata（`stage_id`、`stage_type`、`trigger_type` 等）

2. 调用 `build_case_structurer_prompt`：
- 读取 `configs/prompts/v2/case_structurer.md`（若不可读则使用内置 fallback）。
- 将 stage metadata + source documents 序列化为输入 JSON。
- 返回给 LLM 的完整 prompt 字符串。

3. LLM 返回 payload 后，调用 `parse_case_structurer_payload`：
- 先做越权字段拦截。
- 再 `CaseStructuringDraft.model_validate(payload)`。
- 再做调用上下文对齐校验（case_id、source_doc_ids subset、stage_id、stage_index、stage_type、trigger_type、parent_stage_id，以及条件字段 clinical_time/stage_label）。

4. 输出 `CaseStructurerResult`：
- `accepted`：携带 `draft`。
- `rejected/manual_review`：不携带 `draft`，返回结构化 `errors`。

## 5. Self-service modification guide

后续若要扩展本模块，建议按以下位置修改：

1. 调整越权字段策略：
- 编辑 `src/agents/case_structurer.py` 中 `FORBIDDEN_PAYLOAD_FIELDS`。

2. 调整 prompt 合同文案：
- 编辑 `configs/prompts/v2/case_structurer.md`。

3. 调整解析失败分级策略（rejected/manual_review）：
- 编辑 `parse_case_structurer_payload` 的异常分支。

4. 调整输入序列化字段：
- 编辑 `_serialize_stage_metadata` 与 `_serialize_source_document`。

5. 增加新规则后要同步测试：
- 更新 `tests/test_case_structurer_adapter.py`，至少覆盖成功、失败与边界条件。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_case_structurer_adapter.py tests/test_case_structuring_adapter_contract.py
```

期望结果：

1. 两个测试文件全部通过。
2. 对非法 payload 返回结构化错误，不抛未捕获异常。
3. adapter 不产生诊断类字段，也不写入权威状态。

常见失败原因：

1. payload 含有 `final_diagnosis` 或 `hypotheses` 等越权字段。
2. payload 中 `source_doc_ids` 不属于输入 `source_documents`。
3. payload `proposed_stage_context.stage_id` 与输入 `stage_id` 不一致。

## 7. Concept notes

本次实现的核心概念如下：

1. **Case Structurer 是 adapter，不是诊断代理**
- 它只把原始文本组织成 `CaseStructuringDraft`。
- 它不能输出 final diagnosis、hypothesis、action、arbitration。

2. **Draft 是非权威对象**
- `CaseStructuringDraft` 只是候选草稿。
- 不能替代 validator-gated authoritative state。

3. **不能绕过 validator 和 write gate**
- 本模块不调用 `attempt_phase1_write`。
- 本模块不做任何持久化。
- 权威写入依然由既有机制层控制。

4. **previous_stage_summary 的边界**
- 仅作为 non-authoritative 上下文提示。
- 仅可用于阶段连续性表达。
- 不作为 diagnosis / differential / hypotheses / treatment / confidence / action / conflict / arbitration / safety decision 的推断依据。

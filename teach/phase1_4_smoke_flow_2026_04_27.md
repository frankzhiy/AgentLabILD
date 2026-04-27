# Phase 1-4 Smoke Flow（2026-04-27）

## 1. Analysis path

本次按以下顺序阅读并确认边界：

1. `AGENTS.md`
2. `.github/copilot-instructions.md`
3. `.github/instructions/agents.instructions.md`
4. `.github/instructions/tests.instructions.md`
5. `src/intake/intake_gate.py`
6. `src/schemas/intake.py`
7. `src/agents/case_structurer.py`
8. `src/agents/evidence_atomizer.py`
9. `src/adapters/case_structuring.py`
10. `src/adapters/evidence_atomization.py`
11. `src/adapters/validation_bridge.py`
12. `tests/test_case_structurer_adapter.py`
13. `tests/test_evidence_atomizer_adapter.py`
14. `tests/test_adapter_validation_bridge.py`
15. `tests/test_intake_gate.py`
16. `docs/devlog.md`

这样做的目的：

1. 确保 smoke flow 只覆盖 Phase 1-4 的 intake -> adapter -> bridge 机制连接。
2. 复用既有 adapter 解析边界和 bridge issue_code，避免重复实现。
3. 明确不触发 writer/sink，不越界到权威状态写入路径。

## 2. Change list

本次变更文件：

1. `tests/test_phase1_4_smoke_flow.py`
- 新增 deterministic 正向 smoke 流：
  - raw free-text -> `attempt_raw_intake`
  - `CaseStructurerInput` + `parse_case_structurer_payload`
  - `EvidenceAtomizerInput` + `parse_evidence_atomizer_payload`
  - `validate_adapter_drafts_against_sources`
- 新增负例：
  - Case payload 含 `final_diagnosis` 在 bridge 前即拒绝。
  - Evidence payload 含 `hypotheses` / `action_candidates` 在 bridge 前即拒绝。
  - Evidence raw_excerpt 不在 source text 时，bridge 返回 blocking provenance issue。
- 新增边界守卫：测试模块不导入 state/storage，不出现 `attempt_phase1_write` / `StateWriter`。

2. `teach/phase1_4_smoke_flow_2026_04_27.md`
- 新增本教学说明。

3. `docs/devlog.md`
- 追加本次任务记录。

## 3. Connection mechanism

本次仅新增测试，不改动运行时拓扑。连接机制如下：

1. `pytest` 自动发现 `tests/test_phase1_4_smoke_flow.py`。
2. 测试直接调用既有机制函数：
   - `attempt_raw_intake`
   - `parse_case_structurer_payload`
   - `parse_evidence_atomizer_payload`
   - `validate_adapter_drafts_against_sources`
3. 测试结果用于证明“raw intake 到 adapter validation bridge”的最小端到端连接成立。

## 4. Runtime data flow

正向 smoke 的运行时数据流：

1. 输入一段原始 ILD 自由文本。
2. 调用 `attempt_raw_intake` 生成 intake decision。
3. 断言 intake accepted，且仅形成一个 `SourceDocument`。
4. 用该 `SourceDocument` 组装 `CaseStructurerInput` 与确定性 stage 元数据。
5. 用确定性 payload 调用 `parse_case_structurer_payload`，得到 accepted `CaseStructuringDraft`。
6. 用 accepted `CaseStructuringDraft` + source docs 组装 `EvidenceAtomizerInput`。
7. 用确定性 payload 调用 `parse_evidence_atomizer_payload`，得到 accepted `EvidenceAtomizationDraft`。
8. 调用 `validate_adapter_drafts_against_sources`。
9. 断言 bridge `PASSED` 且 `has_blocking_issue=False`。

负例数据流：

1. adapter forbidden 顶层字段在 parse 阶段立即拒绝。
2. provenance grounding 缺口（raw_excerpt 不存在）在 bridge 阶段转化为 blocking issue。

## 5. Self-service modification guide

若你后续想调整 smoke 覆盖范围，可按下列入口修改：

1. 调整原始输入文本与 stage 常量：
- `tests/test_phase1_4_smoke_flow.py` 顶部常量。

2. 增减 case structurer payload 字段：
- `_build_case_structurer_payload`。

3. 增减 evidence atomizer payload 字段：
- `_build_evidence_atomizer_payload`。

4. 新增 bridge 负例类型（例如 source_doc 覆盖缺口）：
- 仿照 `test_phase1_4_smoke_flow_bridge_blocks_raw_excerpt_not_found`。

5. 若 bridge issue_code 变更：
- 同步更新本 smoke 测试中的 issue_code 断言。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_phase1_4_smoke_flow.py
python -m pytest -q tests/test_phase1_4_smoke_flow.py tests/test_adapter_validation_bridge.py tests/test_case_structurer_adapter.py tests/test_evidence_atomizer_adapter.py
```

预期结果：

1. 新增 smoke 文件通过。
2. 与 adapter/bridge 既有测试联合运行无回归。

常见失败原因：

1. stage 或 source_doc_id 对齐字段不一致，导致 parse 阶段拒绝。
2. evidence raw_excerpt/span 与 source text 不一致，导致 bridge 阻断。
3. forbidden 顶层字段误入 payload，导致 adapter 在 bridge 前即拒绝。

## 7. Concept notes

1. **Smoke flow 验证的是机制连通性，不是诊断能力**
- 目标是证明 raw intake、两个 adapter parser、bridge 的可组合性。

2. **Adapter 输出保持 non-authoritative**
- `CaseStructuringDraft` / `EvidenceAtomizationDraft` 仍是草稿，不代表权威状态。

3. **桥接校验先于任何写入机制**
- 本测试不调用 `attempt_phase1_write`、`StateWriter` 或其他 sink。

4. **Mechanism-first deterministic check**
- 全部输入和断言是确定性的结构化规则，不依赖 LLM 结果。

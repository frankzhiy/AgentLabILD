# Phase 1-2 provenance checking 教学说明（2026-04-23）

## 1. Analysis path

本次实现按“先边界、后规则、再报告”的顺序推进：

1. src/provenance/model.py
- 先确认 SourceAnchor / EvidenceProvenance / ClaimProvenance 已有字段与内建校验，避免重复定义或改写 schema 语义。

2. src/schemas/evidence.py 与 src/schemas/claim.py
- 确认 provenance 是可选字段（兼容旧 payload），并识别哪些规则应放在外部 checker 而不是模型内。

3. src/schemas/stage.py 与 src/schemas/state.py
- 确认 stage_context.source_doc_ids、case_id、stage_id 在 envelope 中的位置，明确“可见性对齐”和“case/stage 对齐”检查入口。

4. src/schemas/validation.py
- 对齐 ValidationIssue / StateValidationReport 的字段契约，确保 checker 输出可稳定转换为报告。

5. tests/test_phase1_state_envelope.py
- 复用现有 Phase 1 状态构造风格，避免新增测试偏离项目约定。

## 2. Change list

### 新增 src/provenance/checker.py
- 新增 `ProvenanceCheckIssue` 结构化 issue 对象（可直接映射为 ValidationIssue）。
- 新增 `check_phase1_provenance(...)`，覆盖以下规则：
  - source span 完整性与顺序
  - stage 对齐
  - case 对齐
  - source_doc 对 StageContext 可见性约束
  - claim provenance 与 ClaimReference.evidence_ids 一致性
  - orphan provenance / missing provenance
- 提供 `require_provenance` 开关：
  - `False`（默认）：missing provenance 记为 warning（兼容旧状态）
  - `True`：missing provenance 记为 blocking error

### 新增 src/validators/provenance_validator.py
- 新增 `build_provenance_validation_issues(...)`：从 checker 收集 issue 并转换。
- 新增 `convert_provenance_issues_to_validation_issues(...)`：生成稳定 issue_id（`issue-provenance-0001`...）。
- 新增 `validate_phase1_provenance(...)`：生成 StateValidationReport（含 summary、blocking 统计）。

### 修改 src/validators/__init__.py
- 导出 provenance validator 相关 API，供外部调用。

### 新增测试
- tests/test_provenance_checker.py
  - 覆盖 checker 规则本身与边界条件（含 model_construct 绕过 schema 后的防御性检查）。
- tests/test_provenance_validator.py
  - 覆盖 checker->ValidationIssue->StateValidationReport 转换链路与 blocking 语义。

### 修改 docs/devlog.md
- 追加本次任务记录。

## 3. Connection mechanism

本次连接方式是“checker 负责规则，validator 负责报告”：

1. 上游继续构造 Phase1StateEnvelope（不改 pipeline，不改 writer）。
2. `src/provenance/checker.py` 读取 envelope 并返回 `ProvenanceCheckIssue` 列表。
3. `src/validators/provenance_validator.py` 将 issue 列表转换成 ValidationIssue。
4. 由 validator 组装 StateValidationReport，供后续写入门禁或审计层消费。

该设计保持 schema 语义稳定，不将控制逻辑塞进 prompt 或 agent。

## 4. Runtime data flow

运行时数据流如下：

1. 输入：Phase1StateEnvelope。
2. checker 读取：
  - stage_context（stage_id/case_id/source_doc_ids）
  - evidence_atoms[*].provenance
  - claim_references[*].provenance
3. checker 产出：`tuple[ProvenanceCheckIssue, ...]`。
4. validator 转换为：`tuple[ValidationIssue, ...]`。
5. validator 统计 blocking/non-blocking，并输出 StateValidationReport。
6. 报告可直接被后续 gate 使用（本任务未实现 writer/gate 执行层）。

## 5. Self-service modification guide

后续扩展建议：

1. 若需新增 provenance 规则
- 修改 `src/provenance/checker.py`，新增 issue_code（建议 `provenance.*` 命名空间），并补对应测试。

2. 若需改变 missing provenance 策略
- 调整 `require_provenance` 的默认值或 issue 严重度映射，不要改 EvidenceAtom/ClaimReference 的可选字段语义。

3. 若需接入 writer gate
- 保持 checker 与 validator 不变，在写入层消费 `StateValidationReport.has_blocking_issue`。

4. 若需扩展报告元信息
- 在 `validate_phase1_provenance(...)` 中添加 summary 细节，不改 ValidationIssue 基础结构。

## 6. Validation method

建议命令：

```bash
python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py
python -m pytest -q
```

本次实际结果：

- 定向测试：13 passed
- 全量回归：通过

常见失败优先排查：

1. `stage_context.source_doc_ids` 与 provenance activity/anchor 的 source_doc 不一致。
2. claim provenance 的 evidence_ids 与 ClaimReference.evidence_ids 集合不一致。
3. claim provenance 的 evidence_provenance_ids 指向不存在的 eprov。
4. 用 `model_construct` 构造测试对象时忘记补全关键字段。

## 7. Concept notes

本次涉及的关键概念：

1. Checker/Validator 分层
- checker 只做规则判断，validator 只做报告转换，避免职责混杂。

2. Structured failure taxonomy
- 使用 `provenance.*` issue_code，保证 provenance 失败可区分、可统计、可追踪。

3. Backward-compatible strictness switch
- 用 `require_provenance` 在“兼容历史数据”和“强约束写入”之间平滑过渡。

4. Defense-in-depth
- 即使模型层已有校验，checker 仍覆盖关键约束，防止后续流程中出现非正常构造对象。

# Phase 1-1 Direction A 语义收敛说明（2026-04-23）

## 1. Analysis path

本次先读以下文件，再确定最小改动路径：

- src/schemas/validation.py：确认当前 ValidationIssue/StateValidationReport 字段与一致性规则。
- src/schemas/state.py：确认 envelope 的硬结构校验逻辑与 validation_report 的耦合点。
- src/schemas/common.py：确认共享层是否过薄、可新增哪些低争议复用函数。
- src/schemas/stage.py、src/schemas/evidence.py、src/schemas/claim.py、src/schemas/hypothesis.py、src/schemas/action.py、src/schemas/board.py：评估固定 kind 标签是否可低风险加入。
- tests/test_phase1_state_envelope.py 与各 schema 测试：确认原有断言与新增需求之间的差异。

这些文件是正确起点，因为任务核心是“报告语义 + 根封装语义 + 共享层 + 可选 kind 元数据”，不涉及编排或 agent 行为。

## 2. Change list

本次变更如下：

- src/schemas/common.py
  - 保留 NonEmptyStr。
  - 新增 normalize_optional_text。
  - 新增 normalize_optional_note。
  - 新增 find_duplicate_items。

- src/schemas/validation.py
  - 扩展 ValidationIssue：
    - issue_id
    - issue_code
    - severity
    - message
    - target_kind
    - target_id
    - field_path
    - related_ids
    - blocking
    - suggested_fix（可选）
    - non_authoritative_note
  - 新增 ValidationTargetKind。
  - 扩展 StateValidationReport：
    - report_id
    - case_id
    - stage_id
    - board_id（可选）
    - generated_at
    - is_valid
    - has_blocking_issue
    - issues
    - validator_name
    - validator_version
    - summary
  - 新增一致性规则：
    - has_blocking_issue 必须与 issues.blocking 派生结果一致。
    - is_valid=True 时不允许 blocking issue。
    - is_valid=False 时至少一条 issue。
    - issue_id 去重。
    - case/stage/board id 命名模式校验。

- src/schemas/state.py
  - Phase1StateEnvelope.validation_report 从必填改为可选。
  - 保留并继续执行 envelope 硬结构校验并抛异常：
    - case/stage 对齐
    - duplicate id
    - missing claim references
    - missing evidence references
    - ranked hypothesis ids 缺失
  - 在 docstring 与注释中明确语义分工：
    - envelope validator：硬结构完整性。
    - StateValidationReport：外部 validator/write-gate 的结构化结果。

- src/schemas/stage.py、src/schemas/evidence.py、src/schemas/claim.py、src/schemas/hypothesis.py、src/schemas/action.py、src/schemas/board.py
  - 以 Literal 固定值加入 kind：
    - stage_context
    - evidence_atom
    - claim_reference
    - hypothesis_state
    - action_candidate
    - hypothesis_board_init

- tests/test_phase1_state_envelope.py
  - 覆盖有效 StateValidationReport。
  - 覆盖 is_valid=True + blocking issue 失败。
  - 覆盖 is_valid=False + 空 issues 失败。
  - 覆盖 ValidationIssue 重复/格式失败场景。
  - 覆盖 validation_report=None 的 envelope 成功构造。
  - 保留 envelope 硬失败断言。

- tests/test_stage_context.py、tests/test_evidence_schema.py、tests/test_claim_reference_schema.py、tests/test_hypothesis_state_schema.py、tests/test_action_candidate_schema.py、tests/test_hypothesis_board_init.py
  - 新增或更新 kind 默认值与非法值拒绝测试。

- docs/devlog.md
  - 追加本次变更记录。

## 3. Connection mechanism

连接方式保持不变，仍是 schema 层被上层流程按需调用：

1. 上游先构造各子对象（stage/evidence/claim/hypothesis/action/board）。
2. 可选地构造外部 StateValidationReport。
3. 组装 Phase1StateEnvelope。
4. envelope 仅在构造时执行硬结构一致性检查。

本次没有更改 experiment YAML、pipeline 图、orchestration 拓扑，也没有引入 validator engine 实现。

## 4. Runtime data flow

运行时数据流：

1. 输入对象进入各 schema 的字段级/对象级校验。
2. 如提供 validation_report，报告对象先完成自身一致性校验（id 模式、blocking 一致性、issue 去重等）。
3. 进入 Phase1StateEnvelope 后执行跨对象硬检查（stage/case 对齐、引用闭包、rank 引用存在性等）。
4. 任一硬检查失败立即抛出异常，阻断无效根状态构造。
5. 通过后得到可写入或可评审的结构化 state package；validation_report 仅作为外部校验结果载体。

## 5. Self-service modification guide

后续如需扩展：

- 若要新增 issue 分类：
  - 修改 src/schemas/validation.py 的 ValidationTargetKind 或 issue_code 校验策略。
  - 同步补充对应失败/成功测试。

- 若要更改 report 有效性规则：
  - 修改 StateValidationReport.validate_report_consistency。
  - 保持 has_blocking_issue 与 issues.blocking 的一致性策略明确。

- 若要扩展 envelope 硬检查：
  - 修改 src/schemas/state.py 的 validate_envelope_consistency。
  - 只加入结构完整性规则，不在此处实现完整 validator engine。

- 若未来 kind 需要更多对象：
  - 在对应 schema 添加 Literal 固定值。
  - 增加最小测试（默认值 + 非法值失败）。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_phase1_state_envelope.py tests/test_stage_context.py tests/test_evidence_schema.py tests/test_claim_reference_schema.py tests/test_hypothesis_state_schema.py tests/test_action_candidate_schema.py tests/test_hypothesis_board_init.py
python -m pytest -q
```

本次结果：

- 定向测试：116 passed
- 全量测试：118 passed

常见失败优先排查：

1. report_id/case_id/stage_id/board_id 命名不符合 pattern。
2. has_blocking_issue 与 issues.blocking 不一致。
3. is_valid 与 issues 组合不满足规则。
4. envelope 跨对象引用闭包不完整。
5. kind 传入了非 Literal 固定值。

## 7. Concept notes

本次涉及的关键设计点：

- Direction A 的职责分离：
  - 根 envelope 负责硬结构完整性。
  - validation report 负责外部校验结果表达。

- blocking 与 severity 分离：
  - severity 描述问题严重级别。
  - blocking 描述是否阻断写入。
  - 两者分离可避免“只凭 severity 推断阻断策略”的隐式行为。

- common.py 保持小而稳：
  - 只放高复用、低争议辅助函数。
  - 不抽取对象专属 regex 或领域规则，避免过度抽象。

- kind 标签定位：
  - 用于对象自描述与跨组件识别便利。
  - 不替代类型系统、字段位置或 envelope 结构。

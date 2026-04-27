# Phase 1-3：Schema Validator Mutation Hardening（2026-04-27）

## 1. Analysis path

本次先按“入口行为 -> 约束来源 -> 现有测试”的顺序查看：

- src/validators/schema_validator.py
  - 定位 `validate_phase1_schema` 对 `Phase1StateEnvelope` 实例输入的处理分支。
- src/schemas/state.py
  - 确认 envelope-level `model_validator` 已覆盖 board/hypothesis/claim 结构闭包约束。
- tests/test_schema_validator.py
  - 对齐现有断言风格，确定新增“先构造后突变”回归测试位置。
- tests/test_validation_pipeline.py
  - 检查 schema 报告语义变化对 pipeline 粒度断言的影响。

这个路径能直接回答本次核心问题："为什么已构造实例会绕过 schema 一致性检查"。

## 2. Change list

- src/validators/schema_validator.py
  - 将 `Phase1StateEnvelope` 输入改为统一走：`model_dump(mode="python") -> Phase1StateEnvelope.model_validate(payload)`。
  - 这样即使是已构造实例，也会重新触发 envelope-level `model_validator`。
  - 若重验失败，继续沿用现有错误映射，输出 blocking `schema.model_error`。
  - `SCHEMA_VALIDATOR_VERSION` 从 `1.3.0` 更新为 `1.3.1`。

- tests/test_schema_validator.py
  - 新增 3 个“已构造后突变”回归测试：
    - board closure 破坏（`board_init.hypothesis_ids`）。
    - hypothesis closure 破坏（`action_candidates[].linked_hypothesis_ids`）。
    - claim closure 破坏（`claim_references[].target_id` 与 owner 不一致）。
  - 每个测试都验证：`has_blocking_issue=True` 且包含 `schema.model_error`。

- tests/test_validation_pipeline.py
  - 调整一个旧断言：从“schema_report.issues 必须为空”改为“schema 报告 issue_code 必须属于 `schema.*` 命名空间”。
  - 原因是本次加固后，突变 envelope 在 schema 阶段会被正确识别。

- docs/devlog.md
  - 追加本次任务记录。

- teach/phase1_3_schema_validator_mutation_hardening_2026_04_27.md
  - 新增教学说明（本文档）。

## 3. Connection mechanism

连接方式保持不变：

- 外部仍通过 `validate_phase1_schema` 调用 schema validator。
- pipeline 仍在原有顺序中调用 schema validator（未调整顺序、未增删阶段）。
- 输出仍是 `StateValidationReport`，下游 write-gate 合同不变。

## 4. Runtime data flow

1. 输入是原始 payload（dict）时：
   - 直接 `model_validate`。
   - 成功返回无 issue 报告；失败转为结构化 schema issue。

2. 输入是已构造 envelope 实例时：
   - 先 `model_dump(mode="python")` 生成当前快照。
   - 再对快照 `model_validate`，重新执行 envelope-level 一致性检查。

3. 若重验失败：
   - 将 `ValidationError` 映射为 `ValidationIssue`。
   - 对 model-level 一致性错误归类为 `schema.model_error`。
   - 返回 blocking `StateValidationReport`。

4. 若重验成功：
   - 返回 schema pass 报告。

## 5. Self-service modification guide

后续如需扩展，可按以下入口改动：

1. 若要改成“权威模型冻结”策略：
   - 在 `Phase1StateEnvelope` 及关键子模型 `model_config` 启用 `frozen=True`，并同步评估现有测试中对突变赋值的依赖。
2. 若要调整 model_error/field_error 分类边界：
   - 修改 `src/validators/schema_validator.py` 中 `_is_model_level_error()`。
   - 同步更新 `tests/test_schema_validator.py` 断言。
3. 若要改变 pipeline 对 schema blocking 的编排策略：
   - 仅在 `src/validators/pipeline.py` 修改（本次未做此变更）。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_schema_validator.py tests/test_validation_pipeline.py
```

预期结果：

- 全部通过。
- 本次实测：`20 passed`。

常见失败点：

1. 仅对 envelope 输入做“实例直通”而未重验，导致新增突变测试失败。
2. 将 model-level 错误误判为 field_error，导致 issue_code 断言失败。
3. pipeline 旧断言仍要求 schema_report 无 issue。

## 7. Concept notes

- Pydantic 默认可变模型
  - “构造时有效”不等于“后续始终有效”。
  - 机制层不能假设实例输入天然可信。

- Schema gate 的职责
  - schema validator 是 write-gate 之前的显式机制边界。
  - 对实例输入重验属于机制强化，不是提示词补丁。

- model-level consistency 与 field-level constraints
  - field-level 更偏字段格式/范围。
  - model-level 更偏对象间闭包关系与跨集合一致性。
  - 这一区分直接影响审计可解释性与下游阻断策略。

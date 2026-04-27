# Phase 1-3：Validator Hardening（2026-04-27）

## 1. Analysis path

本次从以下文件开始排查：

- src/validators/schema_validator.py
  - 定位 fallback id 与 model_error 判定逻辑。
- src/validators/temporal_validator.py
  - 定位默认 generated_at 时间源。
- src/validators/provenance_validator.py
  - 确认 report builder 是否同样使用 utcnow。
- tests/test_schema_validator.py、tests/test_temporal_validator.py、tests/test_provenance_validator.py
  - 对齐当前测试风格并确定最小回归点。

这样做的原因是本次需求是“在不改 Phase 1 机制边界的前提下做稳健化”，核心落点就是 validator/report-builder 层。

## 2. Change list

- src/utils/time.py
  - 新增统一时间 helper：utc_now()。
  - 当前返回 timezone-aware UTC 时间，避免继续扩散 naive datetime。
- src/utils/__init__.py
  - 导出 utc_now。
- src/validators/constants.py
  - 收口 validator fallback id：case/stage/state/board。
- src/validators/schema_validator.py
  - 改为使用 utc_now() 生成默认 generated_at。
  - 改为从 validators.constants 读取 fallback id。
  - 强化 _is_model_level_error()：
    - 对对象级/集合项级一致性错误优先判为 schema.model_error。
    - 对 missing required field 保持 schema.field_error。
  - 增加注释说明判定意图，降低后续 schema 扩展时误分类风险。
- src/validators/temporal_validator.py
  - 默认 generated_at 改为 utc_now()。
- src/validators/provenance_validator.py
  - 默认 generated_at 改为 utc_now()。
- tests/test_schema_validator.py
  - 新增 root object consistency 回归测试（board_init 子集约束场景）。
  - 新增 utc_now helper 使用测试（monkeypatch）。
- tests/test_temporal_validator.py
  - 新增 utc_now helper 使用测试（monkeypatch）。
- tests/test_provenance_validator.py
  - 新增 utc_now helper 使用测试（monkeypatch）。

## 3. Connection mechanism

连接机制保持不变：

- 外部依然通过 src.validators 的公开 API 调用 validator。
- 本次只替换 validator 内部默认时间来源与常量来源，不改变返回对象类型（仍是 StateValidationReport）。
- write-gate、pipeline、storage、event-log 均未接入或改动。

## 4. Runtime data flow

1. validator 被调用后，如果调用方未传 generated_at：
   - schema/temporal/provenance validator 都会调用同一个 utc_now()。
2. schema validator 在 payload 构造失败时：
   - 解析 ValidationError。
   - 用增强后的 _is_model_level_error() 进行 issue_code 分类。
   - 构建 blocking report 返回，不修改输入对象。
3. temporal/provenance validator：
   - 逻辑不变，仅默认时间来源统一。

## 5. Self-service modification guide

后续如果你要继续调整：

1. 若时间策略要改为 naive 或其他时区：只改 src/utils/time.py 的 utc_now()。
2. 若 id 命名规则调整：优先检查 src/validators/constants.py 的 fallback 值是否仍满足 pattern。
3. 若 schema.model_error 规则需要再收放：修改 src/validators/schema_validator.py 的 _is_model_level_error()，并同步更新 tests/test_schema_validator.py 的回归场景。
4. 若新增其他 report builder：默认时间请复用 utc_now()，避免再直接写 datetime.utcnow()。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py tests/test_phase1_state_envelope.py
```

预期结果：

- 全部通过。
- 当前实测：45 passed。

常见失败排查：

1. monkeypatch 路径写错（应 patch 到具体模块命名空间）。
2. fallback id 改动后不满足 id pattern，导致 report 构造失败。
3. schema model_error 判定过窄，导致对象级一致性错误回落为 field_error。

## 7. Concept notes

- 统一时间源
  - 这是机制层的可演化点管理，不是单纯代码风格。
  - 先收敛入口，再在后续阶段决定 naive/aware 的全局策略。

- model_error 与 field_error 分离
  - field_error 更偏字段约束。
  - model_error 更偏对象/一致性约束（常见于 model_validator after 阶段）。
  - 分类稳定性直接影响后续 write-gate 的审计可解释性。

- fallback id 集中管理
  - report 生成属于“错误路径上的核心机制”。
  - 将 fallback id 收口可降低“校验失败后无法产出报告”的二次失败风险。

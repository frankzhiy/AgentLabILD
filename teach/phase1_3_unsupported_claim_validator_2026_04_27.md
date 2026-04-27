# Phase 1-3：Unsupported-Claim Validator（2026-04-27）

## 1. Analysis path

本次按以下顺序阅读与定位：

- src/schemas/state.py
  - 确认 Phase1StateEnvelope 已在构造期做结构闭环（如 missing evidence、claim target mismatch）。
  - 明确本次 validator 应提供“独立 namespace 解释”，而不是替代 envelope 构造约束。
- src/schemas/claim.py、src/schemas/evidence.py、src/schemas/validation.py
  - 确认 ClaimReference/EvidenceAtom 可用字段与 ValidationIssue/StateValidationReport 的契约。
- src/validators/schema_validator.py、src/validators/provenance_validator.py、src/validators/temporal_validator.py
  - 对齐 validator API 形状、issue_id/report_id 生成与 summary 风格。
- tests/test_schema_validator.py、tests/test_temporal_validator.py、tests/test_provenance_validator.py、tests/test_provenance_checker.py
  - 复用现有 `build_valid_envelope()` 基线夹具，保持测试风格一致。

选择这条路径的原因：本任务是新增机制化 validator，不是改 schema 本体；因此应以现有报告契约与 validator 风格为主轴，再补充独立 unsupported_claim 命名空间。

## 2. Change list

- src/validators/unsupported_claims.py
  - 新增 `validate_phase1_unsupported_claims(...) -> StateValidationReport`。
  - 新增常量：
    - `UNSUPPORTED_CLAIM_VALIDATOR_NAME`
    - `UNSUPPORTED_CLAIM_VALIDATOR_VERSION`
  - 明确定位：该 validator 是 claim-level review lens，不替代 envelope closure。
  - 保留 `invalid_target_binding` 与 `missing_evidence_reference` 的 claim 命名空间解释（可与 closure 规则部分重叠）。
  - 将 evidence 可用性检查拆成 policy hook（当前默认 strict）：
    - `strict_current_stage_only`
    - `allow_historical_authoritative_evidence`（为后续阶段预留）
  - 实现 v1 规则：
    1. `unsupported_claim.missing_evidence_reference`（blocking）
    2. `unsupported_claim.unusable_evidence_reference`（blocking）
    3. `unsupported_claim.invalid_target_binding`（blocking）
    4. `unsupported_claim.overstated_strength`（warning, non-blocking）
  - 采用小 helper 拆分：
    - 证据引用分区（存在/缺失）
    - claim target 绑定校验
    - evidence 可用性判定
    - 强 claim 过度表述判定
    - issue 统一构造
- src/validators/__init__.py
  - 导出 unsupported-claim validator API 与常量。
- tests/test_unsupported_claims.py
  - 新增 7 个聚焦测试，覆盖成功、失败、warning、非变异、依赖边界。
- docs/devlog.md
  - 追加本次任务记录。

## 3. Connection mechanism

连接方式保持最小侵入：

- 通过 validators 包直接发现并调用：
  - `from src.validators import validate_phase1_unsupported_claims`
- 输入是已构造 `Phase1StateEnvelope`。
- 输出是 `StateValidationReport`，可与 schema/provenance/temporal 报告并列用于后续 write-gate 聚合。
- 未改 pipeline、storage、writer、orchestration。

## 4. Runtime data flow

1. 外部调用 `validate_phase1_unsupported_claims(envelope)`。
2. validator 从 envelope 建立只读视图：
   - `evidence_id -> EvidenceAtom` 映射
   - hypothesis/action id 集合
   - 当前 stage_id 与可见 source_doc_id 集合
3. 对每个 ClaimReference 执行规则：
  - target 是否能绑定到现有对象（claim-namespace 审阅视角）
  - evidence_ids 是否存在缺失（claim-namespace 审阅视角）
   - 已存在 evidence 中是否至少有一条“当前可用”
   - 若 claim 为 strong，且可用证据全部弱/不确定/reported，则给 warning
4. evidence 可用性判定走 policy hook：
  - 当前默认 `strict_current_stage_only`
  - 预留 `allow_historical_authoritative_evidence` 以支持未来历史权威证据视图
5. 把 issue 组装为 `ValidationIssue`（含 target_kind/field_path/related_ids/blocking）。
6. 汇总生成 `StateValidationReport`：
   - `has_blocking_issue = any(issue.blocking)`
   - `is_valid = not has_blocking_issue`

## 5. Self-service modification guide

如果后续要扩展规则，建议按以下方式改：

1. 新增规则时优先加独立 helper，不要把判断塞进主循环。
2. 保持 `unsupported_claim.*` 命名空间稳定，避免与 `schema.* / provenance.* / temporal.*` 混淆。
3. 若要收紧“evidence 可用性”标准，只使用 envelope 内已有结构字段（stage/source_doc/provenance 结构），不要引入语义推理。
4. 若要切换历史证据可用策略，优先调整 evidence usability policy hook，不要在主循环写死分支。
5. 若要调整 overstated 规则阈值，优先修改 `_is_weak_or_uncertain_evidence`，并同步更新测试。
6. 每次规则变更都新增对应 failure/warning 测试，避免回归成隐式行为。

## 6. Validation method

建议执行：

```bash
python -m pytest -q tests/test_unsupported_claims.py tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py
```

预期：

- `tests/test_unsupported_claims.py` 全通过。
- 现有 schema/temporal/provenance validator 测试不回归。

常见失败原因：

1. issue_id 或 report_id 不满足 pattern（`issue-*` / `report-*`）。
2. warning 误设为 blocking，导致 `is_valid` 语义错误。
3. related_ids 重复，触发 ValidationIssue 约束失败。

## 7. Concept notes

已确认事实：

- unsupported-claim validator 是外部机制层，必须 deterministic、auditable、non-mutation。
- 本次实现不做医学真值判断，不做 NLI，不做 guideline 推理。
- `invalid_target_binding` 与 `missing_evidence_reference` 可能和 envelope closure 局部重叠；本模块保留它们是为了 claim namespace 下的可审阅解释，不是替代 closure。

合理推断：

- 该 validator 在 write-gate 聚合中将承担“claim 支撑充分性”结构边界，补足 schema/provenance/temporal 的互补视角。

可选后续扩展（非本次交付）：

- 与 future state writer 聚合多份 report 决策 accepted/rejected/manual_review。
- 在不引入语义模型前提下，扩展更多 envelope-internal conservative 规则（例如 stage 可见性范围内的 claim-evidence 关联密度提示）。

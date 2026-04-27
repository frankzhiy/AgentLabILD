# Phase 1-6 Issue 1: Deterministic Fixtures for Benchmark Hook（2026-04-27）

## 1. Analysis path

本次先按“机制入口 -> 已有测试风格 -> 夹具边界”顺序定位：

1. `src/validators/pipeline.py`：确认基准入口是 `validate_phase1_candidate_pipeline`，以及 schema-only / full pipeline 执行分支。
2. `tests/test_validation_pipeline.py`：确认现有断言风格、validator 执行顺序常量和 issue namespace 约定。
3. `tests/test_provenance_checker.py`：复用已验证的 `build_valid_envelope` 字段结构，避免手写夹具偏离现有 schema。
4. `src/validators/schema_validator.py`、`src/validators/temporal_validator.py`、`src/validators/unsupported_claims.py`：锁定每个失败模式对应的 issue_code 与触发条件。
5. `src/validators/provenance_validator.py` 与 `tests/test_source_document_evidence_alignment.py`：确认 source alignment 夹具应走 `validate_evidence_atoms_against_sources`。

为什么这样做：

1. 先锁定执行入口，保证 fixture 直接服务 benchmark hook，而不是绕行到新机制。
2. 先对齐现有测试语义，再设计 fixture，可减少“夹具通过但断言不稳定”的风险。
3. source alignment 作为桥接校验独立于主 pipeline，单独建夹具能清晰表达边界。

## 2. Change list

本次新增文件：

1. `tests/fixtures/phase1/valid_minimal_case.json`
- 最小可通过 envelope（单 evidence、单 hypothesis、无 action）。
- 含完整 provenance，可在 `require_provenance=True` 下通过 full pipeline。

2. `tests/fixtures/phase1/valid_multihypothesis_case.json`
- 多 hypothesis + action 的可通过 envelope。
- 覆盖 board 集合闭环、多证据与多 claim 关联。

3. `tests/fixtures/phase1/invalid_missing_evidence_ref.json`
- 触发 `schema.model_error`，原因是 claim 引用了 envelope 不存在的 evidence id。

4. `tests/fixtures/phase1/invalid_unsupported_claim.json`
- 保持 schema 有效，但构造“游离 claim 指向不存在 hypothesis”，触发 `unsupported_claim.invalid_target_binding`。

5. `tests/fixtures/phase1/invalid_stage_mismatch.json`
- 构造 hypothesis 的 `stage_id` 与 `stage_context.stage_id` 不一致，触发 schema 层 stage 对齐失败。

6. `tests/fixtures/phase1/invalid_temporal_order.json`
- 构造 `stage_context.created_at > envelope.created_at`，触发 `temporal.stage_after_envelope`。

7. `tests/fixtures/phase1/invalid_source_alignment.json`
- 独立的 source alignment 夹具（`source_documents + evidence_atoms`），触发 `provenance.raw_excerpt_not_found`。

8. `tests/fixtures/phase1/valid_two_stage_version_chain.json`
- 两个 state 组成的版本链正例（`state_version=1 -> 2`，第二版 `parent_state_id` 指向第一版）。

9. `tests/test_phase1_fixtures.py`
- 新增 fixture 加载与验证测试。
- 包含 valid/invalid 路径、版本链持久化路径、source alignment 路径。
- 每个 invalid fixture 的失败模式注释写在测试文件中（不写入 JSON）。

## 3. Connection mechanism

新内容如何被现有框架发现和调用：

1. benchmark hook 侧可直接读取 `tests/fixtures/phase1/*.json` 作为稳定输入。
2. 主验证入口使用 `validate_phase1_candidate_pipeline`：
- valid 夹具走 full pipeline。
- schema 级无效夹具走 schema-only 分支。
3. source alignment 夹具由 `validate_evidence_atoms_against_sources` 消费，不改变主 pipeline 责任边界。
4. 版本链夹具通过 `InMemoryStateStore.persist_snapshot` 验证 state lineage，与已有存储机制直接兼容。

## 4. Runtime data flow

### 4.1 valid fixture 主路径

1. 从 JSON 读取 envelope payload。
2. 调用 `validate_phase1_candidate_pipeline(payload, policy=require_provenance=True)`。
3. pipeline 顺序执行：schema -> provenance -> temporal -> unsupported_claim。
4. 返回 `Phase1ValidationPipelineResult`，断言 `has_blocking_issue=False`。

### 4.2 invalid fixture 主路径

1. 从 JSON 读取特定失败模式 payload。
2. 运行 pipeline。
3. 根据 fixture 设计断言对应 validator report 与 issue_code：
- schema-only（如 missing evidence ref、stage mismatch）
- downstream blocking（如 temporal、unsupported claim）

### 4.3 source alignment 路径

1. 从 JSON 读取 `source_documents` 与 `evidence_atoms`。
2. 分别反序列化为 `SourceDocument` 与 `EvidenceAtom`。
3. 调用 `validate_evidence_atoms_against_sources`。
4. 断言 `provenance.raw_excerpt_not_found`。

### 4.4 two-stage version chain 路径

1. 逐个 state payload 跑 full pipeline。
2. 将通过验证的 `candidate_envelope` 写入 `InMemoryStateStore`。
3. 断言版本顺序、parent linkage 和 latest state。

## 5. Self-service modification guide

如果后续要扩展夹具集，建议按以下原则修改：

1. 新增 valid 夹具
- 优先在现有 valid 夹具基础上做最小增量，不要一次混入多个新语义点。
- 如需 strict provenance，通过 `require_provenance=True` 验证。

2. 新增 invalid 夹具
- 一次只触发一个主失败机制（schema/provenance/temporal/unsupported_claim/source_alignment）。
- 在测试文件写清“预期失败模式注释 + 对应 issue_code 断言”。

3. 调整版本链夹具
- 保持 `state_version` 严格递增。
- `state_version > 1` 时必须让 `parent_state_id` 指向上一版 `state_id`。

4. 保持机制边界
- 夹具只表达状态与校验输入，不引入 prompt 控制逻辑。
- 不要为让夹具通过而修改 schema/validator 语义。

## 6. Validation method

本次改动建议执行：

```bash
python -m pytest -q tests/test_phase1_fixtures.py
python -m pytest -q
```

预期：

1. `tests/test_phase1_fixtures.py` 全部通过。
2. 全量测试无回归。

常见失败排查：

1. ID pattern 不匹配（`case-`/`stage-`/`evd-`/`claim_ref-` 等前缀）。
2. board 集合与 envelope 实体不一致（`evidence_ids`/`hypothesis_ids`/`action_candidate_ids`）。
3. claim 与 evidence/hypothesis 绑定关系不闭环。
4. 版本链 parent linkage 与 state_version 规则不一致。
5. source alignment 测试把失败码写成 `source_span_*`，但实际夹具触发的是 `raw_excerpt_not_found`。

## 7. Concept notes

本次夹具设计强调以下机制概念：

1. Deterministic benchmark input
- 夹具是 benchmark 的“稳定输入合同”，不能依赖 LLM 运行时随机性。

2. Failure mode isolation
- 每个 invalid fixture 对应一个主失败机制，避免一个样本触发多类错误导致结果不可解释。

3. Mechanism-first verification
- 先验证 schema/provenance/temporal/unsupported_claim/source_alignment 机制层，再谈 metrics 或 runner。

4. Stage-aware and lineage-aware state
- 夹具不只验证单状态合法性，也验证阶段语义与版本链可持续性。

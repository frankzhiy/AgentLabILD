# Phase 1-2 EvidenceAtom/Provenance 权威源收敛（2026-04-23）

## 1. Analysis path
- 首先阅读 `src/schemas/evidence.py`，确认 EvidenceAtom 里 flat source 字段与 `provenance` 并存且当前仅做 id/stage 轻校验。
- 接着阅读 `src/provenance/checker.py`，确认检查器覆盖 stage/case/source_doc 可见性与 claim 绑定，但尚未覆盖 flat-source 与 provenance 对齐。
- 然后阅读 `src/validators/provenance_validator.py`，确认 validator 仅负责 issue 转换与 report 组装，适合保持“薄层”。
- 最后阅读 `tests/test_provenance_checker.py` 与 `tests/test_provenance_validator.py`，确定可在现有构造器上补充单锚/多锚对齐测试。

## 2. Change list
- `src/schemas/evidence.py`
  - 仅更新语义注释与类文档，明确 authority rule：
    - `provenance is None`：flat source 字段继续用于历史兼容。
    - `provenance is not None`：`provenance` 为权威，flat 字段为兼容镜像。
  - 保持字段与已有 schema 校验不变，不把 checker 业务逻辑搬进 schema。
- `src/provenance/checker.py`
  - 新增 flat/provenance 对齐检查（只产出结构化 issue，不做修复，不做对象变更）：
    - `provenance.evidence_flat_source_doc_mismatch`
    - `provenance.evidence_flat_excerpt_mismatch`
    - `provenance.evidence_flat_span_mismatch`
    - `provenance.evidence_flat_extraction_method_mismatch`
    - `provenance.evidence_flat_multi_anchor_ambiguous`
  - 新增 extraction method 归一化比较函数，兼容字符串/枚举表现形式（如 `manual-curation` vs `manual_curation`）。
- `tests/test_provenance_checker.py`
  - 将基准 fixture 调整为“单锚完全对齐”（避免基准数据天然冲突）。
  - 新增覆盖：单锚 doc/excerpt/span mismatch、extraction_method mismatch、多锚 source_doc membership mismatch、多锚 excerpt/span ambiguous、以及 provenance 缺失兼容模式。
- `tests/test_provenance_validator.py`
  - 新增 validator 级回归：flat source_doc mismatch 会进入 blocking report。

## 3. Connection mechanism
- 运行入口仍是 `validate_phase1_provenance`（`src/validators/provenance_validator.py`）。
- validator 调用 `check_phase1_provenance`（`src/provenance/checker.py`）拿到 `ProvenanceCheckIssue`。
- validator 再转换为 `ValidationIssue`，输出 `StateValidationReport`。
- 因此本次新增规则无需改 orchestration/agent；只要复用现有 validator 调用链就可生效。

## 4. Runtime data flow
- 输入：`Phase1StateEnvelope`（包含 `evidence_atoms[*]` 与可选 `provenance`）。
- checker 处理流程：
  - 先执行既有 stage/case/source_doc/evidence/claim 绑定检查。
  - 对每个 `EvidenceAtom`：
    - 若 `provenance` 缺失，按 `require_provenance` 输出 warning 或 error（兼容模式保留）。
    - 若 `provenance` 存在：
      - 单锚：flat `source_doc_id`/`raw_excerpt`/`span` 必须严格等于 anchor。
      - 多锚：flat `source_doc_id` 必须属于 anchor doc 集合；flat excerpt/span 无法唯一映射时输出 `multi_anchor_ambiguous`。
      - `extraction_method` 若提供，需与 `extraction_activity.extraction_method` 归一化后对齐。
- 输出：结构化 issues（含 `issue_code`、`target_kind`、`field_path`、`blocking`），无自动修复、无状态变异。

## 5. Self-service modification guide
- 想调整“多锚 ambiguous”严重度：修改 `src/provenance/checker.py` 中 `provenance.evidence_flat_multi_anchor_ambiguous` 的 `severity/blocking`。
- 想收紧 extraction method 规则：修改 `_normalize_extraction_method`（例如取消 `-` 与 `_` 的归一化等价）。
- 想增加更多 flat mirror 字段对齐：在 checker 的 EvidenceAtom 分支增加新的 issue_code 与测试，不建议放到 schema validator。

## 6. Validation method
- 相关回归：
  - `python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py`
  - 期望：`21 passed`
- 全量回归：
  - `python -m pytest -q`
  - 期望：`179 passed`
- 常见失败优先排查：
  - fixture 是否在“有 provenance”路径下保持 flat/source_anchors 对齐；
  - 多锚测试是否同步更新 `stage_context.source_doc_ids` 与 `input_source_doc_ids`。

## 7. Concept notes
- 单一权威源（single source of truth）：当 `provenance` 存在时，结构化 provenance 是权威；flat 字段只做兼容镜像。
- 镜像一致性（mirror alignment）：镜像字段仍可保留，但必须可验证，不允许“隐式修复”。
- 纯检查器（pure checker）：checker 只报告问题，不写回、不纠正，保持审计可追溯与机制边界清晰。
- 兼容优先：当 `provenance` 缺失时仍保留 legacy 行为，避免破坏现有数据与流程。

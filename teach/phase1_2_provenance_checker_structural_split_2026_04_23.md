# Phase 1-2 provenance checker 结构拆分教学说明（2026-04-23）

## 1. Analysis path

本次任务是结构拆分且语义冻结，因此分析顺序是“先锁行为，再拆文件”：

1. src/provenance/checker.py
- 先定位 issue 结构、evidence 检查块、claim 检查块、orchestrator 尾部逻辑的边界与执行顺序。

2. src/validators/provenance_validator.py
- 确认外部依赖点仅要求 `ProvenanceCheckIssue` 与 `check_phase1_provenance(...)` 行为稳定。

3. tests/test_provenance_checker.py 与 tests/test_provenance_validator.py
- 锁定必须保持的行为：issue_code、blocking 语义、backward-compatible 缺失 provenance 处理、输出顺序可转换性。

4. docs/devlog.md
- 确认日志追加格式。

## 2. Change list

### 新增 src/provenance/issues.py
- 从旧 checker 迁移：
  - ProvenanceCheckIssue
  - _make_issue
  - _missing_provenance_issue
  - _normalize_extraction_method
- 作用：集中承载 issue 结构和 issue 构造辅助。

### 新增 src/provenance/evidence_checks.py
- 从旧 checker 迁移 evidence 相关检查循环。
- 新增入口：run_evidence_provenance_checks(...)
- 返回：
  - tuple[ProvenanceCheckIssue, ...]
  - evidence_provenance_id -> evidence_id 映射

### 新增 src/provenance/claim_checks.py
- 从旧 checker 迁移 claim 相关检查循环。
- 新增入口：run_claim_provenance_checks(...)
- 返回：
  - tuple[ProvenanceCheckIssue, ...]
  - 被 claim 引用的 evidence_provenance_id 集合

### 修改 src/provenance/checker.py
- 收敛为薄编排器：
  - 准备 stage/case/source_doc 上下文
  - 调用 evidence/claim 两个分域检查函数
  - 保留 envelope 级 `provenance.orphan_provenance` 汇总告警
- 保持公共导出不变：
  - ProvenanceCheckIssue
  - check_phase1_provenance

### 修改 docs/devlog.md
- 追加本次结构拆分记录。

## 3. Connection mechanism

连接路径保持不变：

1. 外部调用仍从 src/provenance/checker.py 的 check_phase1_provenance(...) 进入。
2. checker 内部调用：
- run_evidence_provenance_checks(...)
- run_claim_provenance_checks(...)
3. validator 层继续调用 checker 并转换为 ValidationIssue / StateValidationReport。

因此外部 validator API 与调用方行为不需要改动。

## 4. Runtime data flow

运行时数据流：

1. 输入：Phase1StateEnvelope。
2. checker 提取 stage_id 与可见 source_doc_ids。
3. evidence_checks 处理 EvidenceAtom 相关一致性，输出 issue + evidence_provenance 映射。
4. claim_checks 处理 ClaimReference 相关一致性，输出 issue + referenced evidence_provenance 集合。
5. checker 计算未被 claim 引用的 evidence_provenance 并追加 warning。
6. 返回 tuple[ProvenanceCheckIssue, ...] 给 validator。

## 5. Self-service modification guide

后续若要扩展规则，按责任放置：

1. 新增/调整 issue 结构字段
- 修改 src/provenance/issues.py。

2. 新增 EvidenceAtom 侧规则
- 修改 src/provenance/evidence_checks.py。

3. 新增 ClaimReference 侧规则
- 修改 src/provenance/claim_checks.py。

4. 新增 envelope 级汇总规则或跨域编排规则
- 修改 src/provenance/checker.py。

注意：若规则影响 issue_code、blocking 或缺失 provenance 兼容语义，需要同步更新测试并显式记录行为变更。

## 6. Validation method

建议命令：

```bash
python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py
python -m pytest -q
```

本次实际结果：

- provenance 定向测试：21 passed
- 全量回归：179 passed

常见失败优先排查：

1. 迁移时 issue_code 文本或 field_path 被改动。
2. evidence/claim issue 追加顺序变化导致报告序号漂移。
3. missing provenance 的 require_provenance 分支语义被改动。

## 7. Concept notes

1. 结构拆分与语义冻结
- 先冻结行为，再拆模块，避免“重构顺带改逻辑”。

2. 薄编排器模式
- checker 只做上下文准备与跨域汇总，规则细节下沉到分域模块。

3. 可审计 issue 管线
- issue 构造集中化有助于稳定 issue_code、severity、blocking 语义与后续报告映射一致性。

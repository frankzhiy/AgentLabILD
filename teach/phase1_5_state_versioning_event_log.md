# Phase 1-5 Stage-aware State Versioning + Append-only Event Log（2026-04-27）

## 1. Analysis path

本次按以下顺序分析并定位改动点：

1. AGENTS.md
2. .github/copilot-instructions.md
3. .github/instructions/schemas.instructions.md
4. .github/instructions/tests.instructions.md
5. src/schemas/state.py
6. src/schemas/common.py
7. src/schemas/intake.py
8. src/state/sinks.py
9. src/state/state_writer.py
10. src/storage/__init__.py
11. src/storage/placeholder.py
12. tests/test_phase1_state_envelope.py
13. tests/test_state_writer.py
14. tests/test_intake_schemas.py
15. docs/devlog.md

为什么这个顺序是合理的：

1. 先锁定机制边界与仓库约束，避免 Phase 1-5 越界到诊断/仲裁逻辑。
2. 再确认现有 envelope、id pattern、writer/sink 合同，确保新层“包裹”而不是“重构”。
3. 最后对齐测试风格与文档风格，保证新增内容可直接进入现有研发节奏。

## 2. Change list

本次新增/修改如下：

1. src/schemas/common.py
- 新增 `EVENT_ID_PATTERN` 并导出，统一事件 id 正则入口。

2. src/schemas/state_event.py
- 新增 `StateEventType`：
  - `source_document_received`
  - `candidate_state_submitted`
  - `state_validation_accepted`
  - `state_validation_rejected`
  - `state_persisted`
  - `snapshot_created`
- 新增 `StateEvent`，字段满足 Phase 1-5 要求：
  - `kind`, `event_id`, `event_type`, `case_id`, `stage_id`, `state_id`, `parent_state_id`, `state_version`, `source_doc_ids`, `created_at`, `created_by`, `non_authoritative_note`
- 关键约束：
  - `extra="forbid"`
  - 稳定 id pattern 校验
  - `source_doc_ids` 去重
  - `state_version >= 1`（当存在时）
  - `parent_state_id != state_id`
  - `state_persisted` 必须有 `state_id/state_version`
  - `source_document_received` 必须至少一个 `source_doc_id`

3. src/schemas/__init__.py
- 导出 `StateEvent` / `StateEventType`。

4. src/storage/event_log.py
- 新增 `EventLog` protocol。
- 新增 `InMemoryEventLog`：
  - append-only
  - 拒绝重复 `event_id`
  - 按 `created_at` 再按 `event_id` 排序返回
  - 存储和读取都走 deep copy

5. src/storage/state_store.py
- 新增 `StateStore` protocol。
- 新增 `InMemoryStateStore`：
  - `persist_snapshot` / `get_state` / `get_latest_state` / `list_state_versions` / `replay`
  - 实现 `persist(envelope)` 兼容 `StateSink`
- 关键约束：
  - case 内 `state_version` 严格递增
  - 第一版必须 `state_version=1`
  - `state_version>1` 时 `parent_state_id` 必须指向上一版 `state_id`
  - 拒绝重复 `state_id`
  - deep copy 存储与返回

6. src/storage/__init__.py
- 从 skeleton 改为正式导出 `EventLog` / `InMemoryEventLog` / `StateStore` / `InMemoryStateStore`。

7. tests/test_state_event.py
- 覆盖事件 schema 成功/失败路径。
- 包含 free-text 提交被建模为 `source_document_received`（而非拆成多个 StageContext）的语义用例。

8. tests/test_event_log.py
- 覆盖 append/retrieve、重复 id 阻断、排序规则、deep copy 语义。

9. tests/test_state_store.py
- 覆盖版本链、父状态引用、replay 行为、重复 state_id 阻断、deep copy、`StateSink.persist` 兼容。

10. docs/devlog.md
- 追加本次任务记录。

11. teach/phase1_5_state_versioning_event_log.md
- 新增本教学说明文档。

## 3. Connection mechanism

新机制如何被现有框架发现与调用：

1. 事件模型
- 导入路径：`src.schemas.state_event`
- 包级导出：`src.schemas`

2. 事件日志
- 导入路径：`src.storage.event_log`
- 包级导出：`src.storage`

3. 状态快照存储
- 导入路径：`src.storage.state_store`
- 包级导出：`src.storage`

4. 与既有 write gate 的兼容点
- `InMemoryStateStore.persist(envelope)` 与 `src.state.sinks.StateSink.persist` 同签名。
- 这意味着现有 `attempt_phase1_write(..., sink=...)` 可以直接传入 `InMemoryStateStore`，无需改 writer。

## 4. Runtime data flow

典型运行时数据流如下：

1. 用户提交 free-text。
2. intake 层把该提交登记为 source document（既有机制）。
3. 系统创建 `StateEvent(event_type=source_document_received, source_doc_ids=...)`。
4. adapter + validator + write gate 产生被接受的 `Phase1StateEnvelope`（既有机制）。
5. 系统追加 `StateEvent`（如 `state_validation_accepted` / `state_persisted` / `snapshot_created`）。
6. `InMemoryStateStore.persist_snapshot(envelope, created_from_event=...)` 持久化快照：
- 检查版本链和父状态约束。
- 通过后 deep copy 存储。
7. `replay(case_id)` 返回最新版本，`replay(case_id, until_state_id=...)` 返回指定历史快照。

说明：

1. 该流程只补“历史与版本”机制层。
2. 不新增诊断推理、不做冲突检测、不做局部修订与仲裁。

## 5. Self-service modification guide

后续你可按以下位置定制：

1. 增加事件类型或事件约束
- 编辑 `src/schemas/state_event.py`：`StateEventType` 与 `validate_event_consistency`。

2. 调整事件排序策略
- 编辑 `src/storage/event_log.py` 中 `list_events` / `list_events_for_state` 的排序 key。

3. 调整版本链策略（例如是否允许跳号）
- 编辑 `src/storage/state_store.py` 的 `persist_snapshot` 版本检查分支。

4. 增强事件到快照的追踪字段
- 现在已保留 `created_from_event` 参数并做一致性检查。
- 若要对外暴露查询接口，可在 `state_store.py` 新增只读 getter（不破坏 append-only/immutable 原则）。

5. 若接入真实存储后端
- 保持 `EventLog` / `StateStore` 协议不变，新增实现类即可。
- 先保留 in-memory 作为测试后端，避免破坏现有测试稳定性。

## 6. Validation method

本次执行的验证命令：

```bash
python -m pytest -q tests/test_state_event.py tests/test_event_log.py tests/test_state_store.py
python -m pytest -q tests/test_skeleton_imports.py tests/test_state_writer.py tests/test_common_id_patterns.py
```

预期结果：

1. 新增三组测试通过。
2. 既有 writer/import/id-pattern 回归通过。

常见失败原因排查：

1. 事件 id 前缀不匹配（应为 `event-` 或 `event_`）。
2. `state_persisted` 缺 `state_id` 或 `state_version`。
3. 第二版快照 `parent_state_id` 未指向上一版。
4. 返回对象未 deep copy，导致“读后改写污染存储”。

## 7. Concept notes

本次涉及的核心设计概念：

1. Append-only event log
- 事件只追加，不覆盖，不删除。
- 用排序规则保证可重放顺序稳定。

2. Snapshot version chain
- 快照是权威状态切片。
- `state_version` + `parent_state_id` 构成可审计 lineage。

3. Event vs Stage 边界
- free-text 中的“8 years ago/2 months ago/日期”属于证据时间事实。
- 默认不会自动拆成多个 `StageContext`。
- 新阶段由用户提交新的 review/supplementary material 触发。

4. Mechanism-first
- 规则在可执行 schema/storage 中，而不是写在 prompt 里。
- 这样才能保证可追溯、可复现、可审计。

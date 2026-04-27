# Phase 1-5 State History Semantic Tightening（2026-04-27）

## 1. Analysis path

本次按以下顺序分析：

1. AGENTS.md
2. .github/copilot-instructions.md
3. .github/instructions/schemas.instructions.md
4. .github/instructions/tests.instructions.md
5. src/schemas/state_event.py
6. src/storage/event_log.py
7. src/storage/state_store.py
8. src/state/sinks.py
9. src/state/state_writer.py
10. tests/test_state_event.py
11. tests/test_event_log.py
12. tests/test_state_store.py
13. tests/test_state_writer.py
14. docs/devlog.md

为什么这样看：

1. 先确认机制边界，避免把 Phase 1-5 扩展到 Phase 4 语义。
2. 再对齐 schema/store/writer 接口，确保新增能力可被现有 write gate 直接消费。
3. 最后以测试驱动收紧失败路径，保证规则是可执行约束而非文档约束。

## 2. Change list

1. src/schemas/state_event.py
- `model_config` 改为 `frozen=True`，确保事件对象不可变。
- 新增 `input_event_ids`（可选，默认空）用于 intake 审计直连。
- 新增 `input_event_ids` 去重与 `INPUT_EVENT_ID_PATTERN` 校验。

2. src/storage/state_store.py
- 首次写入 case 时新增硬约束：
  - `state_version == 1`
  - `parent_state_id is None`
- 强化 `created_from_event` 一致性校验：
  - `case_id` 必须匹配
  - `stage_id`（若提供）必须匹配 `envelope.stage_context.stage_id`
  - `state_id`（若提供）必须匹配
  - `parent_state_id`（若提供）必须匹配
  - `state_version`（若提供）必须匹配
  - `event_type` 必须是 `state_persisted` 或 `snapshot_created`
- `replay()` 文档澄清为 snapshot-level replay，不是事件重建。

3. src/storage/versioned_state_sink.py（新增）
- 新增 `VersionedStateSink`，实现现有 `StateSink.persist(envelope)` 合同。
- `persist(envelope)` 行为：
  1. 生成不碰撞 `event_id`
  2. 构建 `StateEvent(event_type=state_persisted)`
  3. append 到 `event_log`
  4. 调用 `state_store.persist_snapshot(envelope, created_from_event=event)`

4. src/storage/__init__.py
- 导出 `VersionedStateSink`。

5. tests/test_state_event.py
- 增加 `input_event_ids` 去重/格式失败用例。
- 增加 frozen 不可变用例。
- 保留 free-text 提交语义用例，并补 `input_event_ids` 断言。

6. tests/test_event_log.py
- 适配 frozen 语义，改为断言实例不可修改。
- 保留 append-only 与 deep-copy 返回行为断言。

7. tests/test_state_store.py
- 新增首版本 `parent_state_id` 非空拒绝用例。
- 新增 `created_from_event` 的 stage_id mismatch、parent_state_id mismatch、invalid event_type 失败用例。
- 新增 `snapshot_created` 作为合法 `created_from_event` 类型的通过用例。

8. tests/test_versioned_state_sink.py（新增）
- 新增 writer 集成测试：`attempt_phase1_write(..., sink=VersionedStateSink(...))` 同时产生快照与 `state_persisted` 事件。
- 新增 event_id 防碰撞测试（预置冲突 id 后自动跳过）。

## 3. Connection mechanism

连接机制如下：

1. 现有写入路径不变：`attempt_phase1_write` 仍只调用 `sink.persist`。
2. 当 sink 使用 `VersionedStateSink` 时，`persist` 内部自动串联：
- append-only event log
- versioned snapshot store
3. 因为 `VersionedStateSink` 仍遵守 `StateSink` 合同，上游 orchestration/pipeline 无需改动。

## 4. Runtime data flow

运行时路径：

1. candidate 进入 `attempt_phase1_write`。
2. 通过 validator pipeline 后得到 `ACCEPTED`。
3. writer 调用 `VersionedStateSink.persist(envelope)`。
4. sink 创建 `state_persisted` 事件并 append 到 `EventLog`。
5. sink 以该事件为 `created_from_event` 持久化 `Phase1StateEnvelope` 到 `StateStore`。
6. 后续查询可走：
- `event_log.list_events(case_id)` 查看事件轨迹
- `state_store.list_state_versions(case_id)` 查看快照版本链
- `state_store.replay(...)` 做 snapshot-level 回放

## 5. Self-service modification guide

后续可修改点：

1. 若要新增事件类型
- 修改 src/schemas/state_event.py 的 `StateEventType` 与校验逻辑。

2. 若要更严格约束 `created_from_event`
- 修改 src/storage/state_store.py 的 `_validate_created_from_event`。

3. 若要更换 event_id 生成策略
- 修改 src/storage/versioned_state_sink.py 的 `_next_event_id`。

4. 若要切换存储后端
- 保持 `StateStore` / `EventLog` 协议不变，替换实现类即可。

## 6. Validation method

执行命令：

```bash
python -m pytest -q tests/test_state_event.py tests/test_event_log.py tests/test_state_store.py tests/test_versioned_state_sink.py tests/test_state_writer.py
```

预期输出：

1. 全部测试通过（本次 37 passed）。
2. `VersionedStateSink` 集成路径通过。
3. 新增失败路径（mismatch / invalid event_type）被稳定拦截。

常见失败原因：

1. `created_from_event.event_type` 不是 `state_persisted/snapshot_created`。
2. first snapshot 错误设置了 `parent_state_id`。
3. 事件时间混用 naive/aware，导致 event log 排序比较异常。

## 7. Concept notes

关键概念：

1. 事件不可变（frozen）
- 保证 append-only log 的语义稳定，不允许后改历史事件。

2. 快照链严格约束
- 通过 `state_version + parent_state_id` 明确 lineage，阻断隐式跳链。

3. replay 边界澄清
- 当前 replay 是“读取快照历史”，不是“从事件重建认知状态”。
- 事件重建/局部修订属于后续阶段，不在 Phase 1-5 实现范围。

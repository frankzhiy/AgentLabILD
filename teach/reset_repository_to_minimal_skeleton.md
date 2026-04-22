# 仓库重置教学说明：最小研究平台骨架

## 1. Analysis path

本次重置先读取以下文件作为分析起点：

1. `docs/architecture.md`：识别旧架构叙事与模块耦合范围
2. `src/runner.py`：确认旧实验执行主路径
3. `src/schemas/state.py`：确认旧状态对象形态
4. `.github/copilot-instructions.md` 与 `AGENTS.md`：确认仓库级机制优先约束与交付规范

选择这条路径的原因是：先锁定“旧实验主干”与“必须遵守的机制边界”，才能安全地做破坏性清理。

## 2. Change list

### 2.1 结构重置

- 清空并重建：`src/`、`configs/`、`data/`、`teach/`、`tests/`
- 清理旧文档：删除 `docs/config_reference.md`、`docs/getting_started.md`

### 2.2 骨架源码

- 新增 `src/__init__.py`
- 新增 `src/runner.py`（占位运行器）
- 为以下包新增 `__init__.py` 与 `placeholder.py`：
  - `agents`、`communication`、`conflict`、`evaluation`、`llm`
  - `pipeline`、`schemas`、`tracing`
  - `state`、`validators`、`provenance`、`storage`、`revision`、`arbitration`
- 新增 `src/schemas/state.py`（最小状态占位类型）

### 2.3 文档与测试

- 重写 `README.md` 为重置说明
- 重写 `docs/architecture.md` 为骨架版架构
- 追加 `docs/devlog.md` 重置日志
- 新增 `tests/test_skeleton_imports.py`（骨架导入 + runner 占位行为测试）

## 3. Connection mechanism

重置后连接机制是“显式导入 + 明确占位”。

- 发现机制：Python 包导入系统（`import src...`）
- 入口机制：`run.py` 调用 `src.runner.ExperimentRunner`
- 约束机制：占位模块只暴露最小对象，不承载旧实验逻辑

这让框架在“可导入”与“可扩展”之间保持最小稳定面。

## 4. Runtime data flow

当前运行时数据流是骨架态：

1. 执行 `python run.py`
2. `run.py` 调用 `ExperimentRunner().run()`
3. `run()` 返回固定占位字典（`status`、`experiment_name`、`message`）
4. CLI 打印 `message`

说明：该数据流仅用于验证工程骨架健康，不代表任何临床推理流水线。

## 5. Self-service modification guide

如果你要在此骨架上继续重建：

1. 先从 `src/schemas/` 与 `src/schemas/state.py` 建立显式状态对象
2. 再实现 `src/provenance/` 的证据追溯模型
3. 再实现 `src/validators/` 的写入前校验报告
4. 然后在 `src/state/` 增加状态写入器与迁移接口
5. 最后逐步接回 `storage/revision/conflict/arbitration` 与 agent 适配层

建议每一步都先补对应测试，再引入下一层模块。

## 6. Validation method

建议验证命令：

```bash
python -m pytest -q
python run.py
```

预期结果：

- pytest 通过
- CLI 输出占位提示（表示骨架入口可用）

常见失败原因：

- 缺少某个包的 `__init__.py`
- `run.py` 与 `src/runner.py` 的导入路径不一致
- 新增文件后未在本地正确保存或写入失败

## 7. Concept notes

本次涉及的核心工程概念：

- Skeleton reset（骨架重置）：先剥离旧行为，仅保留可扩展结构
- Import stability（导入稳定性）：通过最小模块保证项目在重建期可被工具链加载
- Placeholder module（占位模块）：以最小接口声明“这里将来会有机制实现”
- Mechanism-first layering（机制优先分层）：先状态与校验，再 agent 与编排

这类重置有助于将“历史实验债务”与“下一阶段研究目标”解耦。
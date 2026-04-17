# 教学文档：编排策略模块重构

## 需求背景

将 YAML 从"决策者"变为纯"选择器"——YAML 不再定义 pipeline 拓扑（nodes/edges），而是引用一个**编排策略**名，拓扑逻辑完全在 Python 代码中定义。

核心改变：

```
# 之前（YAML 决策拓扑）
pipeline:
  nodes:
    - id: "step1"
      agents: ["pulmonologist", "radiologist"]
    - id: "step2"
      agents: ["moderator"]
  edges:
    - from: "START" → to: "step1"
    - from: "step1" → to: "step2"
    - from: "step2" → to: "END"

# 之后（YAML 只选择策略）
orchestration:
  strategy: "sequential_then_synthesize"
  parameters:
    specialists: ["pulmonologist", "radiologist"]
    synthesizer: "moderator"
```

## 分析路径

1. 从 `src/schemas/experiment.py` 入手——这是 YAML 与代码的桥梁，需要先改数据模型
2. 再看 `src/pipeline/builder.py`——这是目前用 nodes/edges 手动建图的代码，需要改为委托
3. 创建 `src/orchestration/` 模块——承接原先由 YAML + builder 共同承担的拓扑定义职责
4. 最后更新 YAML 配置文件和测试

为什么从 schema 开始？因为 schema 是配置结构的"合同"。先确定新的数据结构（`OrchestrationConfig`），其他代码才知道该适配什么。

## 改动清单

### 新建文件

| 文件 | 作用 |
|------|------|
| `src/orchestration/__init__.py` | 空文件，声明 Python 包 |
| `src/orchestration/base.py` | 编排策略的**抽象基类** + **注册表** |
| `src/orchestration/sequential.py` | 第一个具体策略：先专科分析 → 再综合诊断 |

### 修改文件

| 文件 | 改动概要 |
|------|----------|
| `src/schemas/experiment.py` | 删除 `PipelineConfig` 相关类（`PipelineNodeConfig`、`EdgeConfig`、`ConditionalEdgeConfig`、`PipelineConfig`），新增 `OrchestrationConfig`；`ExperimentConfig.pipeline` → `ExperimentConfig.orchestration` |
| `src/pipeline/builder.py` | 删除 `CONDITION_REGISTRY`、`register_condition()`、手动建图逻辑；改为委托编排策略的 `build_graph()` |
| `configs/experiments/baseline_3agent.yaml` | `pipeline:` 段替换为 `orchestration:` 段 |
| `src/runner.py` | 新增 `import src.orchestration.sequential` 确保策略被注册 |
| `tests/test_pipeline_builder.py` | YAML 配置改为 orchestration 格式 |
| `tests/test_runner.py` | mock config 和断言改为 orchestration 格式 |
| `tests/test_schemas.py` | YAML 配置和断言改为 orchestration 格式 |

## 连接原理（新代码如何被框架发现和调用）

### 注册表机制

编排策略沿用项目中已有的注册表模式（与 agent、通信协议一致）：

```
①  定义注册表字典
    ORCHESTRATION_REGISTRY: dict[str, Type[BaseOrchestration]] = {}

②  提供装饰器
    @register_orchestration("sequential_then_synthesize")
    class SequentialThenSynthesize(BaseOrchestration): ...
    → 装饰器在类定义时把 "sequential_then_synthesize" → SequentialThenSynthesize 写入字典

③  提供查询函数
    get_orchestration_class("sequential_then_synthesize") → SequentialThenSynthesize

④  触发注册
    在 pipeline/builder.py 中 import src.orchestration.sequential
    → Python 加载模块 → @register_orchestration 装饰器执行 → 类被注册
```

### YAML → OrchestrationConfig → 策略实例

```
YAML 文件:
  orchestration:
    strategy: "sequential_then_synthesize"
    parameters: { specialists: [...], synthesizer: "..." }

       ↓ yaml.safe_load() + ExperimentConfig(**raw)

OrchestrationConfig:
  .strategy = "sequential_then_synthesize"
  .parameters = { specialists: [...], synthesizer: "..." }

       ↓ builder.py: get_orchestration_class(config.orchestration.strategy)

SequentialThenSynthesize 类

       ↓ cls(parameters=config.orchestration.parameters)

策略实例 (self.parameters 含 specialists/synthesizer)

       ↓ orchestration.build_graph(agents, protocol, llm_client, tracer_factory)

编译后的 LangGraph
```

## 运行时数据流

以 baseline 3-agent 实验为例，完整的数据流：

```
1. ExperimentRunner.__init__()
   ├─ 解析 YAML → ExperimentConfig（包含 orchestration.strategy="sequential_then_synthesize"）
   └─ build_graph_from_config(config, llm_client, tracer_factory)

2. build_graph_from_config() [pipeline/builder.py]
   ├─ _build_agents(config)
   │   └─ 遍历 config.agents ["pulmonologist", "radiologist", "moderator"]
   │       → get_agent_class(name) → 实例化 → agents dict
   ├─ get_protocol_class("blackboard") → BlackboardProtocol 实例
   └─ get_orchestration_class("sequential_then_synthesize")
       → SequentialThenSynthesize(parameters={specialists: [...], synthesizer: "moderator"})
       → orchestration.build_graph(agents, protocol, llm_client, tracer_factory)

3. SequentialThenSynthesize.build_graph() [orchestration/sequential.py]
   ├─ 从 self.parameters 取出 specialists / synthesizer
   ├─ 创建 StateGraph(GraphState)
   ├─ 节点 1 "specialist_analysis"：
   │   └─ make_node_function([pulmonologist, radiologist], protocol, ...)
   │       → 返回一个闭包函数 node_fn(state) → 调用 agent.execute() + 写回 state
   ├─ 节点 2 "final_synthesis"：
   │   └─ make_node_function([moderator], protocol, ...)
   ├─ 连线：START → specialist_analysis → final_synthesis → END
   └─ graph.compile() → CompiledGraph

4. 运行病例时：
   compiled_graph.invoke({"case_id": "...", "case_text": "...", ...})
   ├─ specialist_analysis 节点执行
   │   ├─ pulmonologist.execute(state, protocol, llm_client) → AgentOutput
   │   ├─ radiologist.execute(state, protocol, llm_client) → AgentOutput
   │   └─ 两者的输出追加到 state["agent_outputs"]
   └─ final_synthesis 节点执行
       ├─ moderator.execute(state, protocol, llm_client) → AgentOutput
       └─ 综合诊断追加到 state["agent_outputs"]
```

## 自助修改指南

### 新增一种编排策略

假设你要实现一个"多轮辩论"编排策略：

1. 创建 `src/orchestration/debate.py`
2. 继承 `BaseOrchestration`，用 `@register_orchestration("multi_round_debate")` 装饰
3. 实现 `build_graph()` 方法——在其中用 LangGraph API 构建辩论拓扑
4. 在 `src/pipeline/builder.py` 添加 `import src.orchestration.debate  # noqa: F401`（确保注册）
5. 在 YAML 中引用：

```yaml
orchestration:
  strategy: "multi_round_debate"
  parameters:
    rounds: 3
    debaters: ["pulmonologist", "radiologist"]
    judge: "moderator"
```

**不需要**改动 builder.py 的逻辑、ExperimentConfig schema、或任何其他编排策略。

### 修改现有策略的行为

比如让 `sequential_then_synthesize` 支持多轮 specialist 分析：
- 编辑 `src/orchestration/sequential.py`
- 在 `build_graph()` 中读取 `self.parameters.get("rounds", 1)` 并据此构建循环图
- YAML 中添加 `parameters.rounds: 2`

### 关键注意事项

- **每个编排策略都是完全自包含的**：它自己决定图有几个节点、怎么连线，不依赖外部配置
- **parameters 是自由格式的 dict**：每个策略定义自己需要什么参数，在 `build_graph()` 中通过 `self.parameters` 访问
- **策略不直接创建 agent**：agent 的实例化由 `builder.py` 的 `_build_agents()` 完成，策略只接收已实例化的 agent dict
- **注册触发**：新策略必须在某处被 `import`，否则装饰器不会执行。当前的触发点在 `builder.py` 中

## 验证方法

```bash
conda activate MDTAgent
python -m pytest tests/ -v
```

期望输出：29 个测试全部通过。

如果报错 `KeyError: "Orchestration 'xxx' 未注册"`：
- 检查是否在 `pipeline/builder.py` 中 import 了对应的策略模块
- 检查 `@register_orchestration("xxx")` 装饰器名是否与 YAML 中 `strategy:` 一致

如果报错 `KeyError` 缺少某个 agent：
- 检查 YAML `agents:` 列表是否包含了 `orchestration.parameters` 中引用的所有 agent 名

## 概念补充

### 策略模式（Strategy Pattern）

本次重构的核心设计模式。策略模式将算法的定义从使用者中分离出来：

- **Context**（使用者）：`builder.py` 的 `build_graph_from_config`——它不知道具体的编排逻辑
- **Strategy**（策略接口）：`BaseOrchestration` 抽象基类——定义了 `build_graph()` 接口
- **ConcreteStrategy**（具体策略）：`SequentialThenSynthesize`——实现了具体的图拓扑

好处：新增编排方式只需新增一个 ConcreteStrategy，不需要修改 Context。

### 依赖注入

`build_graph()` 方法接收 `agents`、`protocol`、`llm_client`、`tracer_factory` 四个参数，而不是自己创建它们。这些依赖由 `builder.py` 创建并注入，实现了编排策略与资源管理的解耦。

### StateGraph vs CompiledGraph（LangGraph）

- `StateGraph`：可变的图构建器，支持 `add_node()`、`add_edge()` 等操作
- `graph.compile()`：将 StateGraph "编译"为不可变的 `CompiledGraph`，只有编译后才能 `.invoke()` 执行
- `START` 和 `END`：LangGraph 的特殊节点常量，表示图的入口和出口

### noqa: F401 注释

```python
import src.orchestration.sequential  # noqa: F401
```

这个 import 的**唯一目的**是触发模块加载 → 触发 `@register_orchestration` 装饰器。不使用这个模块的任何导出对象。`# noqa: F401` 告诉 lint 工具"我知道这个 import 没有被显式使用，这是故意的"。

### 为什么 parameters 是 dict 而不是 Pydantic 模型

每种编排策略需要不同的参数（specialist 列表、rounds 数、debaters 等），如果用 Pydantic 模型就需要为每种策略定义一个 schema，这会让 `ExperimentConfig` 与具体策略耦合。使用 `dict` 保持灵活性，参数验证的责任留给策略的 `build_graph()` 实现。

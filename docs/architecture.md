# 代码架构与核心机制详解

> 目标读者：对本项目代码不熟悉，但需要修改、扩展它的研究者。
> 本文不讲"怎么跑"（那是使用指南的事），只讲"代码为什么这么写，改的时候该改哪里"。

---

## 目录

1. [总体思路：一句话理解整个项目](#1-总体思路)
2. [数据流全景：一个病例走完的完整路径](#2-数据流全景)
3. [核心机制一：抽象接口（ABC）—— 你只需要"填空"](#3-抽象接口abc)
4. [核心机制二：注册表（Registry Pattern）—— 让配置找到你的代码](#4-注册表registry-pattern)
5. [核心机制三：Trace 追踪框架 —— 自动记录一切](#5-trace-追踪框架)
6. [核心机制四：LangGraph 状态图 —— 流程编排的引擎](#6-langgraph-状态图)
7. [核心机制五：通信协议 —— agent 之间怎么传话](#7-通信协议)
8. [核心机制六：Prompt 模板 —— 用文件而不是代码写提示词](#8-prompt-模板)
9. [核心机制七：LLM 缓存 —— 省钱 + 可复现](#9-llm-缓存)
10. [实际动手：添加一个新 agent 的完整步骤](#10-添加一个新-agent)
11. [实际动手：添加一种新的冲突检测策略](#11-添加冲突检测策略)
12. [实际动手：添加一种新的通信协议](#12-添加通信协议)
13. [文件地图：每个文件是干什么的](#13-文件地图)

---

## 1. 总体思路

这个项目的核心理念只有一条：**换一个 YAML 配置文件 = 换一个实验，不改任何代码。**

为了做到这一点，代码被分成了两层：

```
┌───────────────────────────────────────────┐
│           框架层（你一般不需要改）            │
│  抽象接口、注册表、Pipeline Builder、Runner  │
│  Tracer、LLM Client、Cache                 │
└──────────────┬────────────────────────────┘
               │  通过"注册名"连接
┌──────────────▼────────────────────────────┐
│           策略层（你的研究工作在这里）         │
│  具体的 Agent 实现、通信协议、冲突检测、      │
│  仲裁策略、评估指标……                       │
└───────────────────────────────────────────┘
```

**框架层**提供了一堆"空槽"（抽象接口），你的任务就是往这些空槽里**填入具体实现**，然后在 YAML 配置里引用它们的注册名。

---

## 2. 数据流全景

当你运行一个实验时，数据是这样流动的：

```
YAML 配置文件
    │
    ▼
ExperimentRunner.run()
    │
    ├── 1. 解析 YAML → ExperimentConfig（Pydantic 模型）
    ├── 2. 加载病例数据（JSONL → CaseData 对象列表）
    ├── 3. 构建 Pipeline（配置 → LangGraph 编译后的图）
    │       ├── 实例化所有 Agent（从注册表查找类 → 传入配置）
    │       ├── 实例化通信协议（从注册表查找）
    │       └── 用 LangGraph StateGraph 把它们连成图
    │
    └── 4. 逐个病例运行：
            │
            ├── 创建 Tracer（追踪器）
            ├── 构建初始 State（放入 case_text）
            ├── graph.invoke(state)  ← LangGraph 开始执行
            │       │
            │       │  对每个节点：
            │       ├── 通信协议.prepare_input() → 从 state 提取输入
            │       ├── agent.execute(input, context) → 调用 LLM
            │       │       └── LLMClient.chat() → 查缓存 / 调 API
            │       └── 通信协议.process_output() → 输出写回 state
            │
            ├── 提取最终输出
            └── 保存 trace + 原始输出到文件
```

**关键理解**：整个流程中，你写的"策略代码"（Agent、Protocol 等）只需要实现几个方法，剩下的调度、追踪、缓存、保存全部由框架自动完成。

---

## 3. 抽象接口（ABC）

### 什么是 ABC

ABC = Abstract Base Class（抽象基类）。可以把它理解为一份"合同"或"模板"：

- 它规定了"你必须实现哪些方法"
- 但**不规定这些方法具体怎么做**
- 如果你忘了实现某个方法，Python 会在你创建对象时直接报错

### 本项目的 ABC 清单

| ABC 类名 | 在哪个文件 | 你必须实现的方法 | 干什么的 |
|-----------|-----------|-----------------|---------|
| `BaseAgent` | `src/agents/base.py` | `execute(input_data, context)` | 接收输入、调用 LLM、返回分析结果 |
| `CommunicationProtocol` | `src/communication/base.py` | `prepare_input(agent_id, state)` 和 `process_output(agent_id, output, state)` | 控制 agent 之间信息怎么传递 |
| `ConflictDetector` | `src/conflict/detection.py` | `detect(agent_outputs, context)` | 检测 agent 之间的意见冲突 |
| `ArbitrationStrategy` | `src/conflict/arbitration.py` | `arbitrate(conflicts, agent_outputs, context)` | 当有冲突时做出最终裁决 |
| `BaseMetric` | `src/evaluation/metrics.py` | `compute(results)` | 计算评估指标 |

### 举个例子

`BaseAgent` 长这样：

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str, config: dict | None = None):
        self.agent_id = agent_id
        self.config = config or {}

    @abstractmethod   # ← 这个标记表示"子类必须实现这个方法"
    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
        ...
```

你要做的就是**继承它，然后填写 `execute` 方法**。框架会在适当的时候自动调用你的 `execute`。

### 为什么用 ABC 而不是直接写函数

因为这个项目的核心是**对比实验**。同一个"位置"（比如"影像科医生"这个角色），你可能要尝试 3 种不同的实现来对比。ABC 确保所有实现都遵守同一个接口，这样它们可以**无缝替换**——你只需要在 YAML 配置里改一个名字。

---

## 4. 注册表（Registry Pattern）

### 问题：配置文件怎么找到你的代码？

YAML 配置里写的是字符串名字（如 `type: "llm_agent"`），而 Python 里用的是类。需要一个机制把**名字**和**类**对应起来。这就是注册表。

### 它是怎么工作的

```python
# 第一步：在你写的类上面加一个装饰器
@register_agent("llm_agent")   # ← "llm_agent" 就是注册名
class LLMAgent(BaseAgent):
    def execute(self, input_data, context):
        ...

# 第二步：上面这行代码一执行，全局字典里就多了一条：
#   AGENT_REGISTRY["llm_agent"] = LLMAgent

# 第三步：框架读到 YAML 里的 type: "llm_agent" 时，就去字典里查：
#   cls = AGENT_REGISTRY["llm_agent"]  → 拿到 LLMAgent 这个类
#   agent = cls(agent_id="...", config={...})  → 创建实例
```

### 装饰器是什么？

如果你不熟悉 `@` 装饰器语法，可以理解为：

```python
# 这两种写法是完全等价的：

# 写法一（装饰器）：
@register_agent("my_agent")
class MyAgent(BaseAgent):
    ...

# 写法二（手动调用）：
class MyAgent(BaseAgent):
    ...
MyAgent = register_agent("my_agent")(MyAgent)
```

装饰器只是一个"在类定义后立刻执行的函数"。在这里，它的作用就是把你的类塞进全局字典。

### 本项目的注册表清单

| 注册表名 | 装饰器 | YAML 配置字段 | 当前已注册的实现 |
|----------|--------|-------------|----------------|
| `AGENT_REGISTRY` | `@register_agent("名字")` | `agents[].type` | `llm_agent` |
| `PROTOCOL_REGISTRY` | `@register_protocol("名字")` | `communication.protocol` | `blackboard` |
| `DETECTOR_REGISTRY` | `@register_detector("名字")` | `conflict.detection.strategy` | *(空，待你实现)* |
| `ARBITRATION_REGISTRY` | `@register_arbitration("名字")` | `conflict.arbitration.strategy` | *(空，待你实现)* |
| `METRIC_REGISTRY` | `@register_metric("名字")` | `evaluation.metrics[]` | *(空，待你实现)* |
| `CONDITION_REGISTRY` | `@register_condition("名字")` | `pipeline.conditional_edges[].condition` | *(空，待你实现)* |

### 重要规则

1. **注册名必须唯一**。重复注册会报错。
2. **被装饰的类所在的模块必须被 import 过**，装饰器才会执行。如果你新建了一个文件写了新 agent，但没有在任何地方 `import` 它，注册表里不会有它。框架在 `builder.py` 和 `runner.py` 中已经自动 import 了 `llm_agent` 和 `blackboard`。你新增实现时需要类似地确保 import。

---

## 5. Trace 追踪框架

### 为什么需要追踪

这是研究平台，你需要知道**每一步发生了什么**：

- agent 收到了什么输入？
- 发给 LLM 的 prompt 长什么样？
- LLM 返回了什么？
- 花了多少 token？多少时间？
- 用的缓存还是真实调用？

### 追踪的层级结构

```
PipelineTrace（一个病例的完整追踪）
├── case_id, experiment_name
├── start_time, end_time
├── total_token_usage（所有 LLM 调用的 token 汇总）
├── node_execution_order（节点执行顺序）
│
├── agent_traces[]（每个 agent 的追踪）
│   ├── agent_id, node_id
│   ├── input_data（这个 agent 收到的输入）
│   ├── output_content（这个 agent 的输出）
│   ├── llm_calls[]（这个 agent 做的 LLM 调用）
│   │   ├── model, messages（发出去的完整 prompt）
│   │   ├── response（LLM 的原始响应）
│   │   ├── token_usage, latency_ms
│   │   └── cached（是否命中缓存）
│   ├── start_time, end_time
│   └── error（如果出错了）
│
├── message_traces[]（agent 间的消息记录）
│   ├── from_agent, to_agent, content, timestamp
│
└── conflict_trace（冲突检测与仲裁记录）
    ├── conflicts_detected[]
    ├── arbitration_steps[]
    └── final_decision
```

### 你不需要手动记录追踪

框架在 `nodes.py` 的 `_execute_single_agent()` 中自动完成追踪：

```
agent 执行前 → tracer.start_agent()  自动记录开始时间和输入
agent 执行后 → tracer.finish_agent() 自动记录结束时间、输出、LLM 调用
```

你写 agent 实现时**不需要管追踪的事**。只需要正常返回 `AgentOutput`，里面的 `llm_calls` 字段会被框架自动收集。

### 追踪数据保存在哪里

每次实验运行后，追踪保存为 JSON 文件：

```
results/{实验名}_{时间戳}/
    traces/
        demo_001.json   ← 第一个病例的完整追踪
        demo_002.json   ← 第二个病例的完整追踪
```

你可以在 Jupyter Notebook 中加载这些 JSON 做分析。

---

## 6. LangGraph 状态图

### 你需要知道的最少知识

LangGraph 是流程编排引擎。你可以把它想象成一张"流程图"：

```
START → [specialist_analysis] → [final_synthesis] → END
```

- 每个方括号 `[]` 是一个**节点**（node），对应一个或多个 agent
- 箭头 `→` 是**边**（edge），表示执行顺序
- 整个图共享一个**状态**（State），节点通过读写状态来交换信息

### State 是什么

State 就是一个大字典，在节点之间传递。它的结构定义在 `src/schemas/state.py`：

```python
class GraphState(TypedDict, total=False):
    case_text: str                  # 病例文本（只读）
    case_id: str                    # 病例 ID（只读）
    agent_outputs: dict[str, Any]   # 所有 agent 的输出（可追加）
    agent_traces: list[AgentTrace]  # 追踪记录（可追加）
    conflicts: list[...]            # 冲突检测结果
    final_output: str               # 最终诊断输出
```

### Reducer 是什么

当多个节点同时往 state 写数据时，需要规则来"合并"。这就是 reducer：

- `agent_outputs` 用 `_merge_dict`：新输出和已有输出合并成一个字典
- `agent_traces` 用 `_append_list`：新追踪追加到已有列表末尾

**你一般不需要改 reducer。** 只有当你改变了 state 的结构时才需要动它。

### Pipeline 是怎么从 YAML 变成图的

`src/pipeline/builder.py` 中的 `build_graph_from_config()` 函数做这件事：

1. 读 YAML 中的 `pipeline.nodes` → 为每个节点创建节点函数
2. 读 YAML 中的 `pipeline.edges` → 添加边（`START`/`END` 是特殊名字）
3. 读 YAML 中的 `pipeline.conditional_edges` → 添加条件路由
4. 编译 → 返回可执行的图

**你一般不需要改 builder。** 你要做的只是在 YAML 里定义新的拓扑结构。

---

## 7. 通信协议

### 问题：agent 之间怎么"看到"彼此的输出？

答案：通过通信协议。协议的两个方法控制了信息流：

```
prepare_input(agent_id, state)  → 从 state 中取出哪些信息给这个 agent
process_output(agent_id, output, state) → 把这个 agent 的输出怎么写回 state
```

### 当前的 Blackboard 协议

最简单的策略——**所有人看到所有人的输出**：

```python
def prepare_input(self, agent_id, state):
    return {
        "case_text": state["case_text"],         # 病例文本
        "agent_outputs": state["agent_outputs"],  # 所有其他 agent 的输出
    }
```

### 为什么要抽象成协议

因为"谁能看到谁的输出"本身就是研究变量。你可能要对比：

- **全共享**（blackboard）：所有 agent 看到所有输出
- **定向传递**：影像科只能看到呼吸科的输出，看不到病理科的
- **结构化通信**：不传递原始文本，而是传递标准化的 claim-evidence 对
- **无通信**：每个 agent 独立分析，互相看不到

每种方式都是一个新的 `CommunicationProtocol` 子类，注册一个名字，YAML 里切换就行。

---

## 8. Prompt 模板

### 为什么 prompt 不写在代码里

因为 prompt 是你最频繁修改的东西。如果写在 `.py` 文件里，每次改 prompt 都要碰代码。把 prompt 放在独立的 `.md` 文件中：

- 改 prompt **不会**触发代码变更
- 不同实验可以用**不同版本**的 prompt（`v1/`, `v2/`...）
- 可以 A/B 对比 prompt 设计的效果

### 模板变量

Prompt 文件中用 `$variable` 表示占位符：

```markdown
## Patient Case
$case_text

## Prior Analyses
$prior_analyses
```

运行时，框架会把 `$case_text` 替换成真实的病例文本。

### 变量从哪里来

在 `LLMAgent._build_messages()` 中：

```python
template_vars = {
    "case_text": input_data["case_text"],       # ← 来自通信协议的 prepare_input
    "prior_analyses": "...",                     # ← 来自其他 agent 的输出
}
system_prompt = self._prompt_loader.load(template_path, **template_vars)
```

如果你需要更多变量，在 `_build_messages()` 中往 `template_vars` 里加就行。

---

## 9. LLM 缓存

### 机制

`LLMCache` 用 `(model, messages, temperature)` 的组合计算 SHA-256 哈希值，作为文件名存储响应。

```
相同的输入 → 相同的哈希 → 直接读文件返回 → 不调 API → 不花钱
```

### 缓存文件在哪

项目根目录的 `.llm_cache/` 文件夹（已加 `.gitignore`）。

### 什么时候需要清缓存

- **改了 prompt 模板**：prompt 变了 → messages 变了 → 哈希变了 → 自动 miss，不需要手动清
- **想让同一个 prompt 重新跑一遍**（如 temperature > 0 时想要不同结果）：删掉 `.llm_cache/` 文件夹即可

---

## 10. 添加一个新 Agent

假设你要添加一个"病理科医生"agent：

### 步骤 1：写 prompt 模板

创建文件 `configs/prompts/v1/pathologist_analysis.md`：

```markdown
You are an experienced pathologist participating in an ILD-MDT discussion.

## Patient Case
$case_text

## Instructions
Analyze the pathology findings...
```

### 步骤 2（可选）：写自定义 agent 类

如果 `LLMAgent` 的行为就够用（从 prompt 加载 → 调 LLM → 返回文本），你**不需要写任何代码**，直接在 YAML 里用 `type: "llm_agent"` 并指定新 prompt 文件即可。

如果你需要不同的行为（比如要求 JSON 输出并解析），才需要新建文件：

```python
# src/agents/pathologist_agent.py

from src.agents.base import AgentContext, AgentOutput, BaseAgent
from src.agents.registry import register_agent

@register_agent("pathologist_v2")   # ← 注册名
class PathologistAgent(BaseAgent):
    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
        # 你的自定义逻辑
        ...
        return AgentOutput(content="...", llm_calls=[...])
```

然后确保这个文件被 import。在 `src/runner.py` 顶部加一行：

```python
import src.agents.pathologist_agent  # noqa: F401
```

### 步骤 3：在 YAML 配置中引用

```yaml
agents:
  # ...已有的 agent...
  - id: "pathologist"
    type: "llm_agent"    # 或你自定义的 "pathologist_v2"
    prompt_template: "configs/prompts/v1/pathologist_analysis.md"
    model: "gpt-4o"
    temperature: 0.3

pipeline:
  nodes:
    - id: "specialist_analysis"
      agents: ["pulmonologist", "radiologist", "pathologist"]  # ← 加到节点里
```

完成。不需要改框架代码。

---

## 11. 添加冲突检测策略

### 步骤 1：创建策略文件

```python
# src/conflict/llm_detector.py

from src.agents.base import AgentOutput
from src.conflict.detection import (
    Conflict, ConflictDetector, DetectionContext, register_detector,
)

@register_detector("llm_based")    # ← 注册名，对应 YAML 中 conflict.detection.strategy
class LLMConflictDetector(ConflictDetector):
    def detect(self, agent_outputs: dict[str, AgentOutput],
               context: DetectionContext) -> list[Conflict]:
        # 你的冲突检测逻辑
        # - 比较各 agent 的输出
        # - 用 LLM 判断是否存在冲突
        # - 返回 Conflict 对象列表
        ...
```

### 步骤 2：确保 import

在 `builder.py` 或 `runner.py` 中加 import。

### 步骤 3：YAML 中启用

```yaml
conflict:
  detection:
    strategy: "llm_based"
    parameters:
      threshold: 0.5
```

---

## 12. 添加通信协议

同理，继承 `CommunicationProtocol`，实现两个方法，用装饰器注册，YAML 里引用。

```python
# src/communication/directed.py

from src.communication.base import CommunicationProtocol, register_protocol

@register_protocol("directed")
class DirectedProtocol(CommunicationProtocol):
    def prepare_input(self, agent_id, state):
        # 根据 self.parameters 中定义的规则，只传递部分 agent 的输出
        ...

    def process_output(self, agent_id, output, state):
        ...
```

---

## 13. 文件地图

```
src/
├── schemas/                 ← 📦 数据结构定义（一般不需要改）
│   ├── case.py             ← 病例数据模型 (CaseData, GroundTruth)
│   ├── experiment.py       ← YAML 配置的 Pydantic 模型 (ExperimentConfig)
│   ├── state.py            ← LangGraph 运行时状态 (GraphState + reducers)
│   ├── trace.py            ← 追踪数据结构 (LLMCallTrace, AgentTrace, PipelineTrace)
│   └── results.py          ← 实验结果结构 (CaseResult, ExperimentResult)
│
├── agents/                  ← 🤖 Agent 相关
│   ├── base.py             ← Agent 抽象接口 (BaseAgent ABC)
│   ├── registry.py         ← Agent 注册表
│   └── llm_agent.py        ← ⭐ LLM Agent 参考实现（你最常改的文件之一）
│
├── communication/           ← 📡 通信协议
│   ├── base.py             ← 通信协议抽象接口 + 注册表
│   └── blackboard.py       ← ⭐ Blackboard 协议参考实现
│
├── conflict/                ← ⚔️ 冲突检测与仲裁
│   ├── detection.py        ← 冲突检测抽象接口 + 注册表（待你实现具体策略）
│   └── arbitration.py      ← 仲裁策略抽象接口 + 注册表（待你实现具体策略）
│
├── pipeline/                ← 🔧 流程编排（一般不需要改）
│   ├── builder.py          ← 从 YAML 配置构建 LangGraph 图
│   └── nodes.py            ← 将 Agent 包装为 LangGraph 节点
│
├── llm/                     ← 🧠 LLM 调用相关（一般不需要改）
│   ├── client.py           ← LLM 客户端（OpenAI 兼容接口）
│   ├── cache.py            ← 响应缓存（基于文件哈希）
│   └── prompt_loader.py    ← Prompt 模板加载器
│
├── tracing/                 ← 📊 追踪（一般不需要改）
│   ├── tracer.py           ← Tracer 类
│   └── cost.py             ← Token 成本追踪（待实现）
│
├── evaluation/              ← 📏 评估
│   ├── metrics.py          ← 评估指标抽象接口 + 注册表（待你实现具体指标）
│   └── comparator.py       ← 多实验对比工具（待实现）
│
└── runner.py                ← 🚀 实验运行器入口

configs/
├── experiments/             ← 实验配置 YAML（每个文件 = 一个实验）
└── prompts/v1/             ← ⭐ Prompt 模板文件（你最常改的目录）

data/
├── cases/                  ← 病例数据 (JSONL)
└── ground_truth/           ← 金标准标注 (JSONL)
```

标 ⭐ 的是你日常研究中**最频繁修改**的文件/目录。标"待你实现"的是预留给后续研究的空接口。

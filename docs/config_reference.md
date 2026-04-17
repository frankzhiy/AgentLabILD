# 实验配置速查手册

> 每个 YAML 文件 = 一个实验。本文逐字段解释 YAML 配置文件的含义，并给出常用配置模板。

---

## 目录

1. [完整字段一览](#1-完整字段一览)
2. [各段详解](#2-各段详解)
3. [常用配置模板](#3-常用配置模板)

---

## 1. 完整字段一览

```yaml
experiment:
  name: str              # 实验名（必填），用于结果目录命名
  description: str       # 实验描述（可选）
  seed: int              # 随机种子（默认 42）

data:
  cases: str             # 病例数据 JSONL 路径（必填）
  ground_truth: str      # 金标准标注 JSONL 路径（可选）

agents:                  # Agent 列表（必填，至少 1 个）
  - id: str              # Agent 唯一 ID（必填），pipeline 中用这个名字引用
    type: str            # 注册的 agent 类型名（必填），如 "llm_agent"
    prompt_template: str # Prompt 模板 .md 文件路径（必填）
    model: str           # LLM 模型名（默认 "gpt-4o"）
    temperature: float   # 采样温度 0.0~2.0（默认 0.3）
    parameters: dict     # 额外参数（默认 {}），透传给 agent 实现

pipeline:
  nodes:                 # 节点列表（必填）
    - id: str            # 节点 ID（必填）
      agents: [str]      # 属于此节点的 agent ID 列表（必填）

  edges:                 # 固定边列表（必填）
    - from: str          # 起点节点 ID，"START" = 流程入口
      to: str            # 终点节点 ID，"END" = 流程结束

  conditional_edges:     # 条件路由边列表（可选，默认 []）
    - from: str          # 起点节点 ID
      condition: str     # 注册的条件函数名
      true_target: str   # 条件为真时跳转的节点 ID
      false_target: str  # 条件为假时跳转的节点 ID

communication:
  protocol: str          # 注册的通信协议名（默认 "blackboard"）
  parameters: dict       # 传给协议的参数（默认 {}）

conflict:
  detection:
    strategy: str        # 注册的冲突检测策略名（默认 "none" = 不检测）
    parameters: dict     # 传给检测策略的参数（默认 {}）
  arbitration:
    strategy: str        # 注册的仲裁策略名（默认 "none" = 不仲裁）
    parameters: dict     # 传给仲裁策略的参数（默认 {}）

evaluation:
  metrics: [str]         # 注册的评估指标名列表（默认 []）

tracking:
  save_full_traces: bool      # 是否保存完整追踪（默认 true）
  save_token_usage: bool      # 是否保存 token 统计（默认 true）
  cache_llm_responses: bool   # 是否启用 LLM 缓存（默认 true）
```

---

## 2. 各段详解

### experiment（实验元信息）

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `name` | string | 必填 | 实验名称。会用作结果目录名前缀（`results/{name}_{时间戳}/`），建议用英文 + 下划线 |
| `description` | string | 可选 | 对实验的描述，纯记录用途，不影响运行 |
| `seed` | int | 可选 | 随机种子，默认 42。用于控制可复现性（注意：LLM API 本身不完全可控） |

### data（数据源）

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `cases` | string | 必填 | 病例数据 JSONL 文件路径。相对于项目根目录。每行一个 JSON 对象 |
| `ground_truth` | string | 可选 | 金标准标注 JSONL 路径。用于后续评估。不提供则跳过 ground truth 加载 |

**JSONL 格式示例**：

病例数据（每行必须有 `case_id`，其余字段可选）：
```json
{"case_id": "case_001", "age": 65, "gender": "male", "chief_complaint": "..."}
```

金标准（必须有 `case_id` 和 `diagnosis`）：
```json
{"case_id": "case_001", "diagnosis": "IPF", "confidence": "high"}
```

### agents（Agent 定义）

这是一个列表，每个元素定义一个 agent 参会者。

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `id` | string | 必填 | Agent 的唯一标识。在 `pipeline.nodes[].agents` 中用这个名字引用它 |
| `type` | string | 必填 | 注册表中的类型名。目前可用：`"llm_agent"`。你自己注册的 agent 也用这个字段引用 |
| `prompt_template` | string | 必填 | Prompt 模板文件路径（Markdown 格式），相对于项目根目录 |
| `model` | string | 可选 | 要调用的 LLM 模型名。默认 `"gpt-4o"`。如用 DeepSeek 填 `"deepseek-chat"`，其他类推 |
| `temperature` | float | 可选 | 采样温度，范围 0.0~2.0，默认 0.3。越低越确定性，越高越随机 |
| `parameters` | dict | 可选 | 额外参数字典，会透传给 agent 实现。当前 `llm_agent` 不使用它，但你的自定义 agent 可以读取 |

### pipeline（流程拓扑）

#### nodes — 节点定义

每个节点可以包含**一个或多个** agent。同一节点内的多个 agent 会顺序执行（当前实现），未来可能改为并行。

```yaml
nodes:
  - id: "specialist_analysis"
    agents: ["pulmonologist", "radiologist"]   # 两个 agent 在同一节点
  - id: "final_synthesis"
    agents: ["moderator"]                      # 一个 agent 单独一个节点
```

#### edges — 固定边

定义节点之间的执行顺序。使用 `"START"` 和 `"END"` 作为特殊节点名。

```yaml
edges:
  - from: "START"                 # 从流程开始
    to: "specialist_analysis"     # 到第一个节点
  - from: "specialist_analysis"
    to: "final_synthesis"         # 然后到下一个节点
  - from: "final_synthesis"
    to: "END"                     # 最后结束
```

> **重要**：至少要有一条从 `START` 出发的边和一条到 `END` 的边，否则图无法执行。

#### conditional_edges — 条件路由（高级）

用于根据当前状态决定下一步去哪个节点。需要提前在代码中注册条件函数（`@register_condition("名字")`）。

```yaml
conditional_edges:
  - from: "conflict_check"
    condition: "has_conflict"     # 注册的条件函数名
    true_target: "debate_round"  # 有冲突 → 进入辩论
    false_target: "END"          # 无冲突 → 结束
```

当前没有预注册的条件函数，这是为后续研究预留的。

### communication（通信协议）

| 字段 | 类型 | 是否必填 | 说明 |
|------|------|---------|------|
| `protocol` | string | 可选 | 注册的通信协议名。默认 `"blackboard"`（全共享） |
| `parameters` | dict | 可选 | 传给协议实现的参数。`blackboard` 不需要参数 |

### conflict（冲突检测与仲裁）

当两个子段的 `strategy` 都设为 `"none"` 时，表示不执行冲突检测和仲裁。

要启用冲突机制，需要：
1. 先实现并注册对应策略（继承 ABC + `@register_detector` / `@register_arbitration`）
2. 在配置中填上策略名

### evaluation（评估）

`metrics` 是一个字符串列表，每个元素是注册的评估指标名。当前没有预注册的指标，留给后续实现。

### tracking（追踪与缓存控制）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `save_full_traces` | bool | `true` | 是否为每个病例保存完整追踪 JSON |
| `save_token_usage` | bool | `true` | 是否追踪 token 使用量 |
| `cache_llm_responses` | bool | `true` | 是否启用 LLM 缓存。开启后相同输入不会重复调 API |

> **建议**：除非你在调试缓存相关问题，否则始终开启这三个选项。

---

## 3. 常用配置模板

### 模板 A：最简单的 2-agent 实验

```yaml
experiment:
  name: "minimal_2agent"
  description: "最简实验：1 个分析 + 1 个综合"

data:
  cases: "data/cases/demo_2cases.jsonl"

agents:
  - id: "analyst"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/pulmonologist_analysis.md"
    model: "gpt-4o"
    temperature: 0.3
    parameters: {}

  - id: "synthesizer"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/moderator_synthesis.md"
    model: "gpt-4o"
    temperature: 0.2
    parameters: {}

pipeline:
  nodes:
    - id: "analysis"
      agents: ["analyst"]
    - id: "synthesis"
      agents: ["synthesizer"]
  edges:
    - from: "START"
      to: "analysis"
    - from: "analysis"
      to: "synthesis"
    - from: "synthesis"
      to: "END"
```

### 模板 B：4-agent MDT 完整团队

```yaml
experiment:
  name: "full_mdt_4agent"
  description: "完整 MDT：呼吸科 + 影像科 + 风湿免疫科 + 主持人"

data:
  cases: "data/cases/demo_2cases.jsonl"
  ground_truth: "data/ground_truth/demo_2cases_labels.jsonl"

agents:
  - id: "pulmonologist"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/pulmonologist_analysis.md"
    model: "gpt-4o"
    temperature: 0.3
    parameters: {}

  - id: "radiologist"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/radiologist_analysis.md"
    model: "gpt-4o"
    temperature: 0.3
    parameters: {}

  - id: "rheumatologist"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/rheumatologist_analysis.md"  # 需要新建此模板
    model: "gpt-4o"
    temperature: 0.3
    parameters: {}

  - id: "moderator"
    type: "llm_agent"
    prompt_template: "configs/prompts/v1/moderator_synthesis.md"
    model: "gpt-4o"
    temperature: 0.2
    parameters: {}

pipeline:
  nodes:
    - id: "specialist_analysis"
      agents: ["pulmonologist", "radiologist", "rheumatologist"]
    - id: "final_synthesis"
      agents: ["moderator"]
  edges:
    - from: "START"
      to: "specialist_analysis"
    - from: "specialist_analysis"
      to: "final_synthesis"
    - from: "final_synthesis"
      to: "END"
```

### 模板 C：两轮讨论（分析 → 综合 → 复核）

```yaml
pipeline:
  nodes:
    - id: "round1_analysis"
      agents: ["pulmonologist", "radiologist"]
    - id: "round1_synthesis"
      agents: ["moderator"]
    - id: "round2_review"
      agents: ["pulmonologist", "radiologist"]
    - id: "final_synthesis"
      agents: ["moderator"]
  edges:
    - from: "START"
      to: "round1_analysis"
    - from: "round1_analysis"
      to: "round1_synthesis"
    - from: "round1_synthesis"
      to: "round2_review"
    - from: "round2_review"
      to: "final_synthesis"
    - from: "final_synthesis"
      to: "END"
```

> **注意**：第二轮中的 agent 会通过 blackboard 协议看到第一轮所有人的输出（包括 moderator 的综合意见），因此它们可以做更精准的二次分析。

### 模板 D：模型对比实验

只改模型名称和 temperature，其他保持不变——快速对比不同 LLM 的效果：

```yaml
# experiment_gpt4o.yaml
agents:
  - id: "pulmonologist"
    model: "gpt-4o"
    # ...其他一样

# experiment_deepseek.yaml
agents:
  - id: "pulmonologist"
    model: "deepseek-chat"
    # ...其他一样

# experiment_qwen.yaml
agents:
  - id: "pulmonologist"
    model: "qwen-plus"
    # ...其他一样
```

分别运行三次，在 `results/` 下对比输出。

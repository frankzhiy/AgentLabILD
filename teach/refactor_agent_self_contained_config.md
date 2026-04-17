# 教学文档：Agent 架构重构 —— 从 YAML 配置驱动到 .py 文件自包含

## 任务描述

将 agent 系统从"YAML 中心化配置 + 通用 LLMAgent 类"重构为"每个 agent 独立 .py 文件 + 自包含配置"模式。

---

## 1. 分析路径

重构涉及的核心问题：agent 的配置（model、temperature、prompt_template）原来放在 YAML 里，现在需要移到每个 agent 自己的 .py 文件中。这意味着需要沿着数据流追踪所有涉及 agent 配置的位置：

1. **`configs/experiments/baseline_3agent.yaml`**：配置的起点，原来 agents 区块有 type/model/temperature 等
2. **`src/schemas/experiment.py`**：`AgentConfig` Pydantic 模型负责解析 YAML 中的 agent 配置
3. **`src/pipeline/builder.py`**：`_build_agents()` 函数读取 `AgentConfig` 实例化 agent
4. **`src/agents/llm_agent.py`**：原来是唯一注册的 agent 类（`@register_agent("llm_agent")`），所有角色复用它
5. **`src/runner.py`**：通过 import 触发 agent 注册
6. **`tests/`**：测试中内联构建的 YAML 配置也使用旧格式

---

## 2. 改动清单

### 重构前后对比

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| Agent 身份 | YAML 中的 `id` 字段 | .py 文件中 `@register_agent("名字")` |
| Agent 类型 | YAML 中的 `type: "llm_agent"` | 无此概念（注册名即为 agent 本身） |
| Model/Temperature | YAML 中配置 | .py 文件中 `AGENT_CONFIG` 常量 |
| Prompt 模板路径 | YAML 中配置 | .py 文件中 `AGENT_CONFIG` 常量 |
| LLMAgent 角色 | 直接注册的通用 agent | 不注册，作为基类被继承 |
| YAML agents 区 | `list[{id, type, model, ...}]` | `list[str]`（纯名字列表） |

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/agents/pulmonologist.py` | 呼吸科医生 agent，继承 LLMAgent |
| `src/agents/radiologist.py` | 影像科医生 agent，继承 LLMAgent |
| `src/agents/moderator.py` | MDT 主持人 agent，继承 LLMAgent |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/agents/llm_agent.py` | 移除 `@register_agent("llm_agent")`，改为纯基类 |
| `src/agents/case_analyst.py` | 改为继承 `LLMAgent`，添加 `AGENT_CONFIG` |
| `src/schemas/experiment.py` | 删除 `AgentConfig`，`agents` 改为 `list[str]` |
| `src/pipeline/builder.py` | `_build_agents()` 简化为按名字查注册表实例化 |
| `src/runner.py` | 更新 import：加 3 个新 agent，去掉 `llm_agent` |
| `src/agents/registry.py` | 文档示例更新 |
| `configs/experiments/baseline_3agent.yaml` | agents 区简化为纯列表 |
| `tests/test_pipeline_builder.py` | 按新格式更新 mock config |
| `tests/test_runner.py` | 按新格式更新 mock config |
| `tests/test_schemas.py` | 按新格式更新 config yaml 和断言 |

---

## 3. 连接原理

### 重构后的 agent 发现链路

```
runner.py 顶部
    → import src.agents.pulmonologist
    → 模块加载 → @register_agent("pulmonologist") 执行
    → AGENT_REGISTRY["pulmonologist"] = PulmonologistAgent

YAML 文件
    agents: ["pulmonologist", "radiologist", "moderator"]
    → ExperimentConfig.agents = ["pulmonologist", "radiologist", "moderator"]

_build_agents(config)
    → for agent_name in config.agents:        # 遍历字符串列表
    →   agent_cls = get_agent_class("pulmonologist")  # 从注册表查类
    →   agent = agent_cls(agent_id="pulmonologist")   # 实例化（不传 config）
    →     → PulmonologistAgent.__init__
    →       → merged = {**AGENT_CONFIG, **(config or {})}  # 合并自身配置
    →       → super().__init__(agent_id, merged)           # 传给 LLMAgent
```

### AGENT_CONFIG 的合并机制

```python
# 每个 agent 的 .py 文件中
AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/pulmonologist_analysis.md",
    "model": "gpt-4o",
    "temperature": 0.3,
}

class PulmonologistAgent(LLMAgent):
    def __init__(self, agent_id, config=None):
        merged = {**AGENT_CONFIG, **(config or {})}  # 外部传入的 config 可覆盖默认值
        super().__init__(agent_id, merged)
```

`{**AGENT_CONFIG, **(config or {})}` 的含义：
- 先展开 AGENT_CONFIG 的所有键值对
- 再展开 config 的键值对（如果有的话）
- 后者覆盖前者 → 外部可以覆盖默认配置

---

## 4. 运行时数据流

```
YAML:  agents: ["pulmonologist"]
         ↓
ExperimentConfig.agents = ["pulmonologist"]  （纯字符串列表）
         ↓
_build_agents():
  get_agent_class("pulmonologist") → PulmonologistAgent 类
  PulmonologistAgent(agent_id="pulmonologist")
    → 内部合并 AGENT_CONFIG → self.config = {model: "gpt-4o", temp: 0.3, ...}
         ↓
pipeline 节点调用 agent.execute(input_data, context)
  → self.config["model"]        → "gpt-4o"        （来自 AGENT_CONFIG）
  → self.config["temperature"]  → 0.3             （来自 AGENT_CONFIG）
  → self.config["prompt_template"] → "configs/..."  （来自 AGENT_CONFIG）
```

对比重构前的数据流：
```
重构前：YAML → AgentConfig(model="gpt-4o") → _build_agents() 拼 config dict → agent.config
重构后：.py 文件 AGENT_CONFIG → __init__ 合并 → agent.config
```

配置来源变了，但 agent 内部使用 `self.config["model"]` 的代码完全不变。

---

## 5. 自助修改指南

### 新增一个 agent

1. 在 `src/agents/` 下新建 .py 文件（如 `pathologist.py`）
2. 文件结构遵循模板：

```python
from src.agents.llm_agent import LLMAgent
from src.agents.registry import register_agent

AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/pathologist_analysis.md",
    "model": "gpt-4o",
    "temperature": 0.3,
}

@register_agent("pathologist")
class PathologistAgent(LLMAgent):
    def __init__(self, agent_id, config=None):
        merged = {**AGENT_CONFIG, **(config or {})}
        super().__init__(agent_id, merged)
```

3. 在 `configs/prompts/v1/` 下创建对应的 prompt 模板文件
4. 在 `src/runner.py` 顶部添加 `import src.agents.pathologist  # noqa: F401`
5. 在 YAML 的 `agents` 列表和 `pipeline.nodes` 中引用 `"pathologist"`

### 修改某个 agent 的模型或温度

直接编辑该 agent .py 文件中的 `AGENT_CONFIG`，不需要动 YAML。

### 让某个 agent 有自定义逻辑

在 agent 类中覆写 `_build_messages()` 或 `execute()` 方法。参考 `case_analyst.py` 的做法。

---

## 6. 验证方法

```bash
conda activate MDTAgent

# 跑全部测试
python -m pytest tests/ -v

# 验证 agent 注册
python -c "
from src.agents.registry import AGENT_REGISTRY
import src.agents.pulmonologist, src.agents.radiologist, src.agents.moderator, src.agents.case_analyst
print(list(AGENT_REGISTRY.keys()))
"

# 验证配置加载
python -c "
from src.runner import load_experiment_config
c = load_experiment_config('configs/experiments/baseline_3agent.yaml')
print(c.agents)  # 期望: ['pulmonologist', 'radiologist', 'moderator']
"
```

### 常见报错

- `KeyError: Agent 'xxx' 未注册`：忘了在 `runner.py` 里 import 新 agent 模块
- `ValidationError: agents ... str type expected`：YAML 中 agents 还是旧的 dict 格式，需要改成纯字符串列表

---

## 7. 概念补充

### 继承 vs 配置

重构前的方式是**配置驱动**：一个通用类 `LLMAgent`，通过外部配置（YAML）决定行为。
重构后的方式是**继承驱动**：每个角色是独立类，继承公共基类 `LLMAgent`，通过覆写方法决定行为。

两种方式各有优劣：
- 配置驱动：灵活，改配置不改代码；但所有角色共享一套逻辑，难以差异化
- 继承驱动：每个角色可独立演化；但新增角色需要写代码

本项目选择继承驱动，是因为研究场景中**每个 agent 很可能会有不同的逻辑**（如不同的消息构建、输出解析、多轮对话策略），配置驱动会越来越吃力。

### `{**dict1, **dict2}` 合并语法

Python dict 展开语法。`{**A, **B}` 创建一个新字典，先放 A 的所有键值对，再放 B 的。如果有同名 key，B 覆盖 A。这就是为什么 `{**AGENT_CONFIG, **(config or {})}` 可以让外部传入的 config 覆盖默认值。

### 测试中的 mock agent 注册模式

测试中不能直接用 `@register_agent("xxx")` 装饰一个类，因为多个测试文件可能注册同名 agent 导致冲突。所以用了 `if name not in AGENT_REGISTRY` 的守卫 + 闭包工厂函数 `_make_cls(name)` 的模式来安全地注册多个测试用 agent。

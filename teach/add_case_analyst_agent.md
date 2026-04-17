# 教学文档：新增 CaseAnalystAgent（病例解析 Agent）

## 任务描述

新增一个 `case_analyst` agent，将以自然段落输入的 ILD 病例文本解析为符合 `CaseData` schema 的结构化 JSON。

---

## 1. 分析路径

接到需求后，我的分析链路如下：

1. **`src/agents/base.py`**：先看 `BaseAgent` 抽象类的接口定义——`execute(input_data, context) → AgentOutput`，这是所有 agent 必须实现的接口
2. **`src/agents/llm_agent.py`**：参考现有 `LLMAgent` 的实现模式——如何加载 prompt、构建消息、调用 LLM、返回结果
3. **`src/agents/registry.py`**：了解注册机制——通过 `@register_agent("name")` 装饰器把类放入全局注册表
4. **`src/schemas/case.py`**：确认目标输出结构 `CaseData` 有哪些字段，以及它自带的 `model_json_schema()` 方法可以自动生成 JSON Schema
5. **`src/runner.py`**：发现 agent 注册靠的是在 runner 中显式 `import` 模块来触发装饰器，所以新 agent 也需要加一行导入
6. **`configs/prompts/v1/pulmonologist_analysis.md`**：参考已有 prompt 模板的风格和变量占位符语法（`$variable`）

---

## 2. 改动清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/agents/case_analyst.py` | CaseAnalystAgent 类实现 |
| `configs/prompts/v1/case_analyst_parsing.md` | 配套的 prompt 模板 |

### 修改文件

| 文件 | 改动 | 原因 |
|------|------|------|
| `src/runner.py` | 新增 `import src.agents.case_analyst` | 触发 `@register_agent` 装饰器完成注册 |

---

## 3. 连接原理（框架如何"找到"这个 agent）

```
runner.py 顶部 import
    → import src.agents.case_analyst
    → 模块被加载，Python 执行文件顶层代码
    → @register_agent("case_analyst") 装饰器被调用
    → 装饰器内部执行 AGENT_REGISTRY["case_analyst"] = CaseAnalystAgent
    → 注册表中有了这个 agent

当实验配置 YAML 中写 type: "case_analyst" 时
    → pipeline builder 调用 get_agent_class("case_analyst")
    → 从 AGENT_REGISTRY 中查到 CaseAnalystAgent 类
    → 实例化为 agent 对象
```

**关键机制**：Python 的装饰器在模块被 `import` 时立即执行。所以只要模块被导入（不管是否使用其中的类），注册就完成了。`runner.py` 中的 `import src.agents.case_analyst  # noqa: F401` 就是利用了这个 side effect。

---

## 4. 运行时数据流

```
用户提供自然段落的病例文本
    ↓
文本作为 state["case_text"] 注入 LangGraph state
    ↓
pipeline 节点调用 CaseAnalystAgent.execute(input_data, context)
    ├── input_data["case_text"] = 原始自然段落文本
    └── input_data["case_id"] = 病例 ID（作为兜底 ID）
    ↓
execute() 内部流程：
    1. _build_messages()
       ├── CaseData.model_json_schema() → 自动生成 JSON Schema 字符串
       ├── PromptLoader.load(template_path, schema=schema_json) → 用 Schema 填充模板
       └── 返回 [system_prompt, user_message(原始文本)] 消息列表
    2. context.llm_client.chat(messages, model, temperature)
       └── LLM 返回 JSON 格式的结构化病例数据
    3. _parse_response(response_text, fallback_case_id)
       ├── 处理 markdown 代码块包裹（```json ... ```）
       ├── json.loads() 解析为 dict
       └── CaseData.model_validate(parsed) → Pydantic 校验
    4. 返回 AgentOutput
       ├── content = CaseData 的 JSON 字符串（排除 None 字段）
       ├── metadata = {model, temperature, cached, parsed_case_id}
       └── llm_calls = [call_trace]
    ↓
AgentOutput 写回 state["agent_outputs"]["case_analyst"]
```

---

## 5. 自助修改指南

### 如果想修改提取字段

- 修改 `src/schemas/case.py` 中的 `CaseData` 类，增减字段
- Prompt 模板中的 `$schema` 变量会自动反映变化（因为用的是 `model_json_schema()`）
- 不需要改 agent 代码

### 如果想调整提取规则

- 编辑 `configs/prompts/v1/case_analyst_parsing.md` 中的 "Extraction Rules" 部分
- 不需要改 agent 代码

### 如果想创建另一种解析风格

- 新建一个 prompt 模板文件（如 `configs/prompts/v2/case_analyst_parsing.md`）
- 在 YAML 配置中引用新模板路径即可

### 如果想在 pipeline 中使用此 agent

在实验配置 YAML 中引用：

```yaml
agents:
  - id: "case_analyst"
    type: "case_analyst"
    prompt_template: "configs/prompts/v1/case_analyst_parsing.md"
    model: "gpt-4o"
    temperature: 0.1
    parameters: {}

pipeline:
  nodes:
    - id: "case_parsing"
      agents: ["case_analyst"]
    # ... 后续节点
  edges:
    - from: "START"
      to: "case_parsing"
    # ...
```

---

## 6. 验证方法

### 快速验证注册

```bash
conda activate MDTAgent
python -c "
import src.agents.case_analyst
from src.agents.registry import AGENT_REGISTRY
print('已注册:', list(AGENT_REGISTRY.keys()))
print('类:', AGENT_REGISTRY['case_analyst'])
"
```

期望输出包含 `case_analyst` 在注册表中。

### 如果报错

- `ModuleNotFoundError`：检查文件路径是否正确，`src/agents/case_analyst.py` 是否存在
- `ValueError: Agent 'case_analyst' 已注册`：说明模块被重复导入，检查是否有循环导入
- `KeyError: Agent 'case_analyst' 未注册`：说明 `runner.py` 中的 import 行没有执行到，检查导入是否被注释

---

## 7. 概念补充

### Registry Pattern（注册表模式）

一种设计模式：维护一个全局字典（注册表），用装饰器在模块加载时自动把类"注册"进去。好处是添加新实现不需要修改工厂方法的 if-else 链——只需新建文件 + 导入即可。

### Pydantic `model_json_schema()`

Pydantic v2 的方法，根据模型类的字段定义自动生成 JSON Schema（一种描述 JSON 结构的标准格式）。这里的妙用是：CaseData 的字段定义既是代码中的数据模型，也是 prompt 中告诉 LLM 目标格式的说明——一处定义，两处使用，不会不一致。

### `string.Template` 与 `$variable` 语法

Python 标准库的模板引擎。用 `$variable` 或 `${variable}` 作占位符。项目选择 `$` 而非 `{}`，是因为 prompt 文本中大括号出现频率高（如 JSON 示例），用 `$` 可避免冲突。`safe_substitute` 方法在变量未提供时保留占位符原样，不会报错。

### JSON 解析的防御性处理

LLM 返回 JSON 时经常会包裹在 markdown 代码块中（如 ` ```json ... ``` `）。`_parse_response` 方法先检测并去除这层包裹，再做 `json.loads()`，增强了对 LLM 输出格式变化的容错性。

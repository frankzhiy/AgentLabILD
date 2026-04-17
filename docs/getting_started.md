# 新手上路指南

> 本文假设你**只会基本的电脑操作**，会一步一步带你把项目跑起来。
> 如果你对 conda、pip、VSCode 这些工具已经很熟了，可以直接跳到 [快速跑通实验](#5-快速跑通实验一行命令)。

---

## 目录

1. [打开项目](#1-打开项目)
2. [激活 conda 环境](#2-激活-conda-环境)
3. [安装依赖](#3-安装依赖)
4. [配置 API Key](#4-配置-api-key)
5. [快速跑通实验（一行命令）](#5-快速跑通实验一行命令)
6. [查看运行结果](#6-查看运行结果)
7. [运行测试](#7-运行测试)
8. [改一个实验参数试试](#8-改一个实验参数试试)
9. [常见问题排查](#9-常见问题排查)

---

## 1. 打开项目

在 VSCode 中：

- `File` → `Open Folder...` → 选择 `AgentLabILD` 文件夹
- 或者用命令行：`code /path/to/AgentLabILD`

打开后，左侧文件栏应该能看到 `src/`、`configs/`、`tests/` 等目录。

---

## 2. 激活 conda 环境

打开 VSCode 内置终端：快捷键 `` Ctrl+` `` （macOS 上是 `` Cmd+` ``）

在终端中输入：

```bash
conda activate MDTAgent
```

如果终端提示符变成了 `(MDTAgent) $`，说明环境激活成功。

> **为什么要激活环境？** 这个 conda 环境里预装了 Python 3.11 和项目需要的所有库。不激活环境的话，你可能用的是系统自带的 Python，版本和依赖对不上，项目跑不起来。

**后续打开终端时都要先执行这一步。**

---

## 3. 安装依赖

首先确保你在项目根目录（终端中执行 `pwd` 应该看到路径以 `AgentLabILD` 结尾）。

然后安装项目和所有依赖：

```bash
uv pip install -e ".[dev]"
```

这行命令做了什么：
- `uv pip install` — 使用 `uv` 包管理器安装
- `-e` — "可编辑"模式安装，意思是你改了 `src/` 下的代码，不需要重新安装就能生效
- `".[dev]"` — 安装项目本身（`.`）以及开发依赖（`[dev]` 包含 pytest 等测试工具）

如果安装成功，你应该会在终端看到类似 `Successfully installed ...` 的输出。

> **如果提示 `uv` 命令找不到**，先运行 `pip install uv`

---

## 4. 配置 API Key

项目需要调用 OpenAI（或兼容的）API。你需要一个 API Key。

### 步骤

1. 复制示例文件：
   ```bash
   cp .env.example .env
   ```

2. 用 VSCode 打开 `.env` 文件，编辑成你的实际信息：
   ```
   OPENAI_API_KEY=sk-你的真实key
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

3. 保存文件。

> **关于 Base URL**：
> - 如果你直接用 OpenAI 官方 API，就填 `https://api.openai.com/v1`
> - 如果你用 ChatAnywhere 等国内代理服务，填代理服务提供的 URL
> - 如果你用 DeepSeek、Qwen 等其他兼容 OpenAI 格式的 API，填对应的 URL

> **安全提示**：`.env` 文件已经加入了 `.gitignore`，不会被 git 提交。永远不要把你的真实 API Key 直接写在代码里或提交到 git。

---

## 5. 快速跑通实验（一行命令）

确保你已经：
- ✅ 激活了 `MDTAgent` 环境
- ✅ 安装了依赖
- ✅ 配置了 `.env`

然后在项目根目录运行：

```bash
python -c "
from src.runner import ExperimentRunner
runner = ExperimentRunner('configs/experiments/baseline_3agent.yaml')
result = runner.run()
print(f'完成！运行了 {len(result.case_results)} 个病例')
"
```

或者你喜欢更整洁的方式，创建一个 `run.py` 文件：

```python
# run.py — 放在项目根目录
from src.runner import ExperimentRunner

runner = ExperimentRunner("configs/experiments/baseline_3agent.yaml")
result = runner.run()

print(f"\n=== 实验完成 ===")
print(f"病例数: {len(result.case_results)}")
print(f"总 token: {result.total_token_usage.total_tokens}")
for cr in result.case_results:
    print(f"\n--- {cr.case_id} ---")
    print(cr.final_output[:300])  # 只打印前 300 字符
```

然后运行：

```bash
python run.py
```

**等待** API 返回结果（通常 10~60 秒，取决于网络和模型），你会看到日志输出：

```
INFO:src.runner:开始实验: baseline_3agent
INFO:src.runner:加载了 2 个病例
INFO:src.runner:运行病例 [1/2]: demo_001
INFO:src.runner:运行病例 [2/2]: demo_002
INFO:src.runner:结果已保存到: results/baseline_3agent_20250101_120000
INFO:src.runner:实验完成: 2 个病例, 总 token: xxxx
```

---

## 6. 查看运行结果

实验结果保存在 `results/` 目录下，每次运行会创建一个带时间戳的子文件夹：

```
results/
└── baseline_3agent_20250101_120000/
    ├── config_snapshot.yaml      ← 本次运行使用的配置快照
    ├── raw_outputs.jsonl         ← 每个病例的最终输出（一行一个）
    └── traces/
        ├── demo_001.json         ← 第一个病例的完整追踪
        └── demo_002.json         ← 第二个病例的完整追踪
```

### 看最终诊断输出

```bash
cat results/baseline_3agent_*/raw_outputs.jsonl | python -m json.tool --no-ensure-ascii
```

### 看某个病例的追踪详情

```bash
python -m json.tool results/baseline_3agent_*/traces/demo_001.json | head -100
```

### 在 Python / Jupyter 中分析

```python
import json

# 加载 trace
with open("results/baseline_3agent_xxx/traces/demo_001.json") as f:
    trace = json.load(f)

# 看有哪些 agent 参与了
for at in trace["agent_traces"]:
    print(f"Agent: {at['agent_id']}, Token: {at['llm_calls'][0]['token_usage']['total_tokens']}")
```

---

## 7. 运行测试

测试用来验证"代码有没有写对"。每次改了代码之后都建议跑一下：

```bash
pytest tests/ -v
```

`-v` 表示 verbose（详细模式），会逐个列出每个测试是否通过。

你应该看到类似：

```
tests/test_agents.py::test_base_agent_requires_execute ... PASSED
tests/test_agents.py::test_register_agent ... PASSED
tests/test_schemas.py::test_case_data_basic ... PASSED
...
29 passed in 0.5s
```

如果某个测试 FAILED，说明你改的代码破坏了某个功能，需要检查修复。

### 只运行某一类测试

```bash
pytest tests/test_schemas.py -v       # 只跑 schema 相关测试
pytest tests/test_runner.py -v        # 只跑 runner 相关测试
pytest tests/ -k "test_cache" -v      # 只跑名字包含 "cache" 的测试
```

---

## 8. 改一个实验参数试试

最简单的上手方式是修改实验配置。我们试试把模型从 GPT-4o 换成别的：

### 步骤

1. 复制一份配置：
   ```bash
   cp configs/experiments/baseline_3agent.yaml configs/experiments/my_first_experiment.yaml
   ```

2. 打开 `configs/experiments/my_first_experiment.yaml`，修改你想改的参数。例如：

   ```yaml
   # 改实验名（随意取，用来区分不同实验）
   experiment:
     name: "my_first_experiment"
     description: "换 deepseek 模型试试"

   # 改所有 agent 的模型
   agents:
     - id: "pulmonologist"
       type: "llm_agent"
       prompt_template: "configs/prompts/v1/pulmonologist_analysis.md"
       model: "deepseek-chat"     # ← 改成 deepseek
       temperature: 0.3
       parameters: {}
     # ... radiologist 和 moderator 也类似修改
   ```

3. 运行你的新实验：
   ```bash
   python -c "
   from src.runner import ExperimentRunner
   runner = ExperimentRunner('configs/experiments/my_first_experiment.yaml')
   result = runner.run()
   "
   ```

4. 对比两次结果——它们会存在 `results/` 下不同的目录里。

> **这就是"换一个 YAML 文件就是换一个实验"的含义**。你不需要改任何 Python 代码，所有实验变量（模型、temperature、agent 数量、pipeline 拓扑、prompt 模板……）都在 YAML 文件里控制。

---

## 9. 常见问题排查

### `ModuleNotFoundError: No module named 'src'`

**原因**：没有以 editable 模式安装项目。

**解决**：在项目根目录运行 `uv pip install -e ".[dev]"`

### `openai.AuthenticationError` 或 `Invalid API Key`

**原因**：`.env` 文件中的 API Key 不正确，或 `.env` 文件不存在。

**解决**：
1. 检查是否已创建 `.env`（不是 `.env.example`）
2. 检查 key 是否正确（没有多余空格、引号）
3. 检查 `OPENAI_BASE_URL` 是否和你的 key 对应（比如 DeepSeek 的 key 要配 DeepSeek 的 URL）

### `ImportError: cannot import name 'Send' from 'langgraph.graph'`

**原因**：LangGraph 版本问题。`Send` 在新版中从 `langgraph.types` 导入。

**解决**：`uv pip install --upgrade langgraph`

### `FileNotFoundError: 病例数据文件不存在`

**原因**：YAML 配置指定的数据路径有误。

**解决**：检查 YAML 中 `data.cases` 和 `data.ground_truth` 路径是否存在。路径相对于你**运行命令时的当前目录**（应该是项目根目录）。

### 运行正常但 API 调用很慢

项目内置了 LLM 缓存。第一次调用会慢（需要等 API 返回），但相同输入的第二次调用会直接读缓存（毫秒级）。所以：

- 第一次跑实验：慢是正常的
- 第二次跑**同一个配置**：会很快（全部命中缓存）
- 改了 prompt 或参数后：对应的调用会 miss 缓存，重新调 API

### 想清除缓存重新跑

```bash
rm -rf .llm_cache/
```

### pytest 找不到测试

确保在**项目根目录**运行 `pytest`，因为 `pyproject.toml` 里配置了 `testpaths = ["tests"]` 和 `pythonpath = ["."]`。

---

## 下一步

- 想了解代码是怎么设计的？→ 读 `docs/architecture.md`（代码架构详解）
- 想了解 YAML 配置每个字段是什么意思？→ 读 `docs/config_reference.md`（配置速查手册）
- 想添加新的 agent / 通信协议 / 冲突检测？→ 读 `docs/architecture.md` 最后几节的"实际动手"指南

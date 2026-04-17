"""基于 LLM 的 Agent 基类

提供「加载 prompt → 构建消息 → 调 LLM → 返回结果」的通用流程。
各专科 agent 继承此类，通过 AGENT_CONFIG 定义自身配置，
可按需覆写 _build_messages / execute 来实现专属逻辑。
"""

from __future__ import annotations

from src.agents.base import AgentContext, AgentOutput, BaseAgent
from src.llm.prompt_loader import PromptLoader


class LLMAgent(BaseAgent):
    """基于 LLM 的 agent 基类（不直接注册，由子类继承并注册）

    子类需要在模块级别定义 AGENT_CONFIG 并在 __init__ 中合并：

        AGENT_CONFIG = {
            "prompt_template": "configs/prompts/v1/xxx.md",
            "model": "gpt-4o",
            "temperature": 0.3,
        }

    子类可覆写：
        - _build_messages: 自定义消息构建逻辑
        - execute: 自定义执行流程（如输出解析、多轮对话）
    """

    def __init__(self, agent_id: str, config: dict | None = None):
        super().__init__(agent_id, config)
        self._prompt_loader = PromptLoader()

    def _build_messages(self, input_data: dict) -> list[dict[str, str]]:
        """构建发送给 LLM 的消息列表

        默认行为：用 case_text 和 prior_analyses 填充 prompt 模板。
        子类可覆写此方法以实现不同的消息构建逻辑。
        """
        prompt_template_path = self.config.get("prompt_template", "")
        case_text = input_data.get("case_text", "")

        # 从 state 中获取其他 agent 的已有输出，拼入上下文
        agent_outputs: dict = input_data.get("agent_outputs", {})

        # 用模板变量替换
        template_vars = {"case_text": case_text}

        # 如果有其他 agent 的输出，格式化为文本并作为 prior_analyses 变量注入
        if agent_outputs:
            prior_text_parts = []
            for aid, content in agent_outputs.items():
                prior_text_parts.append(f"### {aid}\n{content}")
            template_vars["prior_analyses"] = "\n\n".join(prior_text_parts)
        else:
            template_vars["prior_analyses"] = "(No prior analyses available)"

        # 加载并填充 prompt 模板 → 作为 system message
        system_prompt = self._prompt_loader.load(prompt_template_path, **template_vars)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please analyze the following case:\n\n{case_text}"},
        ]
        return messages

    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
        """执行 LLM 调用并返回结果

        默认行为：构建消息 → 调用 LLM → 返回纯文本输出。
        子类可覆写此方法以添加输出解析、多轮对话等逻辑。
        """
        model = self.config.get("model", "gpt-4o")
        temperature = self.config.get("temperature", 0.3)

        messages = self._build_messages(input_data)

        call_trace = context.llm_client.chat(
            messages=messages,
            model=model,
            temperature=temperature,
        )

        return AgentOutput(
            content=call_trace.response,
            metadata={
                "model": model,
                "temperature": temperature,
                "cached": call_trace.cached,
            },
            llm_calls=[call_trace],
        )

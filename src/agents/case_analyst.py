"""病例解析 Agent：将自然段落描述的病例信息转换为结构化 CaseData

接收自由文本格式的 ILD 病例信息，通过 LLM 提取关键字段，
输出符合 CaseData schema 的结构化 JSON。
"""

from __future__ import annotations

import json

from src.agents.base import AgentContext, AgentOutput
from src.agents.llm_agent import LLMAgent
from src.agents.registry import register_agent
from src.schemas.case import CaseData

# ── Agent 配置 ──────────────────────────────────────────────
AGENT_CONFIG = {
    "prompt_template": "configs/prompts/v1/case_analyst_parsing.md",
    "model": "gpt-5.4",
    "temperature": 0.1,
}


@register_agent("case_analyst")
class CaseAnalystAgent(LLMAgent):
    """将非结构化病例文本解析为 CaseData 结构的 agent"""

    def __init__(self, agent_id: str, config: dict | None = None):
        merged = {**AGENT_CONFIG, **(config or {})}
        super().__init__(agent_id, merged)

    def _build_messages(self, input_data: dict) -> list[dict[str, str]]:
        """构建发送给 LLM 的消息列表——注入 CaseData JSON Schema"""
        prompt_template_path = self.config.get("prompt_template", "")
        case_text = input_data.get("case_text", "")

        # 将 CaseData 的 JSON Schema 注入模板，让 LLM 知道目标结构
        schema_json = json.dumps(
            CaseData.model_json_schema(),
            indent=2,
            ensure_ascii=False,
        )

        system_prompt = self._prompt_loader.load(
            prompt_template_path,
            schema=schema_json,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case_text},
        ]
        return messages

    def _parse_response(self, response_text: str, fallback_case_id: str) -> CaseData:
        """从 LLM 响应中解析出 CaseData 对象

        尝试从响应中提取 JSON 块并校验。如果 LLM 返回了 markdown 代码块包裹的 JSON，
        也能正确提取。
        """
        text = response_text.strip()

        # 处理 markdown 代码块包裹的情况：```json ... ``` 或 ``` ... ```
        if text.startswith("```"):
            # 去掉首行（```json 或 ```）和末尾的 ```
            lines = text.split("\n")
            lines = lines[1:]  # 去掉 ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        parsed = json.loads(text)

        # 确保有 case_id
        if "case_id" not in parsed or not parsed["case_id"]:
            parsed["case_id"] = fallback_case_id

        return CaseData.model_validate(parsed)

    def execute(self, input_data: dict, context: AgentContext) -> AgentOutput:
        """执行病例解析：原始文本 → 结构化 CaseData"""
        model = self.config.get("model", "gpt-4o")
        temperature = self.config.get("temperature", 0.1)

        messages = self._build_messages(input_data)

        call_trace = context.llm_client.chat(
            messages=messages,
            model=model,
            temperature=temperature,
        )

        # 从 input_data 中取 case_id 作为兜底
        fallback_id = input_data.get("case_id", "unknown")

        case_data = self._parse_response(call_trace.response, fallback_id)

        return AgentOutput(
            content=case_data.model_dump_json(indent=2, exclude_none=True),
            metadata={
                "model": model,
                "temperature": temperature,
                "cached": call_trace.cached,
                "parsed_case_id": case_data.case_id,
            },
            llm_calls=[call_trace],
        )

"""LLM 客户端封装

可实例化（非全局单例），支持多 provider（通过 OpenAI 兼容接口），
集成 response cache，记录 token 消耗和延迟。
"""

from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from src.llm.cache import LLMCache
from src.schemas.trace import LLMCallTrace, TokenUsage


class LLMClient:
    """对 OpenAI 兼容接口的封装，支持缓存和追踪

    Args:
        api_key: API 密钥
        base_url: API 基础 URL（可切换 provider / 代理服务）
        cache: LLMCache 实例；传 None 则禁用缓存
        default_model: 未指定 model 时的默认模型
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        cache: LLMCache | None = None,
        default_model: str = "gpt-4o",
    ):
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)
        self._cache = cache
        self.default_model = default_model

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMCallTrace:
        """发送 chat completion 请求，返回完整的调用追踪

        如果缓存命中则直接返回缓存结果（trace.cached = True）。
        """
        model = model or self.default_model

        # 查缓存
        if self._cache is not None:
            cached = self._cache.get(model, messages, temperature)
            if cached is not None:
                return LLMCallTrace(
                    model=model,
                    messages=messages,
                    response=cached["response_text"],
                    token_usage=TokenUsage(**cached.get("token_usage", {})),
                    latency_ms=0.0,
                    temperature=temperature,
                    cached=True,
                )

        # 实际调用
        t0 = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            **kwargs,
        )
        latency_ms = (time.perf_counter() - t0) * 1000

        response_text = completion.choices[0].message.content or ""
        usage = completion.usage
        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

        # 写缓存
        if self._cache is not None:
            self._cache.put(model, messages, temperature, {
                "response_text": response_text,
                "token_usage": token_usage.model_dump(),
            })

        return LLMCallTrace(
            model=model,
            messages=messages,
            response=response_text,
            token_usage=token_usage,
            latency_ms=latency_ms,
            temperature=temperature,
            cached=False,
        )

"""测试 LLM Cache 和 Client"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.llm.cache import LLMCache
from src.llm.client import LLMClient
from src.schemas.trace import LLMCallTrace


# ── LLMCache 测试 ──────────────────────────────────────────

class TestLLMCache:
    def test_miss_returns_none(self, tmp_path: Path):
        cache = LLMCache(cache_dir=tmp_path / "cache")
        result = cache.get("gpt-4o", [{"role": "user", "content": "hi"}], 0.3)
        assert result is None

    def test_put_and_get(self, tmp_path: Path):
        cache = LLMCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "hello"}]
        response = {"response_text": "world", "token_usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}

        cache.put("gpt-4o", messages, 0.3, response)
        result = cache.get("gpt-4o", messages, 0.3)

        assert result is not None
        assert result["response_text"] == "world"

    def test_different_params_miss(self, tmp_path: Path):
        cache = LLMCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "hello"}]
        response = {"response_text": "world"}

        cache.put("gpt-4o", messages, 0.3, response)
        # 不同 temperature → miss
        assert cache.get("gpt-4o", messages, 0.5) is None
        # 不同 model → miss
        assert cache.get("gpt-3.5-turbo", messages, 0.3) is None

    def test_deterministic_key(self, tmp_path: Path):
        cache = LLMCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "test"}]
        k1 = cache._make_key("m", messages, 0.0)
        k2 = cache._make_key("m", messages, 0.0)
        assert k1 == k2


# ── LLMClient 缓存集成测试 ─────────────────────────────────

class TestLLMClientCache:
    def test_cache_hit_skips_api_call(self, tmp_path: Path):
        """缓存命中时不应调用 OpenAI API"""
        cache = LLMCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "hi"}]
        cache.put("gpt-4o", messages, 0.3, {
            "response_text": "cached response",
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

        client = LLMClient(api_key="fake-key", cache=cache)
        # 不 mock OpenAI——如果调用了真实 API 会失败
        trace = client.chat(messages=messages, model="gpt-4o", temperature=0.3)

        assert trace.cached is True
        assert trace.response == "cached response"
        assert trace.latency_ms == 0.0

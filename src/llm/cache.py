"""LLM Response 文件缓存

基于 (model, messages, temperature) 的 SHA-256 hash 做索引，
将 LLM 响应缓存为 JSON 文件，保证可复现性并节省调用成本。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class LLMCache:
    """基于文件系统的 LLM 响应缓存"""

    def __init__(self, cache_dir: str | Path = ".llm_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _make_key(model: str, messages: list[dict[str, str]], temperature: float) -> str:
        """根据输入参数生成确定性的 hash key"""
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        # 用前两位做子目录，避免单目录文件过多
        return self.cache_dir / key[:2] / f"{key}.json"

    def get(self, model: str, messages: list[dict[str, str]], temperature: float) -> dict[str, Any] | None:
        """查询缓存，命中返回完整响应 dict，未命中返回 None"""
        key = self._make_key(model, messages, temperature)
        path = self._cache_path(key)
        if path.exists():
            return json.loads(path.read_text("utf-8"))
        return None

    def put(self, model: str, messages: list[dict[str, str]], temperature: float,
            response: dict[str, Any]) -> None:
        """将响应写入缓存"""
        key = self._make_key(model, messages, temperature)
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response, ensure_ascii=False, indent=2), "utf-8")

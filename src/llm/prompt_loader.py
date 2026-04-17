"""Prompt 模板加载器

从 Markdown 文件加载 prompt 模板，支持 {variable} 变量替换。
"""

from __future__ import annotations

from pathlib import Path
from string import Template


class PromptLoader:
    """从文件加载 prompt 模板并进行变量替换

    模板使用 Python string.Template 语法：$variable 或 ${variable}
    （选择 $ 而非 {} 语法是因为 prompt 中大括号出现频率高，$ 更不容易冲突）
    """

    def __init__(self, base_dir: str | Path | None = None):
        """
        Args:
            base_dir: prompt 文件的基础目录。如果指定，相对路径将相对于此目录解析
        """
        self.base_dir = Path(base_dir) if base_dir else None

    def _resolve_path(self, template_path: str) -> Path:
        """解析模板文件路径"""
        p = Path(template_path)
        if not p.is_absolute() and self.base_dir:
            p = self.base_dir / p
        return p

    def load_raw(self, template_path: str) -> str:
        """加载原始模板文本（不做变量替换）"""
        path = self._resolve_path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板文件不存在: {path}")
        return path.read_text("utf-8")

    def load(self, template_path: str, **variables: str) -> str:
        """加载模板并替换变量

        使用 safe_substitute：未提供的变量保留原样（不报错），便于调试。

        Args:
            template_path: 模板文件路径
            **variables: 需要替换的变量（如 case_text="...", history="..."）

        Returns:
            替换后的完整 prompt 文本
        """
        raw = self.load_raw(template_path)
        tmpl = Template(raw)
        return tmpl.safe_substitute(variables)

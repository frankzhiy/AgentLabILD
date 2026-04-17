"""测试 Prompt Loader"""

from pathlib import Path

import pytest

from src.llm.prompt_loader import PromptLoader


def test_load_raw(tmp_path: Path):
    """加载原始模板"""
    f = tmp_path / "test.md"
    f.write_text("Hello $name", encoding="utf-8")
    loader = PromptLoader()
    raw = loader.load_raw(str(f))
    assert raw == "Hello $name"


def test_load_with_substitution(tmp_path: Path):
    """变量替换"""
    f = tmp_path / "test.md"
    f.write_text("Case: $case_text\nModel: $model_name", encoding="utf-8")
    loader = PromptLoader()
    result = loader.load(str(f), case_text="Patient A", model_name="GPT-4o")
    assert "Patient A" in result
    assert "GPT-4o" in result


def test_safe_substitute_keeps_unknown(tmp_path: Path):
    """未提供的变量保留原样（safe_substitute 行为）"""
    f = tmp_path / "test.md"
    f.write_text("$known and $unknown", encoding="utf-8")
    loader = PromptLoader()
    result = loader.load(str(f), known="YES")
    assert "YES" in result
    assert "$unknown" in result


def test_base_dir(tmp_path: Path):
    """基础目录解析"""
    sub = tmp_path / "prompts" / "v1"
    sub.mkdir(parents=True)
    (sub / "p.md").write_text("content", encoding="utf-8")

    loader = PromptLoader(base_dir=tmp_path)
    result = loader.load_raw("prompts/v1/p.md")
    assert result == "content"


def test_missing_file_raises(tmp_path: Path):
    loader = PromptLoader(base_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="不存在"):
        loader.load_raw("nonexistent.md")


def test_real_prompt_template():
    """验证项目中的真实 prompt 模板可加载和替换"""
    loader = PromptLoader(base_dir=Path("."))
    result = loader.load(
        "configs/prompts/v1/pulmonologist_analysis.md",
        case_text="65yo male with progressive dyspnea",
    )
    assert "65yo male" in result
    assert "pulmonologist" in result.lower()

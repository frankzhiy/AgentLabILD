"""Minimal tests for repository skeleton integrity."""

from __future__ import annotations

import importlib


MODULES = [
    "src",
    "src.runner",
    "src.agents",
    "src.communication",
    "src.conflict",
    "src.evaluation",
    "src.llm",
    "src.pipeline",
    "src.intake",
    "src.schemas",
    "src.schemas.state",
    "src.tracing",
    "src.state",
    "src.validators",
    "src.provenance",
    "src.storage",
    "src.revision",
    "src.arbitration",
]


def test_modules_are_importable() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)


def test_runner_returns_placeholder_payload() -> None:
    from src.runner import ExperimentRunner

    result = ExperimentRunner().run()

    assert result["status"] == "skeleton"
    assert "unimplemented" in result["message"].lower()

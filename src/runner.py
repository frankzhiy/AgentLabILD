"""Minimal runner placeholder for the reset research platform.

The repository was intentionally reset to a skeleton. This module keeps the
project importable while avoiding any legacy experiment behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RunnerConfig:
    """Minimal non-operational runner config placeholder."""

    experiment_name: str = "skeleton"


class ExperimentRunner:
    """Non-operational runner placeholder.

    TODO:
    - Introduce phased orchestration after mechanism contracts are defined.
    - Add validation-gated state transitions in Phase 1.
    """

    def __init__(self, config: RunnerConfig | None = None) -> None:
        self.config = config or RunnerConfig()

    def run(self) -> dict[str, Any]:
        """Return a static placeholder result for scaffolding validation."""

        return {
            "status": "skeleton",
            "experiment_name": self.config.experiment_name,
            "message": "Runner is intentionally unimplemented after repository reset.",
        }

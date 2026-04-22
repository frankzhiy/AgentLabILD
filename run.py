"""CLI entrypoint for the reset skeleton platform."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure local package imports work when run.py is executed directly.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runner import ExperimentRunner


def main() -> None:
    """Run the minimal placeholder runner and print its status message."""

    result = ExperimentRunner().run()
    print(result["message"])


if __name__ == "__main__":
    main()
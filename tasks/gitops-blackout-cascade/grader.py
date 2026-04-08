#!/usr/bin/env python3
"""Review-facing compatibility wrapper for the Harbor grader.

Sample tasks in this workspace expose a root-level ``grader.py``. This Harbor
task's runtime grader lives at ``tests/score_task.py`` and is invoked by
``tests/test.sh``. This wrapper exists so review tooling can find a grader in
the expected location without changing the Harbor execution path.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    runpy.run_path(str(Path(__file__).parent / "tests" / "score_task.py"), run_name="__main__")


if __name__ == "__main__":
    main()

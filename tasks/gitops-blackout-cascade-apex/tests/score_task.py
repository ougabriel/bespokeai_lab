from __future__ import annotations

"""Visible test entrypoint for the hotfix recovery grader.

The full functional scoring engine lives in `/task/grader.py`, which is the
apex-format root grader reviewers are expected to audit. This wrapper keeps the
same verifier reachable from `/task/tests/score_task.py` for local shell-based
test harnesses and review tooling that look in the tests directory.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grader import grade, main

__all__ = ["grade", "main"]


if __name__ == "__main__":
    main()

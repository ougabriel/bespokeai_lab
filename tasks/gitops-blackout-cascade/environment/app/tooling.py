from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_json_tool(script_path: Path, *args: str) -> tuple[bool, dict[str, object] | None, str]:
    if not script_path.exists():
        return False, None, f"Tool {script_path.name} is missing from the seeded lane."

    result = subprocess.run(
        ["python", str(script_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, None, result.stderr.strip() or result.stdout.strip() or f"{script_path.name} failed."

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, None, f"{script_path.name} did not emit valid JSON."

    return True, payload, ""

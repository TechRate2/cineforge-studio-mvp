from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _python_executable() -> str:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _run(args: list[str]) -> int:
    print(f"\n[backend:test] {' '.join(args)}", flush=True)
    return subprocess.call(args, cwd=ROOT)


def main() -> int:
    python = _python_executable()
    steps = [
        [python, "backend/scripts/test_agent.py"],
        [python, "-m", "pytest", "-q", "backend/scripts/test_phase1_core.py"],
    ]
    for args in steps:
        code = _run(args)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

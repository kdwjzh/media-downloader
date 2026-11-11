"""One-shot check: lint, type check and tests for backend and frontend.

Run from anywhere:  python scripts/check.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS: list[tuple[str, list[str]]] = [
    ("backend", ["uv", "run", "ruff", "check", "."]),
    ("backend", ["uv", "run", "mypy"]),
    ("backend", ["uv", "run", "pytest", "-q"]),
    ("frontend", ["npm", "run", "lint"]),
    ("frontend", ["npm", "run", "typecheck"]),
    ("frontend", ["npm", "test"]),
]


def main() -> int:
    for folder, command in STEPS:
        print(f"\n== {folder}: {' '.join(command)}", flush=True)
        exe = shutil.which(command[0])  # npm is npm.cmd on Windows
        if exe is None:
            print(f"{command[0]} not found on PATH")
            return 1
        if subprocess.run([exe, *command[1:]], cwd=ROOT / folder).returncode != 0:
            print(f"\nFAILED: {folder}: {' '.join(command)}")
            return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compatibility entry point for the relocated presentation integration tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests" / "integration" / "presentation" / "run_checks.py"


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, str(TARGET), *sys.argv[1:]], cwd=ROOT))

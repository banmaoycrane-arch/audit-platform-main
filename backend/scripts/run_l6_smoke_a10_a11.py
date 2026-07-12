#!/usr/bin/env python3
"""L6 路径 A 冒烟：A10 期末处理 + A11 报表与导出。

用法（在 backend 目录）：
    python scripts/run_l6_smoke_a10_a11.py
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_l6_smoke_a10_a11.py",
        "tests/test_report_export_api.py",
        "-v",
        "--tb=short",
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())

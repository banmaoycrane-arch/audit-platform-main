"""
核心主线偏离检测脚本

用法：
    python scripts/focus_drift_detector.py

功能：
    1. 检查当前工作区（git diff）修改的文件是否集中在核心模块路径。
    2. 检查最近 N 次 git 提交主题是否包含核心模块关键词。
    3. 检查是否存在新增非核心模块的迹象。

返回：
    0  表示未偏离
    1  表示检测到偏离，需提醒
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# 核心模块路径白名单（正则匹配）
CORE_PATH_PATTERNS = [
    r"backend/app/services/accounting",
    r"backend/app/services/entries",
    r"backend/app/services/reports",
    r"backend/app/services/period_close",
    r"backend/app/services/opening_balances",
    r"backend/app/services/chart_of_accounts",
    r"backend/app/services/parser_engine",
    r"backend/app/services/import_engine",
    r"backend/app/api/routes_entries",
    r"backend/app/api/routes_reports",
    r"backend/app/api/routes_accounting_periods",
    r"backend/app/api/routes_opening_balances",
    r"backend/app/api/routes_import_jobs",
    r"backend/app/api/routes_parser_engine",
    r"backend/app/models/team",
    r"backend/app/models/ledger",
    r"backend/app/models/project",
    r"backend/app/models/accounting_entry",
    r"backend/app/models/accounting_period",
    r"backend/app/models/opening_balance",
    r"backend/app/models/chart_of_accounts",
    r"backend/app/db/models",
    r"backend/app/services/financial_statements_service",
    r"backend/alembic/versions",
    r"backend/tests/acceptance/accounting",
    r"backend/tests/acceptance/parser_engine",
    r"backend/samples",
    r"frontend/src/pages/Ledger",
    r"frontend/src/pages/Entry",
    r"frontend/src/pages/ChartOfAccounts",
    r"frontend/src/pages/OpeningBalance",
    r"frontend/src/pages/AccountingPeriod",
    r"frontend/src/pages/Reports",
    r"frontend/src/pages/ParserEngine",
    r"frontend/src/pages/ImportJob",
    r"frontend/src/services/accounting",
    r"frontend/src/services/entries",
    r"frontend/src/services/reports",
    r"frontend/src/services/parserEngine",
    r"frontend/src/stores/ledger",
    r"\.trae/daily-focus",
    r"\.trae/weekly-focus",
    r"\.trae/documents/core-focus-guardian",
    r"\.trae/documents/core-business-concepts-boundary",
    r"\.trae/documents/legacy-to-new-concept-mapping",
    r"scripts/focus_drift_detector",
]

# 核心模块关键词（用于提交主题检测）
CORE_KEYWORDS = [
    "entry",
    "ledger",
    "accounting",
    "period",
    "opening balance",
    "chart of accounts",
    "report",
    "parser",
    "import",
    "source file",
    "voucher",
    "journal",
    "trial balance",
    "balance sheet",
    "income statement",
    "core",
    "focus",
    "closure",
]

# 非核心模块信号（新增独立页面/API/服务的文件名关键词）
DRIFT_SIGNALS = [
    "fixed_asset",
    "bank_reconciliation",
    "agent_",
    "agent/",
    "agent.",
    "superadmin",
    "notification",
    "dashboard",
    "analytics",
    "kpi",
    "consolidation",
    "multi_entity",
    "multi_ledger",
    "融资",
    "尽调",
]


def _run_git(args: List[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout.strip()


def _is_core_path(file_path: str) -> bool:
    """判断文件路径是否属于核心模块白名单。"""
    return any(re.search(pattern, file_path) for pattern in CORE_PATH_PATTERNS)


def _has_drift_signal(file_path: str) -> bool:
    """判断文件路径是否包含非核心模块信号。"""
    lower_path = file_path.lower()
    return any(signal in lower_path for signal in DRIFT_SIGNALS)


def check_uncommitted_changes() -> Tuple[List[str], List[str]]:
    """
    检查未提交修改。
    返回 (core_files, drift_files)
    """
    output = _run_git(["diff", "--name-only"])
    if not output:
        return [], []

    files = [line.strip() for line in output.splitlines() if line.strip()]
    core_files = [f for f in files if _is_core_path(f)]
    drift_files = [f for f in files if not _is_core_path(f)]
    return core_files, drift_files


def check_recent_commits(limit: int = 3) -> Tuple[List[str], List[str]]:
    """
    检查最近 N 次提交主题是否偏离核心。
    返回 (core_commits, drift_commits)
    """
    output = _run_git(["log", "--oneline", f"-{limit}"])
    if not output:
        return [], []

    commits = [line.strip() for line in output.splitlines() if line.strip()]
    core_commits = []
    drift_commits = []

    for commit in commits:
        subject = commit.lower()
        if any(kw in subject for kw in CORE_KEYWORDS):
            core_commits.append(commit)
        else:
            drift_commits.append(commit)

    return core_commits, drift_commits


def main() -> int:
    print("=" * 60)
    print("核心主线偏离检测（Core Focus Drift Detector）")
    print("=" * 60)

    exit_code = 0

    # 1. 检查未提交文件
    core_files, drift_files = check_uncommitted_changes()
    print(f"\n[1/3] 未提交文件检查")
    print(f"  核心文件数：{len(core_files)}")
    print(f"  非核心文件数：{len(drift_files)}")

    if drift_files:
        print("  ⚠️ 检测到非核心文件修改：")
        for f in drift_files[:5]:
            print(f"     - {f}")
        if len(drift_files) > 5:
            print(f"     ... 还有 {len(drift_files) - 5} 个文件")
        exit_code = 1

    # 2. 检查新增非核心模块信号
    drift_signals = [f for f in core_files + drift_files if _has_drift_signal(f)]
    if drift_signals:
        print(f"\n[2/3] 非核心模块信号检查")
        print("  ⚠️ 检测到新增非核心模块信号：")
        for f in drift_signals[:5]:
            print(f"     - {f}")
        exit_code = 1
    else:
        print(f"\n[2/3] 非核心模块信号检查：未检测到")

    # 3. 检查最近提交主题（作为趋势参考，历史提交不设置失败状态）
    core_commits, drift_commits = check_recent_commits(limit=3)
    print(f"\n[3/3] 最近提交主题趋势检查")
    print(f"  核心提交数：{len(core_commits)}")
    print(f"  偏离提交数：{len(drift_commits)}")

    if drift_commits and len(drift_commits) >= 2:
        print("  ⚠️ 最近 3 次提交中至少 2 次偏离核心主线（趋势提示，不阻断当前工作）：")
        for c in drift_commits[:3]:
            print(f"     - {c}")
        # 注意：历史提交偏离不设置 exit_code=1，因为机制从今天开始生效。
        # 如需严格模式，请使用 --strict 参数。

    # 总结
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✅ 当前工作未偏离核心主线（核心记账闭环 + 导入解析引擎）")
    else:
        print("⚠️ 检测到偏离核心主线的风险，请立即校准：")
        print("  1. 暂停非核心任务")
        print("  2. 回到 .trae/daily-focus.md 核对今日目标")
        print("  3. 将非核心任务记录到 backlog 并延期")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

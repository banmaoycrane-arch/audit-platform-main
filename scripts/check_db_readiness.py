"""
数据库准备度检查脚本

检查后端数据库中是否已有足够资料支撑核心记账闭环自我测试。
输出：核心表记录数、数据完整性、结构差异、缺失项清单。
"""

import sqlite3
import os
import sys
from pathlib import Path


def get_db_path():
    """优先从环境变量读取，否则使用默认 SQLite 路径。"""
    env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
    db_url = None
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                    db_url = line.split("=", 1)[1].strip()
                    break

    if db_url and db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "").replace("/", os.sep)

    # 默认路径
    return str(Path(__file__).resolve().parent.parent / "backend" / "finance_audit.db")


def get_columns(cursor, table):
    """获取表的所有列名。"""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def main():
    db_path = get_db_path()
    print(f"数据库路径: {db_path}")
    print(f"数据库是否存在: {os.path.exists(db_path)}")

    if not os.path.exists(db_path):
        print("\n⚠️ 数据库文件不存在，无法检查现有资料。")
        print("建议：启动后端服务或运行初始化/迁移命令生成数据库。")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n表总数: {len(tables)}")
    print(f"表列表: {', '.join(tables[:20])}{'...' if len(tables) > 20 else ''}")

    core_tables = {
        "teams": "团队",
        "users": "用户",
        "organizations": "组织",
        "ledgers": "账簿",
        "projects": "项目",
        "accounting_periods": "会计期间",
        "chart_of_accounts": "会计科目",
        "opening_balances": "期初余额",
        "accounting_entries": "会计分录",
        "import_jobs": "导入任务",
        "source_files": "源文件",
        "entities": "主体",
        "counterparties": "往来单位",
    }

    print("\n=== 核心表记录数 ===")
    record_counts = {}
    for table, label in core_tables.items():
        if table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            record_counts[table] = count
            print(f"  {label} ({table}): {count}")
        else:
            record_counts[table] = None
            print(f"  {label} ({table}): 表不存在")

    # 结构差异检查
    print("\n=== 当前数据库结构 vs 代码模型结构差异 ===")
    expected_columns = {
        "ledgers": {"organization_id", "accounting_start_date"},
        "chart_of_accounts": {"ledger_id", "organization_id"},
        "accounting_entries": {"ledger_id"},
        "accounting_periods": {"ledger_id"},
        "opening_balances": {"ledger_id"},
    }

    structure_issues = []
    for table, expected in expected_columns.items():
        if table not in tables:
            continue
        actual = get_columns(cursor, table)
        missing = expected - actual
        if missing:
            structure_issues.append((table, missing))
            print(f"  ⚠️ {table} 缺少当前代码模型期望的字段: {missing}")

    if not structure_issues:
        print("  ✅ 核心表结构与当前代码模型一致")
    else:
        print("\n  说明：数据库结构较旧，可能未执行最新 Alembic 迁移，或数据库文件来自早期版本。")

    # 检查账簿
    print("\n=== 账簿详情 ===")
    if "ledgers" in tables and record_counts.get("ledgers", 0) > 0:
        cols = get_columns(cursor, "ledgers")
        select_cols = ["id", "name", "team_id"]
        if "organization_id" in cols:
            select_cols.append("organization_id")
        if "status" in cols:
            select_cols.append("status")
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM ledgers LIMIT 5")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
    else:
        print("  无账簿数据")

    # 检查期间
    print("\n=== 会计期间详情 ===")
    if "accounting_periods" in tables and record_counts.get("accounting_periods", 0) > 0:
        cols = get_columns(cursor, "accounting_periods")
        select_cols = ["id", "period_code", "status", "start_date", "end_date"]
        if "ledger_id" in cols:
            select_cols.insert(1, "ledger_id")
        if "organization_id" in cols:
            select_cols.insert(1, "organization_id")
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM accounting_periods LIMIT 5")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
    else:
        print("  无会计期间数据")

    # 检查科目
    print("\n=== 会计科目示例 ===")
    if "chart_of_accounts" in tables and record_counts.get("chart_of_accounts", 0) > 0:
        cols = get_columns(cursor, "chart_of_accounts")
        select_cols = ["id", "code", "name", "category", "direction"]
        if "ledger_id" in cols:
            select_cols.insert(1, "ledger_id")
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM chart_of_accounts LIMIT 10")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
    else:
        print("  无会计科目数据")

    # 检查期初余额
    print("\n=== 期初余额借贷平衡检查 ===")
    if "opening_balances" in tables and record_counts.get("opening_balances", 0) > 0:
        cols = get_columns(cursor, "opening_balances")
        debit_col = "debit_amount" if "debit_amount" in cols else "debit_balance"
        credit_col = "credit_amount" if "credit_amount" in cols else "credit_balance"
        cursor.execute(f"SELECT SUM({debit_col}), SUM({credit_col}) FROM opening_balances")
        result = cursor.fetchone()
        debit = result[0] or 0
        credit = result[1] or 0
        print(f"  借方合计: {debit}, 贷方合计: {credit}")
        if debit == credit:
            print("  ✅ 期初余额借贷平衡")
        else:
            print("  ⚠️ 期初余额借贷不平衡")
    else:
        print("  无期初余额数据")

    # 检查凭证
    print("\n=== 会计分录借贷平衡检查 ===")
    if "accounting_entries" in tables and record_counts.get("accounting_entries", 0) > 0:
        cols = get_columns(cursor, "accounting_entries")
        debit_col = "debit_amount" if "debit_amount" in cols else "debit_balance"
        credit_col = "credit_amount" if "credit_amount" in cols else "credit_balance"
        cursor.execute(f"SELECT SUM({debit_col}), SUM({credit_col}) FROM accounting_entries")
        result = cursor.fetchone()
        debit = result[0] or 0
        credit = result[1] or 0
        print(f"  借方合计: {debit}, 贷方合计: {credit}")
        if debit == credit:
            print("  ✅ 分录借贷平衡")
        else:
            print("  ⚠️ 分录借贷不平衡")
    else:
        print("  无会计分录数据")

    # 检查导入/源文件
    print("\n=== 导入任务与源文件 ===")
    if "import_jobs" in tables and record_counts.get("import_jobs", 0) > 0:
        cols = get_columns(cursor, "import_jobs")
        select_cols = ["id", "status", "source_type", "entry_count"]
        if "ledger_id" in cols:
            select_cols.insert(1, "ledger_id")
        if "organization_id" in cols:
            select_cols.insert(1, "organization_id")
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM import_jobs LIMIT 5")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
    else:
        print("  无导入任务数据")

    if "source_files" in tables and record_counts.get("source_files", 0) > 0:
        cols = get_columns(cursor, "source_files")
        select_cols = ["id", "filename", "file_type", "text_extract_status"]
        if "ledger_id" in cols:
            select_cols.insert(1, "ledger_id")
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM source_files LIMIT 5")
        for row in cursor.fetchall():
            print(f"  {dict(row)}")
    else:
        print("  无源文件数据")

    # 最终评估
    print("\n=== 数据库准备度评估 ===")

    missing = []
    if not record_counts.get("teams"):
        missing.append("团队 (teams)")
    if not record_counts.get("users"):
        missing.append("用户 (users)")
    if not record_counts.get("ledgers"):
        missing.append("账簿 (ledgers)")
    if not record_counts.get("accounting_periods"):
        missing.append("会计期间 (accounting_periods)")
    if not record_counts.get("chart_of_accounts"):
        missing.append("会计科目 (chart_of_accounts)")
    if not record_counts.get("opening_balances"):
        missing.append("期初余额 (opening_balances)")
    if not record_counts.get("accounting_entries"):
        missing.append("会计分录 (accounting_entries)")

    if missing:
        print("⚠️ 以下核心数据缺失或为空，无法支撑完整自我测试：")
        for item in missing:
            print(f"  - {item}")
    else:
        print("✅ 核心数据表均存在且有记录，可以支撑自我测试。")

    if structure_issues:
        print("\n⚠️ 数据库结构与当前代码模型不一致，需要处理：")
        print("  - 方案 A：删除旧数据库文件，重新执行 Alembic 迁移，生成新结构。")
        print("  - 方案 B：使用 Alembic 升级，但可能因旧数据与新约束冲突而失败。")
        print("  - 推荐：方案 A（删除后重建），因为当前数据主要是旧测试数据，不具保留价值。")

    print("\n建议：")
    if missing or structure_issues:
        print("1. 删除旧数据库文件 finance_audit.db，重新运行 Alembic 迁移。")
        print("2. 通过前端或 API 初始化基础数据：团队、用户、账簿、组织、会计期间、科目、期初余额。")
        print("3. 或使用标准会计案例样例数据批量初始化。")
        print("4. 确认数据结构和借贷平衡后再执行端到端测试。")
    else:
        print("1. 选择一个账簿，验证凭证录入、审核、过账流程。")
        print("2. 执行损益结转，检查期间状态变化。")
        print("3. 生成资产负债表、利润表、科目余额表，验证恒等式。")
        print("4. 上传业务文件测试导入解析引擎。")

    conn.close()


if __name__ == "__main__":
    main()

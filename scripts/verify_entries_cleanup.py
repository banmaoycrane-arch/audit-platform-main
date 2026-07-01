import sqlite3
import os


def main():
    db_path = "finance_audit.db"
    print(f"数据库路径: {os.path.abspath(db_path)}")
    print(f"数据库是否存在: {os.path.exists(db_path)}")

    if not os.path.exists(db_path):
        print("数据库不存在")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM accounting_entries")
    print(f"accounting_entries 当前记录数: {c.fetchone()[0]}")

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_entries_backup'")
    has_backup = c.fetchone() is not None
    print(f"accounting_entries_backup 是否存在: {has_backup}")
    if has_backup:
        c.execute("SELECT COUNT(*) FROM accounting_entries_backup")
        print(f"accounting_entries_backup 记录数: {c.fetchone()[0]}")

    conn.close()


if __name__ == "__main__":
    main()

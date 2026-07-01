# -*- coding: utf-8 -*-
"""
清理无 voucher_id 的历史 accounting_entries 数据。

业务场景：凭证系统改造后，所有会计分录必须归属于 voucher 主记录，并经过借贷平衡校验。
旧数据库中可能存在直接创建、无 voucher_id 的分录，无法保证借贷平衡，因此需要备份后清理。

运行方式：
    cd backend
    python scripts/cleanup_legacy_entries.py
"""
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.session import Base


def main():
    settings = get_settings()
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if not db_path.exists():
        print(f"数据库文件不存在：{db_path}")
        return

    backup_path = db_path.with_suffix(
        f".db.pre_voucher_cleanup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy(db_path, backup_path)
    print(f"已备份数据库到：{backup_path}")

    engine = create_engine(
        settings.database_url, connect_args={"check_same_thread": False}
    )
    Session = sessionmaker(bind=engine)
    db = Session()

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar()
        legacy = conn.execute(
            text("SELECT COUNT(*) FROM accounting_entries WHERE voucher_id IS NULL")
        ).scalar()
        print(f"总会计分录：{total}")
        print(f"无 voucher_id 的旧分录：{legacy}")

        if legacy > 0:
            conn.execute(text("DELETE FROM accounting_entries WHERE voucher_id IS NULL"))
            conn.commit()
            remaining = conn.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar()
            print(f"已清理旧分录，剩余：{remaining}")
        else:
            print("未发现需要清理的旧分录")

    db.close()
    print("清理完成")


if __name__ == "__main__":
    main()

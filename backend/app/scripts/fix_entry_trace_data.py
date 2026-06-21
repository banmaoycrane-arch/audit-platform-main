"""
数据修复脚本：修复历史数据的 ledger_id 和 entry_source 关联问题

执行前提：
1. 数据库迁移已完成（0004_add_entry_trace_fields）
2. 数据库有历史数据需要修复

修复内容：
1. 为 source_files 表中 ledger_id 为空的记录补充账套ID
2. 为 accounting_entries 表中 entry_source 为空的记录设置默认值

使用方法：
    cd backend
    python -m app.scripts.fix_entry_trace_data
"""
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def fix_source_file_ledger_ids():
    """修复 SourceFile 表中 ledger_id 为空的问题"""
    from app.db.session import SessionLocal
    from app.db.models import SourceFile, ImportJob
    
    db = SessionLocal()
    try:
        # 查找 ledger_id 为空的 SourceFile
        null_count = db.query(SourceFile).filter(SourceFile.ledger_id.is_(None)).count()
        print(f"发现 {null_count} 条 SourceFile 记录 ledger_id 为空")
        
        if null_count == 0:
            print("无需修复 SourceFile 数据")
            return
        
        # 分批处理，每批 100 条
        batch_size = 100
        fixed = 0
        
        while True:
            files = (
                db.query(SourceFile)
                .filter(SourceFile.ledger_id.is_(None))
                .limit(batch_size)
                .all()
            )
            if not files:
                break
            
            for file in files:
                # 从关联的 ImportJob 获取 ledger_id
                job = db.get(ImportJob, file.import_job_id)
                if job and job.ledger_id:
                    file.ledger_id = job.ledger_id
                    fixed += 1
                else:
                    # 尝试从同 organization 的其他 job 获取
                    other_job = (
                        db.query(ImportJob)
                        .filter(
                            ImportJob.organization_id == file.organization_id,
                            ImportJob.ledger_id.isnot(None),
                        )
                        .first()
                    )
                    if other_job:
                        file.ledger_id = other_job.ledger_id
                        fixed += 1
            
            db.commit()
            print(f"已修复 {fixed}/{null_count} 条记录")
        
        print(f"SourceFile ledger_id 修复完成，共修复 {fixed} 条记录")
        
    finally:
        db.close()


def fix_accounting_entry_sources():
    """修复 AccountingEntry 表中 entry_source 为空的问题"""
    from app.db.session import SessionLocal
    from app.db.models import AccountingEntry
    
    db = SessionLocal()
    try:
        # 查找 entry_source 为空或默认值的记录
        null_count = (
            db.query(AccountingEntry)
            .filter(
                (AccountingEntry.entry_source.is_(None)) | 
                (AccountingEntry.entry_source == '')
            )
            .count()
        )
        print(f"发现 {null_count} 条 AccountingEntry 记录 entry_source 为空")
        
        if null_count == 0:
            print("无需修复 AccountingEntry 数据")
            return
        
        # 分批处理
        batch_size = 500
        fixed = 0
        
        while True:
            entries = (
                db.query(AccountingEntry)
                .filter(
                    (AccountingEntry.entry_source.is_(None)) | 
                    (AccountingEntry.entry_source == '')
                )
                .limit(batch_size)
                .all()
            )
            if not entries:
                break
            
            for entry in entries:
                # 默认设置为 'auto'（自动导入）
                entry.entry_source = 'auto'
                fixed += 1
            
            db.commit()
            print(f"已修复 {fixed}/{null_count} 条记录")
        
        print(f"AccountingEntry entry_source 修复完成，共修复 {fixed} 条记录")
        
    finally:
        db.close()


def main():
    print("=" * 60)
    print("开始修复历史数据...")
    print("=" * 60)
    
    fix_source_file_ledger_ids()
    print()
    fix_accounting_entry_sources()
    
    print()
    print("=" * 60)
    print("数据修复完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

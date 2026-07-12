import sqlite3
c = sqlite3.connect("/data/finance_audit.db")
rows = c.execute(
    "SELECT id, import_job_id, filename, storage_path, file_type FROM source_files WHERE import_job_id IN (7,8,9)"
).fetchall()
for r in rows:
    print(r)

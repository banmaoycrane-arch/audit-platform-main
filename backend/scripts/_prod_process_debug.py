import sys
sys.path.insert(0, "/app/backend")
from app.db.session import SessionLocal
from app.db.models import ImportJob, SourceFile
from app.services.audit.audit_day_book_service import process_day_book_import
from app.storage.local_storage import resolve_storage_path
from app.services.doc_parsing.file_parser_service import parse_structured_accounting_entries, build_parse_diagnostics

db = SessionLocal()
for jid in [7, 8, 9]:
    job = db.get(ImportJob, jid)
    sf = db.query(SourceFile).filter_by(import_job_id=jid).first()
    if not sf:
        print(jid, "no file")
        continue
    path = resolve_storage_path(sf.storage_path)
    pr = parse_structured_accounting_entries(path, db=db)
    print(f"job {jid} path={path} exists={__import__('pathlib').Path(path).exists()} entries={len(pr.entries)} engine={build_parse_diagnostics(pr).get('engine')}")
    if jid == 9:
        try:
            r = process_day_book_import(db, job)
            print(f"  process: success={r.success} created={r.entries_created} err={r.error_message!r} diag={r.parse_diagnostics}")
        except Exception as e:
            print(f"  process EXC: {e}")
            db.rollback()
db.close()

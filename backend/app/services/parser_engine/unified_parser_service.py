import asyncio
import json
import time

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.db.models import ImportJob, SourceFile
from app.services.parser_engine.auto_archive_service import auto_review_and_archive
from app.services.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher, performance_monitor
from app.storage.local_storage import resolve_storage_path


def convert_parse_result_to_dict(parse_result: object) -> dict:
    from app.services.parser_engine.parse_result import LLMComparisonResult

    if isinstance(parse_result, dict) and "final_result" in parse_result:
        final = parse_result["final_result"]
        if final:
            file_format = final.file_format.value if hasattr(final.file_format, "value") else str(final.file_format) if final.file_format else "unknown"
            return {
                "file_format": file_format,
                "document_type": final.document_type.value if hasattr(final.document_type, "value") else str(final.document_type),
                "document_sub_type": (
                    final.sub_type.value
                    if hasattr(final.sub_type, "value") and final.sub_type
                    else str(final.sub_type) if final.sub_type else None
                ),
                "confidence": final.confidence,
                "engine_type": final.engine.value if hasattr(final.engine, "value") else str(final.engine),
                "data": final.data or {},
                "raw_text": final.raw_text,
                "error_message": "; ".join(final.validation_errors) if final.validation_errors else None,
                "parse_duration_ms": parse_result.get("parse_duration_ms", 0),
                "engine_comparison": {
                    "rule_engine_result": parse_result.get("rule_engine_result"),
                    "llm_engine_result": parse_result.get("llm_engine_result"),
                    "selection_reason": parse_result.get("selection_reason", ""),
                    "rule_confidence": parse_result.get("engine_comparison", {}).get("rule_confidence", 0.0),
                    "llm_confidence": parse_result.get("engine_comparison", {}).get("llm_confidence", 0.0),
                    "diagnosis": parse_result.get("engine_comparison", {}).get("diagnosis", {}),
                },
            }
        return {
            "file_format": "unknown",
            "document_type": "unknown",
            "document_sub_type": None,
            "confidence": 0.0,
            "engine_type": "unknown",
            "data": {},
            "raw_text": None,
            "error_message": "解析失败",
            "engine_comparison": {
                "rule_engine_result": parse_result.get("rule_engine_result"),
                "llm_engine_result": parse_result.get("llm_engine_result"),
                "selection_reason": parse_result.get("selection_reason", ""),
            },
        }

    if isinstance(parse_result, LLMComparisonResult):
        final = parse_result.final_result
        if final is None and parse_result.engine_results:
            final = list(parse_result.engine_results.values())[0]
        if final:
            file_format = final.file_format.value if hasattr(final.file_format, "value") else str(final.file_format) if final.file_format else "unknown"
            return {
                "file_format": file_format,
                "document_type": final.document_type.value if hasattr(final.document_type, "value") else str(final.document_type),
                "document_sub_type": (
                    final.sub_type.value
                    if hasattr(final.sub_type, "value") and final.sub_type
                    else str(final.sub_type) if final.sub_type else None
                ),
                "confidence": final.confidence,
                "engine_type": final.engine.value if hasattr(final.engine, "value") else str(final.engine),
                "data": final.data or {},
                "raw_text": final.raw_text,
                "error_message": None,
                "multi_llm_comparison": parse_result.to_dict(),
            }
        return {
            "file_format": "unknown",
            "document_type": "unknown",
            "document_sub_type": None,
            "confidence": 0.0,
            "engine_type": "unknown",
            "data": {},
            "raw_text": None,
            "error_message": "多引擎对比未产生结果",
        }

    file_format = parse_result.file_format.value if hasattr(parse_result.file_format, "value") else str(parse_result.file_format) if parse_result.file_format else "unknown"
    return {
        "file_format": file_format,
        "document_type": parse_result.document_type.value if hasattr(parse_result.document_type, "value") else str(parse_result.document_type),
        "document_sub_type": (
            parse_result.sub_type.value
            if hasattr(parse_result.sub_type, "value") and parse_result.sub_type
            else str(parse_result.sub_type) if parse_result.sub_type else None
        ),
        "confidence": parse_result.confidence,
        "engine_type": parse_result.engine.value if hasattr(parse_result.engine, "value") else str(parse_result.engine),
        "data": parse_result.data or {},
        "raw_text": parse_result.raw_text,
        "error_message": "; ".join(parse_result.validation_errors) if parse_result.validation_errors else None,
    }


def get_latest_source_file(db: Session, job_id: int) -> SourceFile | None:
    return (
        db.query(SourceFile)
        .filter(SourceFile.import_job_id == job_id)
        .order_by(SourceFile.id.desc())
        .first()
    )


def build_parser_engine_summary(job: ImportJob, source_file: SourceFile, result_dict: dict) -> dict:
    return {
        "job_id": job.id,
        "total_files": 1,
        "success_files": 0 if result_dict.get("error_message") else 1,
        "failed_files": 1 if result_dict.get("error_message") else 0,
        "total_entries": 0,
        "output_path": "parser_engine_draft",
        "parser_engine_result": result_dict,
        "file_summary": [{
            "filename": source_file.filename,
            "type": "parser_engine_result",
            "success": not bool(result_dict.get("error_message")),
            "error": result_dict.get("error_message"),
            "entries": 0,
            "parse_diagnostics": {
                "source": "parser_engine",
                "document_type": result_dict.get("document_type"),
                "confidence": result_dict.get("confidence"),
                "engine_type": result_dict.get("engine_type"),
                "engine_comparison": result_dict.get("engine_comparison"),
                "multi_llm_comparison": result_dict.get("multi_llm_comparison"),
            },
        }],
    }


def parse_source_file_with_unified_engine(db: Session, job: ImportJob, source_file: SourceFile) -> tuple[dict, dict]:
    parse_start = performance_monitor.record_parse_start()
    dispatcher = ParserEngineDispatcher(db)
    source_path = resolve_storage_path(source_file.storage_path)
    parse_result = asyncio.run(dispatcher.parse(source_path))
    duration_ms = (time.time() - parse_start) * 1000
    result_dict = jsonable_encoder(convert_parse_result_to_dict(parse_result))
    result_dict["parse_duration_ms"] = round(duration_ms, 2)
    result_dict["stage_timings"] = {"统一解析引擎": round(duration_ms, 2)}
    result_dict["context"] = {
        "project_id": job.project_id,
        "ledger_id": job.ledger_id or source_file.ledger_id,
        "source_file_id": source_file.id,
        "import_job_id": job.id,
    }

    if source_file.ledger_id is None and job.ledger_id is not None:
        source_file.ledger_id = job.ledger_id

    source_file.text_extract_status = "extracted" if not result_dict.get("error_message") else "failed"
    source_file.extracted_text = json.dumps(
        {
            "parse_feedback": result_dict,
            "raw_text_preview": (result_dict.get("raw_text") or "")[:1000],
        },
        ensure_ascii=False,
    )

    summary = build_parser_engine_summary(job, source_file, result_dict)
    review_archive_result = auto_review_and_archive(db, job, source_file, result_dict)
    archive_result = review_archive_result["archive"]
    stage = (
        "unified_parser_engine_archived"
        if archive_result.get("archived")
        else "unified_parser_engine_manual_review_required"
    )
    summary["auto_review_result"] = review_archive_result["auto_review"]
    summary["archive_result"] = archive_result

    job.status = "draft"
    job.error_message = None if not result_dict.get("error_message") else str(result_dict.get("error_message"))
    job.draft_data = {
        "stage": stage,
        "parser_engine_result": result_dict,
        "auto_review_result": review_archive_result["auto_review"],
        "archive_result": archive_result,
        "context": {
            "project_id": job.project_id,
            "ledger_id": job.ledger_id or source_file.ledger_id,
            "source_file_id": source_file.id,
            "import_job_id": job.id,
        },
        "file_results": [{
            "filename": source_file.filename,
            "success": not bool(result_dict.get("error_message")),
            "error_message": result_dict.get("error_message"),
            "parse_diagnostics": summary["file_summary"][0]["parse_diagnostics"],
            "entries_created": 0,
        }],
        "total_entries": 0,
        "parsed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": f"parser-engine-{job.id}-{source_file.id}-{int(time.time())}",
    }
    db.commit()
    db.refresh(source_file)
    db.refresh(job)
    return result_dict, summary


def mark_parser_engine_failure(db: Session, job: ImportJob, source_file: SourceFile, error_message: str) -> None:
    source_file.text_extract_status = "failed"
    job.status = "draft"
    job.error_message = error_message
    job.draft_data = {
        "stage": "unified_parser_engine_failed",
        "error_message": error_message,
        "file_results": [{
            "filename": source_file.filename,
            "success": False,
            "error_message": error_message,
            "parse_diagnostics": {"source": "parser_engine"},
            "entries_created": 0,
        }],
        "request_id": f"parser-engine-{job.id}-{source_file.id}-{int(time.time())}",
    }
    db.commit()


def mark_missing_source_file(db: Session, job: ImportJob) -> None:
    job.status = "draft"
    job.error_message = "导入任务没有可解析的上传文件，请重新上传并使用统一解析引擎解析。"
    job.draft_data = {
        "stage": "unified_parser_engine_missing_source_file",
        "error_message": job.error_message,
        "file_results": [],
        "request_id": f"parser-engine-missing-file-{job.id}-{int(time.time())}",
    }
    db.commit()
    db.refresh(job)

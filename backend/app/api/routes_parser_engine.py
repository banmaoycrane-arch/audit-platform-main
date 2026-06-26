import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.models import Organization, SourceFile
from app.db.session import get_db
from app.core.config import get_settings
from app.schemas.parser_engine import (
    FileParseRequest,
    ParseResultResponse,
    LLMComparisonResponse,
    ParserEngineStatusResponse,
)

router = APIRouter(prefix="/api/parser-engine", tags=["parser-engine"])


def _ensure_organization(db: Session, organization_id: int) -> None:
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="组织不存在")


def _convert_parse_result_to_dict(parse_result: Any) -> dict[str, Any]:
    from app.services.parser_engine.parse_result import (
        ParseResult,
        LLMComparisonResult,
    )
    
    if isinstance(parse_result, dict) and "final_result" in parse_result:
        final = parse_result["final_result"]
        if final:
            file_format = final.file_format.value if hasattr(final.file_format, 'value') else str(final.file_format) if final.file_format else "unknown"
            return {
                "file_format": file_format,
                "document_type": final.document_type.value if hasattr(final.document_type, 'value') else str(final.document_type),
                "document_sub_type": (
                    final.sub_type.value
                    if hasattr(final.sub_type, 'value') and final.sub_type
                    else str(final.sub_type) if final.sub_type else None
                ),
                "confidence": final.confidence,
                "engine_type": final.engine.value if hasattr(final.engine, 'value') else str(final.engine),
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
                },
            }
        else:
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
            file_format = final.file_format.value if hasattr(final.file_format, 'value') else str(final.file_format) if final.file_format else "unknown"
            return {
                "file_format": file_format,
                "document_type": final.document_type.value if hasattr(final.document_type, 'value') else str(final.document_type),
                "document_sub_type": (
                    final.sub_type.value
                    if hasattr(final.sub_type, 'value') and final.sub_type
                    else str(final.sub_type) if final.sub_type else None
                ),
                "confidence": final.confidence,
                "engine_type": final.engine.value if hasattr(final.engine, 'value') else str(final.engine),
                "data": final.data or {},
                "raw_text": final.raw_text,
                "error_message": None,
                "multi_llm_comparison": parse_result.to_dict(),
            }
        else:
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
    
    file_format = parse_result.file_format.value if hasattr(parse_result.file_format, 'value') else str(parse_result.file_format) if parse_result.file_format else "unknown"
    return {
        "file_format": file_format,
        "document_type": parse_result.document_type.value if hasattr(parse_result.document_type, 'value') else str(parse_result.document_type),
        "document_sub_type": (
            parse_result.sub_type.value
            if hasattr(parse_result.sub_type, 'value') and parse_result.sub_type
            else str(parse_result.sub_type) if parse_result.sub_type else None
        ),
        "confidence": parse_result.confidence,
        "engine_type": parse_result.engine.value if hasattr(parse_result.engine, 'value') else str(parse_result.engine),
        "data": parse_result.data or {},
        "raw_text": parse_result.raw_text,
        "error_message": "; ".join(parse_result.validation_errors) if parse_result.validation_errors else None,
    }


@router.get("/status", response_model=ParserEngineStatusResponse)
def get_parser_engine_status() -> ParserEngineStatusResponse:
    """获取解析引擎状态和配置信息"""
    settings = get_settings()
    
    from app.services.parser_engine import (
        FileFormat,
        DocumentType,
    )
    
    supported_formats = [fmt.value for fmt in FileFormat]
    supported_document_types = [doc_type.value for doc_type in DocumentType]
    
    return ParserEngineStatusResponse(
        status="running",
        llm_multi_engine_enabled=settings.llm_multi_engine_enabled,
        llm_enable_parallel_parsing=settings.llm_enable_parallel_parsing,
        llm_max_concurrent_models=settings.llm_max_concurrent_models,
        llm_preferred_model=settings.llm_preferred_model,
        llm_comparison_strategy=settings.llm_comparison_strategy,
        supported_formats=supported_formats,
        supported_document_types=supported_document_types,
    )


@router.post("/list-excel-sheets")
def list_excel_sheets_endpoint(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    获取Excel文件的工作表列表
    
    - 上传Excel文件，返回所有工作表名称
    - 用于让用户选择要解析的工作表
    """
    import os
    import tempfile
    
    suffix = os.path.splitext(file.filename or "")[1].lower()
    
    if suffix not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="仅支持Excel文件（.xlsx/.xls）")
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file.file.read())
            temp_path = tmp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    try:
        import pandas as pd
        
        excel_file = pd.ExcelFile(temp_path)
        sheet_names = excel_file.sheet_names
        
        sheets_info = []
        for sheet_name in sheet_names:
            df = pd.read_excel(temp_path, sheet_name=sheet_name, nrows=5)
            rows_count = len(pd.read_excel(temp_path, sheet_name=sheet_name))
            sheets_info.append({
                "name": sheet_name,
                "rows": rows_count,
                "columns": list(df.columns),
                "preview": df.head(3).to_dict(orient="records"),
            })
        
        return {
            "success": True,
            "sheet_count": len(sheet_names),
            "sheets": sheets_info,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取Excel失败: {str(e)}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.post("/parse-file", response_model=ParseResultResponse)
def parse_file_endpoint(
    organization_id: int = Form(...),
    file: UploadFile = File(...),
    sheet_name: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ParseResultResponse:
    """
    上传并解析文件，使用统一解析引擎
    
    - 支持格式：PDF、Excel、CSV、XML、OFD、图片、Word、TXT
    - 自动识别文件格式和文档类型
    - 支持双引擎并行和多LLM对比
    - Excel文件可通过sheet_name指定工作表
    """
    import os
    import tempfile
    
    _ensure_organization(db, organization_id)
    
    settings = get_settings()
    
    suffix = os.path.splitext(file.filename or "")[1].lower()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file.file.read())
            temp_path = tmp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    try:
        import asyncio
        from app.services.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher
        
        start_time = time.time()
        
        dispatcher = ParserEngineDispatcher(db)
        
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                parse_result = loop.run_until_complete(dispatcher.parse(temp_path, sheet_name=sheet_name))
            else:
                parse_result = asyncio.run(dispatcher.parse(temp_path, sheet_name=sheet_name))
        except RuntimeError:
            parse_result = asyncio.run(dispatcher.parse(temp_path, sheet_name=sheet_name))
        
        duration_ms = (time.time() - start_time) * 1000
        
        result_dict = _convert_parse_result_to_dict(parse_result)
        result_dict["parse_duration_ms"] = round(duration_ms, 2)
        
        return ParseResultResponse(**result_dict)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.post("/parse-source-file/{file_id}", response_model=ParseResultResponse)
def parse_source_file(file_id: int, db: Session = Depends(get_db)) -> ParseResultResponse:
    """
    对已上传的源文件进行解析
    
    - 使用新的统一解析引擎
    - 自动识别文档类型
    - 支持多引擎对比
    """
    source_file = db.get(SourceFile, file_id)
    if not source_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    import os
    if not os.path.exists(source_file.storage_path):
        raise HTTPException(status_code=404, detail="文件物理路径不存在")
    
    try:
        import asyncio
        from app.services.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher
        
        start_time = time.time()
        
        dispatcher = ParserEngineDispatcher(db)
        
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                parse_result = loop.run_until_complete(dispatcher.parse(source_file.storage_path))
            else:
                parse_result = asyncio.run(dispatcher.parse(source_file.storage_path))
        except RuntimeError:
            parse_result = asyncio.run(dispatcher.parse(source_file.storage_path))
        
        duration_ms = (time.time() - start_time) * 1000
        
        result_dict = _convert_parse_result_to_dict(parse_result)
        result_dict["parse_duration_ms"] = round(duration_ms, 2)
        
        return ParseResultResponse(**result_dict)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/multi-llm-compare", response_model=LLMComparisonResponse)
def multi_llm_compare(
    file_id: int = Form(...),
    db: Session = Depends(get_db),
) -> LLMComparisonResponse:
    """
    对文件进行多LLM引擎对比解析
    
    - 并行调用多个LLM引擎
    - 加权投票选择最优结果
    - 显示各引擎结果对比
    """
    source_file = db.get(SourceFile, file_id)
    if not source_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    import os
    if not os.path.exists(source_file.storage_path):
        raise HTTPException(status_code=404, detail="文件物理路径不存在")
    
    try:
        import asyncio
        from app.services.parser_engine import format_recognizer
        from app.services.parser_engine import document_type_classifier
        from app.services.parser_engine.parser_engine_dispatcher import (
            multi_llm_comparison,
            extract_text_from_file,
        )
        
        start_time = time.time()
        
        format_result = format_recognizer.recognize_format(source_file.storage_path)
        type_result = document_type_classifier.classify_document_type(
            source_file.storage_path,
            source_file.filename,
            format_result.file_format,
        )
        extracted_text = extract_text_from_file(
            source_file.storage_path,
            format_result.file_format,
        )
        
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                comparison_result = loop.run_until_complete(
                    multi_llm_comparison(
                        source_file.storage_path,
                        type_result.document_type,
                        extracted_text,
                    )
                )
            else:
                comparison_result = asyncio.run(
                    multi_llm_comparison(
                        source_file.storage_path,
                        type_result.document_type,
                        extracted_text,
                    )
                )
        except RuntimeError:
            comparison_result = asyncio.run(
                multi_llm_comparison(
                    source_file.storage_path,
                    type_result.document_type,
                    extracted_text,
                )
            )
        
        total_duration_ms = (time.time() - start_time) * 1000
        
        engine_results = []
        for er in comparison_result.engine_results:
            engine_results.append({
                "engine_id": er.engine_id,
                "engine_type": er.engine_type.value if hasattr(er.engine_type, 'value') else str(er.engine_type),
                "confidence": er.confidence,
                "result_data": er.result_data,
                "parse_duration_ms": er.parse_duration_ms,
            })
        
        return LLMComparisonResponse(
            document_type=comparison_result.document_type.value if hasattr(comparison_result.document_type, 'value') else str(comparison_result.document_type),
            final_result=comparison_result.final_result,
            final_confidence=comparison_result.final_confidence,
            comparison_strategy=comparison_result.comparison_strategy,
            field_consistency_rate=comparison_result.field_consistency_rate,
            engine_results=engine_results,
            total_duration_ms=round(total_duration_ms, 2),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"多引擎对比失败: {str(e)}")


@router.get("/performance-stats")
def get_performance_statistics() -> dict[str, Any]:
    """
    获取解析引擎性能统计数据
    
    - 总解析次数、成功率、失败率
    - 各阶段耗时统计（格式识别、类型判断、文本提取、解析执行）
    - 按文件格式统计平均耗时
    - 按文档类型统计平均耗时
    - 错误类型分布
    """
    from app.services.parser_engine import get_performance_stats
    return get_performance_stats()


@router.post("/performance-stats/reset")
def reset_performance_statistics() -> dict[str, Any]:
    """重置解析引擎性能统计数据"""
    from app.services.parser_engine import reset_performance_stats
    reset_performance_stats()
    return {"status": "success", "message": "性能统计数据已重置"}

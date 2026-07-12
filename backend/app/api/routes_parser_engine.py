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
    ParserQualityDashboardResponse,
)
from app.services.doc_parsing.parser_engine.unified_parser_service import convert_parse_result_to_dict
from app.services.doc_parsing.parser_engine.parse_quality_metric_service import get_quality_dashboard
from app.storage.local_storage import resolve_storage_path

router = APIRouter(prefix="/api/parser-engine", tags=["parser-engine"])


def _ensure_organization(db: Session, organization_id: int) -> None:
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="组织不存在")


def _convert_parse_result_to_dict(parse_result: Any) -> dict[str, Any]:
    return convert_parse_result_to_dict(parse_result)


@router.get("/status", response_model=ParserEngineStatusResponse)
def get_parser_engine_status() -> ParserEngineStatusResponse:
    """获取解析引擎状态和配置信息"""
    settings = get_settings()
    
    from app.services.doc_parsing.parser_engine.parse_result import (
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
        llm_knowledge_base=settings.llm_knowledge_base or None,
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
async def parse_file_endpoint(
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
        from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher, performance_monitor
        
        parse_start = performance_monitor.record_parse_start()
        stage_start = time.time()
        
        dispatcher = ParserEngineDispatcher(db)
        performance_monitor.record_stage_duration(
            "初始化调度器",
            (time.time() - stage_start) * 1000,
        )
        
        stage_start = time.time()
        parse_result = await dispatcher.parse(temp_path, sheet_name=sheet_name)
        performance_monitor.record_stage_duration(
            "解析执行",
            (time.time() - stage_start) * 1000,
        )
        
        duration_ms = (time.time() - parse_start) * 1000
        
        result_dict = _convert_parse_result_to_dict(parse_result)
        result_dict["parse_duration_ms"] = round(duration_ms, 2)
        result_dict["stage_timings"] = {
            "文件保存": round((stage_start - parse_start) * 1000, 2),
            "解析执行": round(result_dict["parse_duration_ms"], 2),
        }
        
        performance_monitor.record_parse_complete(
            result_dict.get("file_format") or "unknown",
            result_dict.get("document_type") or "unknown",
            duration_ms,
            not bool(result_dict.get("error_message")),
            result_dict.get("error_message") or None,
        )
        
        return ParseResultResponse(**result_dict)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.post("/parse-source-file/{file_id}", response_model=ParseResultResponse)
async def parse_source_file(file_id: int, db: Session = Depends(get_db)) -> ParseResultResponse:
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
    source_path = resolve_storage_path(source_file.storage_path)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="文件物理路径不存在")
    
    try:
        from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher
        
        start_time = time.time()
        
        dispatcher = ParserEngineDispatcher(db)
        parse_result = await dispatcher.parse(source_path)
        
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
    source_path = resolve_storage_path(source_file.storage_path)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="文件物理路径不存在")
    
    try:
        import asyncio
        from app.services.doc_parsing.parser_engine import format_recognizer
        from app.services.doc_parsing.parser_engine import document_type_classifier
        from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import (
            multi_llm_comparison,
            extract_text_from_file,
        )
        
        start_time = time.time()
        
        format_result = format_recognizer.recognize_file_format(source_path)
        type_result = document_type_classifier.classify_document_type(
            source_path,
            format_result.file_format,
        )
        extracted_text = extract_text_from_file(
            source_path,
            format_result.file_format,
        )
        
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                comparison_result = loop.run_until_complete(
                    multi_llm_comparison(
                        source_path,
                        type_result.document_type,
                        extracted_text,
                    )
                )
            else:
                comparison_result = asyncio.run(
                    multi_llm_comparison(
                        source_path,
                        type_result.document_type,
                        extracted_text,
                    )
                )
        except RuntimeError:
            comparison_result = asyncio.run(
                multi_llm_comparison(
                    source_path,
                    type_result.document_type,
                    extracted_text,
                )
            )
        
        total_duration_ms = (time.time() - start_time) * 1000
        
        engine_results = []
        for engine_id, er in comparison_result.engine_results.items():
            if er:
                engine_results.append({
                    "engine_id": engine_id,
                    "engine_type": er.engine.value if hasattr(er.engine, 'value') else str(er.engine),
                    "confidence": er.confidence,
                    "result_data": er.data,
                    "parse_duration_ms": getattr(er, 'parse_duration_ms', 0),
                })
        
        final_result_data = comparison_result.final_result.data if comparison_result.final_result else {}
        final_confidence = comparison_result.final_result.confidence if comparison_result.final_result else 0.0
        
        return LLMComparisonResponse(
            document_type=comparison_result.final_result.document_type.value if comparison_result.final_result else "",
            final_result=final_result_data,
            final_confidence=final_confidence,
            comparison_strategy="",
            field_consistency_rate=0.0,
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
    from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import get_performance_stats
    return get_performance_stats()


@router.post("/performance-stats/reset")
def reset_performance_statistics() -> dict[str, Any]:
    """重置解析引擎性能统计数据"""
    from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import reset_performance_stats
    reset_performance_stats()
    return {"status": "success", "message": "性能统计数据已重置"}


@router.get("/quality-dashboard", response_model=ParserQualityDashboardResponse)
def get_parser_quality_dashboard(
    start_date: str | None = None,
    end_date: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
) -> ParserQualityDashboardResponse:
    """
    获取解析稳定性指标看板数据

    - 总体解析次数与复核率
    - 字段准确率、文档完整率、一致性率、稳定性评分
    - 按日期/文档类型的趋势数据
    """
    dashboard_data = get_quality_dashboard(
        db=db,
        start_date=start_date,
        end_date=end_date,
        document_type=document_type,
    )
    return ParserQualityDashboardResponse(**dashboard_data)

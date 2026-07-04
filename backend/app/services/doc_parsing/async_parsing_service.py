# -*- coding: utf-8 -*-
"""
模块功能：文档解析异步任务管理服务
业务场景：处理大批量文档解析、向量嵌入等耗时操作的异步调度与状态管理
政策依据：无
输入数据：文件列表、解析配置、组织/账簿上下文
输出结果：异步任务状态、解析进度、解析结果
创建日期：2025-01-20
更新记录：
    2025-01-20  初始化异步任务管理服务
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session

from app.db.models import DocumentParsingTask, Organization, SourceFile


class AsyncParsingService:
    """
    文档解析异步任务管理服务
    
    功能描述：提供文档解析任务的异步调度、状态跟踪和结果查询能力
    业务逻辑：将大批量文档解析任务拆分为异步任务，支持任务状态查询和结果获取
    会计口径：无特殊会计口径要求
    
    注意事项：
        1. 异步任务通过数据库表记录状态，不依赖外部消息队列
        2. 任务完成后结果存储在output_result字段中
        3. 支持最大重试次数配置
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_parsing_task(
        self,
        organization_id: int,
        task_type: str,
        input_params: Dict[str, Any],
        ledger_id: Optional[int] = None,
        import_job_id: Optional[int] = None,
        total_files: int = 0
    ) -> DocumentParsingTask:
        """
        创建文档解析任务
        
        Args:
            organization_id: 组织ID
            task_type: 任务类型 (single_file/batch_files/embedding/indexing)
            input_params: 输入参数
            ledger_id: 账簿ID（可选）
            import_job_id: 导入作业ID（可选）
            total_files: 待处理文件总数
        
        Returns:
            DocumentParsingTask: 创建的任务记录
        """
        task = DocumentParsingTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            organization_id=organization_id,
            ledger_id=ledger_id,
            import_job_id=import_job_id,
            input_params=input_params,
            total_files=total_files,
            status="pending",
            progress=0,
            processed_files=0,
            failed_files=0,
            retry_count=0,
            max_retries=3,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def get_task_by_id(self, task_id: str) -> Optional[DocumentParsingTask]:
        """
        根据任务ID获取任务信息
        
        Args:
            task_id: 任务唯一标识
        
        Returns:
            Optional[DocumentParsingTask]: 任务记录，如果不存在返回None
        """
        return self.db.query(DocumentParsingTask).filter(
            DocumentParsingTask.task_id == task_id
        ).first()
    
    def get_tasks_by_organization(
        self,
        organization_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[DocumentParsingTask]:
        """
        获取指定组织的任务列表
        
        Args:
            organization_id: 组织ID
            status: 任务状态过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
        
        Returns:
            List[DocumentParsingTask]: 任务列表
        """
        query = self.db.query(DocumentParsingTask).filter(
            DocumentParsingTask.organization_id == organization_id
        )
        if status:
            query = query.filter(DocumentParsingTask.status == status)
        return query.order_by(DocumentParsingTask.created_at.desc()).offset(offset).limit(limit).all()
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态 (pending/running/completed/failed/canceled)
        """
        task = self.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.status = status
        
        if status == "running" and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status in ("completed", "failed", "canceled") and not task.completed_at:
            task.completed_at = datetime.utcnow()
        
        self.db.commit()
    
    def update_task_progress(
        self,
        task_id: str,
        processed_files: int,
        failed_files: int = 0,
        total_files: Optional[int] = None
    ) -> None:
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            processed_files: 已处理文件数
            failed_files: 失败文件数
            total_files: 总文件数（可选，用于计算进度百分比）
        """
        task = self.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.processed_files = processed_files
        task.failed_files = failed_files
        
        if total_files:
            task.total_files = total_files
        
        if task.total_files > 0:
            task.progress = min(
                100,
                int((task.processed_files / task.total_files) * 100)
            )
        
        self.db.commit()
    
    def update_task_result(
        self,
        task_id: str,
        output_result: Dict[str, Any],
        error_message: Optional[str] = None
    ) -> None:
        """
        更新任务结果
        
        Args:
            task_id: 任务ID
            output_result: 任务输出结果
            error_message: 错误信息（可选）
        """
        task = self.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.output_result = output_result
        
        if error_message:
            task.error_message = error_message
            task.status = "failed"
            task.completed_at = datetime.utcnow()
        else:
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.progress = 100
        
        self.db.commit()
    
    def increment_retry_count(self, task_id: str) -> bool:
        """
        增加重试次数，判断是否可以继续重试
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否可以继续重试
        """
        task = self.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        task.retry_count += 1
        
        if task.retry_count >= task.max_retries:
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            self.db.commit()
            return False
        
        self.db.commit()
        return True
    
    async def execute_parsing_task(
        self,
        task_id: str,
        parsing_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        异步执行解析任务
        
        Args:
            task_id: 任务ID
            parsing_func: 解析函数
            *args: 解析函数位置参数
            **kwargs: 解析函数关键字参数
        
        Returns:
            Any: 解析结果
        """
        self.update_task_status(task_id, "running")
        
        try:
            result = await asyncio.to_thread(parsing_func, *args, **kwargs)
            
            self.update_task_result(task_id, {"result": result})
            return result
        
        except Exception as e:
            can_retry = self.increment_retry_count(task_id)
            
            if can_retry:
                self.update_task_status(task_id, "pending")
            else:
                self.update_task_result(task_id, {}, str(e))
            
            raise
    
    async def execute_batch_parsing(
        self,
        task_id: str,
        file_paths: List[str],
        parse_single_file: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        异步执行批量文件解析
        
        Args:
            task_id: 任务ID
            file_paths: 文件路径列表
            parse_single_file: 单文件解析函数
            *args: 解析函数位置参数
            **kwargs: 解析函数关键字参数
        
        Returns:
            Dict[str, Any]: 批量解析结果汇总
        """
        self.update_task_status(task_id, "running")
        total_files = len(file_paths)
        results = []
        failed_files = []
        
        for idx, file_path in enumerate(file_paths):
            try:
                result = await asyncio.to_thread(parse_single_file, file_path, *args, **kwargs)
                results.append({"file_path": file_path, "success": True, "result": result})
            except Exception as e:
                failed_files.append({"file_path": file_path, "error": str(e)})
                results.append({"file_path": file_path, "success": False, "error": str(e)})
            
            self.update_task_progress(
                task_id,
                processed_files=idx + 1,
                failed_files=len(failed_files),
                total_files=total_files
            )
        
        final_result = {
            "total_files": total_files,
            "success_count": len(results) - len(failed_files),
            "failed_count": len(failed_files),
            "failed_files": failed_files,
            "results": results,
        }
        
        self.update_task_result(task_id, final_result)
        return final_result
    
    async def execute_concurrent_parsing(
        self,
        task_id: str,
        file_paths: List[str],
        parse_single_file: Callable[..., Any],
        max_concurrent: int = 4,
        *args: Any,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        并发执行批量文件解析（使用asyncio并发）
        
        Args:
            task_id: 任务ID
            file_paths: 文件路径列表
            parse_single_file: 单文件解析函数
            max_concurrent: 最大并发数
            *args: 解析函数位置参数
            **kwargs: 解析函数关键字参数
        
        Returns:
            Dict[str, Any]: 批量解析结果汇总
        """
        self.update_task_status(task_id, "running")
        total_files = len(file_paths)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def parse_with_semaphore(file_path: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await asyncio.to_thread(parse_single_file, file_path, *args, **kwargs)
                    return {"file_path": file_path, "success": True, "result": result}
                except Exception as e:
                    return {"file_path": file_path, "success": False, "error": str(e)}
        
        tasks = [parse_with_semaphore(fp) for fp in file_paths]
        results = []
        completed_count = 0
        failed_count = 0
        
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
            completed_count += 1
            if not result["success"]:
                failed_count += 1
            
            self.update_task_progress(
                task_id,
                processed_files=completed_count,
                failed_files=failed_count,
                total_files=total_files
            )
        
        final_result = {
            "total_files": total_files,
            "success_count": completed_count - failed_count,
            "failed_count": failed_count,
            "failed_files": [r for r in results if not r["success"]],
            "results": results,
        }
        
        self.update_task_result(task_id, final_result)
        return final_result

# -*- coding: utf-8 -*-
"""
模块功能：生命周期日志查询 API 路由
业务场景：前端调用查询 Ledger 或 Project 的生命周期变更历史
政策依据：会计信息系统内部控制规范——操作日志必须可查询、可导出
输入数据：HTTP 请求（查询参数）
输出结果：生命周期日志 JSON 数据
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建生命周期日志路由
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import lifecycle_service

router = APIRouter(prefix="/api/lifecycle-logs", tags=["lifecycle-logs"])


class LifecycleLogResponse(BaseModel):
    """生命周期日志响应体"""
    id: int
    entity_type: str
    entity_id: int
    action: str
    previous_status: str | None
    new_status: str | None
    reason: str | None
    log_metadata: dict
    operator_id: int | None
    created_at: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[LifecycleLogResponse])
def list_lifecycle_logs(
    entity_type: str | None = Query(None, description="实体类型：ledger / project"),
    entity_id: int | None = Query(None, description="实体ID"),
    action: str | None = Query(None, description="操作动作"),
    limit: int = Query(100, ge=1, le=500, description="返回数量上限"),
    offset: int = Query(0, ge=0, description="跳过数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LifecycleLogResponse]:
    """
    查询生命周期日志列表。

    支持按 entity_type、entity_id、action 筛选，支持分页。
    """
    logs = lifecycle_service.list_lifecycle_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return [
        LifecycleLogResponse(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            previous_status=log.previous_status,
            new_status=log.new_status,
            reason=log.reason,
            log_metadata=log.log_metadata or {},
            operator_id=log.operator_id,
            created_at=str(log.created_at) if log.created_at else None,
        )
        for log in logs
    ]

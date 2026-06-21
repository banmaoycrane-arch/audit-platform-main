# -*- coding: utf-8 -*-
"""
模块功能：团队管理 API 路由
业务场景：前端调用创建团队、查询团队列表、查询团队成员、添加团队成员
政策依据：会计信息系统内部控制规范——团队隔离与成员权限管理
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：团队 JSON 数据、成员 JSON 数据
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建团队管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import ledger_management_service

router = APIRouter(prefix="/api/teams", tags=["teams"])


class CreateTeamRequest(BaseModel):
    """创建团队请求体"""
    name: str
    type: str


class AddTeamMemberRequest(BaseModel):
    """添加团队成员请求体"""
    user_id: int | None = None
    username: str | None = None
    phone: str | None = None
    role: str = "member"


class TeamResponse(BaseModel):
    """团队响应体"""
    id: int
    name: str
    type: str
    created_at: str | None

    model_config = {"from_attributes": True}


class TeamMemberResponse(BaseModel):
    """团队成员响应体"""
    id: int
    username: str | None
    email: str | None
    phone: str | None
    team_id: int | None

    model_config = {"from_attributes": True}


@router.post("", response_model=TeamResponse)
def create_team(
    payload: CreateTeamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    """
    创建团队。

    需要 name 和 type。
    创建后自动将当前用户归属到该团队。
    """
    team = ledger_management_service.create_team(db, payload.name, payload.type)

    # 自动将创建者归属到该团队
    current_user.team_id = team.id
    db.commit()
    db.refresh(current_user)

    return TeamResponse(
        id=team.id,
        name=team.name,
        type=team.type,
        created_at=str(team.created_at) if team.created_at else None,
    )


@router.get("", response_model=list[TeamResponse])
def list_user_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamResponse]:
    """
    返回当前用户所属团队列表。
    """
    teams = ledger_management_service.get_teams_by_user(db, current_user.id)
    return [
        TeamResponse(
            id=team.id,
            name=team.name,
            type=team.type,
            created_at=str(team.created_at) if team.created_at else None,
        )
        for team in teams
    ]


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
def list_team_members(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamMemberResponse]:
    """
    返回团队成员列表。

    当前用户必须属于该团队才能查看成员。
    """
    # 验证当前用户是否属于该团队
    user_teams = ledger_management_service.get_teams_by_user(db, current_user.id)
    if not any(team.id == team_id for team in user_teams):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看该团队成员",
        )

    members = ledger_management_service.get_team_members(db, team_id)
    return [
        TeamMemberResponse(
            id=member.id,
            username=member.username,
            email=member.email,
            phone=member.phone,
            team_id=member.team_id,
        )
        for member in members
    ]


@router.post("/{team_id}/members", response_model=TeamMemberResponse)
def add_team_member(
    team_id: int,
    payload: AddTeamMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    """
    添加成员到团队。

    支持通过 user_id、username 或 phone 定位用户。
    当前用户必须属于该团队才能添加成员。
    """
    if not payload.user_id and not payload.username and not payload.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供 user_id、username 或 phone 中的任意一项",
        )

    # 验证当前用户是否属于该团队
    user_teams = ledger_management_service.get_teams_by_user(db, current_user.id)
    if not any(team.id == team_id for team in user_teams):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权向该团队添加成员",
        )

    try:
        member = ledger_management_service.add_team_member(
            db,
            team_id,
            payload.role,
            user_id=payload.user_id,
            username=payload.username,
            phone=payload.phone,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return TeamMemberResponse(
        id=member.id,
        username=member.username,
        email=member.email,
        phone=member.phone,
        team_id=member.team_id,
    )


class TeamHierarchyResponse(BaseModel):
    """团队层级响应体"""
    id: int
    name: str
    type: str
    parent_team_id: int | None
    sub_team_count: int
    created_at: str | None

    model_config = {"from_attributes": True}


@router.get("/{team_id}/sub-teams", response_model=list[TeamHierarchyResponse])
def list_sub_teams(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamHierarchyResponse]:
    """
    获取团队的直接子团队列表。

    功能描述：
        1. 查询指定团队的直接下级子团队
        2. 返回每个子团队的基本信息和子团队数量

    Args:
        team_id: 团队ID

    Returns:
        list[TeamHierarchyResponse]: 子团队列表
    """
    from app.models.team import Team
    
    # 验证团队是否存在
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="团队不存在")

    # 获取直接子团队
    sub_teams = db.query(Team).filter(Team.parent_team_id == team_id).all()
    
    return [
        TeamHierarchyResponse(
            id=sub.id,
            name=sub.name,
            type=sub.type,
            parent_team_id=sub.parent_team_id,
            sub_team_count=len(sub.sub_teams) if hasattr(sub, 'sub_teams') else 0,
            created_at=str(sub.created_at) if sub.created_at else None,
        )
        for sub in sub_teams
    ]


@router.get("/{team_id}/hierarchy")
def get_team_hierarchy(
    team_id: int,
    depth: int = 3,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取团队的层级结构。

    功能描述：
        1. 向上追溯到根团队
        2. 向下递归获取子团队（受 depth 限制）

    Args:
        team_id: 团队ID
        depth: 向下递归深度，默认3层

    Returns:
        dict: 包含团队层级结构
    """
    from app.models.team import Team
    
    def build_hierarchy(team: Team, current_depth: int, max_depth: int) -> dict:
        result = {
            "id": team.id,
            "name": team.name,
            "type": team.type,
            "parent_team_id": team.parent_team_id,
            "children": [],
        }
        
        if current_depth < max_depth:
            sub_teams = db.query(Team).filter(Team.parent_team_id == team.id).all()
            for sub in sub_teams:
                result["children"].append(build_hierarchy(sub, current_depth + 1, max_depth))
        
        return result

    # 验证团队是否存在
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="团队不存在")

    # 向上追溯到根
    root = team
    while root.parent_team_id:
        parent = db.query(Team).filter(Team.id == root.parent_team_id).first()
        if parent:
            root = parent
        else:
            break

    hierarchy = build_hierarchy(root, 0, depth)
    
    return {
        "root_team": hierarchy,
        "target_team_id": team_id,
        "depth_requested": depth,
    }

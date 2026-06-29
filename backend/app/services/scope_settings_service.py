"""账簿 / 团队 / 项目 / 主体 管理配置服务。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.scope_settings import (
    EntityScopeSettings,
    LedgerSettings,
    ProjectSettings,
    TeamSettings,
)

CurrencyMode = Literal["single", "multi"]
BalanceDirectionRule = Literal["strict", "natural"]
AccountCodePattern = Literal["4-2-2-2", "3-3-2-2"]
LedgerGrantPolicy = Literal["admin_only", "manager_can_grant"]
EntityCategoryDefault = Literal["operating", "holding", "branch"]

DEFAULT_LEDGER_SETTINGS: dict[str, Any] = {
    "currency_mode": "single",
    "base_currency": "CNY",
    "balance_direction_rule": "strict",
    "account_code_pattern": "4-2-2-2",
    "allow_custom_subjects": True,
}

DEFAULT_TEAM_SETTINGS: dict[str, Any] = {
    "allow_multi_team_membership": False,
    "require_binding_approval": True,
    "default_ledger_role": "viewer",
    "ledger_grant_policy": "admin_only",
    "team_roles_enabled": ["admin", "manager", "member", "viewer"],
}

DEFAULT_PROJECT_SETTINGS: dict[str, Any] = {
    "allow_merge": False,
    "allow_virtual_project": True,
    "virtual_project_label": "虚拟项目",
    "require_manager_on_create": True,
}

DEFAULT_ENTITY_SCOPE_SETTINGS: dict[str, Any] = {
    "allow_virtual_entity": True,
    "require_tax_registration": False,
    "default_entity_category": "operating",
    "allow_multi_entity_per_ledger": True,
}

SETTINGS_CATALOG: dict[str, Any] = {
    "ledger": {
        "label": "账簿配置",
        "description": "会计政策、会计假设与核算习惯",
        "fields": {
            "currency_mode": {
                "label": "币种模式",
                "type": "select",
                "options": [
                    {"value": "single", "label": "单一币种"},
                    {"value": "multi", "label": "多币种"},
                ],
            },
            "base_currency": {
                "label": "本位币",
                "type": "text",
                "depends_on": {"currency_mode": "multi"},
            },
            "balance_direction_rule": {
                "label": "余额方向规则",
                "type": "select",
                "options": [
                    {"value": "strict", "label": "账簿余额与借贷方向强制一致"},
                    {"value": "natural", "label": "按科目最终方向定义余额"},
                ],
            },
            "account_code_pattern": {
                "label": "科目代码层级",
                "type": "select",
                "options": [
                    {"value": "4-2-2-2", "label": "4-2-2-2（如 1002.01.01.01）"},
                    {"value": "3-3-2-2", "label": "3-3-2-2（如 100.200.01.01）"},
                ],
            },
            "allow_custom_subjects": {
                "label": "允许自定义会计科目",
                "type": "boolean",
            },
        },
    },
    "team": {
        "label": "团队配置",
        "description": "成员兼任与权限策略",
        "fields": {
            "allow_multi_team_membership": {
                "label": "允许用户兼任多个团队",
                "type": "boolean",
            },
            "require_binding_approval": {
                "label": "加入团队需审批",
                "type": "boolean",
            },
            "default_ledger_role": {
                "label": "新授权默认账簿角色",
                "type": "select",
                "options": [
                    {"value": "admin", "label": "管理员"},
                    {"value": "accountant", "label": "记账员"},
                    {"value": "viewer", "label": "查看者"},
                ],
            },
            "ledger_grant_policy": {
                "label": "账簿授权策略",
                "type": "select",
                "options": [
                    {"value": "admin_only", "label": "仅账簿管理员可授权"},
                    {"value": "manager_can_grant", "label": "团队经理可授权"},
                ],
            },
        },
    },
    "project": {
        "label": "项目配置",
        "description": "项目合并与虚拟项目策略",
        "fields": {
            "allow_merge": {
                "label": "允许合并项目",
                "type": "boolean",
            },
            "allow_virtual_project": {
                "label": "允许定义虚拟项目",
                "type": "boolean",
            },
            "virtual_project_label": {
                "label": "虚拟项目展示名称",
                "type": "text",
                "depends_on": {"allow_virtual_project": True},
            },
            "require_manager_on_create": {
                "label": "创建项目必须指定负责人",
                "type": "boolean",
            },
        },
    },
    "entity": {
        "label": "主体配置",
        "description": "会计主体与纳税主体管理策略",
        "fields": {
            "allow_virtual_entity": {
                "label": "允许虚拟主体",
                "type": "boolean",
            },
            "require_tax_registration": {
                "label": "创建主体必须填写税务登记号",
                "type": "boolean",
            },
            "default_entity_category": {
                "label": "默认主体类别",
                "type": "select",
                "options": [
                    {"value": "operating", "label": "经营实体"},
                    {"value": "holding", "label": "控股主体"},
                    {"value": "branch", "label": "分支机构"},
                ],
            },
            "allow_multi_entity_per_ledger": {
                "label": "账簿下允许多个会计主体",
                "type": "boolean",
            },
        },
    },
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _merge_defaults(defaults: dict[str, Any], stored: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(defaults)
    if stored:
        merged.update(stored)
    return merged


def get_settings_catalog() -> dict[str, Any]:
    return SETTINGS_CATALOG


def get_ledger_settings(db: Session, ledger_id: int) -> dict[str, Any]:
    row = db.query(LedgerSettings).filter(LedgerSettings.ledger_id == ledger_id).first()
    settings = _merge_defaults(DEFAULT_LEDGER_SETTINGS, row.settings if row else None)
    return {
        "scope": "ledger",
        "ledger_id": ledger_id,
        "settings": settings,
        "created_at": _iso(row.created_at) if row else None,
        "updated_at": _iso(row.updated_at) if row else None,
    }


def upsert_ledger_settings(db: Session, ledger_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    row = db.query(LedgerSettings).filter(LedgerSettings.ledger_id == ledger_id).first()
    if row is None:
        row = LedgerSettings(ledger_id=ledger_id, settings={})
        db.add(row)
    current = _merge_defaults(DEFAULT_LEDGER_SETTINGS, row.settings)
    current.update({k: v for k, v in patch.items() if k in DEFAULT_LEDGER_SETTINGS})
    row.settings = current
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return get_ledger_settings(db, ledger_id)


def get_team_settings(db: Session, team_id: int) -> dict[str, Any]:
    row = db.query(TeamSettings).filter(TeamSettings.team_id == team_id).first()
    settings = _merge_defaults(DEFAULT_TEAM_SETTINGS, row.settings if row else None)
    return {
        "scope": "team",
        "team_id": team_id,
        "settings": settings,
        "created_at": _iso(row.created_at) if row else None,
        "updated_at": _iso(row.updated_at) if row else None,
    }


def upsert_team_settings(db: Session, team_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    row = db.query(TeamSettings).filter(TeamSettings.team_id == team_id).first()
    if row is None:
        row = TeamSettings(team_id=team_id, settings={})
        db.add(row)
    current = _merge_defaults(DEFAULT_TEAM_SETTINGS, row.settings)
    current.update({k: v for k, v in patch.items() if k in DEFAULT_TEAM_SETTINGS})
    row.settings = current
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return get_team_settings(db, team_id)


def get_project_settings(db: Session, project_id: int) -> dict[str, Any]:
    row = db.query(ProjectSettings).filter(ProjectSettings.project_id == project_id).first()
    settings = _merge_defaults(DEFAULT_PROJECT_SETTINGS, row.settings if row else None)
    return {
        "scope": "project",
        "project_id": project_id,
        "settings": settings,
        "created_at": _iso(row.created_at) if row else None,
        "updated_at": _iso(row.updated_at) if row else None,
    }


def upsert_project_settings(db: Session, project_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    row = db.query(ProjectSettings).filter(ProjectSettings.project_id == project_id).first()
    if row is None:
        row = ProjectSettings(project_id=project_id, settings={})
        db.add(row)
    current = _merge_defaults(DEFAULT_PROJECT_SETTINGS, row.settings)
    current.update({k: v for k, v in patch.items() if k in DEFAULT_PROJECT_SETTINGS})
    row.settings = current
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return get_project_settings(db, project_id)


def get_entity_scope_settings(db: Session, ledger_id: int) -> dict[str, Any]:
    row = (
        db.query(EntityScopeSettings)
        .filter(EntityScopeSettings.ledger_id == ledger_id)
        .first()
    )
    settings = _merge_defaults(DEFAULT_ENTITY_SCOPE_SETTINGS, row.settings if row else None)
    return {
        "scope": "entity",
        "ledger_id": ledger_id,
        "settings": settings,
        "created_at": _iso(row.created_at) if row else None,
        "updated_at": _iso(row.updated_at) if row else None,
    }


def upsert_entity_scope_settings(
    db: Session, ledger_id: int, patch: dict[str, Any]
) -> dict[str, Any]:
    row = (
        db.query(EntityScopeSettings)
        .filter(EntityScopeSettings.ledger_id == ledger_id)
        .first()
    )
    if row is None:
        row = EntityScopeSettings(ledger_id=ledger_id, settings={})
        db.add(row)
    current = _merge_defaults(DEFAULT_ENTITY_SCOPE_SETTINGS, row.settings)
    current.update({k: v for k, v in patch.items() if k in DEFAULT_ENTITY_SCOPE_SETTINGS})
    row.settings = current
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return get_entity_scope_settings(db, ledger_id)

# -*- coding: utf-8 -*-
"""
模块功能：科目与标签解析规则配置服务。
业务场景：支持从YAML配置文件和数据库动态加载科目解析规则，
         包括强制保留层级的科目编码、科目到Tag类别的映射等。
政策依据：项目"一级科目 + Dimension(Tag)"核心设计思想。
输入数据：YAML配置文件、数据库GlobalSettings记录。
输出结果：AccountTagConfig配置对象，包含强制科目列表、映射规则。
创建日期：2026-07-04
更新记录：
    2026-07-04  初始版本，支持DB+YAML双源配置加载。
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = BACKEND_DIR / "config" / "account_tag_rules.yaml"

CONFIG_KEY = "account_tag_rules"


@dataclass(frozen=True)
class AccountTagConfig:
    """
    科目与标签解析规则配置对象。

    Attributes:
        version: 配置版本号。
        mandatory_hierarchical_accounts: 强制保留层级的科目编码集合。
        mandatory_hierarchical_keywords: 强制保留层级的科目名称关键词集合。
        account_code_tag_category: 一级科目代码到Tag类别的映射。
        account_name_tag_category: 科目名称关键词到Tag类别的映射。
        auxiliary_keywords: 辅助核算维度关键词映射（部门、项目、区域等）。
    """

    version: str
    mandatory_hierarchical_accounts: set[str] = field(default_factory=set)
    mandatory_hierarchical_keywords: set[str] = field(default_factory=set)
    account_code_tag_category: dict[str, str] = field(default_factory=dict)
    account_name_tag_category: dict[str, str] = field(default_factory=dict)
    auxiliary_keywords: dict[str, list[str]] = field(default_factory=dict)


def _default_config() -> AccountTagConfig:
    """内置默认配置，确保即使配置文件缺失也能正常工作。"""
    return AccountTagConfig(
        version="1.0.0-default",
        mandatory_hierarchical_accounts={
            "2221.01.01", "2221.01.02", "2221.01.03", "2221.01.04",
            "2221.01.05", "2221.01.06", "2221.01.07", "2221.01.08",
            "2221.01.09", "2221.01.10", "2221.01.11", "2221.10.01",
            "2211.01.01", "2211.01.02", "2211.01.03", "2211.01.04",
            "2211.01.05", "2211.01.06", "2211.01.07", "2211.01.08",
            "2211.01.09",
        },
        mandatory_hierarchical_keywords={
            "应交增值税", "未交增值税", "进项税额", "销项税额",
            "进项税额转出", "已交税金", "应付职工薪酬",
        },
        account_code_tag_category={
            "1122": "customer",
            "1123": "customer",
            "2202": "supplier",
            "2203": "customer",
            "1221": "counterparty_object",
            "2241": "counterparty_object",
            "1403": "product",
            "1405": "product",
            "5001": "cost_element",
            "5101": "cost_element",
            "5401": "cost_element",
            "6001": "product",
            "6051": "product",
            "6601": "expense_type",
            "6602": "expense_type",
            "6603": "expense_type",
            "6403": "tax_type",
        },
        account_name_tag_category={
            "应收": "customer",
            "应付": "supplier",
            "预付": "supplier",
            "预收": "customer",
            "其他应收": "counterparty_object",
            "其他应付": "counterparty_object",
            "客户": "customer",
            "供应商": "supplier",
            "原材料": "material",
            "库存商品": "product",
            "生产成本": "cost_element",
            "制造费用": "cost_element",
            "主营业务成本": "cost_element",
            "主营业务收入": "product",
            "其他业务收入": "product",
            "销售费用": "expense_type",
            "管理费用": "expense_type",
            "财务费用": "expense_type",
            "研发费用": "expense_type",
            "税金及附加": "tax_type",
        },
        auxiliary_keywords={
            "department": ["行政部", "财务部", "销售部", "研发部", "生产部",
                           "采购部", "人力资源部", "部", "部门", "中心", "事业部", "车间", "工厂"],
            "project": ["PO-", "SO-", "项目", "工程", "课题", "合同"],
            "region": ["北京", "上海", "广州", "深圳", "山西", "杭州", "成都",
                       "武汉", "西安", "重庆", "天津", "南京", "苏州"],
        },
    )


def _build_config_from_dict(data: dict[str, Any]) -> AccountTagConfig:
    """从字典构造配置对象。"""
    return AccountTagConfig(
        version=data.get("version", "1.0.0"),
        mandatory_hierarchical_accounts=set(data.get("mandatory_hierarchical_accounts", [])),
        mandatory_hierarchical_keywords=set(data.get("mandatory_hierarchical_keywords", [])),
        account_code_tag_category=data.get("account_code_tag_category", {}),
        account_name_tag_category=data.get("account_name_tag_category", {}),
        auxiliary_keywords=data.get("auxiliary_keywords", {}),
    )


def load_account_tag_config_from_file(path: Path | str | None = None) -> AccountTagConfig:
    """
    从YAML配置文件加载科目解析规则。

    Args:
        path: 配置文件路径，默认使用 backend/config/account_tag_rules.yaml。

    Returns:
        AccountTagConfig: 配置对象。

    Raises:
        FileNotFoundError: 配置文件不存在。
        ValueError: 配置文件格式错误。
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return _default_config()

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
        if not isinstance(data, dict):
            raise ValueError("配置文件格式错误，应为YAML字典")
        return _build_config_from_dict(data)
    except yaml.YAMLError as exc:
        raise ValueError(f"配置文件解析错误: {exc}")


def load_account_tag_config_from_db(db: Session) -> AccountTagConfig | None:
    """
    从数据库加载科目解析规则。

    Args:
        db: 数据库会话。

    Returns:
        AccountTagConfig | None: 数据库中的配置对象，若不存在则返回 None。
    """
    from app.models.global_settings import GlobalSettings

    settings = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == CONFIG_KEY
    ).first()
    if not settings or not settings.settings_value:
        return None
    return _build_config_from_dict(settings.settings_value)


def load_account_tag_config(
    db: Session | None = None,
    path: Path | str | None = None,
) -> AccountTagConfig:
    """
    加载科目解析规则配置。

    加载优先级：
        1. 数据库中的有效配置（如果 db 传入且数据库存在记录）；
        2. 配置文件；
        3. 内置默认配置。

    Args:
        db: 可选的数据库会话，用于读取数据库配置。
        path: 可选的配置文件路径。

    Returns:
        AccountTagConfig: 配置对象。
    """
    if db is not None:
        db_config = load_account_tag_config_from_db(db)
        if db_config is not None:
            return db_config

    return load_account_tag_config_from_file(path)


def save_account_tag_config_to_db(
    db: Session,
    config: AccountTagConfig,
    user_id: int | None = None,
) -> None:
    """
    保存科目解析规则配置到数据库。

    Args:
        db: 数据库会话。
        config: 配置对象。
        user_id: 操作用户ID（用于审计日志）。
    """
    from app.models.global_settings import GlobalSettings
    from app.db.models import ExecutionAuditLog
    from datetime import datetime, timezone

    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == CONFIG_KEY
    ).first()

    config_dict = {
        "version": config.version,
        "mandatory_hierarchical_accounts": list(config.mandatory_hierarchical_accounts),
        "mandatory_hierarchical_keywords": list(config.mandatory_hierarchical_keywords),
        "account_code_tag_category": config.account_code_tag_category,
        "account_name_tag_category": config.account_name_tag_category,
        "auxiliary_keywords": config.auxiliary_keywords,
    }

    if db_config:
        db.add(
            ExecutionAuditLog(
                trace_id=str(id(config)),
                request_id=str(id(config)),
                service_name="account_tag_config",
                tool_name="save_config",
                execution_source="api",
                business_object_type="global_settings",
                business_object_id=str(db_config.id),
                status="updated",
                risk_level="low",
                operator=str(user_id) if user_id else None,
                input_summary={
                    "before_version": db_config.settings_value.get("version", "unknown"),
                    "after_version": config.version,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        db_config.settings_value = config_dict
    else:
        db_config = GlobalSettings(
            settings_key=CONFIG_KEY,
            settings_value=config_dict,
        )
        db.add(db_config)
        db.add(
            ExecutionAuditLog(
                trace_id=str(id(config)),
                request_id=str(id(config)),
                service_name="account_tag_config",
                tool_name="save_config",
                execution_source="api",
                business_object_type="global_settings",
                business_object_id=str(db_config.id),
                status="created",
                risk_level="low",
                operator=str(user_id) if user_id else None,
                input_summary={
                    "version": config.version,
                },
                created_at=datetime.now(timezone.utc),
            )
        )

    db.commit()

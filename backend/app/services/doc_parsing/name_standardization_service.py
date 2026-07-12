# -*- coding: utf-8 -*-
"""维度显示名称是否已为规范全称的启发式判断。"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.audit.dimension_sync_service import lookup_master_display_name

# 常见法人/组织形态后缀（含个体户、事业单位常见表述）
_LEGAL_ENTITY_MARKERS: tuple[str, ...] = (
    "有限公司",
    "有限责任公司",
    "股份有限公司",
    "集团有限公司",
    "股份公司",
    "分公司",
    "子公司",
    "电力公司",
    "水务公司",
    "燃气公司",
    "技术服务部",
    "经营部",
    "服务部",
    "事务所",
    "研究院",
    "研究所",
    "合作社",
    "培训中心",
    "制造加工有限公司",
)

_ADMIN_REGION_MARKERS: tuple[str, ...] = (
    "省",
    "市",
    "自治区",
    "特别行政区",
    "县",
    "区",
    "州",
    "盟",
    "旗",
    "产业园",
    "示范区",
    "综合改革",
)

# 银行户名常见缩写（无「银行/支行/分行」时视为简称）
_BANK_ABBREVIATIONS: tuple[str, ...] = (
    "工行",
    "建行",
    "农行",
    "中行",
    "交行",
    "招行",
    "邮储",
    "民生",
    "浦发",
    "兴业",
    "光大",
    "华夏",
    "中信",
    "平安",
    "农商",
    "农商行",
    "农信",
    "信用社",
)

_BANK_FULL_MARKERS: tuple[str, ...] = ("银行", "支行", "分行", "营业部", "分理处", "储蓄所")

# 人员类维度（短名称即完整姓名，不按「简称」处理）
_PERSON_CATEGORY_CODES: frozenset[str] = frozenset(
    {"person", "employee", "staff", "personnel", "reimbursement_person"}
)

# 个人往来常见科目（其他应收/应付等挂自然人姓名）
_PERSON_RELATED_ACCOUNT_ROOTS: frozenset[str] = frozenset({"1221", "2241", "1015", "1131", "1132"})

# 明显非正常身份证登记用名（绰号、玩笑称呼）
_PERSON_NICKNAME_MARKERS: tuple[str, ...] = (
    "胖子",
    "瘦子",
    "矮子",
    "大个子",
    "小个子",
    "小子",
    "老炮",
    "二狗",
    "三胖",
    "铁柱",
    "翠花",
    "狗蛋",
    "大傻",
    "二傻",
    "傻瓜",
    "笨蛋",
    "臭小子",
)

# 2～4 字业务简称，勿误判为人名
_NON_PERSON_SHORT_LABELS: frozenset[str] = frozenset(
    {
        "大客户",
        "小客户",
        "某客户",
        "散户",
        "客户",
        "供应商",
        "员工",
        "临时",
        "备用",
        "待查",
        "未知",
        "其他",
        "杂项",
        "合计",
        "现金",
        "库存",
    }
)

_NON_PERSON_NAME_SUFFIXES: tuple[str, ...] = (
    "客户",
    "公司",
    "集团",
    "部",
    "组",
    "店",
    "厂",
    "行",
    "社",
    "中心",
    "银行",
)


def _normalize_name(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_legal_entity_form(name: str) -> bool:
    if any(marker in name for marker in _LEGAL_ENTITY_MARKERS):
        return True
    if len(name) >= 6 and (name.endswith("公司") or name.endswith("集团")):
        return True
    if any(name.endswith(suffix) for suffix in ("支行", "分行", "营业部", "分理处")):
        return True
    return False


def _looks_like_bank_abbreviation(name: str) -> bool:
    if not name:
        return True
    if any(marker in name for marker in _BANK_FULL_MARKERS):
        return False
    if any(abbr in name for abbr in _BANK_ABBREVIATIONS):
        return True
    # 无银行完整标识且较短，多为简称
    return len(name) <= 8


from app.config.tag_category_constants import is_bank_account_category


def _is_bank_related(*, category_code: str | None, account_code: str | None) -> bool:
    if is_bank_account_category(category_code):
        return True
    base = (account_code or "").strip().split(".")[0]
    return base in {"1001", "1002"}


def _is_person_related(*, category_code: str | None, account_code: str | None) -> bool:
    if category_code in _PERSON_CATEGORY_CODES:
        return True
    base = (account_code or "").strip().split(".")[0]
    return base in _PERSON_RELATED_ACCOUNT_ROOTS


def _looks_like_invalid_person_nickname(name: str) -> bool:
    if not name:
        return False
    return any(marker in name for marker in _PERSON_NICKNAME_MARKERS)


def _looks_like_incomplete_person_name(name: str) -> bool:
    """仅姓氏、无名字（如「宋」「李」），身份证登记通常不会只有一字。"""
    if not name:
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fff]", name))


def _looks_like_chinese_person_name(name: str) -> bool:
    """常见中文姓名（2～4 字），不含组织/业务简称与明显绰号。"""
    if not name or name in _NON_PERSON_SHORT_LABELS:
        return False
    if _looks_like_invalid_person_nickname(name):
        return False
    if _has_legal_entity_form(name):
        return False
    if any(name.endswith(suffix) for suffix in _NON_PERSON_NAME_SUFFIXES):
        return False
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
        return False
    return True


def infer_name_standardized(
    display_name: str,
    *,
    category_code: str | None = None,
    tag_value: str | None = None,
    source_sub_code: str | None = None,
    account_code: str | None = None,
) -> bool:
    """
    判断 display_name 是否已像规范全称（而非导入时的简称/缩写）。

    规则要点：
    - 银行户名：识别「招行」「工行」等缩写；含「有限公司」「支行」等视为全称
    - 往来单位：含法人后缀、行政区划+较长名称，视为全称
    - 中文人名（如「张悦」）：视为已规范；仅姓氏（如「宋」）或明显绰号除外
    - 极短非人名（<=4 字）默认视为简称
    """
    _ = source_sub_code  # 预留：后续可按来源段与主数据对照
    name = _normalize_name(display_name)
    if not name:
        return False

    value = _normalize_name(tag_value)
    if value and name != value and len(name) >= len(value) + 2:
        return True

    if _is_bank_related(category_code=category_code, account_code=account_code):
        if _looks_like_bank_abbreviation(name):
            return False
        return _has_legal_entity_form(name) or len(name) >= 10

    if _has_legal_entity_form(name):
        return True

    if len(name) >= 12 and any(marker in name for marker in _ADMIN_REGION_MARKERS):
        return True

    # 费用类型、部门等枚举型短词不算「未规范全称」——无需进简称待办
    if category_code in {
        "expense_type", "department", "project", "region", "product", "service", "cost_element", "tax_type",
        "fixed_asset_class", "fixed_asset_item", "cip_category", "cip_project", "loan_channel",
    }:
        return True

    if category_code in _PERSON_CATEGORY_CODES:
        if _looks_like_invalid_person_nickname(name):
            return False
        if _looks_like_incomplete_person_name(name):
            return False
        if _looks_like_chinese_person_name(name):
            return True
        return False

    if _looks_like_incomplete_person_name(name) and _is_person_related(
        category_code=category_code, account_code=account_code
    ):
        return False

    if _looks_like_chinese_person_name(name) and not _is_bank_related(
        category_code=category_code, account_code=account_code
    ):
        return True

    if _is_person_related(category_code=category_code, account_code=account_code):
        if _looks_like_invalid_person_nickname(name):
            return False
        if _looks_like_incomplete_person_name(name):
            return False
        if _looks_like_chinese_person_name(name):
            return True

    # 往来类：较长且不像编号/代号
    if category_code in {"customer", "supplier", "counterparty", "counterparty_object"}:
        if len(name) >= 8 and not re.fullmatch(r"[A-Za-z0-9\-_.]+", name):
            return True

    if len(name) <= 4:
        return False

    return False


def name_standardization_queue_message(
    display_name: str,
    *,
    category_code: str | None = None,
    account_code: str | None = None,
) -> str:
    """待处理队列中「待补全称」项的口语化说明。"""
    name = _normalize_name(display_name)
    if _looks_like_incomplete_person_name(name) and _is_person_related(
        category_code=category_code, account_code=account_code
    ):
        return "只有姓氏、没有名字，请补全姓名（如「宋某某」）"
    if _looks_like_invalid_person_nickname(name) and _is_person_related(
        category_code=category_code, account_code=account_code
    ):
        return "名称像绰号或玩笑称呼，请改成身份证上的正式姓名"
    return "名称像缩写或尚未对照主数据，请补成规范全称（如银行户名写开户全称）"


def resolve_name_standardized(
    db: Session,
    ledger_id: int | None,
    tag: dict[str, Any],
    *,
    account_code: str | None = None,
) -> bool:
    """结合主数据与启发式，判断 Tag 是否应视为已规范全称。"""
    if tag.get("name_standardized") is True:
        return True

    category_code = str(tag.get("category_code") or "") or None
    tag_value = str(tag.get("tag_value") or "")
    display_name = str(tag.get("display_name") or tag_value or "")
    source_sub_code = tag.get("source_sub_code")

    master_name = lookup_master_display_name(
        db,
        ledger_id,
        category_code=category_code or "",
        tag_value=tag_value,
        source_sub_code=str(source_sub_code) if source_sub_code else None,
        account_code=account_code,
    )
    if master_name:
        return True

    return infer_name_standardized(
        display_name,
        category_code=category_code,
        tag_value=tag_value,
        source_sub_code=str(source_sub_code) if source_sub_code else None,
        account_code=account_code,
    )

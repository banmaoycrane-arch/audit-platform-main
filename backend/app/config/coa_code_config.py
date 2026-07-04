# -*- coding: utf-8 -*-
"""
模块功能：会计科目编码规则配置加载与解析。
业务场景：支持从配置文件和数据库动态加载科目编码层级规则，
         用于自动生成和校验科目编码。
政策依据：《企业会计准则》科目编号惯例。
输入数据：JSON 配置文件、数据库 CoaCodeRule 记录。
输出结果：CoaCodeRuleConfig 配置对象，包含层级规则、字符集、自动生成参数。
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，支持配置文件加载。
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = BACKEND_DIR / "config" / "coa_code_rules.json"


@dataclass(frozen=True)
class LevelRule:
    """
    单个层级编码规则。

    Attributes:
        level: 科目层级（从 1 开始）。
        segment_length: 该层相对前一层新增的编码长度。
        min_code: 该层序号的最小值（字符串）。
        max_code: 该层序号的最大值（字符串）。
        pattern: 该层序号的正则校验表达式。
        description: 层级描述。
    """

    level: int
    segment_length: int
    min_code: str
    max_code: str
    pattern: str
    description: str

    @property
    def compiled_pattern(self) -> re.Pattern[str]:
        """编译后的正则表达式对象。"""
        return re.compile(self.pattern)

    @property
    def min_value(self) -> int:
        """该层序号的最小整数值。"""
        return int(self.min_code)

    @property
    def max_value(self) -> int:
        """该层序号的最大整数值。"""
        return int(self.max_code)


@dataclass(frozen=True)
class AutoGenerationRule:
    """自动编码生成规则。"""

    pad_with_zero: bool
    start_sequence: int
    skip_zero_ending: bool


@dataclass(frozen=True)
class ValidationRule:
    """编码校验规则。"""

    require_parent_exists: bool
    require_continuous: bool
    allow_custom_code: bool


@dataclass(frozen=True)
class CoaCodeRuleConfig:
    """
    科目编码规则配置对象。

    Attributes:
        version: 配置版本号。
        levels: 各层级规则列表。
        max_level: 最大层级深度。
        allowed_charset: 允许字符集（numeric/alphanumeric）。
        auto_generation: 自动生成规则。
        validation: 校验规则。
    """

    version: str
    levels: tuple[LevelRule, ...]
    max_level: int
    allowed_charset: str
    auto_generation: AutoGenerationRule
    validation: ValidationRule

    def get_level_rule(self, level: int) -> LevelRule:
        """根据层级获取对应规则。"""
        for rule in self.levels:
            if rule.level == level:
                return rule
        raise LookupError(f"未找到层级 {level} 的编码规则")

    @property
    def total_code_lengths(self) -> dict[int, int]:
        """各层级完整编码长度（从根到该层的累计长度）。"""
        result: dict[int, int] = {}
        total = 0
        for rule in self.levels:
            total += rule.segment_length
            result[rule.level] = total
        return result

    @property
    def code_pattern(self) -> re.Pattern[str]:
        """完整科目编码的正则表达式。"""
        total_length = self.total_code_lengths[self.max_level]
        return re.compile(rf"^\\d{{{total_length}}}$")


def _build_config_from_dict(data: dict[str, Any]) -> CoaCodeRuleConfig:
    """从字典构造配置对象。"""
    levels = tuple(
        LevelRule(
            level=item["level"],
            segment_length=item["segment_length"],
            min_code=item["min_code"],
            max_code=item["max_code"],
            pattern=item["pattern"],
            description=item["description"],
        )
        for item in data["levels"]
    )
    auto_gen = data["auto_generation"]
    validation = data["validation"]
    return CoaCodeRuleConfig(
        version=data["version"],
        levels=levels,
        max_level=data["max_level"],
        allowed_charset=data["allowed_charset"],
        auto_generation=AutoGenerationRule(
            pad_with_zero=auto_gen["pad_with_zero"],
            start_sequence=auto_gen["start_sequence"],
            skip_zero_ending=auto_gen["skip_zero_ending"],
        ),
        validation=ValidationRule(
            require_parent_exists=validation["require_parent_exists"],
            require_continuous=validation["require_continuous"],
            allow_custom_code=validation["allow_custom_code"],
        ),
    )


def load_coa_code_config_from_file(path: Path | str | None = None) -> CoaCodeRuleConfig:
    """
    从 JSON 配置文件加载科目编码规则。

    Args:
        path: 配置文件路径，默认使用 backend/config/coa_code_rules.json。

    Returns:
        CoaCodeRuleConfig: 配置对象。

    Raises:
        FileNotFoundError: 配置文件不存在。
        ValueError: 配置文件格式错误。
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"科目编码规则配置文件不存在：{config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return _build_config_from_dict(data)


def load_coa_code_config_from_db(db: Session) -> CoaCodeRuleConfig | None:
    """
    从数据库加载科目编码规则。

    Args:
        db: 数据库会话。

    Returns:
        CoaCodeRuleConfig | None: 数据库中的配置对象，若不存在则返回 None。
    """
    from app.db.models import CoaCodeRule

    rule = db.query(CoaCodeRule).order_by(CoaCodeRule.updated_at.desc()).first()
    if not rule or not rule.rule_content:
        return None
    return _build_config_from_dict(rule.rule_content)


def load_coa_code_config(
    db: Session | None = None,
    path: Path | str | None = None,
) -> CoaCodeRuleConfig:
    """
    加载科目编码规则配置。

    加载优先级：
        1. 数据库中的有效配置（如果 db 传入且数据库存在记录）；
        2. 配置文件；
        3. 内置默认配置。

    Args:
        db: 可选的数据库会话，用于读取数据库配置。
        path: 可选的配置文件路径。

    Returns:
        CoaCodeRuleConfig: 配置对象。
    """
    if db is not None:
        db_config = load_coa_code_config_from_db(db)
        if db_config is not None:
            return db_config

    try:
        return load_coa_code_config_from_file(path)
    except FileNotFoundError:
        return _default_config()


def _default_config() -> CoaCodeRuleConfig:
    """内置默认配置，确保即使配置文件缺失也能正常工作。"""
    return CoaCodeRuleConfig(
        version="1.0.0-default",
        levels=(
            LevelRule(level=1, segment_length=4, min_code="1000", max_code="9999", pattern=r"^\d{4}$", description="一级科目"),
            LevelRule(level=2, segment_length=2, min_code="01", max_code="99", pattern=r"^\d{2}$", description="二级科目"),
            LevelRule(level=3, segment_length=2, min_code="01", max_code="99", pattern=r"^\d{2}$", description="三级科目"),
        ),
        max_level=3,
        allowed_charset="numeric",
        auto_generation=AutoGenerationRule(pad_with_zero=True, start_sequence=1, skip_zero_ending=False),
        validation=ValidationRule(require_parent_exists=True, require_continuous=False, allow_custom_code=True),
    )

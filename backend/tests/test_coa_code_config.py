# -*- coding: utf-8 -*-
"""
模块功能：科目编码规则配置与服务单元测试。
业务场景：验证编码校验、自动生成、配置加载等核心功能。
创建日期：2026-07-02
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config.coa_code_config import (
    CoaCodeRuleConfig,
    load_coa_code_config,
    load_coa_code_config_from_db,
    load_coa_code_config_from_file,
)
from app.db.models import ChartOfAccounts, CoaCodeRule
from app.db.session import Base, engine
from app.main import app
from app.services.basic_data.coa_service import (
    create_account,
    generate_account_code,
    validate_account_code,
    save_coa_code_rule,
)


@pytest.fixture(scope="function")
def db_session():
    """测试用数据库会话。"""
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_config_dict():
    return {
        "version": "1.0.0",
        "levels": [
            {"level": 1, "segment_length": 4, "min_code": "1000", "max_code": "9999", "pattern": "^\\d{4}$", "description": "一级科目"},
            {"level": 2, "segment_length": 2, "min_code": "01", "max_code": "99", "pattern": "^\\d{2}$", "description": "二级科目"},
            {"level": 3, "segment_length": 2, "min_code": "01", "max_code": "99", "pattern": "^\\d{2}$", "description": "三级科目"},
        ],
        "max_level": 3,
        "allowed_charset": "numeric",
        "auto_generation": {"pad_with_zero": True, "start_sequence": 1, "skip_zero_ending": False},
        "validation": {"require_parent_exists": True, "require_continuous": False, "allow_custom_code": True},
    }


class TestCoaCodeConfig:
    """科目编码规则配置加载测试。"""

    def test_load_from_file(self, sample_config_dict):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(sample_config_dict, f, ensure_ascii=False)
            temp_path = f.name
        try:
            config = load_coa_code_config_from_file(temp_path)
            assert config.version == "1.0.0"
            assert config.max_level == 3
            assert len(config.levels) == 3
            assert config.total_code_lengths == {1: 4, 2: 6, 3: 8}
        finally:
            os.unlink(temp_path)

    def test_load_from_db(self, db_session, sample_config_dict):
        rule = CoaCodeRule(
            name="测试规则",
            version="1.0.0",
            rule_content=sample_config_dict,
            is_active=True,
        )
        db_session.add(rule)
        db_session.commit()

        config = load_coa_code_config_from_db(db_session)
        assert config is not None
        assert config.version == "1.0.0"
        assert config.max_level == 3

    def test_load_priority_db_over_file(self, db_session, sample_config_dict):
        db_config_dict = dict(sample_config_dict)
        db_config_dict["version"] = "2.0.0"
        rule = CoaCodeRule(
            name="数据库规则",
            version="2.0.0",
            rule_content=db_config_dict,
            is_active=True,
        )
        db_session.add(rule)
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            file_config = dict(sample_config_dict)
            file_config["version"] = "1.0.0"
            json.dump(file_config, f, ensure_ascii=False)
            temp_path = f.name
        try:
            config = load_coa_code_config(db=db_session, path=temp_path)
            assert config.version == "2.0.0"
        finally:
            os.unlink(temp_path)

    def test_default_config_fallback(self, db_session):
        config = load_coa_code_config(db=db_session, path="/nonexistent/path.json")
        assert config.version == "1.0.0-default"
        assert config.max_level == 3

    def test_get_level_rule(self):
        config = load_coa_code_config()
        rule = config.get_level_rule(2)
        assert rule.level == 2
        assert rule.segment_length == 2


class TestCoaCodeValidation:
    """科目编码校验测试。"""

    def test_validate_valid_level1(self, db_session):
        result = validate_account_code("1001", db=db_session)
        assert result["is_valid"] is True
        assert result["level"] == 1
        assert result["parent_code"] is None

    def test_validate_valid_level2(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        result = validate_account_code("100101", parent_code="1001", db=db_session)
        assert result["is_valid"] is True
        assert result["level"] == 2
        assert result["parent_code"] == "1001"

    def test_validate_valid_level3(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        child = ChartOfAccounts(
            code="100101", name="人民币现金", parent_code="1001", level=2,
            category="资产", direction="debit", is_terminal=False, status="active", is_system=False,
        )
        db_session.add_all([parent, child])
        db_session.commit()

        result = validate_account_code("10010101", parent_code="100101", db=db_session)
        assert result["is_valid"] is True
        assert result["level"] == 3
        assert result["parent_code"] == "100101"

    def test_validate_empty_code(self):
        result = validate_account_code("")
        assert result["is_valid"] is False
        assert "不能为空" in result["message"]

    def test_validate_non_numeric(self):
        result = validate_account_code("1001AB")
        assert result["is_valid"] is False
        assert "只能包含数字" in result["message"]

    def test_validate_wrong_length(self):
        result = validate_account_code("100")
        assert result["is_valid"] is False
        assert "长度" in result["message"]

    def test_validate_parent_mismatch(self):
        result = validate_account_code("100101", parent_code="2001")
        assert result["is_valid"] is False
        assert "推断的父级" in result["message"]

    def test_validate_parent_not_exists(self, db_session):
        result = validate_account_code("100101", parent_code="1001", db=db_session)
        assert result["is_valid"] is False
        assert "不存在" in result["message"]

    def test_validate_segment_out_of_range(self):
        result = validate_account_code("0099")
        assert result["is_valid"] is False
        assert "超出范围" in result["message"]


class TestCoaCodeGeneration:
    """科目编码自动生成测试。"""

    def test_generate_level2_first(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        code = generate_account_code(db_session, "1001")
        assert code == "100101"

    def test_generate_level2_next(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        child1 = ChartOfAccounts(
            code="100101", name="人民币现金", parent_code="1001", level=2,
            category="资产", direction="debit", is_terminal=True, status="active", is_system=False,
        )
        db_session.add_all([parent, child1])
        db_session.commit()

        code = generate_account_code(db_session, "1001")
        assert code == "100102"

    def test_generate_level3(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        child = ChartOfAccounts(
            code="100101", name="人民币现金", parent_code="1001", level=2,
            category="资产", direction="debit", is_terminal=False, status="active", is_system=False,
        )
        db_session.add_all([parent, child])
        db_session.commit()

        code = generate_account_code(db_session, "100101")
        assert code == "10010101"

    def test_generate_parent_not_exists(self, db_session):
        with pytest.raises(ValueError, match="不存在"):
            generate_account_code(db_session, "9999")

    def test_generate_max_level_exceeded(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        child = ChartOfAccounts(
            code="100101", name="人民币现金", parent_code="1001", level=2,
            category="资产", direction="debit", is_terminal=False, status="active", is_system=False,
        )
        grandchild = ChartOfAccounts(
            code="10010101", name="日常备用金", parent_code="100101", level=3,
            category="资产", direction="debit", is_terminal=True, status="active", is_system=False,
        )
        db_session.add_all([parent, child, grandchild])
        db_session.commit()

        with pytest.raises(ValueError, match="超过最大"):
            generate_account_code(db_session, "10010101")


class TestCoaCreateAccount:
    """科目创建测试。"""

    def test_create_with_auto_code(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        account = create_account(db_session, {
            "name": "人民币现金",
            "parent_code": "1001",
            "category": "资产",
            "direction": "debit",
        })
        assert account.code == "100101"
        assert account.level == 2
        assert account.parent_code == "1001"

    def test_create_with_explicit_code(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        account = create_account(db_session, {
            "code": "100102",
            "name": "外币现金",
            "parent_code": "1001",
            "category": "资产",
            "direction": "debit",
        })
        assert account.code == "100102"
        assert account.level == 2

    def test_create_with_wrong_level(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        with pytest.raises(ValueError, match="层级"):
            create_account(db_session, {
                "code": "100101",
                "name": "错误层级",
                "level": 3,
                "category": "资产",
                "direction": "debit",
            })

    def test_create_with_wrong_parent(self, db_session):
        parent = ChartOfAccounts(
            code="1001", name="库存现金", level=1, category="资产", direction="debit",
            is_terminal=False, status="active", is_system=False,
        )
        db_session.add(parent)
        db_session.commit()

        with pytest.raises(ValueError, match="父级"):
            create_account(db_session, {
                "code": "100101",
                "name": "错误父级",
                "parent_code": "2001",
                "category": "资产",
                "direction": "debit",
            })

    def test_create_level1(self, db_session):
        account = create_account(db_session, {
            "code": "1001",
            "name": "库存现金",
            "category": "资产",
            "direction": "debit",
        })
        assert account.level == 1
        assert account.parent_code is None


class TestCoaCodeRulePersistence:
    """编码规则持久化测试。"""

    def test_save_rule_to_db(self, db_session, sample_config_dict):
        rule = save_coa_code_rule(db_session, sample_config_dict, "测试规则")
        assert rule.id is not None
        assert rule.name == "测试规则"
        assert rule.version == "1.0.0"
        assert rule.rule_content == sample_config_dict

    def test_load_saved_rule(self, db_session, sample_config_dict):
        save_coa_code_rule(db_session, sample_config_dict, "测试规则")

        config = load_coa_code_config(db=db_session)
        assert config.version == "1.0.0"
        assert config.max_level == 3
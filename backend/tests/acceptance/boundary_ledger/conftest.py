# -*- coding: utf-8 -*-
"""
模块功能：ledger_id 边界改造验收测试公共 fixture
业务场景：为 acceptance/boundary_ledger 测试用例提供独立 SQLite 数据库、
         组织、账簿、期间等基础上下文，并确保 ledger_id 字段正确写入。
政策依据：会计主体假设——不同账簿数据必须物理隔离。
输入数据：无。
输出结果：pytest fixture（db_session、test_organization、test_ledger、test_period）。
创建日期：2026-07-01
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Organization
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.models.project import Project
from app.models.project_ledger import ProjectLedger
from app.models.user_ledger_auth import UserLedgerAuth
from app.services.shared.ledger_timeline_service import initialize_ledger_timeline


# 独立测试数据库，避免污染开发数据库
TEST_DATABASE_URL = "sqlite:///./boundary_ledger_test.db"


engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 在模块首次加载时创建所有表
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    提供独立数据库会话，每个测试函数前后自动回滚，确保互不影响。

    Returns:
        Session: SQLAlchemy 数据库会话对象。
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    # 测试结束后回滚并关闭连接
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_user(db_session):
    """
    创建测试用户，并关联到测试团队。

    Returns:
        User: 测试用户对象。
    """
    team = Team(name="验收测试团队", type="virtual")
    db_session.add(team)
    db_session.flush()

    user = User(
        username="boundary_ledger_test_user",
        phone="13800000000",
        team_id=team.id,
        agreed_terms=True,
        agreed_privacy=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture(scope="function")
def test_organization(db_session):
    """
    创建测试组织，用于承载后续账簿和期间。

    Returns:
        Organization: 测试组织对象。
    """
    organization = Organization(name="验收测试组织", fiscal_year=2026)
    db_session.add(organization)
    db_session.flush()
    return organization

# -*- coding: utf-8 -*-
"""
DocumentTag 服务层单元测试。

覆盖范围：
    1. DocumentTagService CRUD 操作
    2. DocumentTagIndexer 自动标签生成
"""
import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, Column, create_engine, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.ledger import Ledger
from app.services.doc_parsing.document_tag_service import (
    create_document_tag,
    create_document_tags_batch,
    delete_document_tag,
    delete_document_tags_by_document,
    get_document_tag_by_id,
    get_document_tag_stats,
    list_document_tags,
    update_document_tag,
)
from app.services.doc_parsing.document_tag_indexer import DocumentTagIndexer


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class TestDocumentTagService:
    """测试 DocumentTagService CRUD 操作"""

    def test_create_document_tag(self, db_session):
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
            confidence=0.9,
            source="rule",
        )
        assert tag.id is not None
        assert tag.document_id == 1
        assert tag.document_type == "invoice"
        assert tag.tag == "发票类型:增值税专用发票"
        assert tag.tag_type == "business"
        assert tag.confidence == 0.9
        assert tag.source == "rule"
        assert tag.vector_stored is False

    def test_create_document_tag_duplicate(self, db_session):
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
        )
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
        )
        assert tag is not None

    def test_create_document_tag_invalid_tag_type(self, db_session):
        with pytest.raises(ValueError):
            create_document_tag(
                db=db_session,
                document_id=1,
                document_type="invoice",
                tag="test",
                tag_type="invalid",
            )

    def test_get_document_tag_by_id(self, db_session):
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
        )
        fetched = get_document_tag_by_id(db_session, tag.id)
        assert fetched is not None
        assert fetched.id == tag.id
        assert fetched.tag == "发票类型:增值税专用发票"

    def test_get_document_tag_by_id_not_found(self, db_session):
        fetched = get_document_tag_by_id(db_session, 999)
        assert fetched is None

    def test_list_document_tags(self, db_session):
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
        )
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="大额发票",
            tag_type="amount",
        )
        create_document_tag(
            db=db_session,
            document_id=2,
            document_type="contract",
            tag="合同类型:服务合同",
            tag_type="business",
        )

        tags = list_document_tags(db_session)
        assert len(tags) == 3

        tags_by_doc = list_document_tags(db_session, document_id=1)
        assert len(tags_by_doc) == 2

        tags_by_type = list_document_tags(db_session, document_type="invoice")
        assert len(tags_by_type) == 2

        tags_by_tag_type = list_document_tags(db_session, tag_type="business")
        assert len(tags_by_tag_type) == 2

        tags_by_source = list_document_tags(db_session, source="rule")
        assert len(tags_by_source) == 3

    def test_update_document_tag(self, db_session):
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="发票类型:增值税专用发票",
            tag_type="business",
            confidence=0.8,
            source="rule",
        )

        updated = update_document_tag(
            db=db_session,
            document_tag_id=tag.id,
            tag="发票类型:增值税普通发票",
            confidence=0.95,
            source="ai",
        )

        assert updated is not None
        assert updated.tag == "发票类型:增值税普通发票"
        assert updated.confidence == 0.95
        assert updated.source == "ai"
        assert updated.vector_stored is False

    def test_update_document_tag_invalid_tag_type(self, db_session):
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="test",
            tag_type="business",
        )
        with pytest.raises(ValueError):
            update_document_tag(
                db=db_session,
                document_tag_id=tag.id,
                tag_type="invalid",
            )

    def test_update_document_tag_not_found(self, db_session):
        updated = update_document_tag(
            db=db_session,
            document_tag_id=999,
            tag="test",
        )
        assert updated is None

    def test_delete_document_tag(self, db_session):
        tag = create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="test",
            tag_type="business",
        )

        success = delete_document_tag(db_session, tag.id)
        assert success is True

        fetched = get_document_tag_by_id(db_session, tag.id)
        assert fetched is None

    def test_delete_document_tag_not_found(self, db_session):
        success = delete_document_tag(db_session, 999)
        assert success is False

    def test_delete_document_tags_by_document(self, db_session):
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="tag1",
            tag_type="business",
        )
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="tag2",
            tag_type="amount",
        )
        create_document_tag(
            db=db_session,
            document_id=2,
            document_type="contract",
            tag="tag3",
            tag_type="business",
        )

        count = delete_document_tags_by_document(db_session, 1)
        assert count == 2

        tags = list_document_tags(db_session)
        assert len(tags) == 1

    def test_create_document_tags_batch(self, db_session):
        tags_data = [
            {"tag": "发票类型:增值税专用发票", "tag_type": "business", "confidence": 0.9},
            {"tag": "大额发票", "tag_type": "amount", "confidence": 0.95},
            {"tag": "开票日期:2026-07-01", "tag_type": "time", "confidence": 0.95},
        ]

        tags = create_document_tags_batch(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tags=tags_data,
        )

        assert len(tags) == 3
        assert tags[0].tag == "发票类型:增值税专用发票"
        assert tags[1].tag_type == "amount"
        assert tags[2].confidence == 0.95

    def test_get_document_tag_stats(self, db_session):
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="tag1",
            tag_type="business",
            confidence=0.9,
        )
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="tag2",
            tag_type="amount",
            confidence=0.8,
        )
        create_document_tag(
            db=db_session,
            document_id=2,
            document_type="contract",
            tag="tag3",
            tag_type="business",
            confidence=0.95,
        )

        stats = get_document_tag_stats(db_session)

        assert stats["total_tags"] == 3
        assert stats["total_documents"] == 2

        type_stats = {s["tag_type"]: s for s in stats["by_tag_type"]}
        assert type_stats["business"]["count"] == 2
        assert type_stats["amount"]["count"] == 1

    def test_get_document_tag_stats_by_document_type(self, db_session):
        create_document_tag(
            db=db_session,
            document_id=1,
            document_type="invoice",
            tag="tag1",
            tag_type="business",
        )
        create_document_tag(
            db=db_session,
            document_id=2,
            document_type="contract",
            tag="tag2",
            tag_type="business",
        )

        stats = get_document_tag_stats(db_session, document_type="invoice")
        assert stats["by_tag_type"][0]["count"] == 1


class TestDocumentTagIndexer:
    """测试 DocumentTagIndexer 自动标签生成"""

    def test_generate_invoice_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "invoice_type": "增值税专用发票",
            "total_amount": 11300.00,
            "tax_rate": "13%",
            "seller_name": "供应商A",
            "buyer_name": "客户B",
            "invoice_date": "2026-07-15",
            "goods_name": "办公用品",
            "validation_passed": True,
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="invoice",
            parsed_data=parsed_data,
            source="rule",
        )

        assert len(tags) >= 5
        tag_values = [t.tag for t in tags]
        assert "发票类型:增值税专用发票" in tag_values
        assert "税率:13%" in tag_values
        assert "销售方:供应商A" in tag_values
        assert "购买方:客户B" in tag_values
        assert "开票日期:2026-07-15" in tag_values

    def test_generate_invoice_tags_large_amount(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "invoice_type": "增值税专用发票",
            "total_amount": 2000000.00,
            "invoice_date": "2026-07-15",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="invoice",
            parsed_data=parsed_data,
            source="rule",
        )

        tag_values = [t.tag for t in tags]
        assert "大额发票" in tag_values

    def test_generate_contract_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "contract_type": "服务合同",
            "contract_amount": 500000.00,
            "party_a_name": "甲方公司",
            "party_b_name": "乙方公司",
            "sign_date": "2026-07-01",
            "project_name": "项目X",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="contract",
            parsed_data=parsed_data,
            source="rule",
        )

        assert len(tags) >= 4
        tag_values = [t.tag for t in tags]
        assert "合同类型:服务合同" in tag_values
        assert "甲方:甲方公司" in tag_values
        assert "乙方:乙方公司" in tag_values
        assert "项目:项目X" in tag_values

    def test_generate_bank_statement_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "bank_name": "中国工商银行",
            "account_no": "6222021234567890",
            "transactions": [
                {"counterparty_name": "客户A", "amount": 5000.00},
                {"counterparty_name": "供应商B", "amount": -3000.00},
            ],
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="bank_statement",
            parsed_data=parsed_data,
            source="rule",
        )

        assert len(tags) >= 4
        tag_values = [t.tag for t in tags]
        assert "银行:中国工商银行" in tag_values
        assert "起始日期:2026-07-01" in tag_values
        assert "截止日期:2026-07-31" in tag_values

    def test_generate_receipt_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "amount": 15000.00,
            "payee_name": "收款方公司",
            "payer_name": "付款方公司",
            "receipt_date": "2026-07-15",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="receipt",
            parsed_data=parsed_data,
            source="rule",
        )

        tag_values = [t.tag for t in tags]
        assert "大额收据" in tag_values
        assert "收款方:收款方公司" in tag_values

    def test_generate_default_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "amount": 200000.00,
            "date": "2026-07-15",
            "party_name": "测试公司",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="unknown",
            parsed_data=parsed_data,
            source="rule",
        )

        assert len(tags) >= 2
        tag_values = [t.tag for t in tags]
        assert "大额交易" in tag_values
        assert "日期:2026-07-15" in tag_values

    def test_generate_salary_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "employee_count": 50,
            "total_amount": 2500000.00,
            "salary_period": "2026-07",
            "department": "财务部",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="salary_table",
            parsed_data=parsed_data,
            source="rule",
        )

        tag_values = [t.tag for t in tags]
        assert "人数:50" in tag_values
        assert "工资期间:2026-07" in tag_values
        assert "部门:财务部" in tag_values

    def test_generate_expense_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "expense_type": "差旅费",
            "amount": 12000.00,
            "applicant_name": "张三",
            "department": "销售部",
            "expense_date": "2026-07-10",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="expense_document",
            parsed_data=parsed_data,
            source="rule",
        )

        tag_values = [t.tag for t in tags]
        assert "费用类型:差旅费" in tag_values
        assert "大额报销" in tag_values
        assert "报销人:张三" in tag_values

    def test_generate_inventory_tags(self, db_session):
        indexer = DocumentTagIndexer(db_session)
        parsed_data = {
            "receipt_type": "采购入库",
            "goods_name": "原材料A",
            "quantity": 100,
            "amount": 50000.00,
            "supplier_name": "供应商C",
            "receipt_date": "2026-07-15",
        }

        tags = indexer.generate_tags_from_parsed_data(
            document_id=1,
            document_type="inventory_receipt",
            parsed_data=parsed_data,
            source="rule",
        )

        tag_values = [t.tag for t in tags]
        assert "入库类型:采购入库" in tag_values
        assert "商品:原材料A" in tag_values
        assert "供应商:供应商C" in tag_values

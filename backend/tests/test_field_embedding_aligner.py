# -*- coding: utf-8 -*-
"""
测试：基于 embedding 的字段名自动对齐（POC）

测试内容：
1. 余弦相似度计算
2. embedding 字段对齐（mock 方式）
3. 融合静态别名 + embedding 的标准化
4. 字段映射构建

创建日期：2026-07-03
"""
from unittest.mock import patch

import pytest

from app.services.doc_parsing.parser_engine.field_embedding_aligner import (
    _cosine_similarity,
    align_field_by_embedding,
    build_field_mapping_with_embedding,
    normalize_field_with_embedding,
)


def test_cosine_similarity_identical_vectors():
    """相同向量的余弦相似度应为 1.0"""
    vector = [1.0, 2.0, 3.0]
    assert _cosine_similarity(vector, vector) == pytest.approx(1.0, abs=1e-6)


def test_cosine_similarity_orthogonal_vectors():
    """正交向量的余弦相似度应为 0.0"""
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-6)


def test_cosine_similarity_zero_vector():
    """零向量返回 0.0，避免除零"""
    assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def _make_mock_embed(vectors_by_text, default=None):
    """构造 embed_text 的 mock 实现。

    按文本精确匹配返回预置向量；未命中时返回 default 向量，
    避免标准字段库中其他字段触发 KeyError。
    """
    if default is None:
        default = [0.0, 0.0]

    def _mock_embed(text: str):
        key = text.strip().lower()
        return vectors_by_text.get(key, default)

    return _mock_embed


@pytest.fixture(autouse=True)
def _clear_embedding_cache():
    """每个用例前清空 embedding 缓存，避免测试间互相污染"""
    from app.services.doc_parsing.parser_engine import field_embedding_aligner

    field_embedding_aligner._standard_embeddings_cache.clear()
    yield
    field_embedding_aligner._standard_embeddings_cache.clear()


def test_align_field_by_embedding_matches_synonym():
    """embedding 语义相似时应能正确对齐同义字段"""
    # 构造二维向量：让 "contract_amount" 与 "合同金额" 方向一致，
    # 与 "account_no" 方向明显不同。
    vectors = {
        "contract_amount 合同金额 合同总价 标的额 总价款 总金额": [1.0, 0.0],
        "account_no 银行账号 账号": [0.0, 1.0],
        "标的额": [1.0, 0.01],
    }

    with patch(
        "app.services.doc_parsing.parser_engine.field_embedding_aligner.embed_text",
        side_effect=_make_mock_embed(vectors),
    ):
        result = align_field_by_embedding("标的额", threshold=0.80)

    assert result == "contract_amount"


def test_align_field_by_embedding_below_threshold_returns_none():
    """相似度低于阈值时返回 None"""
    vectors = {
        "contract_amount 合同金额 合同总价 标的额 总价款 总金额": [1.0, 0.0],
        "account_no 银行账号 账号": [0.0, 1.0],
        "完全无关": [-1.0, 0.0],
    }

    with patch(
        "app.services.doc_parsing.parser_engine.field_embedding_aligner.embed_text",
        side_effect=_make_mock_embed(vectors),
    ):
        result = align_field_by_embedding("完全无关", threshold=0.80)

    assert result is None


def test_normalize_field_with_embedding_prefers_static_alias():
    """静态别名命中时直接返回，不走 embedding"""
    static_aliases = {
        "contract_amount": ["contract_total", "合同总额"],
    }

    with patch(
        "app.services.doc_parsing.parser_engine.field_embedding_aligner.embed_text"
    ) as mock_embed:
        result = normalize_field_with_embedding(
            "合同总额", static_aliases=static_aliases, embedding_threshold=0.80
        )

    assert result == "contract_amount"
    mock_embed.assert_not_called()


def test_normalize_field_with_embedding_fallback_to_embedding():
    """静态别名未命中时 fallback 到 embedding 对齐"""
    static_aliases = {
        "contract_amount": ["contract_total"],
    }
    vectors = {
        "contract_amount 合同金额 合同总价 标的额 总价款 总金额": [1.0, 0.0],
        "account_no 银行账号 账号": [0.0, 1.0],
        "标的额": [1.0, 0.01],
    }

    with patch(
        "app.services.doc_parsing.parser_engine.field_embedding_aligner.embed_text",
        side_effect=_make_mock_embed(vectors),
    ):
        result = normalize_field_with_embedding(
            "标的额", static_aliases=static_aliases, embedding_threshold=0.80
        )

    assert result == "contract_amount"


def test_build_field_mapping_with_embedding_groups_fields():
    """字段映射应把同义字段聚合到同一标准字段"""
    vectors = {
        "contract_amount 合同金额 合同总价 标的额 总价款 总金额": [1.0, 0.0],
        "account_no 银行账号 账号": [0.0, 1.0],
        "标的额": [1.0, 0.01],
        "合同总额": [1.0, 0.02],
        "银行账号": [0.01, 1.0],
    }

    with patch(
        "app.services.doc_parsing.parser_engine.field_embedding_aligner.embed_text",
        side_effect=_make_mock_embed(vectors),
    ):
        mapping = build_field_mapping_with_embedding(
            {"标的额": 1, "合同总额": 2, "银行账号": 3}, embedding_threshold=0.80
        )

    assert set(mapping.keys()) == {"contract_amount", "account_no"}
    assert sorted(mapping["contract_amount"]) == sorted(["标的额", "合同总额"])
    assert mapping["account_no"] == ["银行账号"]

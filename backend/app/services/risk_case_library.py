"""
风险案例库服务

将预定义风险案例向量化入库，用于相似风险发现
"""

from typing import Any

from app.services.summary_template_service import (
    RISK_CASES,
    get_risk_cases,
)
from app.services.vector_store_service import (
    safe_vector_store,
    chunk_hash,
    chunk_text,
)


# 风险案例向量集合名称
RISK_CASE_COLLECTION = "risk_cases"


def build_risk_case_text(case: dict[str, Any]) -> str:
    """构建风险案例文本（用于向量化）"""
    return (
        f"摘要模式：{case['summary_pattern']}\n"
        f"借方科目：{case['debit_pattern']}\n"
        f"贷方科目：{case['credit_pattern']}\n"
        f"风险类型：{case['risk_type']}\n"
        f"风险描述：{case['risk_description']}\n"
        f"正确模式：{case.get('correct_pattern', '')}\n"
        f"严重程度：{case['severity']}\n"
        f"审计建议：{case['audit_suggestion']}"
    )


def initialize_risk_case_vectors() -> bool:
    """
    初始化风险案例向量

    将预定义风险案例向量化到向量库
    """
    store = safe_vector_store()
    if not store:
        return False

    try:
        for case in RISK_CASES:
            case_text = build_risk_case_text(case)
            case_id = case["id"]

            # 尝试创建集合（如果不存在）
            try:
                store.client.create_collection(
                    collection_name=RISK_CASE_COLLECTION,
                    vectors_config={"size": 1536, "distance": "Cosine"},
                )
            except Exception:
                pass  # 集合可能已存在

            # 向量化并存储
            for chunk in chunk_text(case_text):
                try:
                    store.upsert_text(
                        point_id=case_id,
                        text=chunk,
                        payload={
                            "case_id": case_id,
                            "risk_type": case["risk_type"],
                            "severity": case["severity"],
                            "summary_pattern": case["summary_pattern"],
                            "debit_pattern": case["debit_pattern"],
                            "credit_pattern": case["credit_pattern"],
                            "risk_description": case["risk_description"],
                            "audit_suggestion": case["audit_suggestion"],
                            "is_risk_case": True,
                        },
                    )
                except Exception:
                    pass

        return True
    except Exception:
        return False


def search_similar_risk_cases(
    text: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    搜索相似的风险案例

    Args:
        text: 要搜索的文本（分录摘要+科目组合）
        limit: 返回数量限制

    Returns:
        匹配的风险案例列表
    """
    store = safe_vector_store()
    if not store:
        return []

    try:
        # 搜索相似风险案例
        results = store.search(
            query_text=text,
            limit=limit,
            filter_params={"is_risk_case": True},
        )

        similar_cases = []
        for result in results:
            if result.score >= 0.7:  # 相似度阈值
                similar_cases.append({
                    "case_id": result.payload.get("case_id"),
                    "risk_type": result.payload.get("risk_type"),
                    "severity": result.payload.get("severity"),
                    "summary_pattern": result.payload.get("summary_pattern"),
                    "risk_description": result.payload.get("risk_description"),
                    "audit_suggestion": result.payload.get("audit_suggestion"),
                    "similarity_score": result.score,
                })

        return similar_cases
    except Exception:
        return []


def enhance_entry_with_risk_analysis(entry: dict[str, Any]) -> dict[str, Any]:
    """
    增强分录，添加风险分析

    基于分录内容搜索相似风险案例
    """
    # 构建搜索文本
    search_text = " ".join(filter(None, [
        entry.get("summary", ""),
        entry.get("account_name", ""),
        entry.get("account_code", ""),
        entry.get("counterparty", ""),
    ]))

    # 搜索相似风险案例
    similar_cases = search_similar_risk_cases(search_text, limit=3)

    # 添加到分录
    entry["risk_cases"] = similar_cases

    return entry


def get_risk_case_summary() -> dict[str, Any]:
    """获取风险案例库摘要"""
    total = len(RISK_CASES)

    # 按风险类型统计
    by_type = {}
    for case in RISK_CASES:
        risk_type = case["risk_type"]
        by_type[risk_type] = by_type.get(risk_type, 0) + 1

    # 按严重程度统计
    by_severity = {}
    for case in RISK_CASES:
        severity = case["severity"]
        by_severity[severity] = by_severity.get(severity, 0) + 1

    return {
        "total_cases": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "cases": RISK_CASES,
    }

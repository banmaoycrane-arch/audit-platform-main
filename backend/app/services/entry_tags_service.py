"""
Tags 多维度语义标签服务

将分录中的二级科目、辅助核算项目等统一转为 tags
支持多维度的语义分析和检索
"""

from typing import Any

from app.services.tagging_service import suggest_tags, suggest_voucher_type, VOUCHER_TYPES


# 辅助核算类型定义
AUXILIARY_TYPES = {
    "department": ["部门", "department", "部室"],
    "person": ["人员", "个人", "员工", "person", "staff"],
    "supplier": ["供应商", "vendor", "supply"],
    "customer": ["客户", "customer", "buyer"],
    "project": ["项目", "project", "工程"],
    "item": ["商品", "产品", "item", "product"],
    "contract": ["合同", "contract", "协议"],
}


def extract_auxiliary_tags(entry: dict[str, Any]) -> list[str]:
    """
    从分录中提取辅助核算标签

    辅助核算项目包括：部门、人员、供应商、客户、项目等
    """
    tags = []

    # 从往来单位提取
    counterparty = entry.get("counterparty", "")
    if counterparty:
        tags.append(f"往来单位:{counterparty}")

    # 从摘要中提取可能的辅助核算信息
    summary = entry.get("summary", "")
    account_name = entry.get("account_name", "")

    # 检查是否为供应商相关
    for kw in AUXILIARY_TYPES["supplier"]:
        if kw in summary or kw in account_name:
            tags.append("类型:供应商")
            break

    # 检查是否为客户相关
    for kw in AUXILIARY_TYPES["customer"]:
        if kw in summary or kw in account_name:
            tags.append("类型:客户")
            break

    # 检查是否为部门相关
    for kw in AUXILIARY_TYPES["department"]:
        if kw in summary:
            tags.append("类型:部门")
            break

    return tags


def generate_entry_tags(entry: dict[str, Any]) -> list[str]:
    """
    为分录生成完整的 tags

    Tags 来源：
    1. 凭证字推荐
    2. 自动标签（大额、期末等）
    3. 辅助核算标签
    4. 科目相关标签
    """
    tags = []

    # 1. 凭证字标签
    account_name = entry.get("account_name", "")
    summary = entry.get("summary", "")
    counterparty = entry.get("counterparty", "")

    # 创建模拟对象用于标签推荐
    class MockEntry:
        def __init__(self, e):
            self.summary = e.get("summary", "")
            self.account_name = e.get("account_name", "")
            self.debit_amount = e.get("debit_amount", 0)
            self.credit_amount = e.get("credit_amount", 0)
            self.voucher_date = e.get("voucher_date")
            self.account_code = e.get("account_code", "")

    mock_entry = MockEntry(entry)
    suggested_tags = suggest_tags(mock_entry)

    for tag, _ in suggested_tags:
        if tag.startswith("凭证字:"):
            tags.append(tag)
        elif tag in ["大额交易", "特大额交易", "期末交易", "需人工复核"]:
            tags.append(tag)

    # 2. 科目相关标签
    if account_name:
        # 二级科目标签
        if "银行存款" in account_name:
            tags.append("科目:银行存款")
        elif "库存现金" in account_name:
            tags.append("科目:库存现金")
        elif "应收账款" in account_name:
            tags.append("科目:应收账款")
        elif "应付账款" in account_name:
            tags.append("科目:应付账款")
        elif "主营业务收入" in account_name:
            tags.append("科目:主营业务收入")
        elif "主营业务成本" in account_name:
            tags.append("科目:主营业务成本")
        elif "管理费用" in account_name:
            tags.append("科目:管理费用")
        elif "销售费用" in account_name:
            tags.append("科目:销售费用")
        elif "财务费用" in account_name:
            tags.append("科目:财务费用")
        elif "其他应收" in account_name:
            tags.append("科目:其他应收")
        elif "其他应付" in account_name:
            tags.append("科目:其他应付")
        elif "固定资产" in account_name:
            tags.append("科目:固定资产")
        elif "累计折旧" in account_name:
            tags.append("科目:累计折旧")
        elif "无形资产" in account_name:
            tags.append("科目:无形资产")
        elif "短期借款" in account_name:
            tags.append("科目:短期借款")
        elif "长期借款" in account_name:
            tags.append("科目:长期借款")
        elif "应付职工薪酬" in account_name:
            tags.append("科目:应付职工薪酬")
        elif "应交税费" in account_name:
            tags.append("科目:应交税费")
        elif "本年利润" in account_name:
            tags.append("科目:本年利润")
        elif "利润分配" in account_name:
            tags.append("科目:利润分配")

    # 3. 往来标签
    if counterparty:
        tags.append(f"往来单位:{counterparty}")

    # 4. 金额规模标签
    amount = entry.get("debit_amount", 0) or entry.get("credit_amount", 0)
    if amount >= 10000000:  # 千万以上
        tags.append("规模:千万级")
    elif amount >= 1000000:  # 百万以上
        tags.append("规模:百万级")
    elif amount >= 100000:  # 十万以上
        tags.append("规模:十万级")

    # 5. 辅助核算标签
    auxiliary_tags = extract_auxiliary_tags(entry)
    tags.extend(auxiliary_tags)

    # 去重
    return list(set(tags))


def build_semantic_text(entry: dict[str, Any], tags: list[str]) -> str:
    """
    构建用于向量化的语义文本

    将摘要、科目、tags 等多维度信息合并为语义完整的文本
    """
    parts = [
        entry.get("summary", ""),
        entry.get("account_name", ""),
        entry.get("account_code", ""),
        entry.get("counterparty", ""),
        # 添加 tags 作为语义增强
        " ".join(tags),
    ]

    # 添加借贷信息
    debit = entry.get("debit_amount", 0)
    credit = entry.get("credit_amount", 0)
    if debit > 0:
        parts.append(f"借方金额{debit}")
    if credit > 0:
        parts.append(f"贷方金额{credit}")

    return " ".join(filter(None, parts))


def get_tag_stats(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    获取 tags 统计信息

    用于分析分录中的标签分布
    """
    all_tags: dict[str, int] = {}
    tag_by_category: dict[str, dict[str, int]] = {
        "凭证字": {},
        "科目": {},
        "往来单位": {},
        "规模": {},
        "风险": {},
    }

    for entry in entries:
        tags = generate_entry_tags(entry)
        for tag in tags:
            all_tags[tag] = all_tags.get(tag, 0) + 1

            # 按类别统计
            if tag.startswith("凭证字:"):
                tag_by_category["凭证字"][tag] = tag_by_category["凭证字"].get(tag, 0) + 1
            elif tag.startswith("科目:"):
                tag_by_category["科目"][tag] = tag_by_category["科目"].get(tag, 0) + 1
            elif tag.startswith("往来单位:"):
                tag_by_category["往来单位"][tag] = tag_by_category["往来单位"].get(tag, 0) + 1
            elif tag.startswith("规模:"):
                tag_by_category["规模"][tag] = tag_by_category["规模"].get(tag, 0) + 1
            elif tag in ["大额交易", "特大额交易", "期末交易", "需人工复核"]:
                tag_by_category["风险"][tag] = tag_by_category["风险"].get(tag, 0) + 1

    return {
        "total_tags": len(all_tags),
        "unique_tags": len(set(all_tags.keys())),
        "top_tags": sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:20],
        "by_category": tag_by_category,
    }

# -*- coding: utf-8 -*-
"""
文档标签索引服务（DocumentTag Indexer）。

业务场景：
    根据文档解析结果（发票、合同、银行流水等）自动生成语义标签，
    支持规则引擎和AI引擎两种方式，生成后同步到向量数据库。

政策依据：
    标签仅用于辅助检索和风险识别，不参与正式会计处理。
    AI生成的标签需人工复核后才能提升置信度。

输入数据：
    - document_id / document_type: 文档标识与类型
    - parsed_data: 解析后的结构化数据
    - extracted_text: 原始文本内容（用于AI标签生成）

输出结果：
    - 生成的 DocumentTag 列表
    - 向量同步状态
"""
import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DocumentTag
from app.services.doc_parsing.document_tag_service import (
    create_document_tags_batch,
    delete_document_tags_by_document,
)
from app.services.agent.llm_client_service import LightweightLLMClient, LLMResult


class DocumentTagIndexer:
    """
    文档标签索引器，负责基于解析结果生成文档语义标签。
    支持规则引擎和AI引擎两种方式。
    """

    def __init__(self, db: Session, llm_client: LightweightLLMClient | None = None):
        self.db = db
        self.llm_client = llm_client or LightweightLLMClient()

    def generate_tags_from_parsed_data(
        self,
        document_id: int,
        document_type: str,
        parsed_data: dict[str, Any],
        source: str = "rule",
    ) -> list[DocumentTag]:
        """
        根据解析后的结构化数据生成标签。

        Args:
            document_id: 文档ID
            document_type: 文档类型（invoice/contract/bank_statement/receipt等）
            parsed_data: 解析结果字典
            source: 标签来源（rule/ai/manual）

        Returns:
            list[DocumentTag]: 生成的标签列表
        """
        tag_generators = {
            "invoice": self._generate_invoice_tags,
            "contract": self._generate_contract_tags,
            "bank_statement": self._generate_bank_statement_tags,
            "receipt": self._generate_receipt_tags,
            "expense_document": self._generate_expense_tags,
            "salary_table": self._generate_salary_tags,
            "inventory_receipt": self._generate_inventory_tags,
        }

        generator = tag_generators.get(document_type, self._generate_default_tags)
        tags = generator(parsed_data, source)

        delete_document_tags_by_document(self.db, document_id)
        created_tags = create_document_tags_batch(
            self.db, document_id, document_type, tags
        )
        return created_tags

    def _generate_invoice_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成发票文档标签。
        """
        tags = []

        # 业务类型标签
        invoice_type = parsed_data.get("invoice_type", "")
        if invoice_type:
            tags.append({"tag": f"发票类型:{invoice_type}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 金额规模标签
        total_amount = parsed_data.get("total_amount", 0)
        if total_amount:
            try:
                amount = Decimal(str(total_amount))
                if amount > Decimal("1000000"):
                    tags.append({"tag": "大额发票", "tag_type": "amount", "confidence": 0.95, "source": source})
                elif amount > Decimal("100000"):
                    tags.append({"tag": "中额发票", "tag_type": "amount", "confidence": 0.9, "source": source})
            except (ValueError, TypeError):
                pass

        # 税率标签
        tax_rate = parsed_data.get("tax_rate", "")
        if tax_rate:
            tags.append({"tag": f"税率:{tax_rate}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 销售方标签
        seller_name = parsed_data.get("seller_name", "")
        if seller_name:
            tags.append({"tag": f"销售方:{seller_name}", "tag_type": "relation", "confidence": 0.85, "source": source})

        # 购买方标签
        buyer_name = parsed_data.get("buyer_name", "")
        if buyer_name:
            tags.append({"tag": f"购买方:{buyer_name}", "tag_type": "relation", "confidence": 0.85, "source": source})

        # 日期标签
        invoice_date = parsed_data.get("invoice_date", "")
        if invoice_date:
            invoice_date_str = str(invoice_date)
            tags.append({"tag": f"开票日期:{invoice_date_str}", "tag_type": "time", "confidence": 0.95, "source": source})
            # 提取年份和月份
            if "-" in invoice_date_str:
                year_month = invoice_date_str[:7]
                tags.append({"tag": f"期间:{year_month}", "tag_type": "time", "confidence": 0.95, "source": source})

        # 货物名称标签
        goods_name = parsed_data.get("goods_name", "")
        if goods_name:
            tags.append({"tag": f"货物:{goods_name}", "tag_type": "business", "confidence": 0.8, "source": source})

        # 校验状态标签
        if parsed_data.get("validation_passed"):
            tags.append({"tag": "校验通过", "tag_type": "status", "confidence": 0.9, "source": source})
        if parsed_data.get("validation_warnings"):
            tags.append({"tag": "校验异常", "tag_type": "status", "confidence": 0.9, "source": source})

        return tags

    def _generate_contract_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成合同文档标签。
        """
        tags = []

        # 合同类型标签
        contract_type = parsed_data.get("contract_type", "")
        if contract_type:
            tags.append({"tag": f"合同类型:{contract_type}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 金额规模标签
        contract_amount = parsed_data.get("contract_amount", 0)
        if contract_amount:
            try:
                amount = Decimal(str(contract_amount))
                if amount > Decimal("1000000"):
                    tags.append({"tag": "大额合同", "tag_type": "amount", "confidence": 0.95, "source": source})
                elif amount > Decimal("100000"):
                    tags.append({"tag": "中额合同", "tag_type": "amount", "confidence": 0.9, "source": source})
            except (ValueError, TypeError):
                pass

        # 甲方标签
        party_a_name = parsed_data.get("party_a_name", "")
        if party_a_name:
            tags.append({"tag": f"甲方:{party_a_name}", "tag_type": "relation", "confidence": 0.9, "source": source})

        # 乙方标签
        party_b_name = parsed_data.get("party_b_name", "")
        if party_b_name:
            tags.append({"tag": f"乙方:{party_b_name}", "tag_type": "relation", "confidence": 0.9, "source": source})

        # 日期标签
        sign_date = parsed_data.get("sign_date", "")
        if sign_date:
            tags.append({"tag": f"签订日期:{sign_date}", "tag_type": "time", "confidence": 0.95, "source": source})

        # 合同期限标签
        contract_term = parsed_data.get("contract_term", "")
        if contract_term:
            tags.append({"tag": f"合同期限:{contract_term}", "tag_type": "time", "confidence": 0.85, "source": source})

        # 项目名称标签
        project_name = parsed_data.get("project_name", "")
        if project_name:
            tags.append({"tag": f"项目:{project_name}", "tag_type": "business", "confidence": 0.85, "source": source})

        return tags

    def _generate_bank_statement_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成银行流水文档标签。
        """
        tags = []

        # 银行名称标签
        bank_name = parsed_data.get("bank_name", "")
        if bank_name:
            tags.append({"tag": f"银行:{bank_name}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 账号标签
        account_no = parsed_data.get("account_no", "")
        if account_no:
            tags.append({"tag": f"账号:{account_no[-4:]}", "tag_type": "business", "confidence": 0.8, "source": source})

        # 交易规模标签
        total_inflow = parsed_data.get("total_inflow", 0)
        total_outflow = parsed_data.get("total_outflow", 0)
        try:
            inflow = Decimal(str(total_inflow or 0))
            outflow = Decimal(str(total_outflow or 0))
            total_transaction = inflow + outflow
            if total_transaction > Decimal("1000000"):
                tags.append({"tag": "大额流水", "tag_type": "amount", "confidence": 0.9, "source": source})
            elif total_transaction > Decimal("100000"):
                tags.append({"tag": "中额流水", "tag_type": "amount", "confidence": 0.85, "source": source})
        except (ValueError, TypeError):
            pass

        # 交易数量标签
        transactions = parsed_data.get("transactions", [])
        if transactions:
            tag_count = min(len(transactions), 50)
            tags.append({"tag": f"交易笔数:{tag_count}", "tag_type": "amount", "confidence": 0.95, "source": source})

            # 汇总对方户名
            counterparty_names = []
            for trans in transactions[:10]:
                name = trans.get("counterparty_name", "")
                if name and name not in counterparty_names:
                    counterparty_names.append(name)
            for name in counterparty_names:
                tags.append({"tag": f"对方:{name}", "tag_type": "relation", "confidence": 0.8, "source": source})

        # 余额标签
        closing_balance = parsed_data.get("closing_balance", 0)
        if closing_balance:
            tags.append({"tag": f"期末余额:{closing_balance}", "tag_type": "amount", "confidence": 0.9, "source": source})

        # 日期范围标签
        start_date = parsed_data.get("start_date", "")
        end_date = parsed_data.get("end_date", "")
        if start_date:
            tags.append({"tag": f"起始日期:{start_date}", "tag_type": "time", "confidence": 0.9, "source": source})
        if end_date:
            tags.append({"tag": f"截止日期:{end_date}", "tag_type": "time", "confidence": 0.9, "source": source})

        return tags

    def _generate_receipt_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成收据文档标签。
        """
        tags = []

        # 金额标签
        amount = parsed_data.get("amount", 0)
        if amount:
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal > Decimal("10000"):
                    tags.append({"tag": "大额收据", "tag_type": "amount", "confidence": 0.9, "source": source})
            except (ValueError, TypeError):
                pass

        # 收款方标签
        payee_name = parsed_data.get("payee_name", "")
        if payee_name:
            tags.append({"tag": f"收款方:{payee_name}", "tag_type": "relation", "confidence": 0.85, "source": source})

        # 付款方标签
        payer_name = parsed_data.get("payer_name", "")
        if payer_name:
            tags.append({"tag": f"付款方:{payer_name}", "tag_type": "relation", "confidence": 0.85, "source": source})

        # 日期标签
        receipt_date = parsed_data.get("receipt_date", "")
        if receipt_date:
            tags.append({"tag": f"收款日期:{receipt_date}", "tag_type": "time", "confidence": 0.95, "source": source})

        return tags

    def _generate_expense_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成费用报销文档标签。
        """
        tags = []

        # 费用类型标签
        expense_type = parsed_data.get("expense_type", "")
        if expense_type:
            tags.append({"tag": f"费用类型:{expense_type}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 金额标签
        amount = parsed_data.get("amount", 0)
        if amount:
            try:
                amount_decimal = Decimal(str(amount))
                if amount_decimal > Decimal("10000"):
                    tags.append({"tag": "大额报销", "tag_type": "amount", "confidence": 0.9, "source": source})
            except (ValueError, TypeError):
                pass

        # 报销人标签
        applicant_name = parsed_data.get("applicant_name", "")
        if applicant_name:
            tags.append({"tag": f"报销人:{applicant_name}", "tag_type": "relation", "confidence": 0.9, "source": source})

        # 部门标签
        department = parsed_data.get("department", "")
        if department:
            tags.append({"tag": f"部门:{department}", "tag_type": "business", "confidence": 0.85, "source": source})

        # 日期标签
        expense_date = parsed_data.get("expense_date", "")
        if expense_date:
            tags.append({"tag": f"费用日期:{expense_date}", "tag_type": "time", "confidence": 0.9, "source": source})

        return tags

    def _generate_salary_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成工资表文档标签。
        """
        tags = []

        # 人数标签
        employee_count = parsed_data.get("employee_count", 0)
        if employee_count:
            tags.append({"tag": f"人数:{employee_count}", "tag_type": "amount", "confidence": 0.95, "source": source})

        # 总金额标签
        total_amount = parsed_data.get("total_amount", 0)
        if total_amount:
            try:
                amount_decimal = Decimal(str(total_amount))
                tags.append({"tag": f"工资总额:{amount_decimal}", "tag_type": "amount", "confidence": 0.95, "source": source})
            except (ValueError, TypeError):
                pass

        # 期间标签
        salary_period = parsed_data.get("salary_period", "")
        if salary_period:
            tags.append({"tag": f"工资期间:{salary_period}", "tag_type": "time", "confidence": 0.95, "source": source})

        # 部门标签
        department = parsed_data.get("department", "")
        if department:
            tags.append({"tag": f"部门:{department}", "tag_type": "business", "confidence": 0.85, "source": source})

        return tags

    def _generate_inventory_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成入库单/物流单文档标签。
        """
        tags = []

        # 入库类型标签
        receipt_type = parsed_data.get("receipt_type", "")
        if receipt_type:
            tags.append({"tag": f"入库类型:{receipt_type}", "tag_type": "business", "confidence": 0.9, "source": source})

        # 商品名称标签
        goods_name = parsed_data.get("goods_name", "")
        if goods_name:
            tags.append({"tag": f"商品:{goods_name}", "tag_type": "business", "confidence": 0.85, "source": source})

        # 数量标签
        quantity = parsed_data.get("quantity", 0)
        if quantity:
            tags.append({"tag": f"数量:{quantity}", "tag_type": "amount", "confidence": 0.9, "source": source})

        # 金额标签
        amount = parsed_data.get("amount", 0)
        if amount:
            try:
                amount_decimal = Decimal(str(amount))
                tags.append({"tag": f"金额:{amount_decimal}", "tag_type": "amount", "confidence": 0.9, "source": source})
            except (ValueError, TypeError):
                pass

        # 供应商标签
        supplier_name = parsed_data.get("supplier_name", "")
        if supplier_name:
            tags.append({"tag": f"供应商:{supplier_name}", "tag_type": "relation", "confidence": 0.85, "source": source})

        # 日期标签
        receipt_date = parsed_data.get("receipt_date", "")
        if receipt_date:
            tags.append({"tag": f"入库日期:{receipt_date}", "tag_type": "time", "confidence": 0.95, "source": source})

        return tags

    def _generate_default_tags(
        self,
        parsed_data: dict[str, Any],
        source: str,
    ) -> list[dict[str, Any]]:
        """
        生成默认标签（通用逻辑）。
        """
        tags = []

        # 金额标签（通用）
        amount_fields = ["amount", "total_amount", "contract_amount", "transaction_amount"]
        for field in amount_fields:
            amount = parsed_data.get(field, 0)
            if amount:
                try:
                    amount_decimal = Decimal(str(amount))
                    if amount_decimal > Decimal("100000"):
                        tags.append({"tag": "大额交易", "tag_type": "amount", "confidence": 0.85, "source": source})
                    break
                except (ValueError, TypeError):
                    continue

        # 日期标签（通用）
        date_fields = ["date", "document_date", "create_date", "receipt_date"]
        for field in date_fields:
            doc_date = parsed_data.get(field, "")
            if doc_date:
                tags.append({"tag": f"日期:{doc_date}", "tag_type": "time", "confidence": 0.9, "source": source})
                break

        # 关联方标签（通用）
        party_fields = ["party_name", "counterparty_name", "supplier_name", "customer_name", "buyer_name", "seller_name"]
        for field in party_fields:
            party_name = parsed_data.get(field, "")
            if party_name:
                tags.append({"tag": f"关联方:{party_name}", "tag_type": "relation", "confidence": 0.8, "source": source})
                break

        return tags

    def generate_tags_with_ai(
        self,
        document_id: int,
        document_type: str,
        extracted_text: str,
        parsed_data: dict[str, Any] | None = None,
    ) -> list[DocumentTag]:
        """
        使用AI/LLM从文档文本中生成语义标签。

        业务逻辑：
            1. 调用LLM分析文档文本
            2. 提取业务、风险、关联方、时间、金额等维度标签
            3. 与规则引擎生成的标签合并去重
            4. AI生成的标签置信度设置为0.75（需人工复核）

        Args:
            document_id: 文档ID
            document_type: 文档类型
            extracted_text: 文档原始文本内容
            parsed_data: 已解析的结构化数据（可选，用于补充）

        Returns:
            list[DocumentTag]: 生成的标签列表
        """
        if not self.llm_client.is_configured():
            return self.generate_tags_from_parsed_data(
                document_id=document_id,
                document_type=document_type,
                parsed_data=parsed_data or {},
                source="rule",
            )

        ai_tags = self._call_llm_for_tags(document_type, extracted_text, parsed_data)
        rule_tags = []
        if parsed_data:
            rule_tags = self.generate_tags_from_parsed_data(
                document_id=document_id,
                document_type=document_type,
                parsed_data=parsed_data,
                source="rule",
            )

        all_tags: list[DocumentTag | dict[str, Any]] = []
        seen_tags: set[tuple[str, str]] = set()

        for tag in rule_tags:
            key = (tag.tag_type, tag.tag)
            if key not in seen_tags:
                seen_tags.add(key)
                all_tags.append(tag)

        for tag_data in ai_tags:
            key = (tag_data["tag_type"], tag_data["tag"])
            if key not in seen_tags:
                seen_tags.add(key)
                all_tags.append(tag_data)

        delete_document_tags_by_document(self.db, document_id)
        created_tags = []
        for tag_item in all_tags:
            if isinstance(tag_item, DocumentTag):
                new_tag = create_document_tag(
                    db=self.db,
                    document_id=document_id,
                    document_type=document_type,
                    tag=tag_item.tag,
                    tag_type=tag_item.tag_type,
                    confidence=tag_item.confidence,
                    source=tag_item.source,
                )
                created_tags.append(new_tag)
            else:
                new_tag = create_document_tag(
                    db=self.db,
                    document_id=document_id,
                    document_type=document_type,
                    tag=tag_item["tag"],
                    tag_type=tag_item["tag_type"],
                    confidence=tag_item.get("confidence", 0.75),
                    source=tag_item.get("source", "ai"),
                )
                created_tags.append(new_tag)

        return created_tags

    def generate_tags_hybrid(
        self,
        document_id: int,
        document_type: str,
        extracted_text: str,
        parsed_data: dict[str, Any],
        ai_enabled: bool = True,
    ) -> list[DocumentTag]:
        """
        混合方式生成标签（规则引擎为主，AI补充）。

        业务逻辑：
            1. 优先使用规则引擎生成基础标签（高置信度）
            2. 如果AI可用，调用AI生成补充标签（中等置信度）
            3. 合并去重，规则引擎标签优先级更高

        Args:
            document_id: 文档ID
            document_type: 文档类型
            extracted_text: 文档原始文本内容
            parsed_data: 已解析的结构化数据
            ai_enabled: 是否启用AI补充

        Returns:
            list[DocumentTag]: 生成的标签列表
        """
        if ai_enabled and self.llm_client.is_configured():
            return self.generate_tags_with_ai(
                document_id=document_id,
                document_type=document_type,
                extracted_text=extracted_text,
                parsed_data=parsed_data,
            )
        else:
            return self.generate_tags_from_parsed_data(
                document_id=document_id,
                document_type=document_type,
                parsed_data=parsed_data,
                source="rule",
            )

    def _call_llm_for_tags(
        self,
        document_type: str,
        extracted_text: str,
        parsed_data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        调用LLM生成文档标签。

        Args:
            document_type: 文档类型
            extracted_text: 文档原始文本
            parsed_data: 已解析的结构化数据

        Returns:
            list[dict]: AI生成的标签列表
        """
        system_prompt = """你是一名专业的财务文档标签分析师。请分析以下文档内容，提取语义标签。

标签类型说明：
- business: 业务性质、交易类型、产品/服务类别、行业分类
- risk: 风险提示、异常特征、合规风险、关联交易风险、大额异常
- relation: 关联方、交易对手、合同方、供应商、客户、银行
- time: 日期、期间、时效、到期日、开票日、签订日
- amount: 金额规模、数量级别、大额/中额/小额分类
- status: 审核状态、校验结果、凭证状态

标签值格式规范：
1. 使用"类型:值"格式，如"发票类型:增值税专用发票"、"金额规模:大额"
2. 标签值应简洁明确，不超过20个字符
3. 避免重复的标签值
4. 金额规模判断标准：大额(>100万)、中额(10万-100万)、小额(<10万)

输出格式要求：
必须返回严格的JSON数组格式，每个元素包含 tag、tag_type、confidence 三个字段：
[
    {"tag": "发票类型:增值税专用发票", "tag_type": "business", "confidence": 0.95},
    {"tag": "金额规模:大额", "tag_type": "amount", "confidence": 0.9},
    {"tag": "销售方:北京科技有限公司", "tag_type": "relation", "confidence": 0.85},
    {"tag": "开票日期:2026-07-15", "tag_type": "time", "confidence": 0.95},
    {"tag": "校验状态:通过", "tag_type": "status", "confidence": 0.8}
]

标签生成规则：
1. 从文档中提取关键实体和语义特征
2. 优先提取已解析数据中的结构化信息
3. 从原始文本中补充提取未结构化的语义信息
4. 置信度范围0-1，根据提取确定性设置
5. 至少生成3个标签，最多生成10个标签
6. 避免重复的标签
7. 风险标签应基于文档内容推断潜在风险（如：关联交易、大额现金、异常日期等）"""

        user_prompt = f"""文档类型：{document_type}

已解析数据：
{json.dumps(parsed_data or {}, ensure_ascii=False, indent=2)}

文档原始文本（前2000字）：
{extracted_text[:2000]}

请生成语义标签："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = self.llm_client.chat(messages, temperature=0.3)

        if not result.available or not result.content:
            return []

        try:
            tags = json.loads(result.content)
            if isinstance(tags, list):
                validated_tags = []
                for tag in tags:
                    if isinstance(tag, dict) and "tag" in tag and "tag_type" in tag:
                        validated_tags.append({
                            "tag": tag["tag"],
                            "tag_type": tag.get("tag_type", "business"),
                            "confidence": tag.get("confidence", 0.75),
                            "source": "ai",
                        })
                return validated_tags
        except (json.JSONDecodeError, ValueError):
            pass

        return []


def create_document_tag(
    db: Session,
    document_id: int,
    document_type: str,
    tag: str,
    tag_type: str,
    confidence: float = 0.8,
    source: str = "rule",
) -> DocumentTag:
    """
    为文档创建标签（内部辅助函数）。
    """
    from app.services.doc_parsing.document_tag_service import create_document_tag as service_create
    return service_create(
        db=db,
        document_id=document_id,
        document_type=document_type,
        tag=tag,
        tag_type=tag_type,
        confidence=confidence,
        source=source,
    )

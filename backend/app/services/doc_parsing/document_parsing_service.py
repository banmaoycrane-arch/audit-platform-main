from datetime import date, datetime
from decimal import Decimal
import re
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import (
    Contract, ContractParty, ContractPerformanceObligation, ContractPaymentTerm,
    Invoice, InvoiceItem, InventoryDocument, InventoryItem, BankStatement,
    Company, CompanyPersonnel, RelatedPartyRelation, FieldAliasMapping,
    Organization
)
from app.services.doc_parsing.document_tag_indexer import DocumentTagIndexer


def _to_decimal_or_none(value: Any, precision: str = "0.01") -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(precision))
    except (ValueError, TypeError):
        return None


class DocumentParsingService:
    def __init__(self, db: Session):
        self.db = db

    def parse_contract(self, organization_id: int, contract_data: Dict[str, Any]) -> Contract:
        explicit_parties = contract_data.get("parties", [])
        extracted_parties = self.extract_contract_parties_from_text(contract_data.get("extracted_text"))
        final_parties = []
        seen = set()

        for party_data in [*explicit_parties, *extracted_parties]:
            party_role = party_data.get("party_role", "party_a")
            party_name = party_data.get("party_name")
            if not party_name:
                continue
            party_name = party_name.strip() if isinstance(party_name, str) else party_name
            key = (party_role, party_name)
            if key in seen:
                continue
            seen.add(key)
            final_party_data = dict(party_data)
            final_party_data["party_name"] = party_name
            final_parties.append(final_party_data)

        contract_data["parties"] = final_parties

        contract = Contract(
            organization_id=organization_id,
            ledger_id=contract_data.get("ledger_id"),
            counterparty_id=contract_data.get("counterparty_id"),
            execution_status=contract_data.get("execution_status", "pending"),
            source_file_id=contract_data.get("source_file_id"),
            contract_no=contract_data.get("contract_no"),
            contract_type=contract_data.get("contract_type", "service"),
            contract_name=contract_data.get("contract_name"),
            sign_date=contract_data.get("sign_date"),
            start_date=contract_data.get("start_date"),
            end_date=contract_data.get("end_date"),
            effective_date=contract_data.get("effective_date"),
            contract_amount=_to_decimal_or_none(contract_data.get("contract_amount")),
            currency=contract_data.get("currency", "CNY"),
            tax_rate=_to_decimal_or_none(contract_data.get("tax_rate"), precision="0.0001"),
            tax_amount=_to_decimal_or_none(contract_data.get("tax_amount")),
            performance_obligations=contract_data.get("performance_obligations", {}),
            transaction_price=_to_decimal_or_none(contract_data.get("transaction_price")),
            standalone_price=_to_decimal_or_none(contract_data.get("standalone_price")),
            is_over_time=contract_data.get("is_over_time", False),
            progress_method=contract_data.get("progress_method"),
            completion_percentage=contract_data.get("completion_percentage", 0.0),
            revenue_recognition_type=self._determine_revenue_recognition(contract_data),
            extracted_text=contract_data.get("extracted_text"),
            confidence_score=contract_data.get("confidence_score", 0.8)
        )
        
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        
        for party_data in contract_data.get("parties", []):
            self._add_contract_party(contract.id, party_data)
        
        for obligation_data in contract_data.get("performance_obligations_list", []):
            self._add_performance_obligation(contract.id, obligation_data)
        
        for term_data in contract_data.get("payment_terms", []):
            self._add_payment_term(contract.id, term_data)
        
        self.db.commit()
        
        self._generate_contract_tags(contract.id, contract_data)
        
        return contract

    def _determine_revenue_recognition(self, contract_data: Dict[str, Any]) -> str:
        if contract_data.get("is_over_time"):
            return "over_time"
        return "point_in_time"

    def _add_contract_party(self, contract_id: int, party_data: Dict[str, Any]) -> None:
        party = ContractParty(
            contract_id=contract_id,
            party_role=party_data.get("party_role", "party_a"),
            party_type=party_data.get("party_type", "enterprise"),
            party_name=party_data.get("party_name"),
            party_code=party_data.get("party_code"),
            party_address=party_data.get("party_address"),
            party_contact=party_data.get("party_contact"),
            party_phone=party_data.get("party_phone"),
            legal_representative=party_data.get("legal_representative")
        )
        self.db.add(party)

    def _add_performance_obligation(self, contract_id: int, obligation_data: Dict[str, Any]) -> None:
        obligation = ContractPerformanceObligation(
            contract_id=contract_id,
            obligation_no=obligation_data.get("obligation_no", "PO-001"),
            obligation_name=obligation_data.get("obligation_name"),
            obligation_description=obligation_data.get("obligation_description"),
            standalone_price=_to_decimal_or_none(obligation_data.get("standalone_price")),
            allocated_price=_to_decimal_or_none(obligation_data.get("allocated_price")),
            allocation_method=obligation_data.get("allocation_method"),
            is_over_time=obligation_data.get("is_over_time", False),
            progress_method=obligation_data.get("progress_method"),
            completion_percentage=obligation_data.get("completion_percentage", 0.0),
            revenue_recognized=_to_decimal_or_none(obligation_data.get("revenue_recognized")),
            revenue_pending=_to_decimal_or_none(obligation_data.get("revenue_pending"))
        )
        self.db.add(obligation)

    def _add_payment_term(self, contract_id: int, term_data: Dict[str, Any]) -> None:
        term = ContractPaymentTerm(
            contract_id=contract_id,
            term_no=term_data.get("term_no", 1),
            term_name=term_data.get("term_name", "预付款"),
            term_type=term_data.get("term_type", "percentage"),
            amount=_to_decimal_or_none(term_data.get("amount")),
            percentage=term_data.get("percentage"),
            milestone=term_data.get("milestone"),
            due_date=term_data.get("due_date"),
            due_condition=term_data.get("due_condition"),
            actual_paid=_to_decimal_or_none(term_data.get("actual_paid")),
            paid_date=term_data.get("paid_date")
        )
        self.db.add(term)

    def _generate_contract_tags(self, contract_id: int, contract_data: Dict[str, Any]) -> None:
        indexer = DocumentTagIndexer(self.db)
        indexer.generate_tags_from_parsed_data(
            document_id=contract_id,
            document_type="contract",
            parsed_data=contract_data,
            source="rule",
        )

    def extract_contract_parties_from_text(self, text: str | None) -> list[dict[str, Any]]:
        if not text:
            return []

        role_mapping = {
            "甲方": "party_a",
            "买方": "party_a",
            "采购方": "party_a",
            "发包方": "party_a",
            "乙方": "party_b",
            "卖方": "party_b",
            "供应商": "party_b",
            "承包方": "party_b",
            "丙方": "party_c",
            "丁方": "party_d",
        }
        role_pattern = "|".join(role_mapping.keys())
        pattern = re.compile(rf"({role_pattern})(?:（[^）]*）|\([^)]*\))?\s*[:：]\s*([^\n\r;；,，。]+)")
        parties = []
        seen = set()

        for match in pattern.finditer(text):
            role_label = match.group(1)
            party_name = match.group(2).strip()
            party_name = re.sub(r"\s+", "", party_name)
            if not party_name:
                continue

            party_role = role_mapping[role_label]
            key = (party_role, party_name)
            if key in seen:
                continue
            seen.add(key)
            parties.append({
                "party_role": party_role,
                "party_name": party_name,
                "party_type": "enterprise",
            })

        return parties
        
    def parse_invoice(self, organization_id: int, invoice_data: Dict[str, Any]) -> Invoice:
        invoice = Invoice(
            organization_id=organization_id,
            ledger_id=invoice_data.get("ledger_id"),
            counterparty_id=invoice_data.get("counterparty_id"),
            source_file_id=invoice_data.get("source_file_id"),
            invoice_no=invoice_data.get("invoice_no"),
            invoice_code=invoice_data.get("invoice_code"),
            invoice_type=invoice_data.get("invoice_type", "增值税专用发票"),
            invoice_status=invoice_data.get("invoice_status", "normal"),
            invoice_date=invoice_data.get("invoice_date"),
            buyer_name=invoice_data.get("buyer_name"),
            buyer_tax_no=invoice_data.get("buyer_tax_no"),
            buyer_address=invoice_data.get("buyer_address"),
            buyer_phone=invoice_data.get("buyer_phone"),
            buyer_bank=invoice_data.get("buyer_bank"),
            buyer_account=invoice_data.get("buyer_account"),
            seller_name=invoice_data.get("seller_name"),
            seller_tax_no=invoice_data.get("seller_tax_no"),
            seller_address=invoice_data.get("seller_address"),
            seller_phone=invoice_data.get("seller_phone"),
            seller_bank=invoice_data.get("seller_bank"),
            seller_account=invoice_data.get("seller_account"),
            amount_excluding_tax=_to_decimal_or_none(invoice_data.get("amount_excluding_tax")),
            tax_rate=_to_decimal_or_none(invoice_data.get("tax_rate"), precision="0.0001"),
            tax_amount=_to_decimal_or_none(invoice_data.get("tax_amount")),
            total_amount=_to_decimal_or_none(invoice_data.get("total_amount")),
            related_contract_id=invoice_data.get("related_contract_id"),
            related_order_no=invoice_data.get("related_order_no"),
            extracted_text=invoice_data.get("extracted_text"),
            confidence_score=invoice_data.get("confidence_score", 0.8)
        )
        
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        
        for item_data in invoice_data.get("items", []):
            self._add_invoice_item(invoice.id, item_data)
        
        self._generate_invoice_tags(invoice.id, invoice_data)
        
        return invoice

    def _add_invoice_item(self, invoice_id: int, item_data: Dict[str, Any]) -> None:
        item = InvoiceItem(
            invoice_id=invoice_id,
            item_no=item_data.get("item_no", 1),
            goods_name=item_data.get("goods_name"),
            specification=item_data.get("specification"),
            unit=item_data.get("unit"),
            quantity=_to_decimal_or_none(item_data.get("quantity"), precision="0.0001"),
            unit_price=_to_decimal_or_none(item_data.get("unit_price"), precision="0.0001"),
            amount=_to_decimal_or_none(item_data.get("amount")),
            tax_rate=_to_decimal_or_none(item_data.get("tax_rate"), precision="0.0001"),
            tax_amount=_to_decimal_or_none(item_data.get("tax_amount"))
        )
        self.db.add(item)
        self.db.commit()

    def _generate_invoice_tags(self, invoice_id: int, invoice_data: Dict[str, Any]) -> None:
        indexer = DocumentTagIndexer(self.db)
        indexer.generate_tags_from_parsed_data(
            document_id=invoice_id,
            document_type="invoice",
            parsed_data=invoice_data,
            source="rule",
        )

    def parse_inventory_document(self, organization_id: int, doc_data: Dict[str, Any]) -> InventoryDocument:
        document = InventoryDocument(
            organization_id=organization_id,
            ledger_id=doc_data.get("ledger_id"),
            counterparty_id=doc_data.get("counterparty_id"),
            source_file_id=doc_data.get("source_file_id"),
            document_no=doc_data.get("document_no"),
            document_type=doc_data.get("document_type", "inventory_in"),
            document_date=doc_data.get("document_date"),
            warehouse_name=doc_data.get("warehouse_name"),
            warehouse_code=doc_data.get("warehouse_code"),
            counterparty_type=doc_data.get("counterparty_type"),
            counterparty_name=doc_data.get("counterparty_name"),
            counterparty_code=doc_data.get("counterparty_code"),
            total_quantity=_to_decimal_or_none(doc_data.get("total_quantity"), precision="0.0001"),
            total_amount=_to_decimal_or_none(doc_data.get("total_amount")),
            related_contract_id=doc_data.get("related_contract_id"),
            related_order_no=doc_data.get("related_order_no"),
            related_invoice_id=doc_data.get("related_invoice_id"),
            inspector=doc_data.get("inspector"),
            inspect_date=doc_data.get("inspect_date"),
            inspect_result=doc_data.get("inspect_result"),
            extracted_text=doc_data.get("extracted_text"),
            confidence_score=doc_data.get("confidence_score", 0.8)
        )
        
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        for item_data in doc_data.get("items", []):
            self._add_inventory_item(document.id, item_data)
        
        self._generate_inventory_tags(document.id, doc_data)
        
        return document

    def _add_inventory_item(self, document_id: int, item_data: Dict[str, Any]) -> None:
        item = InventoryItem(
            document_id=document_id,
            item_no=item_data.get("item_no", 1),
            goods_name=item_data.get("goods_name"),
            specification=item_data.get("specification"),
            unit=item_data.get("unit"),
            quantity=_to_decimal_or_none(item_data.get("quantity"), precision="0.0001"),
            unit_price=_to_decimal_or_none(item_data.get("unit_price"), precision="0.0001"),
            amount=_to_decimal_or_none(item_data.get("amount")),
            batch_no=item_data.get("batch_no")
        )
        self.db.add(item)
        self.db.commit()

    def _generate_inventory_tags(self, document_id: int, doc_data: Dict[str, Any]) -> None:
        indexer = DocumentTagIndexer(self.db)
        indexer.generate_tags_from_parsed_data(
            document_id=document_id,
            document_type="inventory_receipt",
            parsed_data=doc_data,
            source="rule",
        )

    def parse_bank_statement(self, organization_id: int, statement_data: Dict[str, Any]) -> BankStatement:
        statement = BankStatement(
            organization_id=organization_id,
            ledger_id=statement_data.get("ledger_id"),
            counterparty_id=statement_data.get("counterparty_id"),
            source_file_id=statement_data.get("source_file_id"),
            transaction_no=statement_data.get("transaction_no"),
            transaction_date=statement_data.get("transaction_date"),
            transaction_time=statement_data.get("transaction_time"),
            transaction_type=statement_data.get("transaction_type", "income"),
            account_name=statement_data.get("account_name"),
            account_no=statement_data.get("account_no"),
            bank_name=statement_data.get("bank_name"),
            counterparty_name=statement_data.get("counterparty_name"),
            counterparty_account=statement_data.get("counterparty_account"),
            counterparty_bank=statement_data.get("counterparty_bank"),
            amount=_to_decimal_or_none(statement_data.get("amount")),
            balance=_to_decimal_or_none(statement_data.get("balance")),
            summary=statement_data.get("summary"),
            purpose=statement_data.get("purpose"),
            remark=statement_data.get("remark"),
            related_contract_id=statement_data.get("related_contract_id"),
            related_invoice_id=statement_data.get("related_invoice_id"),
            extracted_text=statement_data.get("extracted_text"),
            confidence_score=statement_data.get("confidence_score", 0.8)
        )
        
        self.db.add(statement)
        self.db.commit()
        self.db.refresh(statement)
        
        self._generate_bank_statement_tags(statement.id, statement_data)
        
        return statement

    def _generate_bank_statement_tags(self, statement_id: int, statement_data: Dict[str, Any]) -> None:
        indexer = DocumentTagIndexer(self.db)
        indexer.generate_tags_from_parsed_data(
            document_id=statement_id,
            document_type="bank_statement",
            parsed_data=statement_data,
            source="rule",
        )

    def get_field_alias(self, document_type: str, field_name: str) -> List[str]:
        mappings = self.db.query(FieldAliasMapping).filter(
            FieldAliasMapping.document_type == document_type,
            FieldAliasMapping.field_name == field_name
        ).all()
        return [m.alias for m in mappings]

    def add_field_alias(self, document_type: str, field_name: str, alias: str, 
                       alias_type: str = "chinese") -> None:
        existing = self.db.query(FieldAliasMapping).filter(
            FieldAliasMapping.document_type == document_type,
            FieldAliasMapping.field_name == field_name,
            FieldAliasMapping.alias == alias
        ).first()
        
        if not existing:
            mapping = FieldAliasMapping(
                document_type=document_type,
                field_name=field_name,
                alias=alias,
                alias_type=alias_type
            )
            self.db.add(mapping)
            self.db.commit()

    def find_related_parties(self, company_name: str) -> List[RelatedPartyRelation]:
        company = self.db.query(Company).filter(
            Company.company_name.ilike(f"%{company_name}%")
        ).first()
        
        if not company:
            return []
        
        relations = self.db.query(RelatedPartyRelation).filter(
            (RelatedPartyRelation.company_a_id == company.id) |
            (RelatedPartyRelation.company_b_id == company.id),
            RelatedPartyRelation.is_active == True
        ).all()
        
        return relations

    def get_contract_by_party(self, party_name: str) -> List[Contract]:
        parties = self.db.query(ContractParty).filter(
            ContractParty.party_name.ilike(f"%{party_name}%")
        ).all()
        
        contract_ids = [p.contract_id for p in parties]
        return self.db.query(Contract).filter(Contract.id.in_(contract_ids)).all()

    def initialize_default_aliases(self) -> None:
        aliases = [
            {"document_type": "contract", "field_name": "contract_no", "alias": "合同编号"},
            {"document_type": "contract", "field_name": "contract_no", "alias": "合同号"},
            {"document_type": "contract", "field_name": "contract_no", "alias": "编号"},
            {"document_type": "contract", "field_name": "party_a", "alias": "甲方"},
            {"document_type": "contract", "field_name": "party_a", "alias": "买方"},
            {"document_type": "contract", "field_name": "party_a", "alias": "采购方"},
            {"document_type": "contract", "field_name": "party_b", "alias": "乙方"},
            {"document_type": "contract", "field_name": "party_b", "alias": "卖方"},
            {"document_type": "contract", "field_name": "party_b", "alias": "供应商"},
            {"document_type": "contract", "field_name": "amount", "alias": "金额"},
            {"document_type": "contract", "field_name": "amount", "alias": "合同金额"},
            {"document_type": "contract", "field_name": "sign_date", "alias": "签订日期"},
            {"document_type": "contract", "field_name": "sign_date", "alias": "签署日期"},
            {"document_type": "invoice", "field_name": "invoice_no", "alias": "发票号码"},
            {"document_type": "invoice", "field_name": "invoice_no", "alias": "发票号"},
            {"document_type": "invoice", "field_name": "invoice_code", "alias": "发票代码"},
            {"document_type": "invoice", "field_name": "buyer_name", "alias": "购买方名称"},
            {"document_type": "invoice", "field_name": "buyer_name", "alias": "购货单位"},
            {"document_type": "invoice", "field_name": "seller_name", "alias": "销售方名称"},
            {"document_type": "invoice", "field_name": "seller_name", "alias": "销货单位"},
            {"document_type": "invoice", "field_name": "total_amount", "alias": "价税合计"},
            {"document_type": "invoice", "field_name": "total_amount", "alias": "合计"},
            {"document_type": "bank_statement", "field_name": "transaction_no", "alias": "交易号"},
            {"document_type": "bank_statement", "field_name": "transaction_no", "alias": "凭证号"},
            {"document_type": "bank_statement", "field_name": "counterparty_name", "alias": "对方名称"},
            {"document_type": "bank_statement", "field_name": "counterparty_name", "alias": "收款方"},
            {"document_type": "bank_statement", "field_name": "counterparty_name", "alias": "付款方"},
            {"document_type": "inventory", "field_name": "document_no", "alias": "入库单号"},
            {"document_type": "inventory", "field_name": "document_no", "alias": "出库单号"},
            {"document_type": "inventory", "field_name": "goods_name", "alias": "品名"},
            {"document_type": "inventory", "field_name": "goods_name", "alias": "商品名称"}
        ]
        
        for alias_data in aliases:
            existing = self.db.query(FieldAliasMapping).filter(
                FieldAliasMapping.document_type == alias_data["document_type"],
                FieldAliasMapping.field_name == alias_data["field_name"],
                FieldAliasMapping.alias == alias_data["alias"]
            ).first()
            if not existing:
                mapping = FieldAliasMapping(**alias_data)
                self.db.add(mapping)
        
        self.db.commit()
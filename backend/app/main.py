from sqlalchemy import inspect, text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.core.gateway import configure_gateway
from app.core.config import get_settings
from app.api.routes_accounting_periods import router as accounting_periods_router
from app.api.routes_accounting_units import router as accounting_units_router
from app.api.routes_agent import router as agent_router
from app.api.routes_audit_export import router as audit_export_router
from app.api.routes_audit_tests import router as audit_tests_router
from app.api.routes_business_cycles import router as business_cycles_router
from app.api.routes_coa import router as coa_router
from app.api.routes_counterparties import router as counterparties_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_document_parsing import router as document_parsing_router
from app.api.routes_document_tags import router as document_tags_router
from app.api.routes_entities import router as entities_router
from app.api.routes_entries import router as entries_router
from app.api.routes_entry_generation import router as entry_generation_router
from app.api.routes_entry_tags import router as entry_tags_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_product_events import router as product_events_router
from app.api.routes_tax_egress import router as tax_egress_router
from app.api.routes_export import router as export_router
from app.api.routes_files import router as files_router
from app.api.routes_imports import router as imports_router
from app.api.routes_unified_import import router as unified_import_router
from app.api.routes_internal_controls import router as internal_controls_router
from app.api.routes_ledger import router as ledger_router
from app.api.routes_materials import router as materials_router
from app.api.routes_module_registers import router as module_registers_router
from app.api.routes_opening_balances import router as opening_balances_router
from app.api.routes_reports import router as reports_router
from app.api.routes_risks import router as risks_router
from app.api.routes_transactions import router as transactions_router
from app.api.routes_auth import router as auth_router
from app.api.routes_bank import router as bank_router
from app.api.routes_binding_requests import router as binding_requests_router
from app.api.routes_confirmations import router as confirmations_router
from app.api.routes_purchase_match import router as purchase_match_router
from app.api.routes_vouchers import router as vouchers_router
from app.api.routes_workbench import router as workbench_router
from app.api.routes_workpapers import router as workpapers_router
from app.api.routes_audit_workflow import router as audit_workflow_router
from app.api.routes_audit_branches import router as audit_branches_router
from app.api.routes_audit_tasks import router as audit_tasks_router
from app.api.routes_audit_review import router as audit_review_router
from app.api.routes_audit_comments import router as audit_comments_router
from app.api.routes_audit_notifications import router as audit_notifications_router
from app.api.routes_audit_dashboard import router as audit_dashboard_router
from app.api.routes_project import router as project_router
from app.api.routes_lifecycle import router as lifecycle_router
from app.api.routes_team import router as team_router
from app.api.routes_scope_settings import router as scope_settings_router
from app.api.routes_parser_engine import router as parser_engine_router
from app.api.routes_parse_correction import router as parse_correction_router
from app.api.routes_parser_evolution import router as parser_evolution_router
from app.api.routes_parser_voucher import router as parser_voucher_router
from app.api.routes_config import router as config_router
from app.api.routes_llm_resolution import router as llm_resolution_router
from app.api.routes_super_admin import router as super_admin_router
from app.api.routes_seals import router as seals_router
from app.db import models
import app.models  # noqa: F401 — register app.models tables for create_all
from app.db.session import Base, engine

Base.metadata.create_all(bind=engine)


def _ensure_local_sqlite_schema() -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    with engine.begin() as connection:
        if "audit_reports" not in table_names:
            connection.execute(text("""
                CREATE TABLE audit_reports (
                    id INTEGER NOT NULL,
                    import_job_id INTEGER NOT NULL,
                    report_payload JSON,
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_audit_reports_import_job_id UNIQUE (import_job_id),
                    FOREIGN KEY(import_job_id) REFERENCES import_jobs (id)
                )
            """))

        if "source_files" in table_names:
            try:
                source_file_columns = {column["name"] for column in inspector.get_columns("source_files")}
            except Exception:
                source_file_columns = set()
            missing_columns = {
                "text_extract_status": "ALTER TABLE source_files ADD COLUMN text_extract_status VARCHAR(40) DEFAULT 'pending' NOT NULL",
                "extracted_text": "ALTER TABLE source_files ADD COLUMN extracted_text TEXT",
                "ledger_id": "ALTER TABLE source_files ADD COLUMN ledger_id INTEGER",
                "counterparty_id": "ALTER TABLE source_files ADD COLUMN counterparty_id INTEGER",
                "customer_match_source": "ALTER TABLE source_files ADD COLUMN customer_match_source VARCHAR(80)",
                "customer_confidence_note": "ALTER TABLE source_files ADD COLUMN customer_confidence_note VARCHAR(300)",
                "notes": "ALTER TABLE source_files ADD COLUMN notes TEXT",
            }
            for column_name, ddl in missing_columns.items():
                if column_name not in source_file_columns:
                    connection.execute(text(ddl))

        if "import_jobs" in table_names:
            import_job_columns = {column["name"] for column in inspector.get_columns("import_jobs")}
            import_job_missing_columns = {
                "ledger_id": "ALTER TABLE import_jobs ADD COLUMN ledger_id INTEGER",
                "draft_data": "ALTER TABLE import_jobs ADD COLUMN draft_data JSON",
                "audit_scope_type": "ALTER TABLE import_jobs ADD COLUMN audit_scope_type VARCHAR(40)",
                "audit_period_id": "ALTER TABLE import_jobs ADD COLUMN audit_period_id INTEGER",
                "audit_account_codes": "ALTER TABLE import_jobs ADD COLUMN audit_account_codes JSON",
                "project_id": "ALTER TABLE import_jobs ADD COLUMN project_id INTEGER",
            }
            for column_name, ddl in import_job_missing_columns.items():
                if column_name not in import_job_columns:
                    connection.execute(text(ddl))

        if "users" in table_names:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            user_missing_columns = {
                "agreed_terms": "ALTER TABLE users ADD COLUMN agreed_terms BOOLEAN DEFAULT 0 NOT NULL",
                "agreed_privacy": "ALTER TABLE users ADD COLUMN agreed_privacy BOOLEAN DEFAULT 0 NOT NULL",
                "platform_role": "ALTER TABLE users ADD COLUMN platform_role VARCHAR(40) DEFAULT 'user' NOT NULL",
                "team_id": "ALTER TABLE users ADD COLUMN team_id INTEGER",
                "last_ledger_id": "ALTER TABLE users ADD COLUMN last_ledger_id INTEGER",
                "updated_at": "ALTER TABLE users ADD COLUMN updated_at DATETIME",
            }
            for column_name, ddl in user_missing_columns.items():
                if column_name not in user_columns:
                    connection.execute(text(ddl))

        if "ledgers" in table_names:
            ledger_columns = {column["name"] for column in inspector.get_columns("ledgers")}
            ledger_missing_columns = {
                "organization_id": "ALTER TABLE ledgers ADD COLUMN organization_id INTEGER",
                "accounting_start_date": "ALTER TABLE ledgers ADD COLUMN accounting_start_date DATE",
                "is_working": "ALTER TABLE ledgers ADD COLUMN is_working BOOLEAN DEFAULT 0 NOT NULL",
                "project_id": "ALTER TABLE ledgers ADD COLUMN project_id INTEGER",
            }
            for column_name, ddl in ledger_missing_columns.items():
                if column_name not in ledger_columns:
                    connection.execute(text(ddl))

        if "accounting_periods" in table_names:
            period_columns = {column["name"] for column in inspector.get_columns("accounting_periods")}
            period_missing_columns = {
                "ledger_id": "ALTER TABLE accounting_periods ADD COLUMN ledger_id INTEGER",
                "period_type": "ALTER TABLE accounting_periods ADD COLUMN period_type VARCHAR(40) DEFAULT 'monthly' NOT NULL",
                "closed_at": "ALTER TABLE accounting_periods ADD COLUMN closed_at DATETIME",
                "reopened_at": "ALTER TABLE accounting_periods ADD COLUMN reopened_at DATETIME",
            }
            for column_name, ddl in period_missing_columns.items():
                if column_name not in period_columns:
                    connection.execute(text(ddl))

        if "chart_of_accounts" in table_names:
            account_columns = {column["name"] for column in inspector.get_columns("chart_of_accounts")}
            account_missing_columns = {
                "ledger_id": "ALTER TABLE chart_of_accounts ADD COLUMN ledger_id INTEGER",
                "organization_id": "ALTER TABLE chart_of_accounts ADD COLUMN organization_id INTEGER",
                "account_category": "ALTER TABLE chart_of_accounts ADD COLUMN account_category VARCHAR(40)",
                "account_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN account_subcategory VARCHAR(40)",
                "equity_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN equity_subcategory VARCHAR(40)",
                "include_in_dividend_base": "ALTER TABLE chart_of_accounts ADD COLUMN include_in_dividend_base BOOLEAN",
            }
            for column_name, ddl in account_missing_columns.items():
                if column_name not in account_columns:
                    connection.execute(text(ddl))
            if "ledger_id" not in account_columns or any(
                row[0] is None
                for row in connection.execute(
                    text("SELECT ledger_id FROM chart_of_accounts LIMIT 1")
                ).fetchall()
            ):
                default_ledger_id = connection.execute(text("SELECT MIN(id) FROM ledgers")).scalar()
                if default_ledger_id is not None:
                    connection.execute(
                        text(
                            "UPDATE chart_of_accounts SET ledger_id = :ledger_id WHERE ledger_id IS NULL"
                        ),
                        {"ledger_id": default_ledger_id},
                    )
            legacy_code_index = connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='chart_of_accounts' AND name='ix_chart_of_accounts_code'"
                )
            ).fetchone()
            if legacy_code_index:
                connection.execute(text("DROP INDEX ix_chart_of_accounts_code"))
            ledger_code_index = connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='uq_chart_of_accounts_ledger_code'"
                )
            ).fetchone()
            if not ledger_code_index:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX uq_chart_of_accounts_ledger_code "
                        "ON chart_of_accounts (ledger_id, code)"
                    )
                )

        if "counterparties" in table_names:
            counterparty_columns = {column["name"] for column in inspector.get_columns("counterparties")}
            counterparty_missing_columns = {
                "unified_credit_no": "ALTER TABLE counterparties ADD COLUMN unified_credit_no VARCHAR(40)",
                "is_related_party": "ALTER TABLE counterparties ADD COLUMN is_related_party BOOLEAN DEFAULT 0 NOT NULL",
                "default_entity_id": "ALTER TABLE counterparties ADD COLUMN default_entity_id INTEGER",
                "is_active": "ALTER TABLE counterparties ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL",
                "created_at": "ALTER TABLE counterparties ADD COLUMN created_at DATETIME",
                "updated_at": "ALTER TABLE counterparties ADD COLUMN updated_at DATETIME",
            }
            for column_name, ddl in counterparty_missing_columns.items():
                if column_name not in counterparty_columns:
                    connection.execute(text(ddl))

        if "sms_verification_codes" not in table_names:
            connection.execute(text("""
                CREATE TABLE sms_verification_codes (
                    id INTEGER NOT NULL,
                    phone VARCHAR(32) NOT NULL,
                    code VARCHAR(16) NOT NULL,
                    consumed BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
            """))
            connection.execute(text("CREATE INDEX ix_sms_verification_codes_phone ON sms_verification_codes (phone)"))
            connection.execute(text("CREATE INDEX ix_sms_verification_codes_consumed ON sms_verification_codes (consumed)"))
            connection.execute(text("CREATE INDEX ix_sms_verification_codes_created_at ON sms_verification_codes (created_at)"))
            connection.execute(text("CREATE INDEX ix_sms_verification_codes_expires_at ON sms_verification_codes (expires_at)"))

        if "teams" in table_names:
            team_columns = {column["name"] for column in inspector.get_columns("teams")}
            if "parent_team_id" not in team_columns:
                connection.execute(text("ALTER TABLE teams ADD COLUMN parent_team_id INTEGER"))

        if "entry_tags" in table_names:
            tag_columns = {column["name"] for column in inspector.get_columns("entry_tags")}
            tag_missing_columns = {
                "tag_type": "ALTER TABLE entry_tags ADD COLUMN tag_type VARCHAR(40)",
                "tag_value": "ALTER TABLE entry_tags ADD COLUMN tag_value VARCHAR(200)",
                "tag_value_normalized": "ALTER TABLE entry_tags ADD COLUMN tag_value_normalized VARCHAR(200)",
                "vector_pending": "ALTER TABLE entry_tags ADD COLUMN vector_pending BOOLEAN DEFAULT 1 NOT NULL",
            }
            for column_name, ddl in tag_missing_columns.items():
                if column_name not in tag_columns:
                    connection.execute(text(ddl))

        if "accounting_entries" in table_names:
            entry_columns = {column["name"] for column in inspector.get_columns("accounting_entries")}
            entry_missing_columns = {
                "ledger_id": "ALTER TABLE accounting_entries ADD COLUMN ledger_id INTEGER",
                "voucher_id": "ALTER TABLE accounting_entries ADD COLUMN voucher_id INTEGER",
                "entity_id": "ALTER TABLE accounting_entries ADD COLUMN entity_id INTEGER",
                "original_entity_name": "ALTER TABLE accounting_entries ADD COLUMN original_entity_name VARCHAR(500)",
                "source_file_id": "ALTER TABLE accounting_entries ADD COLUMN source_file_id INTEGER",
                "entry_source": "ALTER TABLE accounting_entries ADD COLUMN entry_source VARCHAR(20) DEFAULT 'auto' NOT NULL",
                "counterparty_id": "ALTER TABLE accounting_entries ADD COLUMN counterparty_id INTEGER",
                "entry_line_no": "ALTER TABLE accounting_entries ADD COLUMN entry_line_no INTEGER DEFAULT 1 NOT NULL",
                "review_status": "ALTER TABLE accounting_entries ADD COLUMN review_status VARCHAR(20) DEFAULT 'draft' NOT NULL",
                "post_status": "ALTER TABLE accounting_entries ADD COLUMN post_status VARCHAR(20) DEFAULT 'draft' NOT NULL",
                "posted_at": "ALTER TABLE accounting_entries ADD COLUMN posted_at DATETIME",
                "posted_by": "ALTER TABLE accounting_entries ADD COLUMN posted_by INTEGER",
                "resolved_account_code": "ALTER TABLE accounting_entries ADD COLUMN resolved_account_code VARCHAR(100)",
                "resolved_account_name": "ALTER TABLE accounting_entries ADD COLUMN resolved_account_name VARCHAR(200)",
                "requires_llm_resolution": "ALTER TABLE accounting_entries ADD COLUMN requires_llm_resolution BOOLEAN DEFAULT 0 NOT NULL",
            }
            for column_name, ddl in entry_missing_columns.items():
                if column_name not in entry_columns:
                    connection.execute(text(ddl))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_accounting_entries_ledger_voucher "
                    "ON accounting_entries (ledger_id, voucher_date, voucher_no)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_accounting_entries_ledger_review "
                    "ON accounting_entries (ledger_id, review_status)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_accounting_entries_ledger_date "
                    "ON accounting_entries (ledger_id, voucher_date)"
                )
            )

        if "audit_risks" in table_names:
            risk_columns = {column["name"] for column in inspector.get_columns("audit_risks")}
            risk_missing_columns = {
                "ledger_id": "ALTER TABLE audit_risks ADD COLUMN ledger_id INTEGER",
                "status": "ALTER TABLE audit_risks ADD COLUMN status VARCHAR(40) DEFAULT 'pending_review' NOT NULL",
            }
            for column_name, ddl in risk_missing_columns.items():
                if column_name not in risk_columns:
                    connection.execute(text(ddl))

        if "bank_accounts" in table_names:
            bank_columns = {column["name"] for column in inspector.get_columns("bank_accounts")}
            if "source_sub_code" not in bank_columns:
                connection.execute(text("ALTER TABLE bank_accounts ADD COLUMN source_sub_code VARCHAR(20)"))

        voucher_signature_columns = {
            "vouchers": {
                "source_preparer_name": "ALTER TABLE vouchers ADD COLUMN source_preparer_name VARCHAR(200)",
                "cross_reviewed_by_user_id": "ALTER TABLE vouchers ADD COLUMN cross_reviewed_by_user_id INTEGER",
                "cross_reviewed_at": "ALTER TABLE vouchers ADD COLUMN cross_reviewed_at DATETIME",
                "approved_by_user_id": "ALTER TABLE vouchers ADD COLUMN approved_by_user_id INTEGER",
                "approved_at": "ALTER TABLE vouchers ADD COLUMN approved_at DATETIME",
            },
            "staging_accounting_entries": {
                "source_preparer_name": "ALTER TABLE staging_accounting_entries ADD COLUMN source_preparer_name VARCHAR(200)",
                "cross_reviewed_by_user_id": "ALTER TABLE staging_accounting_entries ADD COLUMN cross_reviewed_by_user_id INTEGER",
                "cross_reviewed_at": "ALTER TABLE staging_accounting_entries ADD COLUMN cross_reviewed_at DATETIME",
            },
        }
        for table_name, missing_columns in voucher_signature_columns.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in missing_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(ddl))

        register_table_columns = {
            "contracts": {
                "ledger_id": "ALTER TABLE contracts ADD COLUMN ledger_id INTEGER",
                "counterparty_id": "ALTER TABLE contracts ADD COLUMN counterparty_id INTEGER",
                "execution_status": "ALTER TABLE contracts ADD COLUMN execution_status VARCHAR(30) DEFAULT 'pending' NOT NULL",
            },
            "invoices": {
                "ledger_id": "ALTER TABLE invoices ADD COLUMN ledger_id INTEGER",
                "counterparty_id": "ALTER TABLE invoices ADD COLUMN counterparty_id INTEGER",
            },
            "bank_statements": {
                "ledger_id": "ALTER TABLE bank_statements ADD COLUMN ledger_id INTEGER",
                "counterparty_id": "ALTER TABLE bank_statements ADD COLUMN counterparty_id INTEGER",
            },
            "inventory_documents": {
                "ledger_id": "ALTER TABLE inventory_documents ADD COLUMN ledger_id INTEGER",
                "counterparty_id": "ALTER TABLE inventory_documents ADD COLUMN counterparty_id INTEGER",
            },
        }
        for table_name, missing_columns in register_table_columns.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in missing_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(ddl))

        if "opening_balances" in table_names:
            ob_columns = {column["name"] for column in inspector.get_columns("opening_balances")}
            if "ledger_id" not in ob_columns:
                connection.execute(text("ALTER TABLE opening_balances ADD COLUMN ledger_id INTEGER"))
                connection.execute(text(
                    "UPDATE opening_balances SET ledger_id = ("
                    "SELECT ledger_id FROM accounting_periods WHERE accounting_periods.id = opening_balances.period_id"
                    ") WHERE ledger_id IS NULL"
                ))

        scope_settings_tables = {
            "ledger_settings": """
                CREATE TABLE ledger_settings (
                    id INTEGER NOT NULL PRIMARY KEY,
                    ledger_id INTEGER NOT NULL UNIQUE,
                    settings JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(ledger_id) REFERENCES ledgers (id)
                )
            """,
            "team_settings": """
                CREATE TABLE team_settings (
                    id INTEGER NOT NULL PRIMARY KEY,
                    team_id INTEGER NOT NULL UNIQUE,
                    settings JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(team_id) REFERENCES teams (id)
                )
            """,
            "project_settings": """
                CREATE TABLE project_settings (
                    id INTEGER NOT NULL PRIMARY KEY,
                    project_id INTEGER NOT NULL UNIQUE,
                    settings JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects (id)
                )
            """,
            "entity_scope_settings": """
                CREATE TABLE entity_scope_settings (
                    id INTEGER NOT NULL PRIMARY KEY,
                    ledger_id INTEGER NOT NULL UNIQUE,
                    settings JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(ledger_id) REFERENCES ledgers (id)
                )
            """,
        }
        for table_name, ddl in scope_settings_tables.items():
            if table_name not in table_names:
                connection.execute(text(ddl))


_ensure_local_sqlite_schema()

from fastapi.responses import JSONResponse

application: FastAPI = FastAPI(
    title="财务向量审计风险识别系统",
    version="0.1.0",
    default_response_class=JSONResponse,
)
configure_gateway(application)
application.add_middleware(GZipMiddleware, minimum_size=1000)
_cors_origins = [
    origin.strip()
    for origin in get_settings().cors_allow_origins.split(",")
    if origin.strip()
]
application.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
application.include_router(auth_router)
application.include_router(imports_router)
application.include_router(unified_import_router)
application.include_router(entries_router)
application.include_router(export_router)
application.include_router(files_router)
application.include_router(risks_router)
application.include_router(accounting_periods_router)
application.include_router(accounting_units_router)
application.include_router(agent_router)
application.include_router(workbench_router)
application.include_router(audit_tests_router)
application.include_router(audit_export_router)
application.include_router(document_parsing_router)
application.include_router(document_tags_router)
application.include_router(entities_router)
application.include_router(coa_router)
application.include_router(counterparties_router)
application.include_router(opening_balances_router)
application.include_router(reports_router)
application.include_router(entry_generation_router)
application.include_router(entry_tags_router)
application.include_router(analytics_router)
application.include_router(product_events_router)
application.include_router(tax_egress_router)
application.include_router(business_cycles_router)
application.include_router(internal_controls_router)
application.include_router(ledger_router)
application.include_router(dashboard_router)
application.include_router(transactions_router)
application.include_router(materials_router)
application.include_router(module_registers_router)
application.include_router(project_router)
application.include_router(lifecycle_router)
application.include_router(team_router)
application.include_router(scope_settings_router)
application.include_router(parser_engine_router)
application.include_router(parse_correction_router)
application.include_router(parser_evolution_router)
application.include_router(parser_voucher_router)
application.include_router(config_router)
application.include_router(llm_resolution_router)
application.include_router(super_admin_router)
application.include_router(binding_requests_router)
application.include_router(bank_router)
application.include_router(confirmations_router)
application.include_router(purchase_match_router)
application.include_router(vouchers_router)
application.include_router(workpapers_router)
application.include_router(audit_workflow_router)
application.include_router(audit_branches_router)
application.include_router(audit_tasks_router)
application.include_router(audit_review_router)
application.include_router(audit_comments_router)
application.include_router(audit_notifications_router)
application.include_router(audit_dashboard_router)
application.include_router(seals_router)


@application.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "finance-vector-audit-backend"}


@application.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 导出给 uvicorn 使用的变量名
app: FastAPI = application  # type: ignore[no-redef]

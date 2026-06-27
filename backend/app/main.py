from sqlalchemy import inspect, text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.gateway import configure_gateway
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
from app.api.routes_entities import router as entities_router
from app.api.routes_entries import router as entries_router
from app.api.routes_entry_generation import router as entry_generation_router
from app.api.routes_entry_tags import router as entry_tags_router
from app.api.routes_export import router as export_router
from app.api.routes_files import router as files_router
from app.api.routes_imports import router as imports_router
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
from app.api.routes_config import router as config_router
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
            source_file_columns = {column["name"] for column in inspector.get_columns("source_files")}
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
                "team_id": "ALTER TABLE users ADD COLUMN team_id INTEGER",
                "last_ledger_id": "ALTER TABLE users ADD COLUMN last_ledger_id INTEGER",
                "updated_at": "ALTER TABLE users ADD COLUMN updated_at DATETIME",
            }
            for column_name, ddl in user_missing_columns.items():
                if column_name not in user_columns:
                    connection.execute(text(ddl))

        if "ledgers" in table_names:
            ledger_columns = {column["name"] for column in inspector.get_columns("ledgers")}
            if "accounting_start_date" not in ledger_columns:
                connection.execute(text("ALTER TABLE ledgers ADD COLUMN accounting_start_date DATE"))

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
                "account_category": "ALTER TABLE chart_of_accounts ADD COLUMN account_category VARCHAR(40)",
                "account_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN account_subcategory VARCHAR(40)",
                "equity_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN equity_subcategory VARCHAR(40)",
                "include_in_dividend_base": "ALTER TABLE chart_of_accounts ADD COLUMN include_in_dividend_base BOOLEAN",
            }
            for column_name, ddl in account_missing_columns.items():
                if column_name not in account_columns:
                    connection.execute(text(ddl))

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
            }
            for column_name, ddl in entry_missing_columns.items():
                if column_name not in entry_columns:
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

app = FastAPI(title="财务向量审计风险识别系统", version="0.1.0")
configure_gateway(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(imports_router)
app.include_router(entries_router)
app.include_router(export_router)
app.include_router(files_router)
app.include_router(risks_router)
app.include_router(accounting_periods_router)
app.include_router(accounting_units_router)
app.include_router(agent_router)
app.include_router(audit_tests_router)
app.include_router(audit_export_router)
app.include_router(document_parsing_router)
app.include_router(entities_router)
app.include_router(coa_router)
app.include_router(counterparties_router)
app.include_router(opening_balances_router)
app.include_router(reports_router)
app.include_router(entry_generation_router)
app.include_router(entry_tags_router)
app.include_router(business_cycles_router)
app.include_router(internal_controls_router)
app.include_router(ledger_router)
app.include_router(dashboard_router)
app.include_router(transactions_router)
app.include_router(materials_router)
app.include_router(module_registers_router)
app.include_router(project_router)
app.include_router(lifecycle_router)
app.include_router(team_router)
app.include_router(scope_settings_router)
app.include_router(parser_engine_router)
app.include_router(config_router)
app.include_router(binding_requests_router)
app.include_router(bank_router)
app.include_router(confirmations_router)
app.include_router(purchase_match_router)
app.include_router(workpapers_router)
app.include_router(audit_workflow_router)
app.include_router(audit_branches_router)
app.include_router(audit_tasks_router)
app.include_router(audit_review_router)
app.include_router(audit_comments_router)
app.include_router(audit_notifications_router)
app.include_router(audit_dashboard_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "finance-vector-audit-backend"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

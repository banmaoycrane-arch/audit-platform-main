from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.core.config import get_settings
from app.db.models import Base

# 导入 app.models 包中的模型，确保所有共享同一个 Base 的 DeclarativeBase 子类
# 都注册到 Base.metadata。这样 Alembic 在 autogenerate 时才能完整解析
# 外键关系，避免 "NoReferencedTableError"。
from app.models import (  # noqa: E402,F401
    BindingRequest,
    Ledger,
    LifecycleLog,
    Project,
    ProjectLedger,
    ProjectMember,
    Team,
    User,
    UserLedgerAuth,
)

settings = get_settings()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    connectable = create_engine(settings.database_url, connect_args=connect_args)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

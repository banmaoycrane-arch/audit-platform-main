"""tax city egress pool tables

Revision ID: 0028_tax_city_egress_pool
Revises: 0027_cash_flow_item
Create Date: 2026-07-21

Idempotent for production DBs that already received tables via deploy/fix_legacy_db.py.
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_tax_city_egress_pool"
down_revision = "0027_cash_flow_item"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def upgrade() -> None:
    connection = op.get_bind()

    if not _table_exists(connection, "tax_city_egress_pools"):
        op.create_table(
            "tax_city_egress_pools",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("city_code", sa.String(12), nullable=False),
            sa.Column("city_name", sa.String(80), nullable=False),
            sa.Column("bureau_province", sa.String(40), nullable=False),
            sa.Column(
                "pool_policy",
                sa.String(40),
                nullable=False,
                server_default="sticky_with_failover",
            ),
            sa.Column(
                "max_rotate_per_taxpayer_7d",
                sa.Integer(),
                nullable=False,
                server_default="2",
            ),
            sa.Column("cooling_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("city_code", name="uq_tax_city_egress_pools_city_code"),
        )
        op.create_index("ix_tax_city_egress_pools_city_code", "tax_city_egress_pools", ["city_code"])

    if not _table_exists(connection, "tax_egress_nodes"):
        op.create_table(
            "tax_egress_nodes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pool_id", sa.Integer(), sa.ForeignKey("tax_city_egress_pools.id"), nullable=False),
            sa.Column("node_key", sa.String(40), nullable=False),
            sa.Column("egress_ip", sa.String(64), nullable=False),
            sa.Column("worker_host", sa.String(200), nullable=True),
            sa.Column("provider", sa.String(120), nullable=True),
            sa.Column("asn_type", sa.String(40), nullable=False, server_default="enterprise"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("max_tenants", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("current_bindings", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("health_score", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("last_health_at", sa.DateTime(), nullable=True),
            sa.Column("cooling_until", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("node_key", name="uq_tax_egress_nodes_node_key"),
        )
        op.create_index("ix_tax_egress_nodes_pool_id", "tax_egress_nodes", ["pool_id"])
        op.create_index("ix_tax_egress_nodes_node_key", "tax_egress_nodes", ["node_key"])
        op.create_index("ix_tax_egress_nodes_egress_ip", "tax_egress_nodes", ["egress_ip"])
        op.create_index("ix_tax_egress_nodes_status", "tax_egress_nodes", ["status"])

    if not _table_exists(connection, "tax_egress_bindings"):
        op.create_table(
            "tax_egress_bindings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("taxpayer_id", sa.String(32), nullable=False),
            sa.Column("taxpayer_name", sa.String(200), nullable=False),
            sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True),
            sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
            sa.Column("city_code", sa.String(12), nullable=False),
            sa.Column(
                "egress_node_id",
                sa.Integer(),
                sa.ForeignKey("tax_egress_nodes.id"),
                nullable=False,
            ),
            sa.Column("lease_start", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("lease_end", sa.DateTime(), nullable=False),
            sa.Column("rotate_count_7d", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_rotate_at", sa.DateTime(), nullable=True),
            sa.Column("session_state", sa.String(20), nullable=False, server_default="idle"),
            sa.Column("binding_status", sa.String(20), nullable=False, server_default="healthy"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("taxpayer_id", name="uq_tax_egress_bindings_taxpayer"),
        )
        op.create_index("ix_tax_egress_bindings_taxpayer_id", "tax_egress_bindings", ["taxpayer_id"])
        op.create_index("ix_tax_egress_bindings_ledger_id", "tax_egress_bindings", ["ledger_id"])
        op.create_index("ix_tax_egress_bindings_team_id", "tax_egress_bindings", ["team_id"])
        op.create_index("ix_tax_egress_bindings_city_code", "tax_egress_bindings", ["city_code"])
        op.create_index(
            "ix_tax_egress_bindings_egress_node_id",
            "tax_egress_bindings",
            ["egress_node_id"],
        )

    if not _table_exists(connection, "tax_rotation_events"):
        op.create_table(
            "tax_rotation_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("taxpayer_id", sa.String(32), nullable=False),
            sa.Column(
                "binding_id",
                sa.Integer(),
                sa.ForeignKey("tax_egress_bindings.id"),
                nullable=True,
            ),
            sa.Column("old_node_id", sa.Integer(), nullable=True),
            sa.Column("new_node_id", sa.Integer(), nullable=True),
            sa.Column("old_egress_ip", sa.String(64), nullable=True),
            sa.Column("new_egress_ip", sa.String(64), nullable=True),
            sa.Column("trigger_code", sa.String(40), nullable=False),
            sa.Column("reason_detail", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(80), nullable=False, server_default="system"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_tax_rotation_events_taxpayer_id", "tax_rotation_events", ["taxpayer_id"])
        op.create_index("ix_tax_rotation_events_binding_id", "tax_rotation_events", ["binding_id"])
        op.create_index("ix_tax_rotation_events_trigger_code", "tax_rotation_events", ["trigger_code"])
        op.create_index("ix_tax_rotation_events_created_at", "tax_rotation_events", ["created_at"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "tax_rotation_events",
        "tax_egress_bindings",
        "tax_egress_nodes",
        "tax_city_egress_pools",
    ):
        if _table_exists(connection, table):
            op.drop_table(table)

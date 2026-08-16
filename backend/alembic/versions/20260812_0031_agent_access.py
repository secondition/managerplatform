"""agent registry and access grants

Revision ID: 20260812_0031
Revises: 20260805_0030
"""

from collections.abc import Sequence
from datetime import datetime, timezone
import json

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0031"
down_revision: str | None = "20260805_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    agents = op.create_table(
        "ai_agents",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("agent_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("implementation_type", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "uq_ai_agents_agent_key_active",
        "ai_agents",
        ["agent_key"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "ai_agent_user_grants",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("agent_id", BIGINT, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "ix_ai_agent_user_grants_user",
        "ai_agent_user_grants",
        ["user_id", "agent_id"],
    )
    op.create_index(
        "uq_ai_agent_user_grants_active",
        "ai_agent_user_grants",
        ["agent_id", "user_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "ai_agent_group_grants",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("agent_id", BIGINT, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("group_id", BIGINT, sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "ix_ai_agent_group_grants_group",
        "ai_agent_group_grants",
        ["group_id", "agent_id"],
    )
    op.create_index(
        "uq_ai_agent_group_grants_active",
        "ai_agent_group_grants",
        ["agent_id", "group_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        agents,
        [
            {
                "agent_key": "chabao",
                "name": "查宝",
                "description": "企业数据查询与经营分析助手",
                "avatar_url": None,
                "implementation_type": "feishu_group_projection",
                "enabled": True,
                "sort_order": 0,
                "config_json": json.dumps(
                    {"display_name": "心选茶包（查宝）"},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_ai_agent_group_grants_active", table_name="ai_agent_group_grants")
    op.drop_index("ix_ai_agent_group_grants_group", table_name="ai_agent_group_grants")
    op.drop_table("ai_agent_group_grants")
    op.drop_index("uq_ai_agent_user_grants_active", table_name="ai_agent_user_grants")
    op.drop_index("ix_ai_agent_user_grants_user", table_name="ai_agent_user_grants")
    op.drop_table("ai_agent_user_grants")
    op.drop_index("uq_ai_agents_agent_key_active", table_name="ai_agents")
    op.drop_table("ai_agents")

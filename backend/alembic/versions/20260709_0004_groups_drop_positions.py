"""drop positions/position_id, add groups + group_members

Revision ID: 20260709_0004
Revises: 20260708_0003
Create Date: 2026-07-09 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0004"
down_revision: str | None = "20260708_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    ]


def upgrade() -> None:
    # --- 人员组 ---
    op.create_table(
        "groups",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_table(
        "group_members",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("group_id", BIGINT, sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        *audit_columns(),
    )
    op.create_index(
        "uq_group_members_group_user",
        "group_members",
        ["group_id", "user_id"],
        unique=True,
    )

    # --- 砍岗位 ---
    with op.batch_alter_table("users") as batch:
        batch.drop_column("position_id")
    op.drop_table("positions")


def downgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("department_id", BIGINT, sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("position_id", BIGINT, sa.ForeignKey("positions.id"), nullable=True)
        )

    op.drop_index("uq_group_members_group_user", table_name="group_members")
    op.drop_table("group_members")
    op.drop_table("groups")

"""add company settings

Revision ID: 20260709_0008
Revises: 20260709_0007
Create Date: 2026-07-09 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0008"
down_revision: str | None = "20260709_0007"
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
    op.create_table(
        "company_settings",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("company_name", sa.String(length=100), nullable=False, server_default="Manager Platform"),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column(
            "footer_text",
            sa.String(length=200),
            nullable=False,
            server_default="MANAGER PLATFORM · Open Source Work Management",
        ),
        *audit_columns(),
    )
    op.execute(
        """
        INSERT INTO company_settings
          (id, company_name, logo_url, footer_text, created_at, updated_at, deleted_at, created_by, updated_by)
        VALUES
          (1, 'Manager Platform', NULL, 'MANAGER PLATFORM · Open Source Work Management', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL, NULL)
        """
    )


def downgrade() -> None:
    op.drop_table("company_settings")

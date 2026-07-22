"""upgrade OKR reviews to whole-set quality scoring

Revision ID: 20260710_0018
Revises: 20260710_0017
Create Date: 2026-07-10 20:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.ai.defaults import DEFAULT_TEMPLATES, DEFAULT_VARIABLES

revision: str = "20260710_0018"
down_revision: str | None = "20260710_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("okr_reviews", sa.Column("level", sa.String(length=50), nullable=True))
    op.add_column(
        "okr_reviews",
        sa.Column("highlights_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "okr_reviews",
        sa.Column("optional_improvements_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "okr_reviews", sa.Column("impact_on_daily_scoring", sa.Text(), nullable=True)
    )

    conn = op.get_bind()
    conn.exec_driver_sql(
        "UPDATE prompt_configs SET template_content = ?, variables_json = ?, version = ? "
        "WHERE prompt_type = ?",
        (
            DEFAULT_TEMPLATES["okr_quality"],
            json.dumps(DEFAULT_VARIABLES["okr_quality"], ensure_ascii=False),
            "v1",
            "okr_quality",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("okr_reviews") as batch:
        batch.drop_column("impact_on_daily_scoring")
        batch.drop_column("optional_improvements_json")
        batch.drop_column("highlights_json")
        batch.drop_column("level")

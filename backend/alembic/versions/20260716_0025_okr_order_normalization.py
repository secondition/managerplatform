"""normalize persisted OKR priority order

Revision ID: 20260716_0025
Revises: 20260715_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0025"
down_revision: str | None = "20260715_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    objectives = sa.table(
        "okr_objectives",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("month", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("deleted_at", sa.DateTime),
    )
    key_results = sa.table(
        "okr_key_results",
        sa.column("id", sa.Integer),
        sa.column("objective_id", sa.Integer),
        sa.column("sort_order", sa.Integer),
        sa.column("deleted_at", sa.DateTime),
    )

    rows = bind.execute(
        sa.select(objectives.c.id, objectives.c.user_id, objectives.c.month)
        .where(objectives.c.deleted_at.is_(None))
        .order_by(objectives.c.user_id, objectives.c.month, objectives.c.sort_order, objectives.c.id)
    ).all()
    counters: dict[tuple[int, str], int] = {}
    for row in rows:
        key = (row.user_id, row.month)
        counters[key] = counters.get(key, 0) + 1
        bind.execute(sa.update(objectives).where(objectives.c.id == row.id).values(sort_order=counters[key]))

    kr_rows = bind.execute(
        sa.select(key_results.c.id, key_results.c.objective_id)
        .where(key_results.c.deleted_at.is_(None))
        .order_by(key_results.c.objective_id, key_results.c.sort_order, key_results.c.id)
    ).all()
    kr_counters: dict[int, int] = {}
    for row in kr_rows:
        kr_counters[row.objective_id] = kr_counters.get(row.objective_id, 0) + 1
        bind.execute(sa.update(key_results).where(key_results.c.id == row.id).values(sort_order=kr_counters[row.objective_id]))


def downgrade() -> None:
    pass

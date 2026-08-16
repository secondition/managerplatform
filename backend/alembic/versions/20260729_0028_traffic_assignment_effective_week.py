"""make new traffic assignments immediately fillable

Revision ID: 20260729_0028
Revises: 20260729_0027
"""

from collections.abc import Sequence
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0028"
down_revision: str | None = "20260729_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _last_completed_week_start() -> date:
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    return current_week_start - timedelta(days=7)


def upgrade() -> None:
    assignments = sa.table(
        "traffic_metric_assignments",
        sa.column("effective_from", sa.Date()),
        sa.column("deleted_at", sa.DateTime()),
    )
    cutoff = _last_completed_week_start()
    op.get_bind().execute(
        assignments.update()
        .where(
            assignments.c.deleted_at.is_(None),
            assignments.c.effective_from > cutoff,
        )
        .values(effective_from=cutoff)
    )


def downgrade() -> None:
    pass

"""bind chat send idempotency keys to message text

Revision ID: 20260812_0035
Revises: 20260812_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0035"
down_revision: str | None = "20260812_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_send_requests") as batch_op:
        batch_op.add_column(
            sa.Column(
                "request_text_hash",
                sa.String(64),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_send_requests") as batch_op:
        batch_op.drop_column("request_text_hash")

"""split feature/advanced permissions: admin:group -> feature:group, backfill defaults

Revision ID: 20260710_0012
Revises: 20260710_0011
Create Date: 2026-07-10 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260710_0012"
down_revision: str | None = "20260710_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEATURES = ("feature:daily", "feature:traffic", "feature:okr")


def upgrade() -> None:
    conn = op.get_bind()
    # 1) admin:group rows become feature:group (same semantics, new home).
    conn.exec_driver_sql(
        "UPDATE user_permissions SET permission = 'feature:group' "
        "WHERE permission = 'admin:group'"
    )
    # 2) Backfill every feature permission for all active users (owner included —
    #    feature perms apply by row so owner can toggle their own). feature:group
    #    is here too, covering users who never had admin:group. Idempotent.
    for feature in (*FEATURES, "feature:group"):
        conn.exec_driver_sql(
            """
            INSERT INTO user_permissions
                (user_id, permission, enabled, created_at, updated_at)
            SELECT u.id, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM users u
            WHERE u.status = 'active'
              AND u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM user_permissions p
                  WHERE p.user_id = u.id AND p.permission = ?
              )
            """,
            (feature, feature),
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Drop the backfilled feature permissions; restore feature:group -> admin:group.
    conn.exec_driver_sql(
        "DELETE FROM user_permissions "
        "WHERE permission IN ('feature:daily', 'feature:traffic', 'feature:okr')"
    )
    conn.exec_driver_sql(
        "UPDATE user_permissions SET permission = 'admin:group' "
        "WHERE permission = 'feature:group'"
    )

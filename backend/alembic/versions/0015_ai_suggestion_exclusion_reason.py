"""ai suggestion exclusion reason

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_suggestions",
        sa.Column("exclusion_reason", sa.String(length=200), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ai_suggestions", "exclusion_reason")

"""used_tokens table for single-use password reset JWTs

Revision ID: c4f8a2b1d905
Revises: b7c2e1a4f903
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4f8a2b1d905"
down_revision: Union[str, None] = "b7c2e1a4f903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "used_tokens",
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )


def downgrade() -> None:
    op.drop_table("used_tokens")

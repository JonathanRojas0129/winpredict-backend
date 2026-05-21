"""users lockout fields and auth_logs table

Revision ID: d5e6f7a8b901
Revises: c4f8a2b1d905
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5e6f7a8b901"
down_revision: Union[str, None] = "c4f8a2b1d905"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))

    op.create_table(
        "auth_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("accion", sa.String(length=50), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_logs_email", "auth_logs", ["email"])
    op.create_index("ix_auth_logs_accion", "auth_logs", ["accion"])
    op.create_index("ix_auth_logs_created_at", "auth_logs", ["created_at"])
    op.create_index("ix_auth_logs_user_id", "auth_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_logs_user_id", table_name="auth_logs")
    op.drop_index("ix_auth_logs_created_at", table_name="auth_logs")
    op.drop_index("ix_auth_logs_accion", table_name="auth_logs")
    op.drop_index("ix_auth_logs_email", table_name="auth_logs")
    op.drop_table("auth_logs")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")

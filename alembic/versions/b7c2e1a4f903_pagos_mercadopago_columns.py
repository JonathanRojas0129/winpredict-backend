"""pagos: columnas MercadoPago y nullable en campos legacy Stripe

Revision ID: b7c2e1a4f903
Revises: 448d8038d5ed
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c2e1a4f903"
down_revision: Union[str, None] = "448d8038d5ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pagos", sa.Column("preference_id", sa.String(length=255), nullable=True))
    op.add_column("pagos", sa.Column("payment_id", sa.String(length=255), nullable=True))
    op.add_column("pagos", sa.Column("monto_cop", sa.Float(), nullable=True))
    op.add_column("pagos", sa.Column("creado_en", sa.DateTime(), nullable=True))

    # Migrar datos mal mapeados (MP guardado en columnas Stripe)
    op.execute(
        """
        UPDATE pagos
        SET preference_id = stripe_session_id,
            monto_cop     = monto_usd
        WHERE stripe_session_id IS NOT NULL
          AND preference_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE pagos
        SET monto_usd = 3.5
        WHERE monto_usd IS NOT NULL AND monto_usd > 100
        """
    )

    op.drop_constraint("pagos_stripe_session_id_key", "pagos", type_="unique")
    op.alter_column("pagos", "stripe_session_id", existing_type=sa.String(length=255), nullable=True)
    op.alter_column("pagos", "monto_usd", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.alter_column("pagos", "monto_usd", existing_type=sa.Float(), nullable=False)
    op.alter_column("pagos", "stripe_session_id", existing_type=sa.String(length=255), nullable=False)
    op.create_unique_constraint("pagos_stripe_session_id_key", "pagos", ["stripe_session_id"])

    op.drop_column("pagos", "creado_en")
    op.drop_column("pagos", "monto_cop")
    op.drop_column("pagos", "payment_id")
    op.drop_column("pagos", "preference_id")

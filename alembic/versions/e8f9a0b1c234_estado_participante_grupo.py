"""grupo_participantes estado_participante (aprobación de ingreso)

Revision ID: e8f9a0b1c234
Revises: d5e6f7a8b901
Create Date: 2026-05-21

Participantes existentes reciben DEFAULT 'aprobado' en BD.
Nuevos ingresos usan default del modelo Python: 'pendiente'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8f9a0b1c234"
down_revision: Union[str, None] = "d5e6f7a8b901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grupo_participantes",
        sa.Column(
            "estado_participante",
            sa.String(length=20),
            nullable=False,
            server_default="aprobado",
        ),
    )
    # El default en BD solo aplica al ADD; nuevas filas sin valor explícito
    # tomarán el default del ORM ('pendiente') en inserts de la app.


def downgrade() -> None:
    op.drop_column("grupo_participantes", "estado_participante")

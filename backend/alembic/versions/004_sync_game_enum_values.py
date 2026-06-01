"""sync game enum values

Revision ID: 004
Revises: 003
Create Date: 2026-06-01 20:40:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE gametype ADD VALUE IF NOT EXISTS 'pokemon_battle'")
    op.execute("ALTER TYPE gamestatus ADD VALUE IF NOT EXISTS 'paused'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values without recreating the type.
    pass

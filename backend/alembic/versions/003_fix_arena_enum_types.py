"""fix arena enum column types

Revision ID: 003
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '003'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'matchtype') THEN
                CREATE TYPE matchtype AS ENUM ('QA_PK', 'CODE', 'CREATIVE', 'REASONING', 'MULTIMODAL');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'matchstatus') THEN
                CREATE TYPE matchstatus AS ENUM ('WAITING', 'IN_PROGRESS', 'VOTING', 'FINISHED', 'CANCELLED');
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE arena_matches ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE arena_matches
        ALTER COLUMN match_type TYPE matchtype
        USING (
            CASE lower(match_type::text)
                WHEN 'qa_pk' THEN 'QA_PK'
                WHEN 'code' THEN 'CODE'
                WHEN 'creative' THEN 'CREATIVE'
                WHEN 'reasoning' THEN 'REASONING'
                WHEN 'multimodal' THEN 'MULTIMODAL'
                ELSE match_type::text
            END
        )::matchtype
        """
    )
    op.execute(
        """
        ALTER TABLE arena_matches
        ALTER COLUMN status TYPE matchstatus
        USING (
            CASE lower(status::text)
                WHEN 'pending' THEN 'WAITING'
                WHEN 'waiting' THEN 'WAITING'
                WHEN 'in_progress' THEN 'IN_PROGRESS'
                WHEN 'voting' THEN 'VOTING'
                WHEN 'finished' THEN 'FINISHED'
                WHEN 'cancelled' THEN 'CANCELLED'
                ELSE status::text
            END
        )::matchstatus
        """
    )
    op.execute("ALTER TABLE arena_matches ALTER COLUMN status SET DEFAULT 'WAITING'::matchstatus")


def downgrade() -> None:
    op.execute("ALTER TABLE arena_matches ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE arena_matches ALTER COLUMN status TYPE varchar(20) USING lower(status::text)")
    op.execute("ALTER TABLE arena_matches ALTER COLUMN status SET DEFAULT 'waiting'")
    op.execute("ALTER TABLE arena_matches ALTER COLUMN match_type TYPE varchar(50) USING lower(match_type::text)")
    op.execute("DROP TYPE IF EXISTS matchstatus")
    op.execute("DROP TYPE IF EXISTS matchtype")

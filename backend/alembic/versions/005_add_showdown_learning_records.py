"""add showdown learning records

Revision ID: 005
Revises: 004
Create Date: 2026-06-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pokemon_showdown_battle_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(80), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('username_key', sa.String(100), nullable=False),
        sa.Column('battle_format', sa.String(50), nullable=False),
        sa.Column('showdown_format', sa.String(80), nullable=False),
        sa.Column('mode', sa.String(20), server_default='balanced'),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reward', sa.Float(), server_default='0.0'),
        sa.Column('turns', sa.Integer(), server_default='0'),
        sa.Column('faints_for', sa.Integer(), server_default='0'),
        sa.Column('faints_against', sa.Integer(), server_default='0'),
        sa.Column('decisions', postgresql.JSONB, server_default='[]'),
        sa.Column('analysis', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('idx_showdown_record_session', 'pokemon_showdown_battle_records', ['session_id'])
    op.create_index('idx_showdown_record_user_format', 'pokemon_showdown_battle_records', ['username_key', 'battle_format'])
    op.create_index('idx_showdown_record_status', 'pokemon_showdown_battle_records', ['status'])
    op.create_index('idx_showdown_record_created', 'pokemon_showdown_battle_records', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_showdown_record_created', table_name='pokemon_showdown_battle_records')
    op.drop_index('idx_showdown_record_status', table_name='pokemon_showdown_battle_records')
    op.drop_index('idx_showdown_record_user_format', table_name='pokemon_showdown_battle_records')
    op.drop_index('idx_showdown_record_session', table_name='pokemon_showdown_battle_records')
    op.drop_table('pokemon_showdown_battle_records')

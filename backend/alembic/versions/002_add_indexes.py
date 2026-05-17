"""Add missing indexes

Revision ID: 002
Revises: 001
Create Date: 2025-05-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agent hierarchy indexes
    op.create_index('ix_agent_hierarchy_parent_agent_id', 'agent_hierarchy', ['parent_agent_id'])
    op.create_index('ix_agent_hierarchy_child_agent_id', 'agent_hierarchy', ['child_agent_id'])

    # Agent experience index
    op.create_index('ix_agent_experiences_agent_id', 'agent_experiences', ['agent_id'])

    # Game player indexes
    op.create_index('ix_game_players_game_id', 'game_players', ['game_id'])
    op.create_index('ix_game_players_agent_id', 'game_players', ['agent_id'])

    # Message turn number index
    op.create_index('ix_messages_turn_number', 'messages', ['turn_number'])

    # Media asset indexes
    op.create_index('ix_media_assets_message_id', 'media_assets', ['message_id'])
    op.create_index('ix_media_assets_uploader_id', 'media_assets', ['uploader_id'])


def downgrade() -> None:
    op.drop_index('ix_media_assets_uploader_id')
    op.drop_index('ix_media_assets_message_id')
    op.drop_index('ix_messages_turn_number')
    op.drop_index('ix_game_players_agent_id')
    op.drop_index('ix_game_players_game_id')
    op.drop_index('ix_agent_experiences_agent_id')
    op.drop_index('ix_agent_hierarchy_child_agent_id')
    op.drop_index('ix_agent_hierarchy_parent_agent_id')

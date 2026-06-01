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
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_hierarchy_parent_agent_id ON agent_hierarchy (parent_agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_hierarchy_child_agent_id ON agent_hierarchy (child_agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_experiences_agent_id ON agent_experiences (agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_game_players_game_id ON game_players (game_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_game_players_agent_id ON game_players (agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_turn_number ON messages (turn_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_media_assets_message_id ON media_assets (message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_media_assets_uploader_id ON media_assets (uploader_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_media_assets_uploader_id")
    op.execute("DROP INDEX IF EXISTS ix_media_assets_message_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_turn_number")
    op.execute("DROP INDEX IF EXISTS ix_game_players_agent_id")
    op.execute("DROP INDEX IF EXISTS ix_game_players_game_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_experiences_agent_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_hierarchy_child_agent_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_hierarchy_parent_agent_id")

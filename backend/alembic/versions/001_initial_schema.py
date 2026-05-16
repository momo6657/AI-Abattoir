"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create all tables in dependency order

    # 1. users (no FK dependencies)
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('github_id', sa.String(100), unique=True, nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_username', 'users', ['username'])

    # 2. models (FK to users)
    op.create_table(
        'models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=True),
        sa.Column('api_base', sa.String(500), nullable=True),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('status', sa.String(20), server_default=sa.text("'offline'")),
        sa.Column('avg_response_time', sa.Float(), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), server_default=sa.text('0')),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_models_owner_id', 'models', ['owner_id'])

    # 3. model_capabilities (FK to models)
    op.create_table(
        'model_capabilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('models.id', ondelete='CASCADE'), nullable=False),
        sa.Column('capability', sa.Enum('text_generation', 'image_generation', 'image_understanding', 'tts', 'stt', 'code_execution', 'video_generation', 'search', name='capabilitytype'), nullable=False),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index('ix_model_capabilities_model_id', 'model_capabilities', ['model_id'])

    # 4. agents (FK to models, users)
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('models.id'), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('voice_model_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('models.id'), nullable=True),
        sa.Column('is_template', sa.String(1), server_default=sa.text("'0'")),
        sa.Column('level', sa.Enum('novice', 'proficient', 'expert', 'master', name='agentlevel'), server_default=sa.text("'novice'")),
        sa.Column('experience_points', sa.Integer(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_agents_model_id', 'agents', ['model_id'])
    op.create_index('ix_agents_owner_id', 'agents', ['owner_id'])

    # 5. agent_profiles (FK to agents)
    op.create_table(
        'agent_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('persona', sa.Text(), nullable=True),
        sa.Column('personality', sa.Text(), nullable=True),
        sa.Column('speaking_style', sa.Text(), nullable=True),
        sa.Column('background_story', sa.Text(), nullable=True),
        sa.Column('strengths', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('custom_config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index('ix_agent_profiles_agent_id', 'agent_profiles', ['agent_id'], unique=True)

    # 6. agent_hierarchy (FK to agents)
    op.create_table(
        'agent_hierarchy',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(50), server_default=sa.text("'command'")),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_agent_hierarchy_parent_agent_id', 'agent_hierarchy', ['parent_agent_id'])
    op.create_index('ix_agent_hierarchy_child_agent_id', 'agent_hierarchy', ['child_agent_id'])

    # 7. agent_experiences (FK to agents)
    op.create_table(
        'agent_experiences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scene_type', sa.String(50), nullable=False),
        sa.Column('context_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('decision', sa.Text(), nullable=True),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('lesson', sa.Text(), nullable=True),
        sa.Column('xp_gained', sa.Integer(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_agent_experiences_agent_id', 'agent_experiences', ['agent_id'])

    # 8. conversations (FK to users)
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('mode', sa.Enum('free', 'debate', 'relay', 'interview', name='conversationmode'), server_default=sa.text("'free'")),
        sa.Column('status', sa.Enum('active', 'paused', 'ended', name='conversationstatus'), server_default=sa.text("'active'")),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_conversations_creator_id', 'conversations', ['creator_id'])

    # 9. messages (FK to conversations, agents)
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', postgresql.JSONB(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('ix_messages_agent_id', 'messages', ['agent_id'])

    # 10. games (FK to users, agents)
    op.create_table(
        'games',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('game_type', sa.Enum('werewolf', 'debate', 'chess', 'text_adventure', 'negotiation', name='gametype'), nullable=False),
        sa.Column('status', sa.Enum('waiting', 'in_progress', 'finished', 'cancelled', name='gamestatus'), server_default=sa.text("'waiting'")),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('state', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('winner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_games_creator_id', 'games', ['creator_id'])

    # 11. game_players (FK to games, agents)
    op.create_table(
        'game_players',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('game_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('is_alive', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_game_players_game_id', 'game_players', ['game_id'])
    op.create_index('ix_game_players_agent_id', 'game_players', ['agent_id'])

    # 12. media_assets (FK to messages, users)
    op.create_table(
        'media_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploader_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_media_assets_message_id', 'media_assets', ['message_id'])
    op.create_index('ix_media_assets_uploader_id', 'media_assets', ['uploader_id'])

    # 13. arena_matches (FK to users, agents)
    op.create_table(
        'arena_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('match_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), server_default=sa.text("'pending'")),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('winner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_arena_matches_creator_id', 'arena_matches', ['creator_id'])
    op.create_index('ix_arena_matches_status', 'arena_matches', ['status'])

    # 14. arena_participants (FK to arena_matches, agents)
    op.create_table(
        'arena_participants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arena_matches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('response_content', postgresql.JSONB(), nullable=True),
        sa.Column('vote_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_arena_participants_match_id', 'arena_participants', ['match_id'])
    op.create_index('ix_arena_participants_agent_id', 'arena_participants', ['agent_id'])

    # 15. arena_votes (FK to arena_matches, arena_participants)
    op.create_table(
        'arena_votes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arena_matches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arena_participants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('voter_session', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_arena_votes_match_id', 'arena_votes', ['match_id'])
    op.create_index('ix_arena_votes_participant_id', 'arena_votes', ['participant_id'])


def downgrade() -> None:
    # Drop all tables in reverse dependency order
    op.drop_table('arena_votes')
    op.drop_table('arena_participants')
    op.drop_table('arena_matches')
    op.drop_table('media_assets')
    op.drop_table('game_players')
    op.drop_table('games')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('agent_experiences')
    op.drop_table('agent_hierarchy')
    op.drop_table('agent_profiles')
    op.drop_table('agents')
    op.drop_table('model_capabilities')
    op.drop_table('models')
    op.drop_table('users')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS gametype")
    op.execute("DROP TYPE IF EXISTS gamestatus")
    op.execute("DROP TYPE IF EXISTS conversationmode")
    op.execute("DROP TYPE IF EXISTS conversationstatus")
    op.execute("DROP TYPE IF EXISTS agentlevel")
    op.execute("DROP TYPE IF EXISTS capabilitytype")

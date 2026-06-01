"""add pokemon tables

Revision ID: a1b2c3d4e5f6
Revises: 002
Create Date: 2026-05-31 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pokemon Species
    op.create_table(
        'pokemon_species',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('name_zh', sa.String(50), nullable=False),
        sa.Column('form', sa.String(50), nullable=True),
        sa.Column('types', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('base_stats', postgresql.JSONB, nullable=False),
        sa.Column('abilities', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('hidden_ability', sa.String(50), nullable=True),
        sa.Column('learn_set', postgresql.JSONB, server_default='{}'),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('gender_ratio', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_species_name', 'pokemon_species', ['name'])
    op.create_index('idx_species_types', 'pokemon_species', ['types'], postgresql_using='gin')

    # Pokemon Moves
    op.create_table(
        'pokemon_moves',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('name_zh', sa.String(50), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('power', sa.Integer(), nullable=True),
        sa.Column('accuracy', sa.Integer(), nullable=True),
        sa.Column('pp', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0'),
        sa.Column('target', sa.String(20), server_default='normal'),
        sa.Column('flags', postgresql.JSONB, server_default='{}'),
        sa.Column('effect', sa.Text(), nullable=True),
        sa.Column('effect_data', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_move_type', 'pokemon_moves', ['type'])
    op.create_index('idx_move_category', 'pokemon_moves', ['category'])

    # Pokemon Abilities
    op.create_table(
        'pokemon_abilities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('name_zh', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('effect_data', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Pokemon Items
    op.create_table(
        'pokemon_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('name_zh', sa.String(50), nullable=False),
        sa.Column('effect', sa.Text(), nullable=True),
        sa.Column('effect_data', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Type Effectiveness
    op.create_table(
        'type_effectiveness',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('attacking_type', sa.String(20), nullable=False),
        sa.Column('defending_type', sa.String(20), nullable=False),
        sa.Column('multiplier', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attacking_type', 'defending_type'),
    )
    op.create_index('idx_type_matchup', 'type_effectiveness', ['attacking_type', 'defending_type'])

    # Pokemon Teams
    op.create_table(
        'pokemon_teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('format', sa.String(20), server_default='vgc2024'),
        sa.Column('pokemon_list', postgresql.JSONB, nullable=False),
        sa.Column('source', sa.String(20), server_default='template'),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('rating', sa.Integer(), server_default='1500'),
        sa.Column('win_rate', sa.Float(), server_default='0.0'),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
    )
    op.create_index('idx_team_agent', 'pokemon_teams', ['agent_id'])
    op.create_index('idx_team_format', 'pokemon_teams', ['format'])
    op.create_index('idx_team_rating', 'pokemon_teams', ['rating'])

    # Pokemon Battles
    op.create_table(
        'pokemon_battles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('battle_format', sa.String(20), server_default='vgc2024'),
        sa.Column('mode', sa.String(20), server_default='local'),
        sa.Column('player1_agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('player2_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('player1_team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('player2_team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('winner', sa.Integer(), nullable=True),
        sa.Column('turns', sa.Integer(), server_default='0'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('replay_url', sa.String(500), nullable=True),
        sa.Column('rating_change_p1', sa.Integer(), nullable=True),
        sa.Column('rating_change_p2', sa.Integer(), nullable=True),
        sa.Column('battle_log', postgresql.JSONB, server_default='[]'),
        sa.Column('summary', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['player1_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['player2_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['player1_team_id'], ['pokemon_teams.id']),
        sa.ForeignKeyConstraint(['player2_team_id'], ['pokemon_teams.id']),
    )
    op.create_index('idx_battle_agent1', 'pokemon_battles', ['player1_agent_id'])
    op.create_index('idx_battle_agent2', 'pokemon_battles', ['player2_agent_id'])
    op.create_index('idx_battle_format', 'pokemon_battles', ['battle_format'])
    op.create_index('idx_battle_created', 'pokemon_battles', ['created_at'])

    # Pokemon Decisions
    op.create_table(
        'pokemon_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('battle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('turn', sa.Integer(), nullable=False),
        sa.Column('state_hash', sa.String(64), nullable=True),
        sa.Column('state', postgresql.JSONB, nullable=False),
        sa.Column('action', postgresql.JSONB, nullable=False),
        sa.Column('alternatives', postgresql.JSONB, server_default='[]'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('thinking_time_ms', sa.Integer(), nullable=True),
        sa.Column('llm_reasoning', sa.Text(), nullable=True),
        sa.Column('immediate_reward', sa.Float(), server_default='0.0'),
        sa.Column('final_reward', sa.Float(), nullable=True),
        sa.Column('q_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['battle_id'], ['pokemon_battles.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
    )
    op.create_index('idx_decision_battle', 'pokemon_decisions', ['battle_id'])
    op.create_index('idx_decision_agent', 'pokemon_decisions', ['agent_id'])
    op.create_index('idx_decision_state_hash', 'pokemon_decisions', ['state_hash'])

    # Pokemon Knowledge Cache
    op.create_table(
        'pokemon_knowledge_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=False),
        sa.Column('query_key', sa.String(200), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_knowledge_query', 'pokemon_knowledge_cache', ['query_type', 'query_key'])
    op.create_index('idx_knowledge_expires', 'pokemon_knowledge_cache', ['expires_at'])

    # Add Pokemon fields to agents table
    op.add_column('agents', sa.Column('pokemon_rating', sa.Integer(), server_default='1500'))
    op.add_column('agents', sa.Column('pokemon_favorite_format', sa.String(20), server_default='vgc2024'))
    op.add_column('agents', sa.Column('pokemon_playstyle', sa.String(50), nullable=True))
    op.add_column('agents', sa.Column('pokemon_stats', postgresql.JSONB, server_default='{}'))


def downgrade() -> None:
    # Remove agent columns
    op.drop_column('agents', 'pokemon_stats')
    op.drop_column('agents', 'pokemon_playstyle')
    op.drop_column('agents', 'pokemon_favorite_format')
    op.drop_column('agents', 'pokemon_rating')

    # Drop tables in reverse order
    op.drop_table('pokemon_knowledge_cache')
    op.drop_table('pokemon_decisions')
    op.drop_table('pokemon_battles')
    op.drop_table('pokemon_teams')
    op.drop_table('type_effectiveness')
    op.drop_table('pokemon_items')
    op.drop_table('pokemon_abilities')
    op.drop_table('pokemon_moves')
    op.drop_table('pokemon_species')

import uuid as uuid_module
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Index, UniqueConstraint, JSON
from sqlalchemy.types import TypeDecorator, String as SQLString
from app.core.database import Base


# SQLite-compatible TypeDecorators for PostgreSQL types
class PGArray(TypeDecorator):
    """PostgreSQL ARRAY type with SQLite fallback (stores as JSON array)"""
    impl = JSON
    cache_ok = True

    def __init__(self, item_type=None):
        super().__init__()


class PGJSONB(TypeDecorator):
    """PostgreSQL JSONB type with SQLite fallback (stores as JSON)"""
    impl = JSON
    cache_ok = True


class PGUUID(TypeDecorator):
    """PostgreSQL UUID type with SQLite fallback (stores as string)"""
    impl = SQLString(36)
    cache_ok = True

    def __init__(self, as_uuid=True):
        self.as_uuid = as_uuid
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if self.as_uuid:
            return uuid_module.UUID(value)
        return value


# Alias for convenience
ARRAY = PGArray
JSONB = PGJSONB


class PokemonSpecies(Base):
    """宝可梦种族数据"""
    __tablename__ = "pokemon_species"

    id = Column(Integer, primary_key=True)  # 全国图鉴编号
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    form = Column(String(50), nullable=True)  # 形态（洗翠、伽勒尔等）
    types = Column(PGArray(), nullable=False)  # ['Water', 'Flying']
    base_stats = Column(PGJSONB, nullable=False)  # {hp, atk, def, spa, spd, spe}
    abilities = Column(PGArray(), nullable=False)
    hidden_ability = Column(String(50), nullable=True)
    learn_set = Column(PGJSONB, default=dict)  # {move_name: learn_method}
    weight = Column(Float, nullable=False)  # kg
    gender_ratio = Column(PGJSONB, default=dict)  # {male: 0.5, female: 0.5}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_species_name', 'name'),
        Index('idx_species_types', 'types', postgresql_using='gin'),
    )


class PokemonMove(Base):
    """宝可梦技能数据"""
    __tablename__ = "pokemon_moves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)
    category = Column(String(20), nullable=False)  # physical/special/status
    power = Column(Integer, nullable=True)
    accuracy = Column(Integer, nullable=True)
    pp = Column(Integer, nullable=False)
    priority = Column(Integer, default=0)
    target = Column(String(20), default='normal')
    flags = Column(PGJSONB, default=dict)  # {contact: true, protect: true}
    effect = Column(Text, nullable=True)
    effect_data = Column(PGJSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_move_type', 'type'),
        Index('idx_move_category', 'category'),
    )


class PokemonAbility(Base):
    """特性数据"""
    __tablename__ = "pokemon_abilities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    effect_data = Column(PGJSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PokemonItem(Base):
    """道具数据"""
    __tablename__ = "pokemon_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    effect = Column(Text, nullable=True)
    effect_data = Column(PGJSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TypeEffectiveness(Base):
    """属性克制表"""
    __tablename__ = "type_effectiveness"

    id = Column(Integer, primary_key=True, autoincrement=True)
    attacking_type = Column(String(20), nullable=False)
    defending_type = Column(String(20), nullable=False)
    multiplier = Column(Float, nullable=False)  # 0, 0.5, 1, 2, 4

    __table_args__ = (
        Index('idx_type_matchup', 'attacking_type', 'defending_type'),
        UniqueConstraint('attacking_type', 'defending_type'),
    )


class PokemonTeam(Base):
    """队伍配置"""
    __tablename__ = "pokemon_teams"

    id = Column(PGUUID(), primary_key=True, default=uuid_module.uuid4)
    agent_id = Column(PGUUID(), ForeignKey("agents.id"), nullable=False)
    name = Column(String(100), nullable=False)
    format = Column(String(20), default='vgc2024')
    pokemon_list = Column(PGJSONB, nullable=False)
    source = Column(String(20), default='template')
    source_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    rating = Column(Integer, default=1500)
    win_rate = Column(Float, default=0.0)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_team_agent', 'agent_id'),
        Index('idx_team_format', 'format'),
        Index('idx_team_rating', 'rating'),
    )


class PokemonBattle(Base):
    """对战记录"""
    __tablename__ = "pokemon_battles"

    id = Column(PGUUID(), primary_key=True, default=uuid_module.uuid4)
    battle_format = Column(String(20), default='vgc2024')
    mode = Column(String(20), default='local')
    player1_agent_id = Column(PGUUID(), ForeignKey("agents.id"), nullable=False)
    player2_agent_id = Column(PGUUID(), ForeignKey("agents.id"), nullable=True)
    player1_team_id = Column(PGUUID(), ForeignKey("pokemon_teams.id"), nullable=False)
    player2_team_id = Column(PGUUID(), ForeignKey("pokemon_teams.id"), nullable=True)
    winner = Column(Integer, nullable=True)
    turns = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)
    replay_url = Column(String(500), nullable=True)
    rating_change_p1 = Column(Integer, nullable=True)
    rating_change_p2 = Column(Integer, nullable=True)
    battle_log = Column(PGJSONB, default=list)
    summary = Column(PGJSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_battle_agent1', 'player1_agent_id'),
        Index('idx_battle_agent2', 'player2_agent_id'),
        Index('idx_battle_format', 'battle_format'),
        Index('idx_battle_created', 'created_at'),
    )


class PokemonDecision(Base):
    """决策记录（用于强化学习）"""
    __tablename__ = "pokemon_decisions"

    id = Column(PGUUID(), primary_key=True, default=uuid_module.uuid4)
    battle_id = Column(PGUUID(), ForeignKey("pokemon_battles.id"), nullable=False)
    agent_id = Column(PGUUID(), ForeignKey("agents.id"), nullable=False)
    turn = Column(Integer, nullable=False)
    state_hash = Column(String(64), nullable=True)
    state = Column(PGJSONB, nullable=False)
    action = Column(PGJSONB, nullable=False)
    alternatives = Column(PGJSONB, default=list)
    confidence = Column(Float, nullable=True)
    thinking_time_ms = Column(Integer, nullable=True)
    llm_reasoning = Column(Text, nullable=True)
    immediate_reward = Column(Float, default=0.0)
    final_reward = Column(Float, nullable=True)
    q_value = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_decision_battle', 'battle_id'),
        Index('idx_decision_agent', 'agent_id'),
        Index('idx_decision_state_hash', 'state_hash'),
    )


class PokemonKnowledgeCache(Base):
    """联网搜索的知识缓存"""
    __tablename__ = "pokemon_knowledge_cache"

    id = Column(PGUUID(), primary_key=True, default=uuid_module.uuid4)
    query_type = Column(String(50), nullable=False)
    query_key = Column(String(200), nullable=False)
    source_url = Column(String(500), nullable=True)
    content = Column(PGJSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_knowledge_query', 'query_type', 'query_key'),
        Index('idx_knowledge_expires', 'expires_at'),
    )

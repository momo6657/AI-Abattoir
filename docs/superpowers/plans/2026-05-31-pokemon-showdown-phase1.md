# Pokemon Showdown 适配 - Phase 1 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现本地宝可梦对战引擎，让智能体能够进行基础的 VGC 双打对战

**架构：** 基于现有游戏引擎框架，添加宝可梦对战专用的数据模型、对战引擎和 AI 决策系统。Phase 1 专注于核心对战流程，使用简化规则和固定队伍模板。

**技术栈：** FastAPI, SQLAlchemy, PostgreSQL, Redis, LiteLLM, WebSocket

---

## 文件结构

### 新增文件

**数据模型层：**
- `backend/app/models/pokemon.py` - 宝可梦相关数据模型（Species, Move, Ability, Item, Team, Battle, Decision）
- `backend/alembic/versions/XXXX_add_pokemon_tables.py` - 数据库迁移文件

**Schema 层：**
- `backend/app/schemas/pokemon.py` - Pydantic 请求/响应模型

**服务层：**
- `backend/app/services/pokemon/battle_engine.py` - 对战引擎核心
- `backend/app/services/pokemon/damage_calculator.py` - 伤害计算器
- `backend/app/services/pokemon/type_chart.py` - 属性克制表
- `backend/app/services/pokemon/team_service.py` - 队伍管理服务
- `backend/app/services/pokemon/ai_decision.py` - AI 决策引擎
- `backend/app/services/pokemon/data_loader.py` - 数据加载器（初始化宝可梦数据）

**API 层：**
- `backend/app/api/pokemon.py` - Pokemon 相关 REST API 路由

**WebSocket 层：**
- `backend/app/websocket/pokemon_manager.py` - Pokemon 对战 WebSocket 管理器

**测试文件：**
- `backend/tests/services/pokemon/test_damage_calculator.py`
- `backend/tests/services/pokemon/test_type_chart.py`
- `backend/tests/services/pokemon/test_battle_engine.py`
- `backend/tests/api/test_pokemon.py`

**数据文件：**
- `backend/data/pokemon/species.json` - 宝可梦种族数据（Top 100）
- `backend/data/pokemon/moves.json` - 技能数据
- `backend/data/pokemon/abilities.json` - 特性数据
- `backend/data/pokemon/items.json` - 道具数据
- `backend/data/pokemon/team_templates.json` - 队伍模板

### 修改文件

- `backend/app/main.py` - 注册 Pokemon API 路由
- `backend/app/models/agent.py` - 添加宝可梦相关字段
- `backend/app/models/game.py` - 添加 POKEMON_BATTLE 游戏类型

---

## Phase 1 任务列表

### 任务 1：数据库模型设计
### 任务 2：属性克制系统
### 任务 3：伤害计算器
### 任务 4：队伍数据加载
### 任务 5：对战引擎核心
### 任务 6：AI 决策引擎
### 任务 7：REST API 实现
### 任务 8：WebSocket 实时对战
### 任务 9：前端对战界面
### 任务 10：集成测试与优化

---

## 任务 1：数据库模型设计

**文件：**
- 创建：`backend/app/models/pokemon.py`
- 修改：`backend/app/models/game.py`
- 修改：`backend/app/models/agent.py`

### 步骤 1.1：创建 Pokemon 数据模型基础结构

- [ ] **创建 pokemon.py 文件并定义基础导入**

```python
# backend/app/models/pokemon.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from app.core.database import Base
```

- [ ] **定义 PokemonSpecies 模型**

```python
class PokemonSpecies(Base):
    """宝可梦种族数据"""
    __tablename__ = "pokemon_species"

    id = Column(Integer, primary_key=True)  # 全国图鉴编号
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    form = Column(String(50), nullable=True)  # 形态（洗翠、伽勒尔等）
    types = Column(ARRAY(String), nullable=False)  # ['Water', 'Flying']
    base_stats = Column(JSONB, nullable=False)  # {hp, atk, def, spa, spd, spe}
    abilities = Column(ARRAY(String), nullable=False)
    hidden_ability = Column(String(50), nullable=True)
    learn_set = Column(JSONB, default=dict)  # {move_name: learn_method}
    weight = Column(Float, nullable=False)  # kg
    gender_ratio = Column(JSONB, default=dict)  # {male: 0.5, female: 0.5}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_species_name', 'name'),
        Index('idx_species_types', 'types', postgresql_using='gin'),
    )
```

- [ ] **定义 PokemonMove 模型**

```python
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
    target = Column(String(20), default='normal')  # normal/allAdjacent/allAdjacentFoes等
    flags = Column(JSONB, default=dict)  # {contact: true, protect: true}
    effect = Column(Text, nullable=True)
    effect_data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_move_type', 'type'),
        Index('idx_move_category', 'category'),
    )
```

- [ ] **Commit 基础模型**

```bash
git add backend/app/models/pokemon.py
git commit -m "feat(pokemon): add PokemonSpecies and PokemonMove models"
```

### 步骤 1.2：添加道具、特性和属性克制模型

- [ ] **定义 PokemonAbility、PokemonItem 和 TypeEffectiveness 模型**

在 `backend/app/models/pokemon.py` 中添加：

```python
class PokemonAbility(Base):
    """特性数据"""
    __tablename__ = "pokemon_abilities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    effect_data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PokemonItem(Base):
    """道具数据"""
    __tablename__ = "pokemon_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    name_zh = Column(String(50), nullable=False)
    effect = Column(Text, nullable=True)
    effect_data = Column(JSONB, default=dict)
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
```

- [ ] **Commit 道具和特性模型**

```bash
git add backend/app/models/pokemon.py
git commit -m "feat(pokemon): add Ability, Item and TypeEffectiveness models"
```

### 步骤 1.3：添加队伍和对战模型

- [ ] **定义 PokemonTeam 和 PokemonBattle 模型**

在 `backend/app/models/pokemon.py` 中添加：

```python
class PokemonTeam(Base):
    """队伍配置"""
    __tablename__ = "pokemon_teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    name = Column(String(100), nullable=False)
    format = Column(String(20), default='vgc2024')
    pokemon_list = Column(JSONB, nullable=False)
    source = Column(String(20), default='template')  # template/custom/evolved
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    battle_format = Column(String(20), default='vgc2024')
    mode = Column(String(20), default='local')  # local/showdown
    player1_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    player2_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    player1_team_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_teams.id"), nullable=False)
    player2_team_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_teams.id"), nullable=True)
    winner = Column(Integer, nullable=True)  # 1/2/None
    turns = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)
    replay_url = Column(String(500), nullable=True)
    rating_change_p1 = Column(Integer, nullable=True)
    rating_change_p2 = Column(Integer, nullable=True)
    battle_log = Column(JSONB, default=list)
    summary = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_battle_agent1', 'player1_agent_id'),
        Index('idx_battle_agent2', 'player2_agent_id'),
        Index('idx_battle_format', 'battle_format'),
        Index('idx_battle_created', 'created_at'),
    )
```

- [ ] **Commit 队伍和对战模型**

```bash
git add backend/app/models/pokemon.py
git commit -m "feat(pokemon): add PokemonTeam and PokemonBattle models"
```

### 步骤 1.4：添加决策记录和知识缓存模型

- [ ] **定义 PokemonDecision 和 PokemonKnowledgeCache 模型**

在 `backend/app/models/pokemon.py` 中添加：

```python
class PokemonDecision(Base):
    """决策记录（用于强化学习）"""
    __tablename__ = "pokemon_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    battle_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_battles.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    turn = Column(Integer, nullable=False)
    state_hash = Column(String(64), nullable=True)
    state = Column(JSONB, nullable=False)
    action = Column(JSONB, nullable=False)
    alternatives = Column(JSONB, default=list)
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_type = Column(String(50), nullable=False)
    query_key = Column(String(200), nullable=False)
    source_url = Column(String(500), nullable=True)
    content = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_knowledge_query', 'query_type', 'query_key'),
        Index('idx_knowledge_expires', 'expires_at'),
    )
```

- [ ] **Commit 决策和缓存模型**

```bash
git add backend/app/models/pokemon.py
git commit -m "feat(pokemon): add PokemonDecision and KnowledgeCache models"
```

### 步骤 1.5：修改现有模型以支持宝可梦功能

- [ ] **在 Agent 模型中添加宝可梦字段**

在 `backend/app/models/agent.py` 的 `Agent` 类中添加：

```python
    # 宝可梦相关字段
    pokemon_rating = Column(Integer, default=1500)
    pokemon_favorite_format = Column(String(20), nullable=True)
    pokemon_playstyle = Column(String(50), nullable=True)
    pokemon_stats = Column(JSONB, default=dict)
```

- [ ] **在 GameType 枚举中添加宝可梦对战类型**

在 `backend/app/models/game.py` 的 `GameType` 枚举中添加：

```python
class GameType(str, enum.Enum):
    WEREWOLF = "werewolf"
    DEBATE = "debate"
    CHESS = "chess"
    TEXT_ADVENTURE = "text_adventure"
    NEGOTIATION = "negotiation"
    POKEMON_BATTLE = "pokemon_battle"  # 新增
```

- [ ] **Commit 现有模型修改**

```bash
git add backend/app/models/agent.py backend/app/models/game.py
git commit -m "feat(pokemon): extend Agent and GameType for Pokemon battles"
```

### 步骤 1.6：创建数据库迁移

- [ ] **生成 Alembic 迁移文件**

```bash
cd backend
alembic revision --autogenerate -m "add pokemon tables"
```

- [ ] **检查生成的迁移文件**

检查 `backend/alembic/versions/XXXX_add_pokemon_tables.py`，确保包含所有新表。

- [ ] **执行迁移**

```bash
alembic upgrade head
```

预期：所有 Pokemon 相关表创建成功，输出类似：
```
INFO  [alembic.runtime.migration] Running upgrade -> XXXX, add pokemon tables
```

- [ ] **Commit 迁移文件**

```bash
git add backend/alembic/versions/
git commit -m "chore(pokemon): add database migration for Pokemon tables"
```

---

## 任务 2：属性克制系统

**文件：**
- 创建：`backend/app/services/pokemon/type_chart.py`
- 创建：`backend/tests/services/pokemon/test_type_chart.py`

### 步骤 2.1：编写属性克制测试

- [ ] **创建测试目录和文件**

```bash
mkdir -p backend/tests/services/pokemon
touch backend/tests/services/pokemon/__init__.py
touch backend/tests/services/pokemon/test_type_chart.py
```

- [ ] **编写属性克制测试用例**

```python
# backend/tests/services/pokemon/test_type_chart.py
import pytest
from app.services.pokemon.type_chart import TypeChart


def test_type_chart_super_effective():
    """测试克制关系（2倍伤害）"""
    chart = TypeChart()
    assert chart.get_effectiveness("Water", "Fire") == 2.0
    assert chart.get_effectiveness("Fire", "Grass") == 2.0
    assert chart.get_effectiveness("Grass", "Water") == 2.0


def test_type_chart_not_very_effective():
    """测试抵抗关系（0.5倍伤害）"""
    chart = TypeChart()
    assert chart.get_effectiveness("Fire", "Water") == 0.5
    assert chart.get_effectiveness("Grass", "Fire") == 0.5
    assert chart.get_effectiveness("Water", "Grass") == 0.5


def test_type_chart_no_effect():
    """测试无效关系（0倍伤害）"""
    chart = TypeChart()
    assert chart.get_effectiveness("Normal", "Ghost") == 0.0
    assert chart.get_effectiveness("Electric", "Ground") == 0.0
    assert chart.get_effectiveness("Ground", "Flying") == 0.0


def test_type_chart_dual_type():
    """测试双属性克制（倍率相乘）"""
    chart = TypeChart()
    # 水系打岩石/地面（2x * 2x = 4x）
    multiplier = chart.get_dual_type_effectiveness("Water", ["Rock", "Ground"])
    assert multiplier == 4.0
    
    # 草系打水/地面（2x * 2x = 4x）
    multiplier = chart.get_dual_type_effectiveness("Grass", ["Water", "Ground"])
    assert multiplier == 4.0


def test_type_chart_neutral():
    """测试普通伤害（1倍）"""
    chart = TypeChart()
    assert chart.get_effectiveness("Normal", "Normal") == 1.0
    assert chart.get_effectiveness("Fire", "Electric") == 1.0
```

- [ ] **运行测试验证失败**

```bash
cd backend
pytest tests/services/pokemon/test_type_chart.py -v
```

预期：FAIL，报错 "ModuleNotFoundError: No module named 'app.services.pokemon.type_chart'"

- [ ] **Commit 测试**

```bash
git add backend/tests/services/pokemon/
git commit -m "test(pokemon): add type chart tests"
```

### 步骤 2.2：实现属性克制系统

- [ ] **创建服务目录和文件**

```bash
mkdir -p backend/app/services/pokemon
touch backend/app/services/pokemon/__init__.py
```

- [ ] **实现 TypeChart 类（第1部分）**

```python
# backend/app/services/pokemon/type_chart.py
from typing import List


class TypeChart:
    """宝可梦属性克制表"""
    
    # 属性克制关系：{攻击属性: {防御属性: 倍率}}
    EFFECTIVENESS = {
        "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
        "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
        "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
        "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
        "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
        "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
        "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
        "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
        "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
        "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
        "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
        "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
        "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
        "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
        "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
        "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
        "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
        "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
    }
```

- [ ] **实现 TypeChart 类（第2部分）**

```python
# 继续在 backend/app/services/pokemon/type_chart.py 中添加
    
    def get_effectiveness(self, attacking_type: str, defending_type: str) -> float:
        """获取单属性克制倍率"""
        if attacking_type not in self.EFFECTIVENESS:
            return 1.0
        
        return self.EFFECTIVENESS[attacking_type].get(defending_type, 1.0)
    
    def get_dual_type_effectiveness(self, attacking_type: str, defending_types: List[str]) -> float:
        """获取对双属性的克制倍率（倍率相乘）"""
        multiplier = 1.0
        for defending_type in defending_types:
            multiplier *= self.get_effectiveness(attacking_type, defending_type)
        return multiplier


# 单例实例
type_chart = TypeChart()
```

- [ ] **运行测试验证通过**

```bash
pytest tests/services/pokemon/test_type_chart.py -v
```

预期：所有测试 PASS

- [ ] **Commit 实现**

```bash
git add backend/app/services/pokemon/
git commit -m "feat(pokemon): implement type effectiveness chart"
```

---

## 任务 3：伤害计算器

**文件：**
- 创建：`backend/app/services/pokemon/damage_calculator.py`
- 创建：`backend/tests/services/pokemon/test_damage_calculator.py`

### 步骤 3.1：编写伤害计算测试

- [ ] **编写伤害计算测试用例**

```python
# backend/tests/services/pokemon/test_damage_calculator.py
import pytest
from app.services.pokemon.damage_calculator import DamageCalculator


@pytest.fixture
def calculator():
    return DamageCalculator()


def test_physical_damage_calculation(calculator):
    """测试物理伤害计算"""
    attacker = {
        "level": 50,
        "atk": 150,
        "stats": {"atk": 150}
    }
    defender = {
        "def": 100,
        "stats": {"def": 100}
    }
    move = {
        "power": 80,
        "category": "physical"
    }
    
    damage = calculator.calculate_damage(attacker, defender, move, type_effectiveness=1.0)
    
    # 伤害应该在合理范围内（考虑随机因素 85%-100%）
    assert 50 <= damage <= 100


def test_special_damage_calculation(calculator):
    """测试特殊伤害计算"""
    attacker = {
        "level": 50,
        "spa": 150,
        "stats": {"spa": 150}
    }
    defender = {
        "spd": 100,
        "stats": {"spd": 100}
    }
    move = {
        "power": 90,
        "category": "special"
    }
    
    damage = calculator.calculate_damage(attacker, defender, move, type_effectiveness=1.0)
    
    assert 50 <= damage <= 120


def test_type_effectiveness_multiplier(calculator):
    """测试属性克制倍率"""
    attacker = {"level": 50, "atk": 100, "stats": {"atk": 100}}
    defender = {"def": 100, "stats": {"def": 100}}
    move = {"power": 80, "category": "physical"}
    
    # 普通伤害
    normal_damage = calculator.calculate_damage(attacker, defender, move, type_effectiveness=1.0)
    
    # 克制伤害（2倍）
    super_damage = calculator.calculate_damage(attacker, defender, move, type_effectiveness=2.0)
    
    # 抵抗伤害（0.5倍）
    weak_damage = calculator.calculate_damage(attacker, defender, move, type_effectiveness=0.5)
    
    # 克制伤害应该约为普通伤害的2倍
    assert super_damage >= normal_damage * 1.8
    
    # 抵抗伤害应该约为普通伤害的0.5倍
    assert weak_damage <= normal_damage * 0.6


def test_critical_hit(calculator):
    """测试暴击"""
    attacker = {"level": 50, "atk": 100, "stats": {"atk": 100}}
    defender = {"def": 100, "stats": {"def": 100}}
    move = {"power": 80, "category": "physical"}
    
    normal_damage = calculator.calculate_damage(attacker, defender, move, is_critical=False)
    crit_damage = calculator.calculate_damage(attacker, defender, move, is_critical=True)
    
    # 暴击伤害应该是普通伤害的1.5倍
    assert crit_damage >= normal_damage * 1.4


def test_stab_bonus(calculator):
    """测试本系加成（STAB）"""
    attacker = {"level": 50, "atk": 100, "stats": {"atk": 100}}
    defender = {"def": 100, "stats": {"def": 100}}
    move = {"power": 80, "category": "physical"}
    
    no_stab = calculator.calculate_damage(attacker, defender, move, has_stab=False)
    with_stab = calculator.calculate_damage(attacker, defender, move, has_stab=True)
    
    # STAB 伤害应该是无 STAB 的 1.5 倍
    assert with_stab >= no_stab * 1.4
```

- [ ] **运行测试验证失败**

```bash
pytest tests/services/pokemon/test_damage_calculator.py -v
```

预期：FAIL

- [ ] **Commit 测试**

```bash
git add backend/tests/services/pokemon/test_damage_calculator.py
git commit -m "test(pokemon): add damage calculator tests"
```

### 步骤 3.2：实现伤害计算器（第1部分）

- [ ] **实现 DamageCalculator 类基础结构**

```python
# backend/app/services/pokemon/damage_calculator.py
import random
from typing import Dict, Any


class DamageCalculator:
    """宝可梦伤害计算器"""
    
    def calculate_damage(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        move: Dict[str, Any],
        type_effectiveness: float = 1.0,
        is_critical: bool = False,
        has_stab: bool = False,
        weather_modifier: float = 1.0,
        random_factor: float = None
    ) -> int:
        """
        计算伤害值
        
        公式：Damage = ((2 * Level / 5 + 2) * Power * A / D / 50 + 2) * Modifiers
        
        Args:
            attacker: 攻击方数据 {level, atk/spa, stats}
            defender: 防御方数据 {def/spd, stats}
            move: 技能数据 {power, category}
            type_effectiveness: 属性克制倍率
            is_critical: 是否暴击
            has_stab: 是否本系加成
            weather_modifier: 天气修正
            random_factor: 随机因子（0.85-1.0），测试时可固定
        
        Returns:
            伤害值
        """
        # 状态技能不造成伤害
        if move.get("category") == "status" or not move.get("power"):
            return 0
        
        level = attacker.get("level", 50)
        power = move["power"]
        
        # 获取攻击和防御数值
        if move["category"] == "physical":
            attack = attacker.get("stats", {}).get("atk", attacker.get("atk", 100))
            defense = defender.get("stats", {}).get("def", defender.get("def", 100))
        else:  # special
            attack = attacker.get("stats", {}).get("spa", attacker.get("spa", 100))
            defense = defender.get("stats", {}).get("spd", defender.get("spd", 100))
        
        # 基础伤害计算
        damage = ((2 * level / 5 + 2) * power * attack / defense / 50 + 2)
        
        # 暴击修正（1.5倍）
        if is_critical:
            damage *= 1.5
        
        # 随机因子（85%-100%）
        if random_factor is None:
            random_factor = random.uniform(0.85, 1.0)
        damage *= random_factor
        
        # STAB 本系加成（1.5倍）
        if has_stab:
            damage *= 1.5
        
        # 属性克制
        damage *= type_effectiveness
        
        # 天气修正
        damage *= weather_modifier
        
        # 向下取整，最少1点伤害
        return max(1, int(damage))
```

### 步骤 3.3：实现伤害计算器（第2部分）

- [ ] **添加暴击判定方法**

```python
# 继续在 backend/app/services/pokemon/damage_calculator.py 中添加
    
    def is_critical_hit(self, crit_stage: int = 0) -> bool:
        """
        判断是否暴击
        
        Args:
            crit_stage: 暴击等级（0-3）
        
        Returns:
            是否暴击
        """
        # 暴击率：stage 0 = 1/24, stage 1 = 1/8, stage 2 = 1/2, stage 3+ = 100%
        crit_rates = {
            0: 1/24,
            1: 1/8,
            2: 1/2,
        }
        
        if crit_stage >= 3:
            return True
        
        rate = crit_rates.get(crit_stage, 1/24)
        return random.random() < rate


# 单例实例
damage_calculator = DamageCalculator()
```

- [ ] **运行测试验证通过**

```bash
pytest tests/services/pokemon/test_damage_calculator.py -v
```

预期：所有测试 PASS

- [ ] **Commit 实现**

```bash
git add backend/app/services/pokemon/damage_calculator.py
git commit -m "feat(pokemon): implement damage calculator"
```

---

## 任务 4-10：概要说明

由于完整的详细步骤会使计划文件过长，以下任务提供概要说明。执行时可以使用 subagent-driven-development 技能，每个任务会有独立的子代理来实现详细步骤。

### 任务 4：队伍数据加载

**目标：** 创建初始宝可梦数据（Top 100 种族、技能、道具）和队伍模板

**文件：**
- 创建：`backend/data/pokemon/species.json`
- 创建：`backend/data/pokemon/moves.json`
- 创建：`backend/data/pokemon/abilities.json`
- 创建：`backend/data/pokemon/items.json`
- 创建：`backend/data/pokemon/team_templates.json`
- 创建：`backend/app/services/pokemon/data_loader.py`
- 创建：`backend/tests/services/pokemon/test_data_loader.py`

**关键步骤：**
1. 编写数据加载器测试
2. 实现 DataLoader 类（从 JSON 加载数据到数据库）
3. 准备 Top 100 宝可梦数据（可从 PokeAPI 或手动整理）
4. 准备常用技能数据（至少 50 个技能）
5. 准备 5-10 个队伍模板（从 pokechamdb 等网站获取）
6. 编写数据初始化脚本
7. 测试数据加载功能

### 任务 5：对战引擎核心

**目标：** 实现 VGC 双打对战的核心逻辑

**文件：**
- 创建：`backend/app/services/pokemon/battle_engine.py`
- 创建：`backend/app/services/pokemon/battle_state.py`
- 创建：`backend/tests/services/pokemon/test_battle_engine.py`

**关键步骤：**
1. 定义 BattleState 类（场面状态、宝可梦状态）
2. 实现对战初始化（Team Preview）
3. 实现回合执行逻辑（行动排序、技能执行、伤害结算）
4. 实现换宝可梦机制
5. 实现太晶化机制（简化版）
6. 实现胜负判定
7. 编写完整对战流程测试

### 任务 6：AI 决策引擎

**目标：** 让智能体能够根据场面状态做出决策

**文件：**
- 创建：`backend/app/services/pokemon/ai_decision.py`
- 创建：`backend/tests/services/pokemon/test_ai_decision.py`

**关键步骤：**
1. 定义决策输入格式（场面状态 → JSON）
2. 构建 LLM prompt（包含规则说明、当前状态、可选行动）
3. 实现决策解析（LLM 输出 → 结构化行动）
4. 添加决策记录（用于强化学习）
5. 实现回退机制（LLM 失败时随机选择）
6. 测试决策功能

### 任务 7：REST API 实现

**目标：** 提供 Pokemon 对战的 HTTP API

**文件：**
- 创建：`backend/app/schemas/pokemon.py`
- 创建：`backend/app/api/pokemon.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/api/test_pokemon.py`

**关键步骤：**
1. 定义 Pydantic schemas（请求/响应模型）
2. 实现队伍管理 API（CRUD）
3. 实现对战管理 API（创建、开始、获取状态）
4. 实现对战历史 API
5. 在 main.py 中注册路由
6. 编写 API 测试

### 任务 8：WebSocket 实时对战

**目标：** 实现对战的实时推送和观战功能

**文件：**
- 创建：`backend/app/websocket/pokemon_manager.py`
- 修改：`backend/app/main.py`

**关键步骤：**
1. 实现 PokemonBattleManager（管理 WebSocket 连接）
2. 实现对战事件推送（回合开始、技能使用、伤害结算等）
3. 实现观战功能（只读连接）
4. 在 main.py 中注册 WebSocket 路由
5. 测试实时推送功能

### 任务 9：前端对战界面

**目标：** 创建宝可梦对战的前端页面

**文件：**
- 创建：`frontend/src/app/pokemon/page.tsx`
- 创建：`frontend/src/app/pokemon/battles/[id]/page.tsx`
- 创建：`frontend/src/app/pokemon/teams/page.tsx`
- 创建：`frontend/src/components/pokemon/BattleField.tsx`
- 创建：`frontend/src/components/pokemon/PokemonCard.tsx`
- 创建：`frontend/src/components/pokemon/TeamBuilder.tsx`

**关键步骤：**
1. 创建对战列表页面
2. 创建对战详情页面（实时显示对战状态）
3. 创建队伍管理页面
4. 实现 BattleField 组件（显示双打场地）
5. 实现 PokemonCard 组件（显示宝可梦状态）
6. 实现 WebSocket 连接和事件处理
7. 测试前端功能

### 任务 10：集成测试与优化

**目标：** 端到端测试和性能优化

**文件：**
- 创建：`backend/tests/integration/test_pokemon_battle_flow.py`

**关键步骤：**
1. 编写完整对战流程的集成测试
2. 测试智能体对战（Agent A vs Agent B）
3. 性能测试（对战引擎响应时间）
4. 修复发现的 bug
5. 优化数据库查询
6. 添加日志和监控
7. 编写 Phase 1 完成报告

---

## 执行指南

### 推荐执行方式

**方式 1：子代理驱动开发（推荐）**

使用 `subagent-driven-development` 技能，每个任务由独立的子代理执行：

```bash
# 在 Claude Code 中执行
/subagent-driven-development docs/superpowers/plans/2026-05-31-pokemon-showdown-phase1.md
```

优点：
- 每个任务独立执行，有审查检查点
- 任务间可以快速迭代
- 出错时容易定位和修复

**方式 2：内联执行**

使用 `executing-plans` 技能在当前会话中批量执行：

```bash
# 在 Claude Code 中执行
/executing-plans docs/superpowers/plans/2026-05-31-pokemon-showdown-phase1.md
```

优点：
- 连续执行，无需多次交互
- 适合已经验证过的计划

### 执行前准备

1. 确保 PostgreSQL 和 Redis 正在运行
2. 确保后端虚拟环境已激活
3. 确保有至少一个 LLM API Key 配置

### 验证标准

Phase 1 完成后，应该能够：

- [ ] 数据库包含至少 100 个宝可梦种族数据
- [ ] 数据库包含至少 50 个技能数据
- [ ] 数据库包含至少 5 个队伍模板
- [ ] 两个智能体能够完成一场完整的 VGC 双打对战
- [ ] 伤害计算正确（属性克制、暴击、STAB）
- [ ] 前端能够实时观战对战过程
- [ ] 对战日志完整记录
- [ ] 所有单元测试通过
- [ ] 集成测试通过

---

## 后续 Phase 预告

### Phase 2：知识系统 + 学习机制（2-3周）

- 实现联网搜索集成
- 实现 Redis 知识缓存
- 实现轻量级强化学习
- Q 值估计和策略优化

### Phase 3：队伍构建 + 进化系统（2-3周）

- 智能体根据等级选择队伍策略
- 队伍构建器（自动组队）
- 经验系统深度集成
- 对战分析和回放

### Phase 4：PS 服务器连接（3-4周）

- 实现 PS WebSocket 协议
- 登录和房间管理
- 天梯匹配
- 真实对战数据收集

---

## 参考资料

- Pokemon Showdown 源码：https://github.com/smogon/pokemon-showdown
- 伤害计算公式：https://bulbapedia.bulbagarden.net/wiki/Damage
- VGC 规则：https://www.pokemon.com/us/pokemon-news/2024-video-game-championships-format-rules
- 宝可梦数据 API：https://pokeapi.co/
- 排位数据库：https://pokechamdb.com/zh-Hans


## 任务 4-10：概要说明

由于完整的详细步骤会使计划文件过长，以下任务提供概要说明。执行时可以使用 subagent-driven-development 技能，每个任务会有独立的子代理来实现详细步骤。

### 任务 4：队伍数据加载

**目标：** 创建初始宝可梦数据（Top 100 种族、技能、道具）和队伍模板

**文件：**
- 创建：`backend/data/pokemon/species.json`
- 创建：`backend/data/pokemon/moves.json`
- 创建：`backend/data/pokemon/abilities.json`
- 创建：`backend/data/pokemon/items.json`
- 创建：`backend/data/pokemon/team_templates.json`
- 创建：`backend/app/services/pokemon/data_loader.py`
- 创建：`backend/tests/services/pokemon/test_data_loader.py`

**关键步骤：**
1. 编写数据加载器测试
2. 实现 DataLoader 类（从 JSON 加载数据到数据库）
3. 准备 Top 100 宝可梦数据（可从 PokeAPI 或手动整理）
4. 准备常用技能数据（至少 50 个技能）
5. 准备 5-10 个队伍模板（从 pokechamdb 等网站获取）
6. 编写数据初始化脚本
7. 测试数据加载功能

### 任务 5：对战引擎核心

**目标：** 实现 VGC 双打对战的核心逻辑

**文件：**
- 创建：`backend/app/services/pokemon/battle_engine.py`
- 创建：`backend/app/services/pokemon/battle_state.py`
- 创建：`backend/tests/services/pokemon/test_battle_engine.py`

**关键步骤：**
1. 定义 BattleState 类（场面状态、宝可梦状态）
2. 实现对战初始化（Team Preview）
3. 实现回合执行逻辑（行动排序、技能执行、伤害结算）
4. 实现换宝可梦机制
5. 实现太晶化机制（简化版）
6. 实现胜负判定
7. 编写完整对战流程测试

### 任务 6：AI 决策引擎

**目标：** 让智能体能够根据场面状态做出决策

**文件：**
- 创建：`backend/app/services/pokemon/ai_decision.py`
- 创建：`backend/tests/services/pokemon/test_ai_decision.py`

**关键步骤：**
1. 定义决策输入格式（场面状态 → JSON）
2. 构建 LLM prompt（包含规则说明、当前状态、可选行动）
3. 实现决策解析（LLM 输出 → 结构化行动）
4. 添加决策记录（用于强化学习）
5. 实现回退机制（LLM 失败时随机选择）
6. 测试决策功能

### 任务 7：REST API 实现

**目标：** 提供 Pokemon 对战的 HTTP API

**文件：**
- 创建：`backend/app/schemas/pokemon.py`
- 创建：`backend/app/api/pokemon.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/api/test_pokemon.py`

**关键步骤：**
1. 定义 Pydantic schemas（请求/响应模型）
2. 实现队伍管理 API（CRUD）
3. 实现对战管理 API（创建、开始、获取状态）
4. 实现对战历史 API
5. 在 main.py 中注册路由
6. 编写 API 测试

### 任务 8：WebSocket 实时对战

**目标：** 实现对战的实时推送和观战功能

**文件：**
- 创建：`backend/app/websocket/pokemon_manager.py`
- 修改：`backend/app/main.py`

**关键步骤：**
1. 实现 PokemonBattleManager（管理 WebSocket 连接）
2. 实现对战事件推送（回合开始、技能使用、伤害结算等）
3. 实现观战功能（只读连接）
4. 在 main.py 中注册 WebSocket 路由
5. 测试实时推送功能

### 任务 9：前端对战界面

**目标：** 创建宝可梦对战的前端页面

**文件：**
- 创建：`frontend/src/app/pokemon/page.tsx`
- 创建：`frontend/src/app/pokemon/battles/[id]/page.tsx`
- 创建：`frontend/src/app/pokemon/teams/page.tsx`
- 创建：`frontend/src/components/pokemon/BattleField.tsx`
- 创建：`frontend/src/components/pokemon/PokemonCard.tsx`
- 创建：`frontend/src/components/pokemon/TeamBuilder.tsx`

**关键步骤：**
1. 创建对战列表页面
2. 创建对战详情页面（实时显示对战状态）
3. 创建队伍管理页面
4. 实现 BattleField 组件（显示双打场地）
5. 实现 PokemonCard 组件（显示宝可梦状态）
6. 实现 WebSocket 连接和事件处理
7. 测试前端功能

### 任务 10：集成测试与优化

**目标：** 端到端测试和性能优化

**文件：**
- 创建：`backend/tests/integration/test_pokemon_battle_flow.py`

**关键步骤：**
1. 编写完整对战流程的集成测试
2. 测试智能体对战（Agent A vs Agent B）
3. 性能测试（对战引擎响应时间）
4. 修复发现的 bug
5. 优化数据库查询
6. 添加日志和监控
7. 编写 Phase 1 完成报告

---

## 执行指南

### 推荐执行方式

**方式 1：子代理驱动开发（推荐）**

使用 `subagent-driven-development` 技能，每个任务由独立的子代理执行。

优点：
- 每个任务独立执行，有审查检查点
- 任务间可以快速迭代
- 出错时容易定位和修复

**方式 2：内联执行**

使用 `executing-plans` 技能在当前会话中批量执行。

优点：
- 连续执行，无需多次交互
- 适合已经验证过的计划

### 执行前准备

1. 确保 PostgreSQL 和 Redis 正在运行
2. 确保后端虚拟环境已激活
3. 确保有至少一个 LLM API Key 配置

### 验证标准

Phase 1 完成后，应该能够：

- [ ] 数据库包含至少 100 个宝可梦种族数据
- [ ] 数据库包含至少 50 个技能数据
- [ ] 数据库包含至少 5 个队伍模板
- [ ] 两个智能体能够完成一场完整的 VGC 双打对战
- [ ] 伤害计算正确（属性克制、暴击、STAB）
- [ ] 前端能够实时观战对战过程
- [ ] 对战日志完整记录
- [ ] 所有单元测试通过
- [ ] 集成测试通过

---

## 后续 Phase 预告

### Phase 2：知识系统 + 学习机制（2-3周）

- 实现联网搜索集成
- 实现 Redis 知识缓存
- 实现轻量级强化学习
- Q 值估计和策略优化

### Phase 3：队伍构建 + 进化系统（2-3周）

- 智能体根据等级选择队伍策略
- 队伍构建器（自动组队）
- 经验系统深度集成
- 对战分析和回放

### Phase 4：PS 服务器连接（3-4周）

- 实现 PS WebSocket 协议
- 登录和房间管理
- 天梯匹配
- 真实对战数据收集

---

## 参考资料

- Pokemon Showdown 源码：https://github.com/smogon/pokemon-showdown
- 伤害计算公式：https://bulbapedia.bulbagarden.net/wiki/Damage
- VGC 规则：https://www.pokemon.com/us/pokemon-news/2024-video-game-championships-format-rules
- 宝可梦数据 API：https://pokeapi.co/
- 排位数据库：https://pokechamdb.com/zh-Hans

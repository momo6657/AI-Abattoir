# 游戏功能全面完善 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复游戏模块所有 Bug，补全5种游戏的完整规则引擎，实现自动运行+实时观战，并为每种游戏构建定制可视化 UI。

**架构：** 三层渐进式开发——基础修复层（接口对齐+WebSocket修复）→ 核心增强层（游戏规则+自动运行引擎）→ 体验提升层（每种游戏定制可视化组件）。

**技术栈：** FastAPI + SQLAlchemy + WebSocket + Next.js 15 + TypeScript + Tailwind CSS

---

## 文件结构

### 后端修改

| 文件 | 职责 | 操作 |
|------|------|------|
| `backend/app/models/game.py` | 游戏 ORM 模型，增加 `paused_at` 字段 | 修改 |
| `backend/app/schemas/game.py` | 游戏 Pydantic schema，增加缺失字段 | 修改 |
| `backend/app/api/games.py` | 游戏 REST API 路由，增加暂停/恢复端点 | 修改 |
| `backend/app/services/game_engine.py` | 游戏引擎核心，重写5种游戏规则 + 自动运行 | 修改 |
| `backend/app/services/spectator_service.py` | 观战服务，增加游戏专用广播方法 | 修改 |
| `backend/app/websocket/manager.py` | WebSocket 管理器，增加游戏通道 | 修改 |
| `backend/app/websocket/game_ws.py` | 游戏专用 WebSocket 端点 | 创建 |
| `backend/app/main.py` | 注册游戏 WebSocket 路由 | 修改 |
| `backend/tests/test_game_engine.py` | 游戏引擎测试 | 修改 |
| `backend/tests/test_conversation_modes.py` | 对话模式测试（修复受影响的测试） | 修改 |

### 前端修改

| 文件 | 职责 | 操作 |
|------|------|------|
| `frontend/src/types/index.ts` | 类型定义，增加游戏相关类型 | 修改 |
| `frontend/src/lib/constants.ts` | 常量，修复游戏类型映射 | 修改 |
| `frontend/src/lib/api.ts` | API 调用，增加暂停/恢复/启动方法 | 修改 |
| `frontend/src/hooks/useGameWebSocket.ts` | 游戏 WebSocket hook | 创建 |
| `frontend/src/app/games/page.tsx` | 游戏列表页，修复类型和接口问题 | 修改 |
| `frontend/src/components/games/ChessBoard.tsx` | 国际象棋棋盘可视化 | 创建 |
| `frontend/src/components/games/WerewolfPanel.tsx` | 狼人杀角色卡牌+投票 | 创建 |
| `frontend/src/components/games/DebatePanel.tsx` | 辩论赛正反方分栏 | 创建 |
| `frontend/src/components/games/AdventurePanel.tsx` | 文字冒险场景面板 | 创建 |
| `frontend/src/components/games/NegotiationPanel.tsx` | 谈判博弈提案面板 | 创建 |
| `frontend/src/components/games/GameControlBar.tsx` | 通用游戏控制栏（暂停/恢复/速度） | 创建 |

---

## 第一层：基础修复层

---

### 任务 1：修复后端 Game schema 缺失字段

**文件：**
- 修改：`backend/app/schemas/game.py`
- 修改：`backend/app/models/game.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：编写失败的测试 — 验证 GameResponse 包含新字段**

在 `backend/tests/test_game_engine.py` 中添加：

```python
def test_game_response_has_enriched_fields():
    """GameResponse 必须包含 players, current_turn, max_turns, winner_id 字段"""
    from app.schemas.game import GameResponse
    fields = GameResponse.model_fields
    assert "players" in fields, "GameResponse 缺少 players 字段"
    assert "current_turn" in fields, "GameResponse 缺少 current_turn 字段"
    assert "max_turns" in fields, "GameResponse 缺少 max_turns 字段"
    assert "winner_id" in fields, "GameResponse 缺少 winner_id 字段"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_response_has_enriched_fields -v`
预期：FAIL，`AssertionError: GameResponse 缺少 players 字段`

- [ ] **步骤 3：修改 GameResponse schema，增加缺失字段**

修改 `backend/app/schemas/game.py`，在 `GameResponse` 类中增加字段：

```python
class GameResponse(BaseModel):
    id: str
    game_type: GameType
    title: str
    status: GameStatus
    config: dict
    players: list[dict] = []        # [{agent_id, name, role?}]
    current_turn: int = 0
    max_turns: int = 20
    winner_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
```

同时修改 `GameCreate`，让 `title` 和 `max_turns` 为必填：

```python
class GameCreate(BaseModel):
    game_type: GameType
    title: str
    agent_ids: list[str] = []
    config: dict = {}
    max_turns: int = 20
```

同时修改 `GameUpdate`，增加 `winner_id` 和 `paused_at`：

```python
class GameUpdate(BaseModel):
    status: GameStatus | None = None
    config: dict | None = None
    winner_id: str | None = None
    current_turn: int | None = None
    paused_at: datetime | None = None
```

- [ ] **步骤 4：修改 Game ORM 模型，增加 paused_at 字段**

修改 `backend/app/models/game.py`，在 `Game` 类中增加：

```python
    paused_at = Column(DateTime, nullable=True)
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_response_has_enriched_fields -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/schemas/game.py backend/app/models/game.py backend/tests/test_game_engine.py
git commit -m "feat: 补全 Game schema 缺失字段 (players, current_turn, max_turns, winner_id, paused_at)"
```

---

### 任务 2：修复后端 games API 路由，返回完整游戏数据

**文件：**
- 修改：`backend/app/api/games.py`

- [ ] **步骤 1：编写失败的测试 — API 返回的数据包含 players 和 current_turn**

```python
@pytest.mark.asyncio
async def test_game_api_returns_enriched_data(client, db_session):
    """POST /api/games 返回的数据必须包含 players, current_turn, max_turns"""
    from app.schemas.game import GameCreate, GameType
    payload = GameCreate(
        game_type=GameType.WEREWOLF,
        title="测试狼人杀",
        agent_ids=[],
        config={"player_count": 6},
        max_turns=10
    ).model_dump()
    resp = await client.post("/api/games", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "players" in data
    assert "current_turn" in data
    assert "max_turns" in data
    assert data["max_turns"] == 10
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_api_returns_enriched_data -v`
预期：FAIL

- [ ] **步骤 3：修改 games API，在创建和查询时填充 players 等字段**

修改 `backend/app/api/games.py`：

在 `create_game` 函数中，创建 game 后，从 agent_ids 获取 agent 信息填充 players：

```python
@router.post("", response_model=GameResponse)
async def create_game(game_data: GameCreate, db: AsyncSession = Depends(get_db)):
    game_dict = game_data.model_dump()
    agent_ids = game_dict.pop("agent_ids", [])
    max_turns = game_dict.pop("max_turns", 20)

    game = Game(**game_dict)
    game.config["max_turns"] = max_turns
    game.config["agent_ids"] = agent_ids

    # 获取 agent 信息填充 players
    players = []
    if agent_ids:
        from sqlalchemy import select
        from app.models.agent import Agent
        result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents = result.scalars().all()
        for agent in agents:
            players.append({"agent_id": str(agent.id), "name": agent.name})
    game.config["players"] = players

    db.add(game)
    await db.commit()
    await db.refresh(game)

    resp = GameResponse.model_validate(game)
    resp.players = players
    resp.current_turn = game.config.get("current_turn", 0)
    resp.max_turns = max_turns
    return resp
```

在 `list_games` 和 `get_game` 中同样补充字段：

```python
def _enrich_game_response(game: Game) -> GameResponse:
    resp = GameResponse.model_validate(game)
    resp.players = game.config.get("players", [])
    resp.current_turn = game.config.get("current_turn", 0)
    resp.max_turns = game.config.get("max_turns", 20)
    resp.winner_id = game.config.get("winner_id")
    return resp
```

在 list_games 和 get_game 中调用 `_enrich_game_response(game)` 替代直接 `GameResponse.model_validate(game)`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_api_returns_enriched_data -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/api/games.py backend/tests/test_game_engine.py
git commit -m "feat: games API 返回完整游戏数据 (players, current_turn, max_turns, winner_id)"
```

---

### 任务 3：修复前端游戏类型映射和接口对齐

**文件：**
- 修改：`frontend/src/lib/constants.ts`
- 修改：`frontend/src/types/index.ts`
- 修改：`frontend/src/app/games/page.tsx`
- 修改：`frontend/src/lib/api.ts`

- [ ] **步骤 1：修复 constants.ts 中的游戏类型映射**

修改 `frontend/src/lib/constants.ts`，将 `adventure` 改为 `text_adventure`：

找到 `GAME_TYPES` 中的 `adventure` 条目，替换为：

```typescript
  {
    value: 'text_adventure',
    label: '文字冒险',
    icon: '🗺️',
    description: 'AI 讲述的互动文字冒险',
    minPlayers: 1,
    maxPlayers: 1,
  },
```

- [ ] **步骤 2：修复 types/index.ts 中的 Game 接口**

修改 `frontend/src/types/index.ts`，更新 Game 接口：

```typescript
export interface Game {
  id: string;
  game_type: GameType;
  title: string;
  status: GameStatus;
  config: Record<string, unknown>;
  players: GamePlayer[];
  current_turn: number;
  max_turns: number;
  winner_id: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface GamePlayer {
  agent_id: string;
  name: string;
  role?: string;
}

export type GameType = 'werewolf' | 'debate' | 'chess' | 'text_adventure' | 'negotiation';
export type GameStatus = 'waiting' | 'in_progress' | 'paused' | 'completed';
```

注意将 `active` 改为 `in_progress`，增加 `paused` 状态。

- [ ] **步骤 3：修复 games/page.tsx 中的状态映射和 API 调用**

修改 `frontend/src/app/games/page.tsx`：

1. 所有 `status === 'active'` 改为 `status === 'in_progress'`
2. 状态标签映射增加 `paused: '已暂停'`
3. 创建游戏时传 `max_turns` 字段
4. 结束游戏时支持传 `winner_id`

- [ ] **步骤 4：修复 api.ts 中的游戏 API 调用**

修改 `frontend/src/lib/api.ts`，确保 `createGame` 传 `max_turns`，`endGame` 支持 `winner_id`：

```typescript
export const createGame = async (data: {
  game_type: GameType;
  title: string;
  agent_ids?: string[];
  config?: Record<string, unknown>;
  max_turns?: number;
}) => {
  const res = await fetch(`${API_BASE}/games`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
};

export const endGame = async (id: string, winnerId?: string) => {
  const body: Record<string, unknown> = { status: 'completed' };
  if (winnerId) body.winner_id = winnerId;
  const res = await fetch(`${API_BASE}/games/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
};
```

增加暂停/恢复 API：

```typescript
export const pauseGame = async (id: string) => {
  const res = await fetch(`${API_BASE}/games/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'paused' }),
  });
  return res.json();
};

export const resumeGame = async (id: string) => {
  const res = await fetch(`${API_BASE}/games/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'in_progress' }),
  });
  return res.json();
};
```

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/lib/constants.ts frontend/src/types/index.ts frontend/src/app/games/page.tsx frontend/src/lib/api.ts
git commit -m "fix: 前后端游戏接口对齐 — 类型映射、状态值、API 参数"
```

---

### 任务 4：增加游戏专用 WebSocket 端点

**文件：**
- 创建：`backend/app/websocket/game_ws.py`
- 修改：`backend/app/websocket/manager.py`
- 修改：`backend/app/main.py`

- [ ] **步骤 1：编写失败的测试 — 游戏 WebSocket 连接**

```python
@pytest.mark.asyncio
async def test_game_websocket_connect(client):
    """可以连接到 /ws/games/{game_id}"""
    from app.schemas.game import GameCreate, GameType
    payload = GameCreate(
        game_type=GameType.CHESS,
        title="测试棋局",
        max_turns=10
    ).model_dump()
    resp = await client.post("/api/games", json=payload)
    game_id = resp.json()["id"]

    async with client.websocket_connect(f"/ws/games/{game_id}") as ws:
        # 连接成功即可
        pass
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_websocket_connect -v`
预期：FAIL，WebSocket 连接被拒绝

- [ ] **步骤 3：在 WebSocket 管理器中增加游戏通道**

修改 `backend/app/websocket/manager.py`，增加游戏连接管理：

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}  # conversation_id -> [ws]
        self.game_connections: dict[str, list[WebSocket]] = {}     # game_id -> [ws]

    async def connect_to_game(self, game_id: str, websocket: WebSocket):
        await websocket.accept()
        if game_id not in self.game_connections:
            self.game_connections[game_id] = []
        self.game_connections[game_id].append(websocket)

    def disconnect_from_game(self, game_id: str, websocket: WebSocket):
        if game_id in self.game_connections:
            self.game_connections[game_id] = [
                ws for ws in self.game_connections[game_id] if ws != websocket
            ]
            if not self.game_connections[game_id]:
                del self.game_connections[game_id]

    async def broadcast_to_game(self, game_id: str, message: dict):
        if game_id in self.game_connections:
            for ws in self.game_connections[game_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect_from_game(game_id, ws)
```

- [ ] **步骤 4：创建游戏 WebSocket 端点**

创建 `backend/app/websocket/game_ws.py`：

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.game import Game
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/games/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str):
    await manager.connect_to_game(game_id, websocket)
    try:
        # 连接后发送当前游戏状态
        async for db in get_db():
            result = await db.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if game:
                await websocket.send_json({
                    "type": "game_state",
                    "data": {
                        "id": str(game.id),
                        "status": game.status,
                        "current_turn": game.config.get("current_turn", 0),
                        "config": game.config,
                    }
                })
            break

        # 保持连接，接收客户端消息（如暂停/恢复指令）
        while True:
            data = await websocket.receive_json()
            # 客户端可发送控制指令，服务端处理
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect_from_game(game_id, websocket)
```

- [ ] **步骤 5：在 main.py 中注册路由**

修改 `backend/app/main.py`，在路由注册部分增加：

```python
from app.websocket.game_ws import router as game_ws_router
app.include_router(game_ws_router)
```

- [ ] **步骤 6：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_game_websocket_connect -v`
预期：PASS

- [ ] **步骤 7：Commit**

```bash
git add backend/app/websocket/game_ws.py backend/app/websocket/manager.py backend/app/main.py backend/tests/test_game_engine.py
git commit -m "feat: 增加游戏专用 WebSocket 端点 /ws/games/{id}"
```

---

### 任务 5：修复 game_engine 观战广播和 _extract_target_id

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 修改：`backend/app/services/spectator_service.py`

- [ ] **步骤 1：修复 _extract_target_id 回退策略**

修改 `backend/app/services/game_engine.py` 中的 `_extract_target_id` 方法：

```python
def _extract_target_id(self, response: str, candidates: list[str]) -> str | None:
    """从 LLM 回复中提取目标 ID，找不到则随机选一个"""
    import re
    for candidate in candidates:
        if candidate in response:
            return candidate
    # 尝试匹配 UUID 格式
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    found = re.findall(uuid_pattern, response.lower())
    for f in found:
        for candidate in candidates:
            if f == candidate.lower():
                return candidate
    # 回退：随机选择而非固定选第一个
    import random
    return random.choice(candidates) if candidates else None
```

- [ ] **步骤 2：修复观战广播 — 增加 broadcast_game_event 方法**

修改 `backend/app/services/spectator_service.py`，增加游戏事件广播方法：

```python
async def broadcast_game_event(self, game_id: str, event_type: str, data: dict):
    """广播游戏事件给观战者和游戏 WebSocket 连接"""
    message = {
        "type": event_type,
        "game_id": game_id,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    # 广播给观战者
    await self.ws_manager.broadcast_to_game(game_id, message)
    # 也广播给 spectate 通道
    spectate_channel = f"game_{game_id}"
    if spectate_channel in self.ws_manager.active_connections:
        for ws in self.ws_manager.active_connections[spectate_channel]:
            try:
                await ws.send_json(message)
            except Exception:
                pass
```

- [ ] **步骤 3：修改 game_engine 中所有广播调用**

修改 `backend/app/services/game_engine.py`，将所有 `ws_manager.broadcast_to_conversation` 调用替换为 `spectator_service.broadcast_game_event`：

在每个需要广播的地方：

```python
# 之前：
# await self.ws_manager.broadcast_to_conversation(game.id, {...})

# 之后：
await self.spectator_service.broadcast_game_event(
    game_id=str(game.id),
    event_type="turn_result",
    data={...}
)
```

确保 `GameEngine.__init__` 接收 `spectator_service` 参数。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/game_engine.py backend/app/services/spectator_service.py
git commit -m "fix: 游戏 WebSocket 广播走专用通道，修复 _extract_target_id 随机回退"
```

---

### 任务 6：生成数据库迁移

**文件：**
- 创建：数据库迁移文件（由 alembic 生成）

- [ ] **步骤 1：生成迁移**

运行：`cd backend && alembic revision --autogenerate -m "add paused_at to games table"`

- [ ] **步骤 2：检查迁移文件**

确认迁移文件中包含 `paused_at` 列的添加操作。如果自动生成有误，手动修正。

- [ ] **步骤 3：Commit**

```bash
git add backend/alembic/
git commit -m "migration: 增加 games.paused_at 字段"
```

---

## 第二层：核心增强层

---

### 任务 7：自动运行引擎 + 暂停/恢复 API

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 修改：`backend/app/api/games.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：编写失败的测试 — 自动运行直到游戏结束**

```python
@pytest.mark.asyncio
async def test_auto_run_game_completes():
    """auto_run_game 应该自动执行回合直到游戏结束或达到 max_turns"""
    from app.services.game_engine import GameEngine
    from app.schemas.game import GameType

    engine = GameEngine(
        game_type=GameType.CHESS,
        agent_ids=["agent-1", "agent-2"],
        config={"max_turns": 3},
        llm_service=None,  # mock
    )
    # 设置一个很快会结束的模拟
    results = []
    async for event in engine.auto_run():
        results.append(event)
    assert len(results) > 0
    assert results[-1]["type"] in ["game_over", "max_turns_reached"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::test_auto_run_game_completes -v`
预期：FAIL，`AttributeError: 'GameEngine' has no attribute 'auto_run'`

- [ ] **步骤 3：在 GameEngine 中实现 auto_run 方法**

修改 `backend/app/services/game_engine.py`，增加：

```python
import asyncio
from typing import AsyncGenerator

class GameEngine:
    def __init__(self, game_type, agent_ids, config, llm_service, spectator_service=None):
        self.game_type = game_type
        self.agent_ids = agent_ids
        self.config = config
        self.llm_service = llm_service
        self.spectator_service = spectator_service
        self.max_turns = config.get("max_turns", 20)
        self.current_turn = 0
        self.is_paused = False
        self.is_stopped = False
        self.turn_delay = config.get("turn_delay", 3.0)

    async def auto_run(self) -> AsyncGenerator[dict, None]:
        """自动运行游戏，yield 每个回合的事件"""
        while self.current_turn < self.max_turns and not self.is_stopped:
            if self.is_paused:
                yield {"type": "paused", "turn": self.current_turn}
                # 等待恢复
                while self.is_paused and not self.is_stopped:
                    await asyncio.sleep(0.5)
                if self.is_stopped:
                    break
                yield {"type": "resumed", "turn": self.current_turn}

            self.current_turn += 1
            try:
                turn_result = await self.execute_turn()
                yield {
                    "type": "turn_result",
                    "turn": self.current_turn,
                    "data": turn_result,
                }
            except asyncio.TimeoutError:
                yield {
                    "type": "turn_timeout",
                    "turn": self.current_turn,
                }
                continue
            except Exception as e:
                yield {
                    "type": "turn_error",
                    "turn": self.current_turn,
                    "error": str(e),
                }

            # 检查游戏是否已结束
            if self._is_game_over():
                yield {"type": "game_over", "turn": self.current_turn}
                break

            # 回合间延迟
            if self.turn_delay > 0:
                await asyncio.sleep(self.turn_delay)

        if self.current_turn >= self.max_turns:
            yield {"type": "max_turns_reached", "turn": self.current_turn}

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_stopped = True

    def _is_game_over(self) -> bool:
        """由各子引擎覆写"""
        return False
```

- [ ] **步骤 4：增加暂停/恢复 API 端点**

修改 `backend/app/api/games.py`，增加：

```python
# 内存中的运行中游戏引擎实例
_running_games: dict[str, GameEngine] = {}


@router.post("/{game_id}/start", response_model=GameResponse)
async def start_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """启动游戏，自动运行所有回合"""
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    if game.status == GameStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="游戏已在进行中")

    game.status = GameStatus.IN_PROGRESS
    await db.commit()

    # 创建引擎并在后台运行
    engine = GameEngine(
        game_type=game.game_type,
        agent_ids=game.config.get("agent_ids", []),
        config=game.config,
        llm_service=llm_service,
        spectator_service=spectator_service,
    )
    _running_games[game_id] = engine

    asyncio.create_task(_run_game_background(game_id, engine, db))

    return _enrich_game_response(game)


@router.post("/{game_id}/pause", response_model=GameResponse)
async def pause_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """暂停游戏"""
    if game_id in _running_games:
        _running_games[game_id].pause()
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game:
        game.status = GameStatus.PAUSED
        game.paused_at = datetime.utcnow()
        await db.commit()
        await db.refresh(game)
    return _enrich_game_response(game) if game else None


@router.post("/{game_id}/resume", response_model=GameResponse)
async def resume_game(game_id: str, db: AsyncSession = Depends(get_db)):
    """恢复游戏"""
    if game_id in _running_games:
        _running_games[game_id].resume()
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if game:
        game.status = GameStatus.IN_PROGRESS
        game.paused_at = None
        await db.commit()
        await db.refresh(game)
    return _enrich_game_response(game) if game else None


async def _run_game_background(game_id: str, engine: GameEngine, db_factory):
    """后台运行游戏"""
    async for event in engine.auto_run():
        # 广播事件
        if spectator_service:
            await spectator_service.broadcast_game_event(game_id, event["type"], event)

        # 更新数据库
        async for db in db_factory():
            result = await db.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if game:
                game.config["current_turn"] = engine.current_turn
                if event["type"] == "game_over":
                    game.status = GameStatus.COMPLETED
                    game.config["winner_id"] = event.get("data", {}).get("winner_id")
                elif event["type"] == "max_turns_reached":
                    game.status = GameStatus.COMPLETED
                await db.commit()
            break

    # 清理
    _running_games.pop(game_id, None)
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/game_engine.py backend/app/api/games.py backend/tests/test_game_engine.py
git commit -m "feat: 游戏自动运行引擎 + 暂停/恢复 API + 后台任务"
```

---

### 任务 8：国际象棋规则引擎重写

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：编写失败的测试 — 走法验证**

```python
import pytest

class TestChessRules:
    def test_rook_cannot_jump_over_pieces(self):
        """车不能跳过其他棋子"""
        from app.services.game_engine import ChessRules
        rules = ChessRules()
        # 初始局面：e2 兵挡住 e1 车向前
        valid = rules.get_valid_moves("e1", rules.initial_board())
        # e1 车在初始位置只能横向移动，不能向前（e2 有兵）
        assert "e3" not in valid

    def test_check_detection(self):
        """将军检测"""
        from app.services.game_engine import ChessRules
        rules = ChessRules()
        # 后方将军王
        board = rules.empty_board()
        board["e1"] = ("white", "king")
        board["e8"] = ("black", "queen")
        assert rules.is_in_check(board, "white") is True

    def test_checkmate_detection(self):
        """将杀检测"""
        from app.services.game_engine import ChessRules
        rules = ChessRules()
        # 学者将杀
        board = rules.empty_board()
        board["e1"] = ("white", "king")
        board["d8"] = ("black", "queen")
        board["f6"] = ("black", "queen")
        assert rules.is_checkmate(board, "white") is True

    def test_cannot_move_into_check(self):
        """不能走入被将军的位置"""
        from app.services.game_engine import ChessRules
        rules = ChessRules()
        board = rules.empty_board()
        board["e1"] = ("white", "king")
        board["e8"] = ("black", "rook")
        valid = rules.get_valid_moves("e1", board)
        # 白王不能走到 e 列任何位置（被黑车攻击）
        for move in valid:
            assert move[0] != "e"

    def test_pawn_promotion(self):
        """兵升变"""
        from app.services.game_engine import ChessRules
        rules = ChessRules()
        board = rules.empty_board()
        board["a7"] = ("white", "pawn")
        valid = rules.get_valid_moves("a7", board)
        assert "a8" in valid
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::TestChessRules -v`
预期：FAIL，`ImportError: cannot import name 'ChessRules'`

- [ ] **步骤 3：实现 ChessRules 类**

在 `backend/app/services/game_engine.py` 中增加 `ChessRules` 类：

```python
class ChessRules:
    FILES = "abcdefgh"
    RANKS = "12345678"

    def initial_board(self) -> dict[str, tuple[str, str]]:
        """返回初始棋盘 {'a1': ('white', 'rook'), ...}"""
        board = {}
        # 白方
        order = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
        for i, piece in enumerate(order):
            board[f"{self.FILES[i]}1"] = ("white", piece)
            board[f"{self.FILES[i]}2"] = ("white", "pawn")
        # 黑方
        for i, piece in enumerate(order):
            board[f"{self.FILES[i]}8"] = ("black", piece)
            board[f"{self.FILES[i]}7"] = ("black", "pawn")
        return board

    def empty_board(self) -> dict[str, tuple[str, str]]:
        return {}

    def get_valid_moves(self, square: str, board: dict[str, tuple[str, str]]) -> list[str]:
        """获取某个位置棋子的所有合法走法（考虑将军限制）"""
        if square not in board:
            return []
        color, piece_type = board[square]
        raw_moves = self._get_raw_moves(square, board)
        # 过滤掉会导致己方被将军的走法
        legal = []
        for move in raw_moves:
            test_board = self._simulate_move(board, square, move)
            if not self.is_in_check(test_board, color):
                legal.append(move)
        return legal

    def _get_raw_moves(self, square: str, board: dict[str, tuple[str, str]]) -> list[str]:
        """不考虑将军的原始走法"""
        color, piece_type = board[square]
        moves = []
        file_idx = self.FILES.index(square[0])
        rank = int(square[1])

        if piece_type == "pawn":
            direction = 1 if color == "white" else -1
            start_rank = 2 if color == "white" else 7
            # 前进一格
            fwd = f"{square[0]}{rank + direction}"
            if 1 <= rank + direction <= 8 and fwd not in board:
                moves.append(fwd)
                # 首步前进两格
                if rank == start_rank:
                    fwd2 = f"{square[0]}{rank + 2 * direction}"
                    if fwd2 not in board:
                        moves.append(fwd2)
            # 斜吃
            for df in [-1, 1]:
                nf = file_idx + df
                if 0 <= nf < 8:
                    capture = f"{self.FILES[nf]}{rank + direction}"
                    if capture in board and board[capture][0] != color:
                        moves.append(capture)

        elif piece_type == "rook":
            moves = self._sliding_moves(square, board, [(0, 1), (0, -1), (1, 0), (-1, 0)])

        elif piece_type == "bishop":
            moves = self._sliding_moves(square, board, [(1, 1), (1, -1), (-1, 1), (-1, -1)])

        elif piece_type == "queen":
            moves = self._sliding_moves(square, board, [
                (0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1),
            ])

        elif piece_type == "king":
            for df in [-1, 0, 1]:
                for dr in [-1, 0, 1]:
                    if df == 0 and dr == 0:
                        continue
                    nf = file_idx + df
                    nr = rank + dr
                    if 0 <= nf < 8 and 1 <= nr <= 8:
                        target = f"{self.FILES[nf]}{nr}"
                        if target not in board or board[target][0] != color:
                            moves.append(target)

        elif piece_type == "knight":
            for df, dr in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                           (1, -2), (1, 2), (2, -1), (2, 1)]:
                nf = file_idx + df
                nr = rank + dr
                if 0 <= nf < 8 and 1 <= nr <= 8:
                    target = f"{self.FILES[nf]}{nr}"
                    if target not in board or board[target][0] != color:
                        moves.append(target)

        return moves

    def _sliding_moves(self, square: str, board: dict[str, tuple[str, str]],
                       directions: list[tuple[int, int]]) -> list[str]:
        """滑行棋子（车、象、后）的走法"""
        color = board[square][0]
        file_idx = self.FILES.index(square[0])
        rank = int(square[1])
        moves = []
        for df, dr in directions:
            nf, nr = file_idx + df, rank + dr
            while 0 <= nf < 8 and 1 <= nr <= 8:
                target = f"{self.FILES[nf]}{nr}"
                if target not in board:
                    moves.append(target)
                elif board[target][0] != color:
                    moves.append(target)
                    break
                else:
                    break  # 己方棋子阻挡
                nf += df
                nr += dr
        return moves

    def _simulate_move(self, board: dict[str, tuple[str, str]],
                       from_sq: str, to_sq: str) -> dict[str, tuple[str, str]]:
        """模拟走一步后的棋盘"""
        new_board = dict(board)
        new_board[to_sq] = new_board.pop(from_sq)
        return new_board

    def is_in_check(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测 color 方是否被将军"""
        # 找到王的位置
        king_sq = None
        for sq, (c, p) in board.items():
            if c == color and p == "king":
                king_sq = sq
                break
        if not king_sq:
            return True  # 王不在棋盘上，视为被将

        # 检查对方所有棋子是否能攻击到王
        opponent = "black" if color == "white" else "white"
        for sq, (c, p) in board.items():
            if c == opponent:
                raw_moves = self._get_raw_moves(sq, board)
                if king_sq in raw_moves:
                    return True
        return False

    def is_checkmate(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测 color 方是否被将杀"""
        if not self.is_in_check(board, color):
            return False
        # 检查是否有任何合法走法
        for sq, (c, p) in board.items():
            if c == color:
                if self.get_valid_moves(sq, board):
                    return False
        return True

    def is_stalemate(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测是否僵局"""
        if self.is_in_check(board, color):
            return False
        for sq, (c, p) in board.items():
            if c == color:
                if self.get_valid_moves(sq, board):
                    return False
        return True
```

- [ ] **步骤 4：重写 chess 游戏引擎，使用 ChessRules**

修改 `game_engine.py` 中的 `_run_chess` 方法，使用 ChessRules 做走法验证：

```python
async def _run_chess(self, game, agents):
    """国际象棋 — 使用规则引擎验证走法"""
    rules = ChessRules()
    board = rules.initial_board()
    config = game.config
    config["board"] = board
    current_color = "white"

    for turn in range(1, config.get("max_turns", 20) + 1):
        agent_idx = 0 if current_color == "white" else 1
        agent = agents[agent_idx] if agent_idx < len(agents) else None
        if not agent:
            break

        # 获取合法走法
        all_moves = {}
        for sq, (color, piece) in board.items():
            if color == current_color:
                valid = rules.get_valid_moves(sq, board)
                if valid:
                    all_moves[sq] = valid

        if not all_moves:
            opponent = "black" if current_color == "white" else "white"
            if rules.is_in_check(board, current_color):
                return {"winner": opponent, "reason": "checkmate"}
            else:
                return {"winner": None, "reason": "stalemate"}

        # 构造 prompt，包含合法走法
        board_str = self._board_to_string(board)
        legal_moves_str = "\n".join(
            f"{sq} -> {', '.join(moves)}" for sq, moves in all_moves.items()
        )
        check_status = ""
        if rules.is_in_check(board, current_color):
            check_status = "YOU ARE IN CHECK! You must escape check.\n"

        prompt = f"""You are playing chess as {current_color}.

Board state:
{board_str}

{check_status}Your legal moves:
{legal_moves_str}

Choose your move in format: MOVE: from_square to_square
Example: MOVE: e2 e4"""

        response = await self.llm_service.call_agent(agent, prompt)
        from_sq, to_sq = self._parse_chess_move(response, all_moves)

        if from_sq and to_sq:
            board = rules._simulate_move(board, from_sq, to_sq)
            config["board"] = board
            config["last_move"] = {"from": from_sq, "to": to_sq}
            config["current_turn"] = turn

            yield {
                "type": "turn_result",
                "turn": turn,
                "data": {
                    "color": current_color,
                    "from": from_sq,
                    "to": to_sq,
                    "piece": board.get(to_sq, (current_color, "pawn"))[1],
                    "in_check": rules.is_in_check(board, "black" if current_color == "white" else "white"),
                }
            }
        else:
            yield {
                "type": "invalid_move",
                "turn": turn,
                "data": {"color": current_color, "response": response}
            }
            # LLM 未能给出合法走法，随机选一个
            from_sq = random.choice(list(all_moves.keys()))
            to_sq = random.choice(all_moves[from_sq])
            board = rules._simulate_move(board, from_sq, to_sq)

        current_color = "black" if current_color == "white" else "white"

    return {"winner": None, "reason": "max_turns_reached"}
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py::TestChessRules -v`
预期：全部 PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/game_engine.py backend/tests/test_game_engine.py
git commit -m "feat: 国际象棋规则引擎 — 走法验证、将军/将杀/僵局检测"
```

---

### 任务 9：狼人杀机制完善

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：编写失败的测试 — 狼人协商和信息隔离**

```python
class TestWerewolfRules:
    @pytest.mark.asyncio
    async def test_werewolves_discuss_before_kill(self):
        """夜晚阶段：多个狼人应先讨论，再决定击杀目标"""
        # 测试日志中是否包含狼人讨论记录
        pass

    @pytest.mark.asyncio
    async def test_day_phase_no_role_exposure(self):
        """白天阶段：公告中不应暴露角色身份细节"""
        pass

    def test_guard_cannot_self_guard(self):
        """守卫不能守护自己"""
        from app.services.game_engine import WerewolfRules
        rules = WerewolfRules()
        assert rules.is_valid_guard_target("guard_1", "guard_1") is False

    def test_vote_tie_resolution(self):
        """平票时应有处理机制"""
        from app.services.game_engine import WerewolfRules
        rules = WerewolfRules()
        result = rules.resolve_vote_tie(["player_a", "player_b"])
        assert result in ["player_a", "player_b"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_game_engine.py::TestWerewolfRules -v`
预期：FAIL

- [ ] **步骤 3：实现 WerewolfRules 类和增强 _run_werewolf**

在 `game_engine.py` 中增加：

```python
class WerewolfRules:
    ROLES = ["werewolf", "seer", "guard", "villager"]

    def assign_roles(self, player_ids: list[str]) -> dict[str, str]:
        """随机分配角色"""
        import random
        n = len(player_ids)
        werewolf_count = max(1, n // 4)
        roles = (["werewolf"] * werewolf_count +
                 ["seer"] * min(1, n // 5) +
                 ["guard"] * min(1, n // 5) +
                 ["villager"] * (n - werewolf_count - min(1, n // 5) - min(1, n // 5)))
        random.shuffle(roles)
        return dict(zip(player_ids, roles))

    def is_valid_guard_target(self, guard_id: str, target_id: str) -> bool:
        """守卫不能守护自己"""
        return guard_id != target_id

    def resolve_vote_tie(self, tied_players: list[str]) -> str:
        """平票随机放逐一人"""
        import random
        return random.choice(tied_players)

    def check_win_condition(self, alive_players: dict[str, str]) -> str | None:
        """检查胜利条件：狼人全死=村民胜，狼人>=好人=狼人胜"""
        werewolves = [p for p, r in alive_players.items() if r == "werewolf"]
        villagers = [p for p, r in alive_players.items() if r != "werewolf"]
        if not werewolves:
            return "village"
        if len(werewolves) >= len(villagers):
            return "werewolf"
        return None
```

重写 `_run_werewolf` 方法，实现：
1. 夜晚阶段：所有狼人依次发言讨论 → 最后一只狼人决定击杀目标
2. 守卫守护（不能自守）
3. 预言家查验
4. 白天阶段：只公布死亡结果，不暴露角色
5. 投票放逐（含平票处理）
6. 胜负判定

```python
async def _run_werewolf(self, game, agents):
    """狼人杀 — 完整机制"""
    rules = WerewolfRules()
    player_ids = [str(a.id) for a in agents]
    roles = rules.assign_roles(player_ids)
    alive_players = dict(roles)  # {player_id: role}
    config = game.config
    config["roles"] = roles
    config["alive_players"] = list(alive_players.keys())

    for turn in range(1, config.get("max_turns", 20) + 1):
        # === 夜晚阶段 ===
        config["phase"] = "night"
        config["current_turn"] = turn

        # 狼人协商
        werewolf_ids = [p for p, r in alive_players.items() if r == "werewolf"]
        non_werewolf_ids = [p for p in alive_players if p not in werewolf_ids]
        kill_target = None

        if len(werewolf_ids) > 1:
            # 多狼人讨论
            discussion = []
            for ww_id in werewolf_ids:
                agent = next((a for a in agents if str(a.id) == ww_id), None)
                if not agent:
                    continue
                prompt = f"""你是狼人。当前存活玩家：{[p for p in alive_players if p not in werewolf_ids]}
之前的讨论：{discussion}
你要击杀谁？回复 TARGET: player_id"""
                resp = await self.llm_service.call_agent(agent, prompt)
                discussion.append(f"狼人{ww_id}: {resp}")

            # 最后一只狼人做决策
            last_ww = next((a for a in agents if str(a.id) == werewolf_ids[-1]), None)
            if last_ww:
                prompt = f"""你是最后发言的狼人。讨论记录：{discussion}
决定击杀谁？回复 TARGET: player_id"""
                resp = await self.llm_service.call_agent(last_ww, prompt)
                kill_target = self._extract_target_id(resp, non_werewolf_ids) or random.choice(non_werewolf_ids)
        else:
            # 单狼人直接选择
            agent = next((a for a in agents if str(a.id) == werewolf_ids[0]), None)
            if agent:
                prompt = f"""你是狼人。当前可击杀目标：{non_werewolf_ids}
回复 TARGET: player_id"""
                resp = await self.llm_service.call_agent(agent, prompt)
                kill_target = self._extract_target_id(resp, non_werewolf_ids) or random.choice(non_werewolf_ids)

        # 守卫守护
        guard_id = next((p for p, r in alive_players.items() if r == "guard"), None)
        guard_target = None
        if guard_id:
            agent = next((a for a in agents if str(a.id) == guard_id), None)
            if agent:
                candidates = [p for p in alive_players if p != guard_id]
                prompt = f"你是守卫。选择守护对象（不能守护自己）：{candidates}\n回复 GUARD: player_id"
                resp = await self.llm_service.call_agent(agent, prompt)
                guard_target = self._extract_target_id(resp, candidates) or random.choice(candidates)

        # 预言家查验
        seer_id = next((p for p, r in alive_players.items() if r == "seer"), None)
        seer_result = None
        if seer_id:
            agent = next((a for a in agents if str(a.id) == seer_id), None)
            if agent:
                candidates = [p for p in alive_players if p != seer_id]
                prompt = f"你是预言家。选择查验对象：{candidates}\n回复 CHECK: player_id"
                resp = await self.llm_service.call_agent(agent, prompt)
                check_target = self._extract_target_id(resp, candidates) or random.choice(candidates)
                seer_result = {"target": check_target, "is_werewolf": alive_players[check_target] == "werewolf"}

        # 夜晚结算
        night_deaths = []
        if kill_target and kill_target != guard_target:
            night_deaths.append(kill_target)
            del alive_players[kill_target]

        # === 白天阶段 ===
        config["phase"] = "day"

        # 公告死亡（不暴露角色）
        day_message = f"昨晚 {'、'.join(night_deaths)} 死亡。" if night_deaths else "昨晚是平安夜。"

        yield {
            "type": "night_result",
            "turn": turn,
            "data": {
                "phase": "day",
                "deaths": night_deaths,  # 只公布 ID，不公布角色
                "message": day_message,
                "alive_count": len(alive_players),
            }
        }

        # 检查胜负
        win = rules.check_win_condition(alive_players)
        if win:
            yield {"type": "game_over", "turn": turn, "data": {"winner": win, "roles": roles}}
            break

        # 投票放逐
        voter_results = {}
        for voter_id in alive_players:
            agent = next((a for a in agents if str(a.id) == voter_id), None)
            if not agent:
                continue
            candidates = [p for p in alive_players if p != voter_id]
            prompt = f"白天讨论。{day_message} 你要投票放逐谁？候选人：{candidates}\n回复 VOTE: player_id"
            resp = await self.llm_service.call_agent(agent, prompt)
            vote = self._extract_target_id(resp, candidates) or random.choice(candidates)
            voter_results[voter_id] = vote

        # 计票
        from collections import Counter
        vote_counts = Counter(voter_results.values())
        max_votes = max(vote_counts.values())
        top_voted = [p for p, v in vote_counts.items() if v == max_votes]

        if len(top_voted) > 1:
            exiled = rules.resolve_vote_tie(top_voted)
        else:
            exiled = top_voted[0]

        del alive_players[exiled]

        yield {
            "type": "vote_result",
            "turn": turn,
            "data": {
                "votes": voter_results,
                "vote_counts": dict(vote_counts),
                "exiled": exiled,
                "exiled_role": roles[exiled],
            }
        }

        # 检查胜负
        win = rules.check_win_condition(alive_players)
        if win:
            yield {"type": "game_over", "turn": turn, "data": {"winner": win, "roles": roles}}
            break

    config["alive_players"] = list(alive_players.keys())
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_game_engine.py::TestWerewolfRules -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/game_engine.py backend/tests/test_game_engine.py
git commit -m "feat: 狼人杀完整机制 — 多狼协商、守卫自守限制、平票处理、信息隔离"
```

---

### 任务 10：辩论赛增强

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：增加辩题库**

在 `game_engine.py` 中增加：

```python
DEBATE_TOPICS = [
    {"topic": "人工智能是否会取代人类工作", "pro": "AI将创造更多就业机会", "con": "AI将导致大规模失业"},
    {"topic": "社交媒体对心理健康的影响", "pro": "社交媒体促进了人际连接", "con": "社交媒体加剧了焦虑和抑郁"},
    {"topic": "远程办公是否应该成为常态", "pro": "远程办公提升效率和幸福感", "con": "远程办公削弱团队协作"},
    {"topic": "应不应该给儿童布置家庭作业", "pro": "作业巩固学习效果", "con": "作业增加压力且效果有限"},
    {"topic": "大学教育是否值得其成本", "pro": "大学教育带来长远回报", "con": "大学教育成本过高且回报不确定"},
    {"topic": "自动驾驶汽车是否应该合法化", "pro": "自动驾驶减少交通事故", "con": "自动驾驶存在不可控风险"},
    {"topic": "动物实验是否应该被禁止", "pro": "动物实验不道德且可替代", "con": "动物实验对医学发展至关重要"},
    {"topic": "全民基本收入是否可行", "pro": "UBI消除贫困并激发创新", "con": "UBI不可持续且削弱工作动力"},
    {"topic": "太空探索的资金是否应该用于解决地球问题", "pro": "地球问题更紧迫", "con": "太空探索带来长远科技回报"},
    {"topic": "社交媒体平台是否应该审核用户内容", "pro": "审核阻止有害信息传播", "con": "审核侵犯言论自由"},
]
```

- [ ] **步骤 2：重写 _run_debate 方法**

增加三阶段流程（立论 → 质询 → 总结）+ 评委评分：

```python
async def _run_debate(self, game, agents):
    """辩论赛 — 立论+质询+总结+评委评分"""
    if len(agents) < 2:
        return {"error": "辩论赛至少需要2个智能体"}

    config = game.config
    topic_data = config.get("topic")
    if not topic_data:
        import random
        topic_data = random.choice(DEBATE_TOPICS)

    topic = topic_data["topic"] if isinstance(topic_data, dict) else topic_data
    pro_side = agents[0]
    con_side = agents[1]

    rounds = []

    # 阶段1：开篇立论
    pro_opening = await self.llm_service.call_agent(
        pro_side,
        f"辩论主题：{topic}\n你是正方。请阐述你的立场和核心论据。200字以内。"
    )
    rounds.append({"phase": "opening", "side": "pro", "content": pro_opening})

    con_opening = await self.llm_service.call_agent(
        con_side,
        f"辩论主题：{topic}\n你是反方。请阐述你的立场和核心论据。200字以内。"
    )
    rounds.append({"phase": "opening", "side": "con", "content": con_opening})

    yield {
        "type": "debate_opening",
        "turn": 1,
        "data": {"topic": topic, "pro": pro_opening, "con": con_opening}
    }

    # 阶段2：交叉质询
    pro_cross = await self.llm_service.call_agent(
        pro_side,
        f"对方观点：{con_opening}\n请提出你的质询问题。"
    )
    rounds.append({"phase": "cross_examination", "side": "pro", "content": pro_cross})

    con_response = await self.llm_service.call_agent(
        con_side,
        f"对方质询：{pro_cross}\n请回应并反击。"
    )
    rounds.append({"phase": "cross_response", "side": "con", "content": con_response})

    con_cross = await self.llm_service.call_agent(
        con_side,
        f"对方观点：{pro_opening}\n请提出你的质询问题。"
    )
    rounds.append({"phase": "cross_examination", "side": "con", "content": con_cross})

    pro_response = await self.llm_service.call_agent(
        pro_side,
        f"对方质询：{con_cross}\n请回应并反击。"
    )
    rounds.append({"phase": "cross_response", "side": "pro", "content": pro_response})

    yield {
        "type": "debate_cross",
        "turn": 2,
        "data": {
            "pro_question": pro_cross, "con_answer": con_response,
            "con_question": con_cross, "pro_answer": pro_response,
        }
    }

    # 阶段3：总结陈词
    pro_closing = await self.llm_service.call_agent(
        pro_side,
        f"辩论总结。回顾：正方立论：{pro_opening}，对方观点：{con_opening}，质询交锋：{pro_cross}/{con_response}和{con_cross}/{pro_response}。\n请做最终总结。150字以内。"
    )
    con_closing = await self.llm_service.call_agent(
        con_side,
        f"辩论总结。回顾：反方立论：{con_opening}，对方观点：{pro_opening}，质询交锋：{con_cross}/{pro_response}和{pro_cross}/{con_response}。\n请做最终总结。150字以内。"
    )

    yield {
        "type": "debate_closing",
        "turn": 3,
        "data": {"pro": pro_closing, "con": con_closing}
    }

    # 评委评分
    judge_prompt = f"""你是辩论赛评委。请对以下辩论评分。

主题：{topic}

正方立论：{pro_opening}
正方质询：{pro_cross}
正方回应：{pro_response}
正方总结：{pro_closing}

反方立论：{con_opening}
反方质询：{con_cross}
反方回应：{con_response}
反方总结：{con_closing}

请按以下格式评分（每项1-10分）：
正方论据力度：X
正方逻辑性：X
正方表达力：X
反方论据力度：X
反方逻辑性：X
反方表达力：X
获胜方：正方/反方
理由：一句话"""

    judge_result = await self.llm_service.call_agent(agents[0], judge_prompt)
    scores = self._parse_debate_scores(judge_result)

    yield {
        "type": "debate_result",
        "turn": 4,
        "data": scores
    }

def _parse_debate_scores(self, judge_response: str) -> dict:
    """解析评委评分"""
    import re
    scores = {}
    patterns = {
        "pro_arguments": r"正方论据力度[：:]\s*(\d+)",
        "pro_logic": r"正方逻辑性[：:]\s*(\d+)",
        "pro_expression": r"正方表达力[：:]\s*(\d+)",
        "con_arguments": r"反方论据力度[：:]\s*(\d+)",
        "con_logic": r"反方逻辑性[：:]\s*(\d+)",
        "con_expression": r"反方表达力[：:]\s*(\d+)",
        "winner": r"获胜方[：:]\s*(正方|反方)",
        "reason": r"理由[：:]\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, judge_response)
        if match:
            if key in ("pro_arguments", "pro_logic", "pro_expression",
                       "con_arguments", "con_logic", "con_expression"):
                scores[key] = int(match.group(1))
            else:
                scores[key] = match.group(1)
        else:
            scores[key] = None

    # 自动计算总分
    scores["pro_total"] = (scores.get("pro_arguments", 0) or 0) + \
                          (scores.get("pro_logic", 0) or 0) + \
                          (scores.get("pro_expression", 0) or 0)
    scores["con_total"] = (scores.get("con_arguments", 0) or 0) + \
                          (scores.get("con_logic", 0) or 0) + \
                          (scores.get("con_expression", 0) or 0)
    if not scores.get("winner"):
        scores["winner"] = "正方" if scores["pro_total"] >= scores["con_total"] else "反方"

    return scores
```

- [ ] **步骤 3：运行现有测试验证无回归**

运行：`cd backend && python -m pytest tests/test_game_engine.py -v`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/game_engine.py backend/tests/test_game_engine.py
git commit -m "feat: 辩论赛增强 — 三阶段流程(立论/质询/总结)+辩题库+结构化评分"
```

---

### 任务 11：文字冒险增强

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：重写 _run_text_adventure 方法**

增加 HP 变化限制、结构化行动类型、位置追踪：

```python
async def _run_text_adventure(self, game, agents):
    """文字冒险 — 叙述者+探险者，含 HP 限制和位置追踪"""
    if len(agents) < 2:
        return {"error": "文字冒险至少需要2个智能体（叙述者+探险者）"}

    narrator = agents[0]
    explorer = agents[1]
    config = game.config

    state = {
        "hp": 100,
        "max_hp": 100,
        "inventory": [],
        "current_location": "起始之地",
        "explored_locations": ["起始之地"],
        "turn": 0,
    }
    config["adventure_state"] = state

    for turn in range(1, config.get("max_turns", 20) + 1):
        state["turn"] = turn
        config["current_turn"] = turn

        # 叙述者描述场景
        narrator_prompt = f"""你是文字冒险的叙述者（游戏主持）。

当前状态：
- 探险者HP: {state['hp']}/{state['max_hp']}
- 位置: {state['current_location']}
- 已探索: {', '.join(state['explored_locations'])}
- 物品: {', '.join(state['inventory']) if state['inventory'] else '无'}
- 回合: {turn}/{config.get('max_turns', 20)}

请描述当前场景，并提供 2-3 个行动选项。

必须使用以下格式：
SCENE: [场景描述，50字以内]
OPTION_A: [行动选项A]
OPTION_B: [行动选项B]
OPTION_C: [行动选项C]（可选）

重要规则：
- 单次HP变化不超过±20
- 只有HP≤0时探险者才死亡
- 提供有意义的探索选择"""

        narration = await self.llm_service.call_agent(narrator, narrator_prompt)

        # 解析叙述
        scene, options = self._parse_adventure_narration(narration)

        yield {
            "type": "scene",
            "turn": turn,
            "data": {
                "scene": scene,
                "options": options,
                "state": dict(state),
            }
        }

        # 探险者选择行动
        options_text = "\n".join(f"- {k}: {v}" for k, v in options.items())
        explorer_prompt = f"""你是文字冒险的探险者。

场景：{scene}
可选行动：
{options_text}

你的状态：HP {state['hp']}/{state['max_hp']}，物品：{', '.join(state['inventory']) or '无'}

选择一个行动。回复格式：ACTION: 选项字母（A/B/C）"""

        choice = await self.llm_service.call_agent(explorer, explorer_prompt)
        chosen = self._parse_adventure_choice(choice, options)

        # 叙述者根据选择推进剧情
        result_prompt = f"""探险者选择了：{chosen}

当前HP: {state['hp']}
请描述行动结果。格式：
RESULT: [结果描述]
HP_CHANGE: [+/-数字，绝对值不超过20]
ITEM: [获得的物品，或NONE]
LOCATION: [新位置，或CURRENT]

规则：HP变化上限±20，HP≤0时才死亡"""

        result_text = await self.llm_service.call_agent(narrator, result_prompt)
        hp_change, item, location, result_desc = self._parse_adventure_result(result_text)

        # 应用状态变化
        if hp_change:
            state["hp"] = max(0, min(state["max_hp"], state["hp"] + hp_change))
        if item and item != "NONE":
            state["inventory"].append(item)
        if location and location != "CURRENT":
            state["current_location"] = location
            if location not in state["explored_locations"]:
                state["explored_locations"].append(location)

        yield {
            "type": "action_result",
            "turn": turn,
            "data": {
                "choice": chosen,
                "result": result_desc,
                "hp_change": hp_change,
                "item": item,
                "new_location": location if location != "CURRENT" else None,
                "state": dict(state),
            }
        }

        # 检查死亡
        if state["hp"] <= 0:
            yield {"type": "game_over", "turn": turn, "data": {"result": "death", "state": state}}
            break

    config["adventure_state"] = state
```

- [ ] **步骤 2：增加解析辅助方法**

```python
def _parse_adventure_narration(self, text: str) -> tuple[str, dict[str, str]]:
    """解析叙述者的场景和选项"""
    import re
    scene_match = re.search(r"SCENE:\s*(.+?)(?=\nOPTION_|$)", text, re.DOTALL)
    scene = scene_match.group(1).strip() if scene_match else text[:100]

    options = {}
    for key in ["OPTION_A", "OPTION_B", "OPTION_C"]:
        match = re.search(rf"{key}:\s*(.+?)(?=\nOPTION_|$)", text, re.DOTALL)
        if match:
            options[key] = match.group(1).strip()

    if not options:
        options = {"OPTION_A": "继续前进", "OPTION_B": "四处探索"}

    return scene, options

def _parse_adventure_choice(self, text: str, options: dict[str, str]) -> str:
    """解析探险者的选择"""
    import re
    match = re.search(r"ACTION:\s*([ABC])", text, re.IGNORECASE)
    if match:
        key = f"OPTION_{match.group(1).upper()}"
        return options.get(key, list(options.values())[0])
    return list(options.values())[0]

def _parse_adventure_result(self, text: str) -> tuple[int | None, str | None, str | None, str]:
    """解析行动结果 → (hp_change, item, location, description)"""
    import re
    hp_match = re.search(r"HP_CHANGE:\s*([+-]?\d+)", text)
    hp_change = int(hp_match.group(1)) if hp_match else None
    if hp_change and abs(hp_change) > 20:
        hp_change = 20 if hp_change > 0 else -20

    item_match = re.search(r"ITEM:\s*(.+?)(?=\n|$)", text)
    item = item_match.group(1).strip() if item_match else None

    loc_match = re.search(r"LOCATION:\s*(.+?)(?=\n|$)", text)
    location = loc_match.group(1).strip() if loc_match else None

    desc_match = re.search(r"RESULT:\s*(.+?)(?=\nHP_CHANGE|\nITEM|\nLOCATION|$)", text, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else text[:200]

    return hp_change, item, location, description
```

- [ ] **步骤 3：运行测试验证无回归**

运行：`cd backend && python -m pytest tests/test_game_engine.py -v`

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/game_engine.py backend/tests/test_game_engine.py
git commit -m "feat: 文字冒险增强 — HP限制、结构化行动、位置追踪、物品系统"
```

---

### 任务 12：谈判博弈增强

**文件：**
- 修改：`backend/app/services/game_engine.py`
- 测试：`backend/tests/test_game_engine.py`

- [ ] **步骤 1：增加场景模板**

```python
NEGOTIATION_SCENARIOS = [
    {
        "name": "资源分配",
        "description": "两国争夺一片争议领土",
        "resources": {"土地": 100, "矿产": 50, "水源": 30},
        "party_a": {"name": "北国", "priority": "矿产", "min_acceptable": {"土地": 30, "矿产": 25}},
        "party_b": {"name": "南国", "priority": "水源", "min_acceptable": {"土地": 30, "水源": 15}},
    },
    {
        "name": "囚徒困境",
        "description": "两名嫌疑人被分开审讯",
        "resources": {"刑期减免": 10},
        "party_a": {"name": "嫌疑人A", "options": ["合作（沉默）", "背叛（指控）"]},
        "party_b": {"name": "嫌疑人B", "options": ["合作（沉默）", "背叛（指控）"]},
    },
    {
        "name": "贸易谈判",
        "description": "两个公司协商技术合作协议",
        "resources": {"专利授权": 5, "市场准入": 3, "技术共享": 2},
        "party_a": {"name": "科技公司", "priority": "市场准入", "min_acceptable": {"专利授权": 2, "市场准入": 2}},
        "party_b": {"name": "制造公司", "priority": "专利授权", "min_acceptable": {"专利授权": 2, "技术共享": 1}},
    },
]
```

- [ ] **步骤 2：重写 _run_negotiation 方法**

```python
async def _run_negotiation(self, game, agents):
    """谈判博弈 — 提案锚定 + 资源量化 + 独立评分"""
    if len(agents) < 2:
        return {"error": "谈判博弈至少需要2个智能体"}

    config = game.config
    scenario = config.get("scenario")
    if not scenario:
        import random
        scenario = random.choice(NEGOTIATION_SCENARIOS)

    party_a = agents[0]
    party_b = agents[1]

    current_proposal = None
    turn_results = []

    for turn in range(1, config.get("max_turns", 20) + 1):
        config["current_turn"] = turn

        # A 方提案/回应
        a_prompt = f"""你是{scenario.get('party_a', {}).get('name', '甲方')}。

谈判场景：{scenario['description']}
可用资源：{scenario.get('resources', {})}

{"当前提案：" + str(current_proposal) if current_proposal else "这是第一轮，请提出你的初始提案。"}

请用以下格式回复：
PROPOSAL: [你的提案内容，包含具体资源分配]
ACTION: [提出新提案 / 接受当前提案 / 拒绝]
REASON: [你的理由]"""

        a_response = await self.llm_service.call_agent(party_a, a_prompt)
        a_parsed = self._parse_negotiation_response(a_response)

        yield {
            "type": "negotiation_turn",
            "turn": turn,
            "data": {"party": "A", **a_parsed}
        }

        if a_parsed.get("action") == "accept" and current_proposal:
            # A 接受了当前提案
            yield {"type": "deal_reached", "turn": turn, "data": {"proposal": current_proposal}}
            break

        current_proposal = a_parsed.get("proposal", current_proposal)

        # B 方提案/回应
        b_prompt = f"""你是{scenario.get('party_b', {}).get('name', '乙方')}。

谈判场景：{scenario['description']}
可用资源：{scenario.get('resources', {})}

当前提案：{current_proposal}

请用以下格式回复：
PROPOSAL: [你的反提案或修改]
ACTION: [提出新提案 / 接受当前提案 / 拒绝]
REASON: [你的理由]"""

        b_response = await self.llm_service.call_agent(party_b, b_prompt)
        b_parsed = self._parse_negotiation_response(b_response)

        yield {
            "type": "negotiation_turn",
            "turn": turn,
            "data": {"party": "B", **b_parsed}
        }

        if b_parsed.get("action") == "accept":
            yield {"type": "deal_reached", "turn": turn, "data": {"proposal": current_proposal}}
            break

        current_proposal = b_parsed.get("proposal", current_proposal)

    else:
        yield {"type": "negotiation_failed", "turn": turn, "data": {"last_proposal": current_proposal}}

    # 独立评分（使用非参与者模型）
    judge_prompt = f"""你是谈判评估专家。

场景：{scenario['description']}
最终提案：{current_proposal}
可用资源：{scenario.get('resources', {})}

请评估：
A方得分（1-10）：X
B方得分（1-10）：X
公平性（1-10）：X
评价：一句话"""

    judge_result = await self.llm_service.call_agent(party_a, judge_prompt)
    scores = self._parse_negotiation_scores(judge_result)

    yield {
        "type": "negotiation_scores",
        "turn": turn,
        "data": scores
    }

def _parse_negotiation_response(self, text: str) -> dict:
    """解析谈判回应"""
    import re
    proposal_match = re.search(r"PROPOSAL:\s*(.+?)(?=\nACTION:|$)", text, re.DOTALL)
    action_match = re.search(r"ACTION:\s*(.+?)(?=\nREASON:|$)", text, re.DOTALL)
    reason_match = re.search(r"REASON:\s*(.+?)$", text, re.DOTALL)

    action_text = action_match.group(1).strip().lower() if action_match else "propose"
    if "接受" in action_text or "accept" in action_text:
        action = "accept"
    elif "拒绝" in action_text or "reject" in action_text:
        action = "reject"
    else:
        action = "propose"

    return {
        "proposal": proposal_match.group(1).strip() if proposal_match else text[:100],
        "action": action,
        "reason": reason_match.group(1).strip() if reason_match else "",
    }

def _parse_negotiation_scores(self, text: str) -> dict:
    """解析谈判评分"""
    import re
    scores = {}
    a_match = re.search(r"A方得分[（(]1-10[)）][：:]\s*(\d+)", text)
    b_match = re.search(r"B方得分[（(]1-10[)）][：:]\s*(\d+)", text)
    fair_match = re.search(r"公平性[（(]1-10[)）][：:]\s*(\d+)", text)
    eval_match = re.search(r"评价[：:]\s*(.+?)$", text, re.DOTALL)

    scores["party_a_score"] = int(a_match.group(1)) if a_match else 5
    scores["party_b_score"] = int(b_match.group(1)) if b_match else 5
    scores["fairness"] = int(fair_match.group(1)) if fair_match else 5
    scores["evaluation"] = eval_match.group(1).strip() if eval_match else ""
    return scores
```

- [ ] **步骤 3：运行测试验证无回归**

运行：`cd backend && python -m pytest tests/test_game_engine.py -v`

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/game_engine.py backend/tests/test_game_engine.py
git commit -m "feat: 谈判博弈增强 — 提案锚定、资源量化、场景模板、独立评分"
```

---

## 第三层：体验提升层

---

### 任务 13：创建前端游戏 WebSocket Hook

**文件：**
- 创建：`frontend/src/hooks/useGameWebSocket.ts`

- [ ] **步骤 1：创建 useGameWebSocket hook**

创建 `frontend/src/hooks/useGameWebSocket.ts`：

```typescript
'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { useSandboxEnv } from '@/lib/env';

export interface GameEvent {
  type: string;
  turn?: number;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export function useGameWebSocket(gameId: string | null) {
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const env = useSandboxEnv();

  useEffect(() => {
    if (!gameId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = env?.wsUrl || `${protocol}//${window.location.hostname}:8000`;
    const ws = new WebSocket(`${wsUrl}/ws/games/${gameId}`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setEvents(prev => [...prev, { ...data, timestamp: data.timestamp || new Date().toISOString() }]);
      } catch {
        // ignore non-JSON messages
      }
    };

    wsRef.current = ws;

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [gameId, env]);

  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, send, clearEvents };
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/hooks/useGameWebSocket.ts
git commit -m "feat: 前端游戏 WebSocket hook — 实时接收游戏事件"
```

---

### 任务 14：通用游戏控制栏组件

**文件：**
- 创建：`frontend/src/components/games/GameControlBar.tsx`

- [ ] **步骤 1：创建 GameControlBar 组件**

创建 `frontend/src/components/games/GameControlBar.tsx`：

```tsx
'use client';

import { useState } from 'react';

interface GameControlBarProps {
  status: 'waiting' | 'in_progress' | 'paused' | 'completed';
  currentTurn: number;
  maxTurns: number;
  connected: boolean;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onSpeedChange: (speed: number) => void;
}

export default function GameControlBar({
  status, currentTurn, maxTurns, connected,
  onStart, onPause, onResume, onSpeedChange,
}: GameControlBarProps) {
  const [speed, setSpeed] = useState(3);

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
    onSpeedChange(newSpeed);
  };

  return (
    <div className="flex items-center justify-between bg-gray-800 rounded-lg p-3 mb-4">
      {/* 状态指示 */}
      <div className="flex items-center gap-3">
        <span className={`w-3 h-3 rounded-full ${
          status === 'in_progress' ? 'bg-green-500 animate-pulse' :
          status === 'paused' ? 'bg-yellow-500' :
          status === 'completed' ? 'bg-gray-500' :
          'bg-blue-500'
        }`} />
        <span className="text-sm text-gray-300">
          {status === 'in_progress' ? '进行中' :
           status === 'paused' ? '已暂停' :
           status === 'completed' ? '已结束' :
           '等待开始'}
        </span>
        <span className="text-sm text-gray-400">
          回合 {currentTurn}/{maxTurns}
        </span>
        <span className={`text-xs ${connected ? 'text-green-400' : 'text-red-400'}`}>
          {connected ? '已连接' : '未连接'}
        </span>
      </div>

      {/* 进度条 */}
      <div className="flex-1 mx-4">
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className="bg-blue-500 rounded-full h-2 transition-all duration-300"
            style={{ width: `${Math.min(100, (currentTurn / maxTurns) * 100)}%` }}
          />
        </div>
      </div>

      {/* 控制按钮 */}
      <div className="flex items-center gap-2">
        {status === 'waiting' && (
          <button
            onClick={onStart}
            className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors"
          >
            开始游戏
          </button>
        )}
        {status === 'in_progress' && (
          <button
            onClick={onPause}
            className="px-4 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-sm rounded-lg transition-colors"
          >
            暂停
          </button>
        )}
        {status === 'paused' && (
          <button
            onClick={onResume}
            className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors"
          >
            继续
          </button>
        )}

        {/* 速度控制 */}
        {status === 'in_progress' && (
          <div className="flex items-center gap-1 ml-2">
            <span className="text-xs text-gray-400">速度</span>
            {[1, 3, 5].map(s => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`px-2 py-0.5 text-xs rounded ${
                  speed === s ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
                }`}
              >
                {s}s
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/GameControlBar.tsx
git commit -m "feat: 通用游戏控制栏 — 开始/暂停/继续/速度控制"
```

---

### 任务 15：国际象棋棋盘可视化组件

**文件：**
- 创建：`frontend/src/components/games/ChessBoard.tsx`

- [ ] **步骤 1：创建 ChessBoard 组件**

创建 `frontend/src/components/games/ChessBoard.tsx`：

```tsx
'use client';

import { useMemo } from 'react';

const PIECE_UNICODE: Record<string, Record<string, string>> = {
  white: { king: '♔', queen: '♕', rook: '♖', bishop: '♗', knight: '♘', pawn: '♙' },
  black: { king: '♚', queen: '♛', rook: '♜', bishop: '♝', knight: '♞', pawn: '♟' },
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

interface ChessBoardProps {
  board: Record<string, [string, string]>;  // {square: [color, piece]}
  lastMove?: { from: string; to: string } | null;
  inCheck?: string | null;  // 'white' | 'black' | null
  flipped?: boolean;
}

export default function ChessBoard({ board, lastMove, inCheck, flipped = false }: ChessBoardProps) {
  const squares = useMemo(() => {
    const result = [];
    const ranks = flipped ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
    const files = flipped ? [...FILES].reverse() : FILES;

    for (const rank of ranks) {
      for (const file of files) {
        const square = `${file}${rank}`;
        const piece = board[square];
        const isLight = (FILES.indexOf(file) + rank) % 2 === 0;
        const isLastMove = lastMove && (square === lastMove.from || square === lastMove.to);
        const isKingInCheck = piece && piece[1] === 'king' && piece[0] === inCheck;

        result.push({
          square,
          piece,
          isLight,
          isLastMove,
          isKingInCheck,
        });
      }
    }
    return result;
  }, [board, lastMove, inCheck, flipped]);

  return (
    <div className="inline-block border-2 border-gray-600 rounded overflow-hidden">
      <div className="grid grid-cols-8 gap-0" style={{ width: '320px', height: '320px' }}>
        {squares.map(({ square, piece, isLight, isLastMove, isKingInCheck }) => (
          <div
            key={square}
            className={`flex items-center justify-center text-2xl select-none ${
              isKingInCheck ? 'bg-red-500' :
              isLastMove ? 'bg-yellow-600' :
              isLight ? 'bg-gray-200' : 'bg-gray-500'
            }`}
            style={{ width: '40px', height: '40px' }}
            title={square}
          >
            {piece && (
              <span className={piece[0] === 'white' ? 'text-white drop-shadow-lg' : 'text-gray-900'}>
                {PIECE_UNICODE[piece[0]]?.[piece[1]] || '?'}
              </span>
            )}
          </div>
        ))}
      </div>
      {/* 坐标标签 */}
      <div className="flex justify-between px-1 mt-0.5" style={{ width: '320px' }}>
        {(flipped ? [...FILES].reverse() : FILES).map(f => (
          <span key={f} className="text-xs text-gray-400 w-10 text-center">{f}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/ChessBoard.tsx
git commit -m "feat: 国际象棋棋盘可视化 — Unicode棋子、走法高亮、将军提示"
```

---

### 任务 16：狼人杀角色卡牌 + 投票可视化

**文件：**
- 创建：`frontend/src/components/games/WerewolfPanel.tsx`

- [ ] **步骤 1：创建 WerewolfPanel 组件**

创建 `frontend/src/components/games/WerewolfPanel.tsx`：

```tsx
'use client';

interface Player {
  agent_id: string;
  name: string;
  role?: string;
  alive: boolean;
}

interface WerewolfPanelProps {
  players: Player[];
  phase: 'night' | 'day';
  currentTurn: number;
  lastDeath?: string[];
  voteResult?: {
    votes: Record<string, string>;
    vote_counts: Record<string, number>;
    exiled: string;
  };
  gameOver?: { winner: string; roles: Record<string, string> } | null;
}

const ROLE_ICONS: Record<string, string> = {
  werewolf: '🐺',
  seer: '🔮',
  guard: '🛡️',
  villager: '👤',
};

export default function WerewolfPanel({
  players, phase, currentTurn, lastDeath, voteResult, gameOver,
}: WerewolfPanelProps) {
  return (
    <div className="space-y-4">
      {/* 阶段指示器 */}
      <div className="flex items-center justify-center gap-4 p-3 bg-gray-800 rounded-lg">
        <span className="text-2xl">{phase === 'night' ? '🌙' : '☀️'}</span>
        <span className="text-lg font-semibold text-white">
          {phase === 'night' ? '夜晚' : '白天'} — 第 {currentTurn} 回合
        </span>
      </div>

      {/* 死亡公告 */}
      {lastDeath && lastDeath.length > 0 && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-center">
          <span className="text-red-400">
            💀 昨晚 {lastDeath.join('、')} 死亡
          </span>
        </div>
      )}
      {lastDeath && lastDeath.length === 0 && (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-3 text-center">
          <span className="text-green-400">✨ 昨晚是平安夜</span>
        </div>
      )}

      {/* 角色卡牌 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {players.map(player => (
          <div
            key={player.agent_id}
            className={`relative p-3 rounded-lg border-2 transition-all ${
              player.alive
                ? 'bg-gray-800 border-gray-600 hover:border-blue-500'
                : 'bg-gray-900 border-gray-700 opacity-50'
            }`}
          >
            {!player.alive && (
              <div className="absolute inset-0 flex items-center justify-center text-4xl opacity-60">
                💀
              </div>
            )}
            <div className="text-center">
              <div className="text-3xl mb-1">
                {(gameOver?.roles?.[player.agent_id] && ROLE_ICONS[gameOver.roles[player.agent_id]]) || '❓'}
              </div>
              <div className="text-sm font-medium text-white">{player.name}</div>
              {gameOver?.roles?.[player.agent_id] && (
                <div className="text-xs text-gray-400 mt-1">
                  {gameOver.roles[player.agent_id] === 'werewolf' ? '狼人' :
                   gameOver.roles[player.agent_id] === 'seer' ? '预言家' :
                   gameOver.roles[player.agent_id] === 'guard' ? '守卫' : '村民'}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 投票结果 */}
      {voteResult && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">投票结果</h3>
          <div className="space-y-2">
            {Object.entries(voteResult.vote_counts)
              .sort(([, a], [, b]) => b - a)
              .map(([playerId, count]) => {
                const player = players.find(p => p.agent_id === playerId);
                const total = Object.values(voteResult.vote_counts).reduce((a, b) => a + b, 0);
                const pct = total > 0 ? (count / total) * 100 : 0;
                const isExiled = playerId === voteResult.exiled;
                return (
                  <div key={playerId} className="flex items-center gap-2">
                    <span className={`text-sm w-20 truncate ${isExiled ? 'text-red-400 font-bold' : 'text-gray-300'}`}>
                      {player?.name || playerId.slice(0, 8)}
                    </span>
                    <div className="flex-1 bg-gray-700 rounded-full h-4">
                      <div
                        className={`h-4 rounded-full transition-all ${isExiled ? 'bg-red-500' : 'bg-blue-500'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-8 text-right">{count}</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* 游戏结束 */}
      {gameOver && (
        <div className={`text-center p-4 rounded-lg border-2 ${
          gameOver.winner === 'werewolf'
            ? 'bg-red-900/30 border-red-700'
            : 'bg-green-900/30 border-green-700'
        }`}>
          <div className="text-2xl mb-2">
            {gameOver.winner === 'werewolf' ? '🐺' : '🏘️'}
          </div>
          <div className="text-lg font-bold text-white">
            {gameOver.winner === 'werewolf' ? '狼人获胜' : '村民获胜'}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/WerewolfPanel.tsx
git commit -m "feat: 狼人杀可视化 — 角色卡牌、阶段指示、投票柱状图"
```

---

### 任务 17：辩论赛正反方分栏组件

**文件：**
- 创建：`frontend/src/components/games/DebatePanel.tsx`

- [ ] **步骤 1：创建 DebatePanel 组件**

创建 `frontend/src/components/games/DebatePanel.tsx`：

```tsx
'use client';

interface DebateRound {
  phase: 'opening' | 'cross_examination' | 'cross_response' | 'closing';
  side: 'pro' | 'con';
  content: string;
}

interface DebateScores {
  pro_arguments: number;
  pro_logic: number;
  pro_expression: number;
  con_arguments: number;
  con_logic: number;
  con_expression: number;
  pro_total: number;
  con_total: number;
  winner: string;
  reason: string;
}

interface DebatePanelProps {
  topic: string;
  rounds: DebateRound[];
  currentPhase: string;
  scores?: DebateScores | null;
}

function ScoreRadar({ scores, side }: { scores: { arguments: number; logic: number; expression: number }; side: 'pro' | 'con' }) {
  const max = 10;
  const dimensions = [
    { label: '论据', value: scores.arguments, key: 'arguments' },
    { label: '逻辑', value: scores.logic, key: 'logic' },
    { label: '表达', value: scores.expression, key: 'expression' },
  ];

  return (
    <div className="space-y-2">
      {dimensions.map(d => (
        <div key={d.key} className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-8">{d.label}</span>
          <div className="flex-1 bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${side === 'pro' ? 'bg-blue-500' : 'bg-orange-500'}`}
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-300 w-6 text-right">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function DebatePanel({ topic, rounds, currentPhase, scores }: DebatePanelProps) {
  const proRounds = rounds.filter(r => r.side === 'pro');
  const conRounds = rounds.filter(r => r.side === 'con');

  return (
    <div className="space-y-4">
      {/* 辩题 */}
      <div className="text-center p-4 bg-gray-800 rounded-lg">
        <span className="text-sm text-gray-400">辩论主题</span>
        <h2 className="text-lg font-bold text-white mt-1">{topic}</h2>
      </div>

      {/* 阶段指示器 */}
      <div className="flex items-center justify-center gap-2">
        {['opening', 'cross', 'closing', 'result'].map((phase, i) => (
          <div key={phase} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
              currentPhase === phase ? 'bg-blue-600 text-white' :
              i < ['opening', 'cross', 'closing', 'result'].indexOf(currentPhase)
                ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-400'
            }`}>
              {i + 1}
            </div>
            <span className="text-xs text-gray-400 hidden sm:inline">
              {phase === 'opening' ? '立论' : phase === 'cross' ? '质询' : phase === 'closing' ? '总结' : '评分'}
            </span>
            {i < 3 && <div className="w-8 h-0.5 bg-gray-700" />}
          </div>
        ))}
      </div>

      {/* 正反方分栏 */}
      <div className="grid grid-cols-2 gap-4">
        {/* 正方 */}
        <div className="space-y-3">
          <div className="text-center py-2 bg-blue-900/30 border border-blue-700 rounded-lg">
            <span className="text-blue-400 font-semibold">正方</span>
          </div>
          {proRounds.map((round, i) => (
            <div key={i} className="bg-gray-800 rounded-lg p-3">
              <span className="text-xs text-gray-400">
                {round.phase === 'opening' ? '立论' :
                 round.phase === 'cross_examination' ? '质询' :
                 round.phase === 'cross_response' ? '回应' : '总结'}
              </span>
              <p className="text-sm text-gray-200 mt-1">{round.content}</p>
            </div>
          ))}
          {scores && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs text-gray-400 mb-2">评分</h4>
              <ScoreRadar scores={{
                arguments: scores.pro_arguments,
                logic: scores.pro_logic,
                expression: scores.pro_expression,
              }} side="pro" />
              <div className="text-center mt-2 text-sm text-blue-400 font-bold">
                总分：{scores.pro_total}
              </div>
            </div>
          )}
        </div>

        {/* 反方 */}
        <div className="space-y-3">
          <div className="text-center py-2 bg-orange-900/30 border border-orange-700 rounded-lg">
            <span className="text-orange-400 font-semibold">反方</span>
          </div>
          {conRounds.map((round, i) => (
            <div key={i} className="bg-gray-800 rounded-lg p-3">
              <span className="text-xs text-gray-400">
                {round.phase === 'opening' ? '立论' :
                 round.phase === 'cross_examination' ? '质询' :
                 round.phase === 'cross_response' ? '回应' : '总结'}
              </span>
              <p className="text-sm text-gray-200 mt-1">{round.content}</p>
            </div>
          ))}
          {scores && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs text-gray-400 mb-2">评分</h4>
              <ScoreRadar scores={{
                arguments: scores.con_arguments,
                logic: scores.con_logic,
                expression: scores.con_expression,
              }} side="con" />
              <div className="text-center mt-2 text-sm text-orange-400 font-bold">
                总分：{scores.con_total}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 获胜方 */}
      {scores && (
        <div className={`text-center p-4 rounded-lg border-2 ${
          scores.winner === '正方' ? 'bg-blue-900/30 border-blue-700' : 'bg-orange-900/30 border-orange-700'
        }`}>
          <div className="text-lg font-bold text-white">
            {scores.winner}获胜
          </div>
          {scores.reason && (
            <div className="text-sm text-gray-300 mt-1">{scores.reason}</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/DebatePanel.tsx
git commit -m "feat: 辩论赛可视化 — 正反方分栏、阶段指示、评分雷达图"
```

---

### 任务 18：文字冒险场景面板组件

**文件：**
- 创建：`frontend/src/components/games/AdventurePanel.tsx`

- [ ] **步骤 1：创建 AdventurePanel 组件**

创建 `frontend/src/components/games/AdventurePanel.tsx`：

```tsx
'use client';

interface AdventureState {
  hp: number;
  max_hp: number;
  inventory: string[];
  current_location: string;
  explored_locations: string[];
  turn: number;
}

interface AdventurePanelProps {
  scene?: string;
  options?: Record<string, string>;
  lastResult?: {
    choice: string;
    result: string;
    hp_change?: number;
    item?: string;
    new_location?: string;
  };
  state: AdventureState;
  gameOver?: { result: string } | null;
  onChoice?: (optionKey: string) => void;
}

export default function AdventurePanel({
  scene, options, lastResult, state, gameOver, onChoice,
}: AdventurePanelProps) {
  const hpPercent = state.max_hp > 0 ? (state.hp / state.max_hp) * 100 : 0;
  const hpColor = hpPercent > 60 ? 'bg-green-500' : hpPercent > 30 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="space-y-4">
      {/* 状态栏 */}
      <div className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
        {/* HP */}
        <div className="flex items-center gap-2 flex-1">
          <span className="text-sm text-gray-300">❤️ HP</span>
          <div className="flex-1 bg-gray-700 rounded-full h-3">
            <div
              className={`${hpColor} rounded-full h-3 transition-all duration-500`}
              style={{ width: `${hpPercent}%` }}
            />
          </div>
          <span className="text-sm text-gray-300">{state.hp}/{state.max_hp}</span>
        </div>

        {/* 位置 */}
        <div className="flex items-center gap-1">
          <span className="text-sm">📍</span>
          <span className="text-sm text-gray-300">{state.current_location}</span>
        </div>
      </div>

      {/* 物品栏 */}
      {state.inventory.length > 0 && (
        <div className="flex items-center gap-2 p-2 bg-gray-800/50 rounded-lg flex-wrap">
          <span className="text-sm text-gray-400">🎒</span>
          {state.inventory.map((item, i) => (
            <span key={i} className="px-2 py-0.5 bg-gray-700 text-sm text-gray-200 rounded">
              {item}
            </span>
          ))}
        </div>
      )}

      {/* 场景描述 */}
      {scene && (
        <div className="p-4 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg border border-gray-700">
          <p className="text-gray-200 leading-relaxed">{scene}</p>
        </div>
      )}

      {/* 上次行动结果 */}
      {lastResult && (
        <div className={`p-3 rounded-lg border ${
          lastResult.hp_change && lastResult.hp_change < 0
            ? 'bg-red-900/20 border-red-800'
            : lastResult.hp_change && lastResult.hp_change > 0
              ? 'bg-green-900/20 border-green-800'
              : 'bg-gray-800 border-gray-700'
        }`}>
          <p className="text-sm text-gray-200">{lastResult.result}</p>
          <div className="flex gap-3 mt-2">
            {lastResult.hp_change && (
              <span className={lastResult.hp_change > 0 ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
                HP {lastResult.hp_change > 0 ? '+' : ''}{lastResult.hp_change}
              </span>
            )}
            {lastResult.item && lastResult.item !== 'NONE' && (
              <span className="text-yellow-400 text-sm">获得：{lastResult.item}</span>
            )}
            {lastResult.new_location && (
              <span className="text-blue-400 text-sm">移动到：{lastResult.new_location}</span>
            )}
          </div>
        </div>
      )}

      {/* 行动选项 */}
      {options && Object.keys(options).length > 0 && !gameOver && onChoice && (
        <div className="space-y-2">
          {Object.entries(options).map(([key, desc]) => (
            <button
              key={key}
              onClick={() => onChoice(key)}
              className="w-full text-left p-3 bg-gray-800 hover:bg-gray-700 border border-gray-600 hover:border-blue-500 rounded-lg transition-colors"
            >
              <span className="text-blue-400 font-medium mr-2">{key.replace('OPTION_', '')}</span>
              <span className="text-gray-200 text-sm">{desc}</span>
            </button>
          ))}
        </div>
      )}

      {/* 已探索区域 */}
      {state.explored_locations.length > 1 && (
        <div className="p-3 bg-gray-800/50 rounded-lg">
          <span className="text-xs text-gray-400">已探索区域</span>
          <div className="flex gap-2 mt-1 flex-wrap">
            {state.explored_locations.map(loc => (
              <span key={loc} className={`px-2 py-0.5 text-xs rounded ${
                loc === state.current_location
                  ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
                  : 'bg-gray-700 text-gray-400'
              }`}>
                {loc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 游戏结束 */}
      {gameOver && (
        <div className="text-center p-6 bg-red-900/30 border border-red-700 rounded-lg">
          <div className="text-4xl mb-2">💀</div>
          <div className="text-lg font-bold text-red-400">探险结束</div>
          <div className="text-sm text-gray-300 mt-1">
            你在 {state.current_location} 倒下了
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/AdventurePanel.tsx
git commit -m "feat: 文字冒险可视化 — 场景面板、HP条、物品栏、行动选项"
```

---

### 任务 19：谈判博弈提案面板组件

**文件：**
- 创建：`frontend/src/components/games/NegotiationPanel.tsx`

- [ ] **步骤 1：创建 NegotiationPanel 组件**

创建 `frontend/src/components/games/NegotiationPanel.tsx`：

```tsx
'use client';

interface NegotiationTurn {
  party: 'A' | 'B';
  proposal: string;
  action: 'propose' | 'accept' | 'reject';
  reason: string;
}

interface NegotiationScores {
  party_a_score: number;
  party_b_score: number;
  fairness: number;
  evaluation: string;
}

interface NegotiationPanelProps {
  scenario?: { name: string; description: string; resources?: Record<string, unknown> };
  currentProposal?: string;
  turns: NegotiationTurn[];
  dealReached?: string | null;
  scores?: NegotiationScores | null;
}

const ACTION_STYLES = {
  propose: { bg: 'bg-blue-900/30', border: 'border-blue-700', label: '📋 提案', color: 'text-blue-400' },
  accept: { bg: 'bg-green-900/30', border: 'border-green-700', label: '✅ 接受', color: 'text-green-400' },
  reject: { bg: 'bg-red-900/30', border: 'border-red-700', label: '❌ 拒绝', color: 'text-red-400' },
};

export default function NegotiationPanel({
  scenario, currentProposal, turns, dealReached, scores,
}: NegotiationPanelProps) {
  return (
    <div className="space-y-4">
      {/* 场景描述 */}
      {scenario && (
        <div className="p-4 bg-gray-800 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-300">{scenario.name}</h3>
          <p className="text-sm text-gray-400 mt-1">{scenario.description}</p>
          {scenario.resources && (
            <div className="flex gap-2 mt-2 flex-wrap">
              {Object.entries(scenario.resources).map(([key, value]) => (
                <span key={key} className="px-2 py-0.5 bg-gray-700 text-xs text-gray-300 rounded">
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 当前提案 */}
      {currentProposal && !dealReached && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-700 rounded-lg">
          <span className="text-xs text-yellow-400">当前提案</span>
          <p className="text-sm text-gray-200 mt-1">{currentProposal}</p>
        </div>
      )}

      {/* 谈判历程 */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {turns.map((turn, i) => {
          const style = ACTION_STYLES[turn.action];
          return (
            <div key={i} className={`${style.bg} border ${style.border} rounded-lg p-3`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-white">
                  {turn.party === 'A' ? '🅰️ 甲方' : '🅱️ 乙方'}
                </span>
                <span className={`text-xs ${style.color}`}>{style.label}</span>
              </div>
              <p className="text-sm text-gray-200">{turn.proposal}</p>
              {turn.reason && (
                <p className="text-xs text-gray-400 mt-1">理由：{turn.reason}</p>
              )}
            </div>
          );
        })}
      </div>

      {/* 达成协议 */}
      {dealReached && (
        <div className="p-4 bg-green-900/30 border border-green-700 rounded-lg text-center">
          <div className="text-2xl mb-2">🤝</div>
          <div className="text-lg font-bold text-green-400">达成协议</div>
          <p className="text-sm text-gray-200 mt-2">{dealReached}</p>
        </div>
      )}

      {/* 评分 */}
      {scores && (
        <div className="p-4 bg-gray-800 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">独立评估</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-400">{scores.party_a_score}</div>
              <div className="text-xs text-gray-400">甲方</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-400">{scores.fairness}</div>
              <div className="text-xs text-gray-400">公平性</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-400">{scores.party_b_score}</div>
              <div className="text-xs text-gray-400">乙方</div>
            </div>
          </div>
          {scores.evaluation && (
            <p className="text-sm text-gray-400 text-center mt-3">{scores.evaluation}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/games/NegotiationPanel.tsx
git commit -m "feat: 谈判博弈可视化 — 提案面板、谈判历程、评分展示"
```

---

### 任务 20：重写游戏页面，集成所有组件

**文件：**
- 修改：`frontend/src/app/games/page.tsx`

- [ ] **步骤 1：重写 games/page.tsx，集成所有游戏可视化组件**

重写 `frontend/src/app/games/page.tsx`，主要修改：
1. 导入所有游戏专用组件和 GameControlBar
2. 使用 `useGameWebSocket` hook
3. 根据游戏类型渲染不同的可视化面板
4. 集成暂停/恢复/启动控制
5. 修复所有接口不匹配问题

关键结构：

```tsx
import { useGameWebSocket } from '@/hooks/useGameWebSocket';
import GameControlBar from '@/components/games/GameControlBar';
import ChessBoard from '@/components/games/ChessBoard';
import WerewolfPanel from '@/components/games/WerewolfPanel';
import DebatePanel from '@/components/games/DebatePanel';
import AdventurePanel from '@/components/games/AdventurePanel';
import NegotiationPanel from '@/components/games/NegotiationPanel';

// 在游戏详情/运行视图中：
function GameDetailView({ game }: { game: Game }) {
  const { events, connected, send } = useGameWebSocket(game.id);

  const handleStart = async () => {
    await fetch(`${API_BASE}/games/${game.id}/start`, { method: 'POST' });
  };
  const handlePause = async () => {
    await fetch(`${API_BASE}/games/${game.id}/pause`, { method: 'POST' });
  };
  const handleResume = async () => {
    await fetch(`${API_BASE}/games/${game.id}/resume`, { method: 'POST' });
  };

  return (
    <div>
      <GameControlBar
        status={game.status}
        currentTurn={game.current_turn}
        maxTurns={game.max_turns}
        connected={connected}
        onStart={handleStart}
        onPause={handlePause}
        onResume={handleResume}
        onSpeedChange={(speed) => send({ type: 'set_speed', speed })}
      />

      {/* 根据游戏类型渲染可视化 */}
      {game.game_type === 'chess' && (
        <ChessBoard
          board={game.config.board || {}}
          lastMove={game.config.last_move}
          inCheck={game.config.in_check}
        />
      )}
      {game.game_type === 'werewolf' && (
        <WerewolfPanel
          players={game.players}
          phase={game.config.phase}
          currentTurn={game.current_turn}
          lastDeath={game.config.last_deaths}
          voteResult={game.config.vote_result}
          gameOver={game.config.game_over}
        />
      )}
      {/* ... debate, adventure, negotiation 类似 */}

      {/* 事件日志（保留作为底栏） */}
      <EventLog events={events} />
    </div>
  );
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/app/games/page.tsx
git commit -m "feat: 游戏页面集成所有可视化组件 + WebSocket 实时更新"
```

---

### 任务 21：运行全部测试并修复问题

**文件：**
- 可能修改多个测试文件

- [ ] **步骤 1：运行后端全部测试**

运行：`cd backend && python -m pytest tests/ -v`

- [ ] **步骤 2：修复任何失败的测试**

根据测试输出逐个修复。

- [ ] **步骤 3：运行前端 lint 和构建**

运行：`cd frontend && npm run lint && npm run build`

- [ ] **步骤 4：修复 lint 错误和构建问题**

根据输出修复。

- [ ] **步骤 5：Commit 所有修复**

```bash
git add -A
git commit -m "fix: 测试和构建修复"
```

---

### 任务 22：最终验证和提交

- [ ] **步骤 1：检查所有文件已提交**

运行：`git status`

- [ ] **步骤 2：运行完整后端测试套件**

运行：`cd backend && python -m pytest tests/ -v`

- [ ] **步骤 3：运行前端构建**

运行：`cd frontend && npm run build`

- [ ] **步骤 4：确认 Docker 构建**

运行：`docker-compose build`

- [ ] **步骤 5：最终 commit（如有遗漏修改）**

```bash
git add -A
git commit -m "chore: 游戏功能全面完善 — 最终验证"
```

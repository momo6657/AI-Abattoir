# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

AI Abattoir 是一个多 AI 模型交互平台，让多个大模型可以对话、合作、竞争、对抗、玩游戏。

## 技术栈

- **前端**: Next.js 15 + TypeScript + Tailwind CSS (App Router)
- **后端**: FastAPI (Python 3.12) + SQLAlchemy (async) + Alembic
- **数据库**: PostgreSQL + Redis + MinIO
- **LLM 适配**: LiteLLM (统一调用 100+ 种模型)
- **实时通信**: 原生 WebSocket (FastAPI WebSocket)
- **部署**: Docker + Docker Compose

## 常用命令

### 启动开发环境
```bash
docker-compose up -d
```

### 后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # 启动后端
pytest tests/ -v                       # 运行测试
alembic revision --autogenerate -m "msg"  # 生成迁移
alembic upgrade head                    # 执行迁移
```

### 前端
```bash
cd frontend
npm install
npm run dev       # 启动开发服务器
npm run build     # 构建生产版本
npm run lint      # 代码检查
npm run test      # 运行测试
```

## 项目结构

```
backend/
├── app/
│   ├── api/           # REST API 路由 (models, agents, conversations, games, arena, auth, search)
│   ├── core/          # 配置、数据库、安全
│   ├── models/        # SQLAlchemy 数据库模型
│   ├── schemas/       # Pydantic 请求/响应模型
│   ├── services/      # 业务逻辑
│   │   ├── llm_adapter.py        # LLM 统一调用适配器 (LiteLLM)
│   │   ├── agent_service.py      # 智能体服务
│   │   ├── conversation_engine.py # 对话引擎 (自由/辩论/接力/采访)
│   │   ├── arena_engine.py       # 竞技场引擎 (问答PK/代码/生图/配音)
│   │   ├── game_engine.py        # 游戏引擎 (狼人杀/辩论/谈判/象棋/文字冒险)
│   │   ├── spectator_service.py  # 观战与回放服务
│   │   ├── hierarchy_service.py  # 层级指挥系统
│   │   ├── evolution_service.py  # 经验进化系统
│   │   ├── message_router.py     # 消息路由
│   │   ├── image_adapter.py      # 图像生成适配
│   │   ├── tts_adapter.py        # 语音合成适配
│   │   ├── search_service.py     # 联网搜索
│   │   └── media_storage.py      # 媒体文件存储
│   └── websocket/     # WebSocket 处理
└── alembic/           # 数据库迁移

frontend/src/
├── app/               # Next.js App Router 页面
│   ├── page.tsx           # 首页
│   ├── models/            # 模型管理
│   ├── agents/            # 智能体管理
│   ├── conversations/     # 对话管理
│   ├── arena/             # 竞技场
│   ├── games/             # 游戏房间
│   ├── hierarchy/         # 层级管理
│   ├── evolution/         # 进化日志
│   ├── spectate/          # 观战/回放
│   └── leaderboard/       # 排行榜
├── components/        # 可复用组件 (Modal, ErrorBanner, LoadingSpinner, Badge, ProgressBar)
├── hooks/             # React hooks (useFetch, useWebSocket)
├── hooks/             # React hooks
└── lib/               # 工具函数 (api.ts 等)
```

## 核心概念

- **Model**: 底层 LLM 接入配置 (API Key、端点、模型 ID)
- **Agent**: 智能体，绑定 Model，拥有独立人设、性格、层级关系
- **Conversation**: 多个 Agent 参与的对话，支持自由/辩论/接力/采访模式
- **Game**: 游戏实例 (狼人杀、策略模拟等)
- **Spectator**: 观战系统，支持实时观看对话/游戏及完整回放
- **Hierarchy**: 层级指挥系统，Agent 之间可建立上下级关系
- **Evolution**: 经验进化系统，Agent 从经验中学习并提升等级
- **Capability**: 模型能力声明 (文本生成、图像生成、TTS、搜索等)

## API 端点

### REST API
- `GET/POST /api/models` - 模型管理 (写入需认证)
- `GET/POST /api/agents` - 智能体管理 (写入需认证)
- `GET/POST /api/conversations` - 对话管理 (写入需认证)
- `GET/POST /api/games` - 游戏管理 (写入需认证)
- `POST /api/arena/matches` - 竞技场比赛
- `POST /api/arena/matches/{id}/start` - 开始比赛
- `POST /api/arena/matches/{id}/vote` - 投票
- `POST /api/auth/register` - 注册
- `POST /api/auth/login` - 登录
- `POST /api/auth/github` - GitHub OAuth 登录
- `GET /api/auth/me` - 当前用户信息
- `GET /api/search` - 联网搜索
- `GET /api/search/fetch` - 抓取网页内容
- `POST /api/hierarchy` - 创建层级关系
- `GET /api/hierarchy/{agent_id}` - 获取层级树
- `GET /api/agents/{id}/evolution` - 智能体进化信息
- `GET /api/agents/{id}/experiences` - 智能体经验日志
- `GET /api/replay/conversations/{id}` - 对话回放
- `GET /api/replay/games/{id}` - 游戏回放
- `GET /health` - 健康检查
- Swagger 文档: `http://localhost:8000/docs`

### WebSocket 端点
- `/ws/conversations/{id}` - 对话实时通信
- `/ws/spectate/conversation/{id}` - 观战对话（只读）
- `/ws/spectate/game/{id}` - 观战游戏（只读）

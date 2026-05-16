# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI Abattoir 是一个多 AI 模型交互平台，让多个大模型可以对话、合作、竞争、对抗、玩游戏。

## 技术栈

- **前端**: Next.js 15 + TypeScript + Tailwind CSS (App Router)
- **后端**: FastAPI (Python 3.12) + SQLAlchemy (async) + Alembic
- **数据库**: PostgreSQL + Redis + MinIO
- **LLM 适配**: LiteLLM (统一调用 100+ 种模型)
- **实时通信**: Socket.IO
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
```

## 项目结构

```
backend/
├── app/
│   ├── api/           # REST API 路由 (models, agents, conversations, games)
│   ├── core/          # 配置、数据库、安全
│   ├── models/        # SQLAlchemy 数据库模型
│   ├── schemas/       # Pydantic 请求/响应模型
│   ├── services/      # 业务逻辑 (LLM适配、图像、TTS、搜索、存储)
│   └── websocket/     # WebSocket 处理
└── alembic/           # 数据库迁移

frontend/src/
├── app/               # Next.js App Router 页面
│   ├── models/        # 模型管理
│   ├── agents/        # 智能体管理
│   ├── conversations/ # 对话
│   ├── arena/         # 竞技场
│   ├── games/         # 游戏房间
│   └── leaderboard/   # 排行榜
├── components/        # 可复用组件
├── hooks/             # React hooks
└── lib/               # 工具函数 (api.ts 等)
```

## 核心概念

- **Model**: 底层 LLM 接入配置 (API Key、端点、模型 ID)
- **Agent**: 智能体，绑定 Model，拥有独立人设、性格、层级关系
- **Conversation**: 多个 Agent 参与的对话，支持自由/辩论/接力/采访模式
- **Game**: 游戏实例 (狼人杀、策略模拟等)
- **Capability**: 模型能力声明 (文本生成、图像生成、TTS、搜索等)

## API 端点

- `GET/POST /api/models` - 模型管理
- `GET/POST /api/agents` - 智能体管理
- `GET/POST /api/conversations` - 对话管理
- `GET/POST /api/games` - 游戏管理
- `GET /health` - 健康检查
- Swagger 文档: `http://localhost:8000/docs`

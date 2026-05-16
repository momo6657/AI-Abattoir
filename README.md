# AI Abattoir

让多个 AI 大模型相互对话、合作、竞争、对抗的平台。

## 功能

- **模型管理**：接入 OpenAI、Claude、Gemini、DeepSeek 等多种 LLM
- **智能体系统**：定制智能体人设、性格、说话风格，支持层级指挥关系
- **对话引擎**：自由对话、辩论、接力、采访，支持文本+图片+语音多模态
- **竞技场**：问答 PK、生图对决、代码竞赛、配音 PK
- **游戏系统**：狼人杀、策略模拟、谈判博弈
- **经验进化**：智能体从经验中学习，不断进化提升能力
- **联网能力**：智能体可搜索互联网获取实时信息

## 快速开始

```bash
# 启动所有服务
docker-compose up -d

# 访问前端
open http://localhost:3000

# 访问 API 文档
open http://localhost:8000/docs
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js + TypeScript + Tailwind CSS |
| 后端 | FastAPI (Python) |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| 文件存储 | MinIO |
| LLM 适配 | LiteLLM |
| 实时通信 | Socket.IO |
| 部署 | Docker + Docker Compose |

## 开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

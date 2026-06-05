<div align="center">

# AI Abattoir

**多 AI 大模型交互竞技平台**

让多个 AI 大模型相互对话、合作、竞争、对抗、玩游戏

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](docker-compose.yml)

[快速开始](#快速开始) | [功能详解](#功能详解) | [API 文档](#api-文档) | [开发指南](#开发指南) | [贡献指南](#贡献指南)

</div>

---

## 项目简介

AI Abattoir 是一个让多个 AI 大模型相互交互的平台。不同于传统的单一对话界面，本平台让 AI 之间可以：

- **对话交流** — 多个 AI 围绕话题自由讨论、辩论、接力创作
- **竞技对抗** — 同题 PK、代码竞赛、生图对决、配音比拼
- **游戏博弈** — 狼人杀、策略模拟、谈判博弈
- **宝可梦训练** — 智能体自动建队、本地 VGC 对战、知识检索与学习记录
- **层级指挥** — 上级 AI 指挥下级 AI，模拟组织架构
- **经验进化** — AI 从每次交互中学习，不断提升能力
- **联网搜索** — AI 可以搜索互联网获取实时信息

### 为什么叫 Abattoir？

Abattoir（竞技场）是一个让 AI 展现真实能力的地方。在这里，不同的大模型不再是孤立的对话工具，而是可以相互比较、学习、进化的智能体。

---

## 功能详解

### 1. 模型管理 (Model Hub)

接入多种 LLM API，通过 LiteLLM 统一调用接口。

| 能力类别 | 具体能力 | 示例模型 |
|----------|----------|----------|
| 文本生成 | 对话、续写、翻译、摘要 | GPT-4o、Claude、DeepSeek |
| 图像生成 | 文生图、图生图、图像编辑 | DALL-E 3、Midjourney、Stable Diffusion |
| 图像理解 | 图片描述、OCR、视觉推理 | GPT-4o Vision、Claude Vision、Gemini |
| 语音合成 (TTS) | 文本转语音、语音克隆 | OpenAI TTS、ElevenLabs、Fish Audio |
| 语音识别 (STT) | 语音转文本 | Whisper、Gemini |
| 代码执行 | 运行代码、沙箱执行 | Claude、CodeLlama |
| 视频生成 | 文生视频 | Sora API、Runway |
| 搜索增强 | 联网搜索 | Perplexity、Gemini |

模型在注册时声明自己的能力集合，平台根据能力自动适配交互方式。

### 2. 智能体系统 (Agent System)

每个智能体都是一个独立的 AI 角色，拥有自己的身份和能力。

**智能体定制**：
- 名称、人设描述、性格特征、说话风格、背景故事
- 能力特长设定（推理/创意/代码/谈判/领导）
- 自定义 system prompt
- 专属头像和语音音色

**预设模板**：

| 模板 | 描述 | 擅长领域 |
|------|------|----------|
| 谋略家 | 深谋远虑的战略家，擅长宏观分析 | 推理、领导 |
| 执行者 | 雷厉风行的执行者，高效精确 | 代码、推理 |
| 创意大师 | 天马行空的创意大脑 | 创意 |
| 谈判专家 | 经验丰富的谈判高手 | 谈判、领导 |
| 领导者 | 具有远见卓识的领袖 | 领导、推理 |

### 3. 对话引擎 (Conversation Engine)

支持 4 种对话模式，每个智能体维护独立的对话上下文。

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 自由对话 | 多个 AI 围绕话题自由讨论 | 头脑风暴、观点碰撞 |
| 辩论模式 | 正反方就指定论点结构化辩论 | 观点对比、深度分析 |
| 接力模式 | AI 依次续写完成任务 | 协作创作、代码开发 |
| 采访模式 | 一个 AI 采访其他 AI | 深度访谈、知识挖掘 |

**多模态消息流**：
- 消息支持文本、图片、音频、视频、代码等多种内容类型
- 对话中 AI 可以调用自己的任意能力（生成图片、语音朗读等）
- 其他 AI 可以看到并理解多模态内容

### 4. 竞技场 (Arena)

让 AI 同台竞技，投票评判。

| 竞技类型 | 说明 | 评判方式 |
|----------|------|----------|
| 问答 PK | 同一问题分别作答 | 用户投票 |
| 代码竞赛 | 编程题自动评测 | 测试用例通过率 |
| 创意比拼 | 同一主题各自创作 | 用户投票 |
| 推理挑战 | 逻辑推理题 | 正确率对比 |
| 生图对决 | 同一 prompt 各自生图 | 用户投票 |
| 配音 PK | 同一文本各自配音 | 用户投票 |

### 5. 游戏系统 (Game Room)

多种游戏类型，AI 扮演角色进行博弈。

**狼人杀**（已完整实现）：
- 6 个玩家：2 狼人、1 预言家、1 女巫、1 猎人、1 普通村民
- 夜晚阶段：狼人选择击杀、预言家查验身份、女巫救人或毒杀
- 白天阶段：所有存活玩家讨论，然后投票放逐一人
- 胜利条件：狼人全死（村民胜）或存活人数 ≤ 2 且有狼人（狼人胜）

**其他游戏类型**（框架已就绪）：
- 辩论赛：正式赛制的辩论对决
- 棋类对弈：国际象棋、围棋等
- 文字冒险：合作或竞争的文字 RPG
- 谈判游戏：资源分配、囚徒困境等博弈论场景

### 6. 宝可梦智能体训练 (Pokemon Showdown Lab)

面向 Pokemon Showdown 的长期智能体训练模块，当前以本地 VGC 双打模拟作为训练底座。

**已接入能力**：
- 本地 VGC 双打对战引擎：属性克制、伤害计算、速度顺序、换人、简化太晶和战斗日志
- 自动建队：智能体按等级和打法从队伍模板中生成队伍，高等级智能体可做轻量变体
- 对战学习：记录决策、奖励、对战分析和经验进化数据
- 联网知识：接入宝可梦知识检索和缓存入口，支持排位/用法数据查询，并可对 Showdown 会话整队批量研究
- 多格式目录：统一管理本地训练格式、Showdown 格式 ID、队伍人数、上场数量和是否需要自建队伍
- Showdown 协议命令层：可打包队伍、上传队伍、搜索天梯、发起/接受挑战、解析 `request/rqid` 并构建选择指令
- Showdown 自动选择：可将队伍预览、强制换人、普通出招请求转换为下一条 `/choose` 命令
- Showdown 战略首发：队伍预览阶段会按队伍招式、特性、模式、知识上下文和学习档案给首发排序
- Showdown 智能换人：强制换人会按 HP、队伍角色、学习档案和对手预览评分后排换入位
- Showdown 异常兜底：活动回合无可用招式且未被 trapped 时，会优先评分后排并换人，无法换人才使用 default
- Showdown 请求去重：会话按 battle room 与 `rqid` 记录已响应请求，避免 websocket 重复推送造成重复 `/choose`
- Showdown 自动驾驶韧性：websocket 接收失败会写入会话错误并返回可见 error step，避免长循环静默崩溃
- Showdown 运行摘要：有界自动运行和一键自动驾驶会返回 `run_summary`，汇总停止原因、步数、发送量、最后决策和错误
- Showdown 运行历史：会话快照保存最近 10 次自动运行摘要，前端可展示 Run 编号和最近停止原因
- Showdown 连接诊断：会话快照记录 websocket 连接、命令发送、消息接收和 assertion 登录阶段，失败时返回可见诊断错误
- Showdown 恢复计划：会话快照根据连接状态、错误阶段、待发命令、挑战和战后结果给出下一步动作建议
- Showdown 多格式目标策略：单打/随机战会省略普通招式 target 位，双打/VGC 会保留精确目标位，降低跨格式指令不合法风险
- Showdown 战术评分：对合法招式按伤害、功能招、铺场、模式偏好和自爆风险打分，并在前端显示选择依据
- Showdown 自动会话：可创建会话、连接 websocket、记录搜索/房间/胜负状态，并对 PS payload 自动产生命令流
- Showdown 房间同步：会话会记录 battle room 的玩家、对手、分级、规则、rated 状态、请求号和最终结果
- Showdown 场面记忆：会话从 `switch`、`drag`、`-damage`、`-heal`、`faint` 和 `request` 事件同步双方在场与 HP
- Showdown 队伍侦察：会话从 `poke` 事件同步双方预览阵容，并将对手预览反哺首发评分
- Showdown 挑战对战：会话可解析 `updatechallenges`，接受或拒绝指定挑战者；开启 `auto_accept_challenges` 后会自动接受同格式挑战，并将挑战命令发送到已连接 websocket
- Showdown 知识上下文：可将整队联网研究结果绑定到当前会话，供 UI、后续策略和学习流程复用
- Showdown 自动知识研究：创建会话时可开启 `auto_research_team`，系统会在自动建队后立即检索整队用法知识并绑定到会话
- Showdown 自动建队：创建或搜索需要队伍的格式时，缺省 `team` 会按格式自动选择本地模板队或生成 Showdown 可上传队伍
- Showdown 学习型建队：低胜率、低奖励或击倒劣势会反哺缺省队伍，自动补充 Protect 或降低高风险道具
- Showdown 学习型出招：弱势学习档案会反哺自动选择评分，优先提升 Protect 和防守型功能招的权重
- Showdown 队伍预览：会话快照返回 `team_preview`，前端可检查自动建队的宝可梦、道具、特性、太晶和招式
- Showdown 实战控制台：前端可创建会话、搜索天梯、连接 PS websocket、单步/有界自动运行、取消搜索和关闭连接
- Showdown 自动驾驶：可一键连接 websocket、排队天梯搜索、发送待发命令，并进入有界自动收发/决策循环
- Showdown 自动登录：收到 `challstr` 后可自动向 PS 请求 assertion 并发送 `/trn`，支持游客名或可选密码登录，密码不会回传到会话响应
- Showdown 学习摘要：可从真实协议事件中汇总回合、出招、换人、受伤、击倒、胜负和奖励信号
- Showdown 学习档案：将已完成实战摘要持久化到数据库，按用户和格式聚合胜率、平均奖励、决策类型收益，并给出下一局模式建议
- Showdown 即时学习回写：完成对战后会把最新学习档案同步回当前会话快照，前端策略面板可直接使用新样本
- Showdown 训练复盘：学习档案会输出训练重点，提示低胜率、击倒劣势、低奖励模式和需要审计的决策类型
- Showdown 自适应策略：创建会话时可使用 `mode=auto`，系统会读取学习档案并选择当前格式下收益最高的策略模式
- 前端训练台：`/pokemon` 页面支持初始化数据、创建智能体、自动建队、创建本地对战、推进回合、查看分析和调试 Showdown payload/会话

**后续深化目标**：
- 真实登录 `play.pokemonshowdown.com`
- 参与天梯匹配和房间对战
- 扩展真实对战数据反哺队伍构建、策略选择和强化学习
- 扩展单打、随机战、不同世代和更多官方/社区格式

### 7. 层级指挥系统 (Hierarchy)

智能体之间可建立上下级指挥关系。

```
         [将军 AI]
        /    |    \
  [军官 A] [军官 B] [军官 C]
   /    \     |
[士兵] [士兵] [士兵]
```

- 上级 AI 可以下发指令，下级 AI 必须执行
- 下级 AI 向上级汇报战况
- 支持树状和网状组织架构
- 适用于军事模拟、企业管理、团队对抗等场景

### 8. 经验进化系统 (Evolution)

智能体从每次交互中学习，不断提升能力。

**等级系统**：

| 等级 | 经验值 | 特征 |
|------|--------|------|
| 新手 (Novice) | 0-99 XP | 基础对话能力 |
| 熟练 (Proficient) | 100-499 XP | 开始展现策略性 |
| 专家 (Expert) | 500-1499 XP | 深度推理和创造力 |
| 大师 (Master) | 1500+ XP | 全面的高级能力 |

**经验来源**：
- 对话结束：5-20 XP（根据对话轮次和质量）
- 竞技场 PK：10-50 XP（根据排名）
- 游戏结束：20-100 XP（根据胜负和表现）

**进化机制**：
- 每次交互后自动提取经验教训
- system prompt 根据经验动态调整
- 经验可以跨场景迁移（辩论中学会的说服技巧可用于谈判）

### 9. 观战系统 (Spectator)

实时观看 AI 互动过程。

- **实时观战**：WebSocket 推送，实时观看对话和游戏
- **历史回放**：回放任意一场对话/游戏的完整过程
- **观战统计**：实时显示观战人数

### 10. 联网能力 (Internet Access)

智能体可以搜索互联网获取实时信息。

- DuckDuckGo 搜索集成
- 网页内容抓取
- SSRF 安全防护（阻止访问私有 IP）
- 用户可控的联网权限

---

## 快速开始

### 前置条件

- [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/)
- 至少一个 LLM API Key（OpenAI、Claude、DeepSeek 等）

### 使用 Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/momo6657/AI-Abattoir.git
cd AI-Abattoir

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，设置 SECRET_KEY 和其他配置

# 3. 启动所有服务
docker-compose up -d

# 4. 初始化数据（注册模型和智能体）
# 编辑 backend/.env.models 填入你的 API Key
docker-compose run --rm seed

# 5. 访问应用
# 前端：http://localhost:3000
# 宝可梦训练台：http://localhost:3000/pokemon
# API 文档：http://localhost:8000/docs
# MinIO 控制台：http://localhost:9001
```

宝可梦训练台首次使用时，可以直接在页面点击「准备训练环境」；它会调用后端初始化宝可梦数据、创建本地策略模型和两个训练智能体、自动构建双方队伍并创建一场本地 VGC 训练对战。也可以手动调用：

```bash
curl -X POST http://localhost:8000/api/pokemon/init
```

### 手动启动

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 执行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 环境变量

在 `backend/.env` 中配置：

```env
# 必填：JWT 密钥（请使用随机生成的强密钥）
SECRET_KEY=your-random-secret-key-here

# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_abattoir

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO 文件存储
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# CORS 允许的前端域名（逗号分隔）
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js 15)                   │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ 模型管理  │ │ 智能体   │ │ 对话引擎 │ │ 竞技场/游戏    │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ 排行榜   │ │ 观战     │ │ 进化日志 │ │ 层级管理       │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket + REST API
┌────────────────────────┴────────────────────────────────────┐
│                      Backend (FastAPI)                        │
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ │
│  │ 对话引擎    │ │ 游戏引擎    │ │ 评分系统 (Elo)         │ │
│  └─────────────┘ └─────────────┘ └────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ │
│  │ 层级指挥    │ │ 经验进化    │ │ 观战服务               │ │
│  └─────────────┘ └─────────────┘ └────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ │
│  │ LLM 适配    │ │ 图像适配    │ │ TTS/STT 适配           │ │
│  └─────────────┘ └─────────────┘ └────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐ │
│  │ 消息路由    │ │ 联网搜索    │ │ 媒体存储               │ │
│  └─────────────┘ └─────────────┘ └────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │PostgreSQL│   │  Redis   │   │   LLM APIs   │
    │  (数据)  │   │ (缓存/MQ)│   │ (多模型接入) │
    └──────────┘   └──────────┘   └──────────────┘
         ▼
    ┌──────────┐
    │  MinIO   │
    │ (文件存储)│
    └──────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Next.js 15 (App Router) | SSR、类型安全、快速开发 |
| UI 样式 | Tailwind CSS | 原子化 CSS，暗色主题 |
| 后端框架 | FastAPI | 异步高性能，自动 API 文档 |
| ORM | SQLAlchemy 2.0 (async) | 异步数据库操作 |
| 数据库迁移 | Alembic | 版本化数据库 schema |
| 数据库 | PostgreSQL 16 | 可靠的关系型数据库 |
| 缓存 | Redis 7 | 会话状态、消息队列 |
| 文件存储 | MinIO | S3 兼容的对象存储 |
| LLM 适配 | LiteLLM | 统一调用 100+ 种 LLM |
| 实时通信 | WebSocket | 双向实时通信 |
| 认证 | JWT + bcrypt | 安全的用户认证 |
| 容器化 | Docker + Docker Compose | 一键部署 |

---

## 项目结构

```
AI-Abattoir/
├── README.md                          # 项目文档
├── CLAUDE.md                          # Claude Code 开发指南
├── docker-compose.yml                 # Docker 编排配置
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                     # GitHub Actions CI
│
├── backend/                           # 后端服务
│   ├── Dockerfile
│   ├── requirements.txt               # Python 依赖
│   ├── alembic.ini                    # Alembic 配置
│   ├── alembic/
│   │   ├── env.py                     # 迁移环境
│   │   └── script.py.mako             # 迁移模板
│   └── app/
│       ├── main.py                    # FastAPI 入口
│       ├── core/
│       │   ├── config.py              # 配置管理
│       │   ├── database.py            # 数据库连接
│       │   └── security.py            # 认证安全
│       ├── models/                    # SQLAlchemy 数据模型
│       │   ├── user.py                # 用户模型
│       │   ├── model.py               # 模型配置
│       │   ├── agent.py               # 智能体（含 Profile/Hierarchy/Experience）
│       │   ├── conversation.py        # 对话和消息
│       │   ├── game.py                # 游戏和玩家
│       │   └── media.py               # 媒体资源
│       ├── schemas/                   # Pydantic 请求/响应模型
│       │   ├── model.py
│       │   ├── agent.py
│       │   ├── conversation.py
│       │   └── game.py
│       ├── api/                       # REST API 路由
│       │   ├── models.py              # 模型管理
│       │   ├── agents.py              # 智能体管理
│       │   ├── conversations.py       # 对话管理
│       │   ├── games.py               # 游戏/层级/进化
│       │   └── auth.py                # 用户认证
│       ├── services/                  # 业务逻辑
│       │   ├── llm_adapter.py         # LLM 统一调用适配器
│       │   ├── agent_service.py       # 智能体管理 + 模板
│       │   ├── conversation_engine.py # 对话引擎（4 种模式）
│       │   ├── message_router.py      # 消息路由
│       │   ├── game_engine.py         # 游戏引擎（狼人杀等）
│       │   ├── hierarchy_service.py   # 层级指挥系统
│       │   ├── evolution_service.py   # 经验进化系统
│       │   ├── spectator_service.py   # 观战与回放
│       │   ├── image_adapter.py       # 图像生成适配
│       │   ├── tts_adapter.py         # TTS/STT 适配
│       │   ├── search_service.py      # 联网搜索
│       │   └── media_storage.py       # 媒体文件存储
│       └── websocket/
│           └── manager.py             # WebSocket 连接管理
│
└── frontend/                          # 前端应用
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── lib/
        │   └── api.ts                 # API 客户端
        └── app/
            ├── layout.tsx             # 根布局（导航栏）
            ├── page.tsx               # 首页
            ├── models/page.tsx        # 模型管理
            ├── agents/page.tsx        # 智能体管理
            ├── conversations/page.tsx # 对话界面
            ├── arena/page.tsx         # 竞技场
            ├── games/page.tsx         # 游戏房间
            └── leaderboard/page.tsx   # 排行榜
```

---

## API 文档

启动后端后访问自动生成的 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### REST API

#### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录（返回 JWT） |
| GET | `/api/auth/me` | 获取当前用户信息 |
| POST | `/api/auth/github` | GitHub OAuth 登录 |

#### 模型管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 获取所有模型 |
| POST | `/api/models` | 创建模型配置 |
| GET | `/api/models/{id}` | 获取模型详情 |
| PUT | `/api/models/{id}` | 更新模型配置 |
| DELETE | `/api/models/{id}` | 删除模型 |

#### 智能体管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 获取所有智能体 |
| POST | `/api/agents` | 创建智能体 |
| GET | `/api/agents/{id}` | 获取智能体详情 |
| PUT | `/api/agents/{id}` | 更新智能体 |
| DELETE | `/api/agents/{id}` | 删除智能体 |
| GET | `/api/agents/{id}/evolution` | 获取进化信息 |
| GET | `/api/agents/{id}/experiences` | 获取经验列表 |

#### 对话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 获取所有对话 |
| POST | `/api/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 获取对话详情 |
| GET | `/api/conversations/{id}/messages` | 获取对话消息 |
| POST | `/api/conversations/{id}/start` | 启动自动对话 |
| POST | `/api/conversations/{id}/messages` | 发送消息 |
| POST | `/api/conversations/{id}/pause` | 暂停对话 |
| POST | `/api/conversations/{id}/resume` | 恢复对话 |
| POST | `/api/conversations/{id}/end` | 结束对话 |

#### 游戏管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/games` | 获取所有游戏 |
| POST | `/api/games` | 创建游戏 |
| GET | `/api/games/{id}` | 获取游戏详情 |
| POST | `/api/games/{id}/start` | 开始游戏 |
| POST | `/api/games/{id}/turn` | 推进一个回合 |
| GET | `/api/games/{id}/state` | 获取游戏状态 |
| POST | `/api/games/{id}/end` | 结束游戏 |

#### 宝可梦训练

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/pokemon/init` | 初始化本地宝可梦数据 |
| GET | `/api/pokemon/formats` | 获取支持的宝可梦对战格式目录 |
| GET | `/api/pokemon/formats/{id}` | 获取单个格式的本地/Showdown 映射 |
| GET | `/api/pokemon/species` | 获取宝可梦种族列表 |
| GET | `/api/pokemon/moves` | 获取招式列表 |
| GET | `/api/pokemon/teams?agent_id=...` | 获取智能体队伍 |
| POST | `/api/pokemon/teams/build` | 根据智能体等级和打法自动构建队伍 |
| POST | `/api/pokemon/battles` | 创建本地宝可梦对战 |
| GET | `/api/pokemon/battles/{id}/state` | 获取当前对战状态 |
| POST | `/api/pokemon/battles/{id}/turn` | 提交双方行动并推进一回合 |
| GET | `/api/pokemon/battles/{id}/analysis` | 获取对战日志分析 |
| POST | `/api/pokemon/battles/{id}/finalize` | 结算对战并写入经验进化 |
| GET | `/api/pokemon/battles/history` | 获取宝可梦对战历史 |
| GET | `/api/pokemon/knowledge/search` | 检索宝可梦知识库并缓存结果 |
| POST | `/api/pokemon/knowledge/team` | 批量检索 Showdown 队伍成员用法知识并返回整队上下文 |
| POST | `/api/pokemon/showdown/parse` | 解析 Pokemon Showdown 协议消息 |
| POST | `/api/pokemon/showdown/commands` | 构建上传队伍、搜索、挑战和对战选择等 Showdown 协议命令 |
| POST | `/api/pokemon/showdown/decision` | 将 Showdown `request` 转换为下一步自动选择计划，可传 `active_pokemon` 适配单打/双打 target 策略，也可传 `knowledge_context` 和 `learning_profile` 调整评分 |
| GET | `/api/pokemon/showdown/learning/profiles` | 列出 Showdown 学习档案 |
| GET | `/api/pokemon/showdown/learning/profile` | 获取指定用户和格式的胜率、平均奖励和模式建议 |
| POST | `/api/pokemon/showdown/sessions` | 创建 Showdown 自动会话状态机，缺省队伍时自动建队，`mode=auto` 时按学习档案选择策略模式，可用 `auto_accept_challenges` 自动接受同格式挑战，或用 `auto_research_team` 自动检索整队知识 |
| GET | `/api/pokemon/showdown/sessions` | 列出 Showdown 自动会话 |
| POST | `/api/pokemon/showdown/sessions/{id}/search` | 为会话生成并记录天梯搜索命令 |
| POST | `/api/pokemon/showdown/sessions/{id}/cancel-search` | 为会话生成并记录取消天梯搜索命令 |
| POST | `/api/pokemon/showdown/sessions/{id}/accept-challenge` | 接受指定或首个收到的 Showdown 挑战 |
| POST | `/api/pokemon/showdown/sessions/{id}/reject-challenge` | 拒绝指定或首个收到的 Showdown 挑战 |
| POST | `/api/pokemon/showdown/sessions/{id}/connect` | 连接 Showdown websocket 并发送待发命令 |
| POST | `/api/pokemon/showdown/sessions/{id}/flush` | 将会话队列里的待发命令发送到已连接 websocket |
| POST | `/api/pokemon/showdown/sessions/{id}/message` | 输入 PS payload 并返回自动响应命令 |
| POST | `/api/pokemon/showdown/sessions/{id}/knowledge` | 检索并绑定当前 Showdown 会话队伍的整队知识上下文 |
| GET | `/api/pokemon/showdown/sessions/{id}/analysis` | 汇总 Showdown 会话的胜负、击倒、奖励和决策学习信号 |
| POST | `/api/pokemon/showdown/sessions/{id}/run-once` | 从 websocket 读取一条消息、自动决策并发送命令 |
| POST | `/api/pokemon/showdown/sessions/{id}/run-until` | 有界运行 Showdown 自动会话循环 |
| POST | `/api/pokemon/showdown/sessions/{id}/autopilot` | 一键连接、搜索并运行有界 Showdown 自动驾驶循环 |
| POST | `/api/pokemon/showdown/sessions/{id}/close` | 关闭 Showdown websocket 会话 |
| DELETE | `/api/pokemon/showdown/sessions/{id}` | 删除 Showdown 自动会话 |

#### 层级与进化

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/hierarchy` | 创建层级关系 |
| GET | `/api/hierarchy/{agent_id}` | 获取层级树 |

#### 回放

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/replay/conversations/{id}` | 对话回放 |
| GET | `/api/replay/games/{id}` | 游戏回放 |

#### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |

### WebSocket 端点

| 路径 | 说明 | 通信方向 |
|------|------|----------|
| `/ws/conversations/{id}` | 对话实时通信 | 双向 |
| `/ws/spectate/conversation/{id}` | 观战对话 | 服务端 → 客户端 |
| `/ws/spectate/game/{id}` | 观战游戏 | 服务端 → 客户端 |
| `/ws/pokemon/battle/{id}` | 宝可梦本地对战实时通道 | 双向 |

---

## 开发指南

### 后端开发

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 生成数据库迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回退迁移
alembic downgrade -1

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

### 数据库操作

```bash
cd backend

# 创建新迁移
alembic revision --autogenerate -m "add_new_table"

# 执行所有待执行的迁移
alembic upgrade head

# 回退到指定版本
alembic downgrade <revision_id>

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

### 添加新的 LLM 提供商

1. 在 `backend/app/services/llm_adapter.py` 中添加适配逻辑
2. 在 `backend/app/models/model.py` 的 `CapabilityType` 中添加新能力类型（如需要）
3. 在前端模型管理页面添加对应的配置选项

### 添加新的游戏类型

1. 在 `backend/app/models/game.py` 的 `GameType` 枚举中添加新类型
2. 在 `backend/app/services/game_engine.py` 中实现游戏逻辑
3. 在前端游戏页面添加游戏类型卡片

---

## 配置说明

### Docker Compose 服务

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | Next.js 前端 |
| backend | 8000 | FastAPI 后端 |
| db | 5432 | PostgreSQL 数据库 |
| redis | 6379 | Redis 缓存 |
| minio | 9000/9001 | MinIO 文件存储 / 控制台 |

### 生产环境部署

1. 生成安全的 SECRET_KEY：
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. 配置 `.env` 文件中的所有密钥

3. 设置 ALLOWED_ORIGINS 为实际的前端域名

4. 使用 Docker Compose 启动：
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

---

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 如何贡献

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m "feat: add amazing feature"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

### 提交规范

使用语义化提交信息：

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复 bug |
| `docs:` | 文档更新 |
| `refactor:` | 重构 |
| `test:` | 测试相关 |
| `chore:` | 构建/工具相关 |
| `perf:` | 性能优化 |
| `style:` | 代码格式调整 |

### 开发规范

- 后端代码遵循 PEP 8 规范
- 前端代码使用 ESLint + Prettier 格式化
- 新功能需要添加对应的测试
- 提交前确保所有测试通过

---

## 路线图

- [x] 模型管理与多模态能力注册
- [x] 智能体定制与预设模板
- [x] 对话引擎（4 种模式）
- [x] 竞技场 PK 系统
- [x] 狼人杀游戏引擎
- [x] 层级指挥系统
- [x] 经验进化系统
- [x] 观战与回放
- [x] 用户认证
- [x] 联网搜索
- [x] 宝可梦 Showdown 整队联网研究入口
- [x] 宝可梦 Showdown 会话级知识上下文绑定
- [x] 宝可梦 Showdown 创建会话时自动整队知识研究
- [x] 宝可梦本地训练台（自动建队、本地对战、日志分析、知识检索入口）
- [x] 宝可梦多格式目录与 Showdown 格式选择（VGC、单打 OU、双打 OU、随机战）
- [x] 宝可梦 Showdown 缺省自动建队和队伍上传命令生成
- [x] 宝可梦 Showdown 自动建队可视化队伍预览
- [x] 宝可梦 Showdown 前端实战控制台（创建、搜索、连接、单步/有界运行、取消、关闭）
- [x] 宝可梦 Showdown challstr 自动 assertion 登录
- [x] 宝可梦 Showdown 挑战接受/拒绝和待发命令发送
- [x] 宝可梦 Showdown 同格式挑战自动接受策略
- [x] 宝可梦 Showdown 战术评分和选择解释
- [x] 宝可梦 Showdown 单打/双打 target 策略适配
- [x] 宝可梦 Showdown 会话事件分析与奖励信号
- [x] 宝可梦 Showdown 学习档案训练重点和前端复盘展示
- [x] 宝可梦 Showdown battle room 元数据同步和前端展示
- [x] 宝可梦 Showdown 一键自动驾驶（连接、搜索、收发、自动决策）
- [x] 宝可梦 Showdown 学习档案反哺缺省队伍调整
- [x] 宝可梦 Showdown 学习档案反哺自动出招评分
- [x] 宝可梦 Showdown 战后学习档案即时回写当前会话
- [x] 宝可梦 Showdown 队伍预览战略首发评分
- [x] 宝可梦 Showdown 房间场面记忆与低血量目标选择
- [x] 宝可梦 Showdown poke 队伍侦察与对手预览首发评分
- [x] 宝可梦 Showdown 强制换人后排评分
- [x] 宝可梦 Showdown 无可用招式 fallback 换人
- [x] 宝可梦 Showdown request/rqid 去重防重复出招
- [x] 宝可梦 Showdown 自动驾驶接收错误可见化
- [x] 宝可梦 Showdown 连续运行结构化摘要和前端展示
- [x] 宝可梦 Showdown 会话级最近运行历史
- [x] 宝可梦 Showdown 真实连接和登录阶段诊断
- [x] 宝可梦 Showdown 自动驾驶恢复计划和下一步动作建议
- [ ] Pokemon Showdown 真实登录和天梯实战
- [ ] 宝可梦完整多格式战斗策略（单打、随机战、不同世代规则）
- [ ] 宝可梦强化学习闭环与长期策略评估
- [ ] Elo 评分排名系统
- [ ] 更多游戏类型（棋类、文字冒险）
- [ ] 多模态竞技（生图对决、配音 PK）
- [ ] 团队对抗模式
- [ ] 插件系统
- [ ] 移动端适配
- [ ] 国际化支持

---

## 常见问题

### Q: 如何添加自己的 LLM API Key？

A: 在前端「模型管理」页面点击「添加模型」，选择提供商，填入 API Key 和模型 ID 即可。

### Q: 支持哪些 LLM？

A: 通过 LiteLLM 支持 100+ 种模型，包括 OpenAI、Claude、Gemini、DeepSeek、通义千问、文心一言等。

### Q: 如何让 AI 玩狼人杀？

A: 1) 创建至少 6 个智能体 → 2) 进入游戏页面 → 3) 选择「狼人杀」→ 4) 选择参与的智能体 → 5) 开始游戏 → 6) 点击「下一回合」推进游戏。

### Q: 如何查看 AI 的进化过程？

A: 在智能体详情页可以看到等级、经验值和成长日志。每次对话/游戏结束后，AI 会自动记录经验并可能升级。

### Q: 数据库迁移失败怎么办？

A: 检查 PostgreSQL 是否正常运行，然后执行 `alembic upgrade head`。如果 schema 有冲突，可以 `alembic downgrade base` 后重新迁移。

---

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 Star 支持一下！**

[![Star History Chart](https://api.star-history.com/svg?repos=momo6657/AI-Abattoir&type=Date)](https://star-history.com/#momo6657/AI-Abattoir&Date)

</div>

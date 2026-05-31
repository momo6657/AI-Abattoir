# Pokemon Showdown 适配设计规格

## 项目概述

为 AI Abattoir 平台添加宝可梦对战功能，让智能体能够在 Pokemon Showdown 平台上进行对战、学习和进化，最终成为宝可梦大师。

## 目标

1. 智能体能够使用宝可梦队伍进行对战
2. 智能体能够根据等级选择队伍策略（新手模仿 → 高手创新）
3. 智能体通过强化学习从对战中学习和进化
4. 支持本地模拟训练和真实 PS 服务器对战

## 技术方案

### 实现阶段

**Phase 1（2-3周）**：本地对战引擎 + 基础 AI 决策
- 实现简化版宝可梦对战规则（伤害计算、属性克制、基础技能）
- 智能体能进行基本对战（选技能、换宝可梦）
- 使用固定队伍模板（从知识库爬取 Top 10 队伍）

**Phase 2（2-3周）**：知识系统 + 学习机制
- 构建宝可梦数据库（种族值、技能、道具）
- 实现联网搜索 + Redis 缓存
- 添加轻量级强化学习（记录决策质量）

**Phase 3（2-3周）**：队伍构建 + 进化系统
- 智能体根据等级选择队伍策略
- 经验系统与宝可梦对战深度集成
- 对战回放与分析

**Phase 4（3-4周）**：PS 服务器连接
- 实现 PS WebSocket 协议
- 智能体可以登录并参与天梯
- 真实对战数据反哺训练

## 架构设计

### 核心模块

```
Pokemon Battle System
├── Data Layer (数据层)
│   ├── PokemonSpecies (宝可梦种族)
│   ├── PokemonMove (技能)
│   ├── PokemonAbility (特性)
│   ├── PokemonItem (道具)
│   └── TypeEffectiveness (属性克制)
├── Team Management (队伍管理)
│   ├── PokemonTeam (队伍配置)
│   ├── TeamBuilder (队伍构建器)
│   └── TeamTemplate (队伍模板)
├── Battle Engine (对战引擎)
│   ├── LocalBattleEngine (本地模拟)
│   ├── ShowdownConnector (PS连接器)
│   └── BattleState (对战状态)
├── Decision Engine (决策引擎)
│   ├── PokemonAI (AI决策)
│   ├── DecisionRecorder (决策记录)
│   └── ReinforcementLearning (强化学习)
├── Knowledge System (知识系统)
│   ├── KnowledgeCache (知识缓存)
│   ├── DataCrawler (数据爬虫)
│   └── SearchIntegration (搜索集成)
└── Battle History (对战历史)
    ├── BattleRecord (对战记录)
    ├── BattleReplay (对战回放)
    └── BattleAnalysis (对战分析)
```

### 数据模型

详见下方数据库 Schema 设计。

## 功能需求

### 1. 数据管理

- 存储宝可梦种族数据（种族值、属性、特性、技能池）
- 存储技能数据（威力、命中、效果、优先度）
- 存储道具和特性数据
- 属性克制表
- 支持多形态宝可梦（洗翠、伽勒尔等）
- 支持第九世代太晶机制

### 2. 队伍管理

- 智能体可以拥有多个队伍
- 队伍包含 6 只宝可梦的完整配置（种族、技能、努力值、性格、道具、太晶属性）
- 队伍来源：模板/自定义/进化
- 队伍评分系统（Elo）
- 根据智能体等级选择队伍策略：
  - Novice/Proficient：使用经过验证的模板队伍
  - Expert/Master：尝试自己的组合和创新

### 3. 对战引擎

#### 本地模拟引擎（Phase 1）

- 支持 VGC 双打格式
- 实现核心对战机制：
  - 伤害计算（物理/特殊/固定伤害）
  - 属性克制（0x, 0.5x, 1x, 2x, 4x）
  - 命中判定
  - 暴击判定
  - 速度计算和行动顺序
  - 换宝可梦机制
  - 太晶化机制
- 简化实现（Phase 1 不包含）：
  - 复杂状态（麻痹、烧伤、中毒等）
  - 天气和场地效果
  - 能力变化（+1/-1 等）
  - 复杂技能效果（守住、替身等）

#### PS 服务器连接器（Phase 4）

- WebSocket 连接到 Pokemon Showdown 服务器
- 协议解析和消息处理
- 登录和房间管理
- 天梯匹配
- 对战状态同步

### 4. AI 决策引擎

- 基于 LLM 的决策系统
- 决策类型：
  - 选择技能（4 个技能 + 目标选择）
  - 换宝可梦（6 只宝可梦选择）
  - 是否太晶化
- 决策输入：
  - 当前场面状态（我方/对方宝可梦、HP、状态）
  - 队伍信息
  - 历史行动
  - 知识库信息（属性克制、技能效果）
- 决策输出：
  - 结构化的行动指令
  - 决策置信度
  - 推理过程（调试用）

### 5. 知识系统

#### 本地知识库

- 常用宝可梦数据（Top 100）
- 属性克制表
- 基础技能效果
- 队伍模板（从排位数据库爬取）

#### 联网搜索

- 集成现有 search_service
- 搜索目标网站：
  - pokechamdb.com (中文)
  - pokedb.tokyo (日文)
  - limitlessvgc.com (英文)
- 搜索内容：
  - 宝可梦使用率
  - 热门队伍配置
  - 对战录像分析
- Redis 缓存策略：
  - 缓存时间：7 天
  - 缓存键：query_type + query_key
  - 自动过期清理

### 6. 强化学习系统

#### 决策记录

- 记录每个决策点的状态-行动-奖励
- 状态哈希：快速查找相似局面
- 置信度和 Q 值估计

#### 奖励函数

- 即时奖励：
  - 造成伤害：+damage_percent
  - 击倒对手：+50
  - 我方被击倒：-50
  - 换宝可梦到有利对位：+20
  - 换宝可梦到不利对位：-20
- 最终奖励（对战结束后回填）：
  - 胜利：+100
  - 失败：-100
  - 平局：0

#### 学习机制

- 对战结束后分析所有决策
- 计算每个决策的贡献度
- 更新 Q 值估计
- 下次遇到相似状态时，优先选择高 Q 值行动
- 探索 vs 利用平衡（ε-greedy）

### 7. 经验进化系统

- 复用现有 evolution_service
- 宝可梦对战经验值：
  - 对战完成：20-100 XP（根据对手强度）
  - 胜利加成：1.5x
  - 连胜加成：最多 2x
- 等级提升触发行为变化：
  - Novice → Proficient：解锁自定义队伍
  - Proficient → Expert：开始尝试创新组合
  - Expert → Master：可以连接 PS 服务器实战
- 记录关键经验：
  - "使用火系技能对抗草系效果显著"
  - "在对方有钢系时不要使用毒系技能"
  - "速度优势时优先使用高威力技能"

### 8. 对战历史与回放

- 完整对战日志（JSONB 格式）
- 对战摘要（避免每次解析完整日志）：
  - MVP 宝可梦
  - 关键时刻（暴击、击倒等）
  - 伤害统计
  - 换宝可梦次数
- WebSocket 实时观战
- 历史对战回放
- PS replay 链接保存

### 9. API 端点

#### REST API

- `GET /api/pokemon/species` - 获取宝可梦列表
- `GET /api/pokemon/species/{id}` - 获取宝可梦详情
- `GET /api/pokemon/moves` - 获取技能列表
- `GET /api/pokemon/teams` - 获取队伍列表
- `POST /api/pokemon/teams` - 创建队伍
- `GET /api/pokemon/teams/{id}` - 获取队伍详情
- `PUT /api/pokemon/teams/{id}` - 更新队伍
- `DELETE /api/pokemon/teams/{id}` - 删除队伍
- `POST /api/pokemon/battles` - 创建对战
- `GET /api/pokemon/battles/{id}` - 获取对战详情
- `POST /api/pokemon/battles/{id}/start` - 开始对战
- `GET /api/pokemon/battles/{id}/state` - 获取对战状态
- `POST /api/pokemon/battles/{id}/action` - 提交行动
- `GET /api/pokemon/battles/history` - 获取对战历史
- `GET /api/pokemon/knowledge/search` - 搜索知识库

#### WebSocket

- `/ws/pokemon/battles/{id}` - 对战实时通信
- `/ws/pokemon/spectate/{id}` - 观战对战

### 10. 前端界面

- 宝可梦对战室页面
- 队伍构建器
- 对战历史列表
- 对战回放播放器
- 智能体宝可梦统计页面

## 数据库 Schema

详见优化后的数据模型设计（已在头脑风暴中确认）。

## 技术栈

- **后端框架**：FastAPI
- **数据库**：PostgreSQL（宝可梦数据、对战记录）
- **缓存**：Redis（知识缓存、RL 数据）
- **LLM 适配**：LiteLLM（AI 决策）
- **搜索**：现有 search_service（联网查询）
- **实时通信**：WebSocket（对战实时推送）
- **前端**：Next.js 15 + TypeScript

## 非功能需求

### 性能

- 本地对战引擎：每回合决策 < 5 秒
- 知识查询：缓存命中 < 100ms，未命中 < 3 秒
- 对战历史查询：< 500ms

### 可扩展性

- 架构支持后续添加其他对战格式（单打、随机对战等）
- 数据模型支持未来世代的新机制
- 决策引擎可插拔（支持不同 AI 算法）

### 可维护性

- 清晰的模块划分
- 完整的单元测试覆盖
- 详细的 API 文档
- 代码注释和类型标注

## 风险与挑战

1. **对战规则复杂度**：宝可梦对战规则极其复杂，Phase 1 需要简化
2. **LLM 决策质量**：初期 AI 可能很弱，需要通过强化学习逐步提升
3. **PS 协议实现**：Phase 4 需要逆向工程 PS 的 WebSocket 协议
4. **数据获取**：需要爬取多个网站的数据，可能遇到反爬虫
5. **性能优化**：对战日志可能很大，需要优化存储和查询

## 成功标准

### Phase 1

- [ ] 智能体能够完成一场完整的 VGC 双打对战
- [ ] 伤害计算和属性克制正确
- [ ] 对战日志完整记录
- [ ] 前端能够实时观战

### Phase 2

- [ ] 本地知识库包含 Top 100 宝可梦数据
- [ ] 联网搜索功能正常，缓存命中率 > 80%
- [ ] 强化学习系统记录所有决策
- [ ] Q 值估计逐步收敛

### Phase 3

- [ ] 智能体能够根据等级选择队伍策略
- [ ] 新手智能体使用模板队伍
- [ ] 高级智能体能够创建自定义队伍
- [ ] 对战回放功能完整

### Phase 4

- [ ] 智能体能够登录 PS 服务器
- [ ] 能够参与天梯匹配
- [ ] 真实对战数据正确记录
- [ ] 至少一个智能体达到 1200+ 天梯分

## 参考资料

- Pokemon Showdown 官网：https://play.pokemonshowdown.com/
- Pokemon Showdown GitHub：https://github.com/smogon/pokemon-showdown
- 宝可梦数据库：
  - https://pokechamdb.com/zh-Hans
  - https://pokedb.tokyo
  - https://limitlessvgc.com
- VGC 规则：https://www.pokemon.com/us/pokemon-news/2024-video-game-championships-format-rules

# 部署方案（免费/低成本）

## 方案一：Vercel + Railway（推荐）

完全免费，适合个人项目和演示。

### 前端 → Vercel

Vercel 是 Next.js 官方平台，免费额度充足。

```bash
# 1. 安装 Vercel CLI
npm i -g vercel

# 2. 在 frontend 目录部署
cd frontend
vercel

# 3. 设置环境变量（在 Vercel 控制台）
# NEXT_PUBLIC_API_URL = https://your-backend.railway.app/api
# NEXT_PUBLIC_WS_URL = wss://your-backend.railway.app
```

### 后端 → Railway

Railway 每月 $5 免费额度，足够开发/演示用。

```bash
# 1. 安装 Railway CLI
npm i -g @railway/cli

# 2. 登录
railway login

# 3. 在 backend 目录初始化
cd backend
railway init

# 4. 添加 PostgreSQL
railway add

# 5. 设置环境变量
railway variables set SECRET_KEY=your-secret-key
railway variables set ALLOWED_ORIGINS=https://your-frontend.vercel.app

# 6. 部署
railway up
```

### 数据库 → Neon（免费 PostgreSQL）

Neon 提供免费的 Serverless PostgreSQL。

1. 注册 https://neon.tech
2. 创建项目，获取连接字符串
3. 格式：`postgresql+asyncpg://user:pass@ep-xxx.aws.neon.tech/dbname`

### Redis → Upstash（免费 Redis）

Upstash 提供免费的 Serverless Redis。

1. 注册 https://upstash.com
2. 创建 Redis 数据库
3. 获取 URL 设置到环境变量

---

## 方案二：Render（全平台免费）

Render 提供免费的 Web Service 和 PostgreSQL。

### 步骤

1. 注册 https://render.com
2. **数据库**：New → PostgreSQL → Free tier
3. **后端**：New → Web Service → 连接 GitHub 仓库
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - 环境变量：DATABASE_URL, SECRET_KEY 等
4. **前端**：New → Static Site → 连接 GitHub 仓库
   - Build Command: `cd frontend && npm install && npm run build`
   - Publish Directory: `frontend/.next`

注意：Render 免费版有 30 秒冷启动，首次访问较慢。

---

## 方案三：本地 Docker + ngrok（临时公网访问）

适合临时演示或测试。

```bash
# 1. 本地启动
docker-compose up -d

# 2. 安装 ngrok
# https://ngrok.com/download

# 3. 暴露后端
ngrok http 8000

# 4. 暴露前端
ngrok http 3000
```

ngrok 免费版每次重启 URL 会变。

---

## 方案四：GitHub Codespaces（开发环境）

GitHub 提供免费的 Codespaces 额度（60 小时/月）。

```bash
# 在 GitHub 仓库页面：
# Code → Codespaces → Create codespace

# 启动后自动配置开发环境
docker-compose up -d
```

---

## 环境变量清单

| 变量 | 说明 | 示例 |
|------|------|------|
| DATABASE_URL | PostgreSQL 连接字符串 | postgresql+asyncpg://... |
| REDIS_URL | Redis 连接字符串 | redis://... |
| SECRET_KEY | JWT 密钥 | 随机字符串 |
| ALLOWED_ORIGINS | CORS 允许的前端地址 | https://xxx.vercel.app |
| MINIO_ENDPOINT | MinIO 地址（可选） | - |
| GITHUB_CLIENT_ID | GitHub OAuth（可选） | - |
| GITHUB_CLIENT_SECRET | GitHub OAuth（可选） | - |

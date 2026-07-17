# 完整可点：公网后端（Postgres）+ GitHub Pages

前端已在 Pages：`https://zzming-tjufe.github.io/yangmind/`  
浏览器**不能**访问你电脑上的 `127.0.0.1`，所以还要把后端 + 数据库挂到公网。

本地 Postgres / 迁移说明见 [`DATABASE_POSTGRES.md`](./DATABASE_POSTGRES.md)。

下面用 **Render** 举例（免费额度够演示）。

---

## A. 一键 Blueprint（推荐）

仓库根目录已有 `render.yaml`（Web + Postgres）。

1. 打开 https://dashboard.render.com → **New +** → **Blueprint**
2. 连接 GitHub 仓库 `zzming-tjufe/yangmind`（或你的 fork）
3. 按提示创建；在环境变量里为 `SEED_ADMIN_PASSWORD` 填：`1234asdF`（或你的强密码）
4. 等 Database + Web Service 都变绿
5. 打开 Web 服务地址：`https://yangmind-api-xxxx.onrender.com/health`  
   应看到 `{"ok":true,...}`

免费库第一次冷启动可能要 30–60 秒。

---

## B. 手动创建（不用 Blueprint 时）

### B1. 先建 PostgreSQL

1. Render → **New +** → **PostgreSQL**
2. Name：`yangmind-db`，Plan：Free
3. 创建后复制 **Internal Database URL**（给 Web Service 用）或 External URL（本机迁移用）

### B2. 再建 Web Service

1. **New + → Web Service**，选同一仓库
2. 填写：

| 项 | 值 |
|----|-----|
| Name | `yangmind-api` |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

3. **Environment**：

| Key | Value |
|-----|--------|
| `APP_ENV` | `production` |
| `SECRET_KEY` | 随机长串（≥32，不要用默认开发密钥） |
| `DATABASE_URL` | 上一步 Postgres 的连接串（`postgres://` 也可） |
| `CORS_ORIGINS` | `https://zzming-tjufe.github.io,http://127.0.0.1:5173,http://localhost:5173` |
| `SEED_ADMIN_PASSWORD` | `1234asdF` |
| `SEED_ADMIN_LOGIN` | `admin` |
| `SEED_ADMIN_EMAIL` | `admin@yangmind.cn` |

注意：`CORS_ORIGINS` 写 **origin**（协议+域名），**不要**带 `/yangmind/` 路径。

4. Deploy 变绿后访问：`https://你的服务.onrender.com/health`

### B3. （可选）把本地数据迁到线上库

在本机 `backend` 目录（需能访问 Render **External** Database URL）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL="这里粘贴 Render External Database URL"
python scripts/migrate_sqlite_to_postgres.py --sqlite ./yangmind.db --postgres $env:DATABASE_URL
```

若线上只要空库 + 种子管理员，可跳过本步，首次启动会自动建表并写入 `admin`。

---

## C. 前端接上公网 API

1. 打开：https://github.com/zzming-tjufe/yangmind/settings/secrets/actions  
2. **New repository secret**

| Name | Secret |
|------|--------|
| `VITE_API_BASE` | `https://yangmind-api-xxxx.onrender.com` |

**不要**末尾斜杠，**不要**写成 `.../api/v1`。

3. 重新跑 Pages 工作流：

- https://github.com/zzming-tjufe/yangmind/actions  
- **Deploy frontend to GitHub Pages** → **Run workflow**

强制刷新：https://zzming-tjufe.github.io/yangmind/

管理员：`admin` / `1234asdF`

---

## D. 自检清单

| 检查 | 期望 |
|------|------|
| `/health` | 返回 ok |
| F12 → Network | 登录打到 `onrender.com`，不是 `127.0.0.1` |
| CORS 报错 | `CORS_ORIGINS` 含 Pages 域名，改完需 Manual Deploy |
| 登录 500 | 看 Render Logs；多半是 `DATABASE_URL` 未配或库未就绪 |
| 仍打本地 | Secret 未改或未重新构建 Pages |

---

## 本地开发不受影响

```
# frontend/.env
VITE_API_BASE=http://127.0.0.1:8003
```

```
# 仓库根目录
docker compose up -d
# backend/.env 里 DATABASE_URL 指向本地 Docker Postgres
```

Pages 用的是 Actions Secret，与本地 `.env` 互不覆盖。

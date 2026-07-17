# 数据库：SQLite → PostgreSQL

目标：本地与线上都用 Postgres；把现有 `backend/yangmind.db` 迁过去。

## 本地（Docker）

### 1. 启动 Docker Desktop

若 `docker info` 失败，先打开 Docker Desktop，等引擎就绪。

### 2. 启动 Postgres

在仓库根目录：

```powershell
docker compose up -d
docker compose ps
```

默认库：

| 项 | 值 |
|----|----|
| 主机 | `127.0.0.1:5432` |
| 库名 | `yangmind` |
| 用户 / 密码 | `yangmind` / `yangmind` |
| URL | `postgresql+psycopg://yangmind:yangmind@127.0.0.1:5432/yangmind` |

### 3. 安装驱动并迁移

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/migrate_sqlite_to_postgres.py
```

脚本会：

1. 在 Postgres 建表  
2. 清空目标表（默认 `--wipe`）  
3. 按外键顺序拷贝 SQLite 数据（保留原 id）  
4. 重置自增序列  

### 4. 切后端到 Postgres

`backend/.env` 已示例为 Postgres URL。确认包含：

```env
DATABASE_URL=postgresql+psycopg://yangmind:yangmind@127.0.0.1:5432/yangmind
```

重启 uvicorn：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

用原账号登录验证；管理员仍是 `admin` / `1234asdF`（启动 seed 会同步该管理员）。

旧文件 `yangmind.db` 可保留作备份，不再作为运行库。

---

## 上线（Render 等）

推荐用仓库根目录的 [`render.yaml`](../render.yaml) Blueprint 一键创建 **Web + Postgres**。  
逐步说明见 [`DEPLOY_PUBLIC_API.md`](./DEPLOY_PUBLIC_API.md)。

手动时，Web Service 环境变量至少包含：

| Key | Value |
|-----|--------|
| `DATABASE_URL` | 平台给的连接串（`postgres://` 也可，后端会自动改成 `postgresql+psycopg://`） |
| `SECRET_KEY` | 随机长串 |
| `APP_ENV` | `production` |
| `CORS_ORIGINS` | 你的 Pages 域名 |
| `SEED_ADMIN_PASSWORD` | 管理员密码 |

若线上要带本地数据：在能访问该库的机器上跑：

```powershell
$env:DATABASE_URL="平台给你的URL"
python scripts/migrate_sqlite_to_postgres.py --sqlite ./yangmind.db --postgres $env:DATABASE_URL
```

免费实例休眠或磁盘策略因平台而异；正式环境务必用托管 Postgres，不要再用 SQLite 文件。

---

## 回退到 SQLite（仅调试）

```env
DATABASE_URL=sqlite:///./yangmind.db
```

重启后端即可。生产不要这样用。

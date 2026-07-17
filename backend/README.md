# YangMind Lab 后端

技术栈：Python + FastAPI + PostgreSQL（本地 Docker）/ 仍兼容 SQLite

## 启动

先起数据库（仓库根目录）：

```powershell
docker compose up -d
```

再起 API：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

从旧 SQLite 迁数据：见 [`docs/DATABASE_POSTGRES.md`](../docs/DATABASE_POSTGRES.md)。

文档：http://127.0.0.1:8003/docs

### 安全配置

- 开发可用默认密钥；启动时会打印警告。
- **生产**请设置：

```powershell
$env:APP_ENV="production"
$env:SECRET_KEY="你的随机长串至少32字符"
```

未设置或仍用默认密钥时，生产环境会**拒绝启动**。

## 管理端新增

| 能力 | 接口 |
|------|------|
| 用户启用/禁用 | `PATCH /api/v1/admin/users/{id}/status` |
| 重置密码 | `POST /api/v1/admin/users/{id}/reset-password` |
| 实验列表/开关/排序 | `/api/v1/admin/experiments...` |
| 场景启用 | `PATCH /api/v1/admin/scenes/{id}` |
| 邀请码 | `/api/v1/admin/invite-codes` |
| 账号事件 | `GET /api/v1/admin/account-events` |
| 导出 CSV | `/api/v1/admin/export/users\|surveys\|rounds.csv` |

管理员：唯一账号 `admin`（密码见配置 `SEED_ADMIN_PASSWORD`，默认 `1234asdF`）。  
注册不再因 `admin@` 前缀自动成为管理员。

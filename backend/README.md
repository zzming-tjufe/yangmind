# YangMind Lab 后端

技术栈：Python + FastAPI + SQLite（开发）

## 启动

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

文档：http://127.0.0.1:8003/docs

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

管理员：`admin@` 开头邮箱。

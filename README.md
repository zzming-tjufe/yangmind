# YangMind Lab

人格与合作博弈实验平台。

## 目录说明

| 路径 | 说明 |
|------|------|
| `index.html` / `app.js` / `styles.css` / `YangMind-Lab.html` | **旧演示前端**（保留，不删） |
| `frontend/` | **正式前端** React + Vite，已对接后端 API |
| `backend/` | FastAPI + SQLite 后端 |
| `docs/` | 设计文档 |

## 推荐启动方式（正式链路）

终端 1 — 数据库（仓库根目录，需 Docker Desktop）：

```powershell
docker compose up -d
```

终端 2 — 后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

终端 3 — 前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173（若 `127.0.0.1` 打不开可改用 http://localhost:5173）

数据库说明与 SQLite 迁移：[`docs/DATABASE_POSTGRES.md`](./docs/DATABASE_POSTGRES.md)

唯一管理员（启动时自动同步）：

- 账号：`admin`（也可用邮箱 `admin@yangmind.cn`）
- 密码：`1234asdF`

也可用环境变量 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` / `SEED_ADMIN_LOGIN` 覆盖。  
注册不会再因 `admin@` 前缀自动成为管理员。

旧演示仍可双击根目录 `index.html` 查看（不连后端）。

## 用 GitHub Pages 给前端同事预览

部署说明见 [`docs/DEPLOY_GITHUB_PAGES.md`](./docs/DEPLOY_GITHUB_PAGES.md)。

预览地址形态：`https://<你的用户名>.github.io/yangmind/`

公网后端（**不用国外信用卡**）：
- 建库：[`docs/NEON_SETUP.md`](./docs/NEON_SETUP.md)
- **已有阿里云：直接部署（推荐）**：[`docs/DEPLOY_ALIYUN.md`](./docs/DEPLOY_ALIYUN.md)
- Zeabur 说明（现需自有服务器）：[`docs/ABOUT_ZEABUR.md`](./docs/ABOUT_ZEABUR.md)
- 备选 HF：[`docs/DEPLOY_HUGGINGFACE.md`](./docs/DEPLOY_HUGGINGFACE.md)

旧方案 Render 见 [`docs/DEPLOY_PUBLIC_API.md`](./docs/DEPLOY_PUBLIC_API.md)（常需绑卡，可忽略）。

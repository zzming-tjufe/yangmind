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

终端 1 — 后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

终端 2 — 前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173

旧演示仍可双击根目录 `index.html` 查看（不连后端）。

## 用 GitHub Pages 给前端同事预览

部署说明见 [`docs/DEPLOY_GITHUB_PAGES.md`](./docs/DEPLOY_GITHUB_PAGES.md)。

预览地址形态：`https://<你的用户名>.github.io/yangmind/`

注意：线上页面访问不到本机 `127.0.0.1` 后端；完整登录需另挂公网 API，并配置仓库 Secret `VITE_API_BASE`。

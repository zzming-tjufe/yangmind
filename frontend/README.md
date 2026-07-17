# YangMind Lab 正式前端（React + Vite）

根目录的 `index.html` / `app.js` / `styles.css` 仍是**旧演示版**，未删除。
本目录是对接后端 API 的新前端。

## 启动

先开后端（另开终端）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

再开前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开终端提示的地址（一般是 http://127.0.0.1:5173 ）。

API 地址在 `.env` 的 `VITE_API_BASE`，默认 `http://127.0.0.1:8003`。

# 用 GitHub Pages 预览前端

给前端同事看 UI 时，可用 GitHub Pages 生成固定网址。

## 一次性步骤

1. 在 GitHub 新建空仓库（建议名 `yangmind`，公开或私有均可；Pages 对私有仓库需 GitHub Pro，免费账号请用 **Public**）。
2. 本地初始化并推送：

```powershell
cd D:\zzmin\Desktop\yangmind
git init
git add .
git commit -m "Initial commit: YangMind Lab frontend + backend"
git branch -M main
git remote add origin https://github.com/<你的用户名>/yangmind.git
git push -u origin main
```

3. 仓库打开 **Settings → Pages**：
   - Source 选 **GitHub Actions**
4. 打开 **Actions**，确认工作流 `Deploy frontend to GitHub Pages` 跑通。
5. 预览地址一般为：

`https://<你的用户名>.github.io/yangmind/`

## 重要：接口地址

线上页面**打不开你电脑上的** `http://127.0.0.1:8003`。

- 只看登录页 / 静态布局：可以，点登录会失败。
- 要完整可点：需要把后端也挂到公网（如 Render / Railway / 云主机），然后在仓库：

  **Settings → Secrets and variables → Actions**

  新增 Secret：`VITE_API_BASE` = `https://你的公网API地址`（不要末尾斜杠）

  同时后端 CORS 要允许：

  `https://<你的用户名>.github.io`

  再重新跑一次 Actions 部署。

## 本地仍怎么跑

```powershell
# 后端
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8003

# 前端
cd frontend
copy .env.example .env
npm run dev
```

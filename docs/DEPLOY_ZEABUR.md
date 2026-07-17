# 免费后端备选（HF 不可用时）

Hugging Face 在国内常出现 **418 / 打不开 / 构建失败**。数据库继续用 Neon，只换「跑 FastAPI 的地方」。

---

## 方案对比（不用国外信用卡）

| 方案 | 适合 | 注意 |
|------|------|------|
| **Zeabur Free**（推荐） | 长期给同学点 | 注册一般不用绑卡；空闲会休眠；有免费额度 |
| **cpolar / Cloudflare Tunnel** | 答辩当天 | 电脑要开着，关机就挂 |
| 腾讯云/阿里云学生机 | 想要稳定 | 微信/支付宝，要学生认证，不是纯 0 元但很便宜 |
| Hugging Face | 备选 | 国内网络差时容易 418 |

Render / Railway / Cloud Run：常要外卡，先跳过。

---

## 推荐：Zeabur 部署 YangMind 后端

官网：https://zeabur.com （可用 GitHub 登录）

### 1. 新建项目并导入仓库

1. 注册 / 登录 Zeabur（**Free Plan，文档写明无需信用卡**）
2. **Create Project** → **Deploy from GitHub** → 授权并选 `yangmind` 仓库
3. 若让你选根目录 / 服务类型：
   - 选 **Python** 或让它自动识别
   - Root Directory 设为：`backend`
4. Start / Run 命令（若需手填）：

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Build 一般会 `pip install -r requirements.txt`（目录已是 `backend`）。

### 2. 环境变量（和 HF 相同）

在服务 **Variables** 里添加：

| Key | Value |
|-----|--------|
| `APP_ENV` | `production` |
| `SECRET_KEY` | ≥32 位随机串 |
| `DATABASE_URL` | Neon 的 URI（整段） |
| `CORS_ORIGINS` | `https://zzming-tjufe.github.io,http://127.0.0.1:5173,http://localhost:5173` |
| `SEED_ADMIN_PASSWORD` | `1234asdF` |
| `SEED_ADMIN_LOGIN` | `admin` |
| `SEED_ADMIN_EMAIL` | `admin@yangmind.cn` |

生成密钥：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Neon 连接串注意

在 Neon **Connect** 窗口：

- Database：`neondb`
- Role：`neondb_owner`
- **Connection pooling：建议先关掉再复制一次「直连」URI**（给长期跑的 uvicorn 更稳）  
  若 Zeabur 报连接数问题，再改回带 `-pooler` 的串。
- 必须带 `sslmode=require`

> 若连接串曾发在聊天/截图里，请在 Neon 点 **Reset password**，用新 URI。

### 4. 部署成功后自检

Zeabur 会给一个公网域名，例如：

```text
https://yangmind-api-xxxx.zeabur.app
```

打开：

```text
https://你的域名/health
```

应返回 `{"ok":true,...}`。再试 `/docs`。

### 5. 前端接上

GitHub → Settings → Secrets → Actions：

```text
VITE_API_BASE=https://你的Zeabur域名
```

然后跑一遍 **Deploy frontend to GitHub Pages**。

---

## 临时方案：cpolar（本机穿透）

适合今晚就要给别人点、电脑能一直开着。

1. 本机照常：`docker compose up -d` + `uvicorn` 在 `8003`
2. 注册 https://www.cpolar.com （国内站，微信即可）
3. 安装后执行：

```powershell
cpolar http 8003
```

4. 把显示的公网 https 地址填进 `VITE_API_BASE`（或临时告诉同学直接访问该地址的 `/docs`）

关机或断网即失效。

---

## 和 Neon 的关系

```
前端 Pages  →  Zeabur / cpolar 上的 FastAPI  →  Neon Postgres
```

库不用重建；只换 API 宿主。

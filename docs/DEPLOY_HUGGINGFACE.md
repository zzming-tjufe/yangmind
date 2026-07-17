# 公网后端（免外卡）：Neon 数据库 + Hugging Face Spaces

适合没有国外信用卡的情况。前端继续用 GitHub Pages。

大约分 4 步，按顺序做即可。

---

## 总览

```
同学浏览器
   → GitHub Pages 前端
   → Hugging Face 上的 FastAPI
   → Neon 免费 Postgres
```

本地开发不变：仍用 `docker compose` + 本机 Postgres。

---

## 第 1 步：注册 Neon（免费库）

> **版本不知道选哪个？** 看超详细说明：[`NEON_SETUP.md`](./NEON_SETUP.md)  
> 结论先说：**Postgres 选 16**（没有就选 17）；地区选 **Singapore**。

1. 打开 https://console.neon.tech/signup ，用 **GitHub / 邮箱** 注册（一般不用绑卡）。
2. **Create a project**
   - Project name：`yangmind`
   - **Postgres version：选 `16`**（界面默认可能是 18，请手动改成 16）
   - Region：`Asia Pacific (Singapore)` / `aws-ap-southeast-1`
3. 创建后进入 **Dashboard → Connection details / Connect**
4. 复制 **Connection string（URI）**，类似：

```text
postgresql://用户名:密码@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

先存进记事本。后面填到 HF 环境变量 `DATABASE_URL`。

> 若 Neon 也提示要卡：改用国内云学生机装 Postgres，或答辩当天用本机 + 隧道。数据库 URL 用法相同。

---

## 第 2 步：创建 Hugging Face Space（跑后端）

1. 打开 https://huggingface.co ，注册 / 登录（邮箱即可，**不用绑卡**）。
2. 右上角头像 → **New Space**
3. 填写：

| 项 | 建议值 |
|----|--------|
| Space name | `yangmind-api` |
| License | MIT（随意） |
| Select the Space SDK | **Docker** |
| Space hardware | **CPU basic · Free** |
| Visibility | Public（演示用） |

4. 点 **Create Space**。

### 把代码推到这个 Space

**方式 A（推荐）：用网页上传**

在 Space 页 → **Files** → **Add file** → **Upload files**，上传仓库里的：

- 根目录 `Dockerfile`
- 整个 `backend/app/` 文件夹（保持路径，上传后应是 `backend/app/...`）
- `backend/requirements.txt`（路径为 `backend/requirements.txt`）

也就是 Space 里最终要有：

```text
Dockerfile
backend/requirements.txt
backend/app/...
```

（与本仓库根目录结构一致；`Dockerfile` 已按这个结构写好。）

**方式 B：Git 推送**

```powershell
# 在 Hugging Face → Settings → Access Tokens 建一个 Write token
git clone https://huggingface.co/spaces/你的用户名/yangmind-api
cd yangmind-api
# 从本仓库复制 Dockerfile、backend/app、backend/requirements.txt 进来
git add .
git commit -m "deploy yangmind api"
git push
```

推送后 Space 会自动 Build，右侧日志变绿即成功。

---

## 第 3 步：在 Space 里填环境变量

打开 Space → **Settings** → **Variables and secrets** → **New secret**（敏感信息用 Secret）：

| Name | Value | 说明 |
|------|--------|------|
| `DATABASE_URL` | 第 1 步 Neon 连接串 | 整段粘贴 |
| `SECRET_KEY` | 一串随机字符（≥32） | 见下方生成命令 |
| `APP_ENV` | `production` | 固定 |
| `CORS_ORIGINS` | `https://zzming-tjufe.github.io,http://127.0.0.1:5173,http://localhost:5173` | 按你的 Pages 域名改 |
| `SEED_ADMIN_PASSWORD` | `1234asdF` | 管理员密码 |
| `SEED_ADMIN_LOGIN` | `admin` | 登录别名 |
| `SEED_ADMIN_EMAIL` | `admin@yangmind.cn` | 可选 |

生成本地随机密钥（PowerShell）：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

保存变量后，到 Space **Settings** 点一次 **Factory reboot**（或等它自动重启）。

### 自检后端

浏览器打开（把用户名换成你的）：

```text
https://你的用户名-yangmind-api.hf.space/health
```

应看到：

```json
{"ok":true,"service":"yangmind-api","version":"0.1.0"}
```

也可打开 `/docs` 看接口文档。

管理员登录试一下：账号 `admin`，密码 `1234asdF`。

---

## 第 4 步：让 GitHub Pages 前端连上它

1. 打开仓库 Secrets：  
   https://github.com/zzming-tjufe/yangmind/settings/secrets/actions  
2. 新建或更新：

| Name | Value |
|------|--------|
| `VITE_API_BASE` | `https://你的用户名-yangmind-api.hf.space` |

**不要**末尾斜杠，**不要**加 `/api/v1`。

3. 重新部署前端：  
   Actions → **Deploy frontend to GitHub Pages** → **Run workflow**
4. 强制刷新：https://zzming-tjufe.github.io/yangmind/  
   F12 → Network：登录请求应打到 `hf.space`，不是 `127.0.0.1`。

---

## （可选）把本地数据迁到 Neon

本机 `backend` 目录：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/migrate_sqlite_to_postgres.py --sqlite ./yangmind.db --postgres "这里粘贴 Neon 的 DATABASE_URL"
```

迁完后重启一下 HF Space。若只要空库 + 管理员，可跳过，首次启动会自动建表和种子账号。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `/health` 打不开 | 等 Build 完成；看 Space 日志有没有报错 |
| 生产启动拒绝：SECRET_KEY | 密钥太短或用了默认值，换 ≥32 随机串 |
| CORS 报错 | `CORS_ORIGINS` 必须含 `https://zzming-tjufe.github.io`（无路径） |
| 第一次很慢 | Free Space 休眠后冷启动，等 30–60 秒再试 |
| Neon 连不上 | 连接串是否带 `sslmode=require`；HF 变量名是否为 `DATABASE_URL` |
| 前端仍打本地 | Secret 没改或没重新跑 Pages 工作流 |

---

## 和本地的关系

| 环境 | 后端 | 数据库 |
|------|------|--------|
| 本机开发 | `uvicorn` @ 8003 | Docker Postgres |
| 公网演示 | Hugging Face Space | Neon |

两边互不影响。改代码后：本机直接跑；公网需把更新后的文件再推到 Space（或再 Upload）。

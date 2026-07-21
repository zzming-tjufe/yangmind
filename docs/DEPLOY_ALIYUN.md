# 阿里云轻量 / ECS 部署 YangMind 后端（推荐）

你已经有 **2 核 2G** 机器时，**不必再买 Zeabur / HF**。  
数据库继续用 **Neon**（在云上），服务器只跑 FastAPI，2G 内存完全够。

为什么够用：

| 组件 | 跑在哪 | 大概占用 |
|------|--------|----------|
| Postgres | Neon（远程） | 不占你阿里云内存 |
| FastAPI + uvicorn | 阿里云 | 通常几十～一两百 MB |
| 系统本身 | 阿里云 | 留 500MB+ 给系统即可 |

不要在 2G 机器上再装一套 Postgres（除非你不用 Neon），否则才可能吃紧。

---

## 0. 准备信息

- 阿里云公网 IP（或已绑定的域名）
- SSH 能登录（root 或普通用户）
- Neon 的 `DATABASE_URL`（整段 URI，建议用直连、带 `sslmode=require`）
- 安全组放行：**22**（SSH）、**8003**（或 80/443）

---

## 1. 登录服务器

本机 PowerShell / 终端：

```powershell
ssh root@你的公网IP
```

（若用密钥或非 root 用户，按你平时习惯即可。）

建议系统：**Ubuntu 22.04**。若是 CentOS，命令略有不同，可再说我帮你改。

---

## 2. 安装 Python 与 Git

```bash
apt update
apt install -y python3 python3-venv python3-pip git
python3 --version
```

---

## 3. 拉取代码

```bash
cd /opt
git clone https://github.com/zzming-tjufe/yangmind.git
cd yangmind/backend
```

若仓库是私有的，用你有权限的地址，或本机 `scp` 上传 `backend` 目录。

---

## 4. 虚拟环境与依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

---

## 5. 写环境变量

```bash
nano /opt/yangmind/backend/.env
```

粘贴（按你的真实值改）：

```env
APP_ENV=production
SECRET_KEY=这里填至少32位随机串
DATABASE_URL=这里粘贴Neon整段URI
CORS_ORIGINS=https://zzming-tjufe.github.io,http://127.0.0.1:5173,http://localhost:5173
SEED_ADMIN_PASSWORD=1234asdF
SEED_ADMIN_LOGIN=admin
SEED_ADMIN_EMAIL=admin@yangmind.cn
```

生成密钥（可在本机跑）：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

保存退出（nano：`Ctrl+O` 回车，`Ctrl+X`）。

---

## 6. 先手动试跑

```bash
cd /opt/yangmind/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8003
```

本机浏览器或手机流量访问：

```text
http://你的公网IP:8003/health
```

看到 `{"ok":true,...}` 即成功。  
`Ctrl+C` 停掉后，再做成开机自启。

若超时：检查阿里云安全组是否放行 **入方向 TCP 8003**。

---

## 7. 做成 systemd 服务（关掉 SSH 也继续跑）

```bash
nano /etc/systemd/system/yangmind-api.service
```

写入：

```ini
[Unit]
Description=YangMind Lab API
After=network.target

[Service]
User=root
WorkingDirectory=/opt/yangmind/backend
EnvironmentFile=/opt/yangmind/backend/.env
ExecStart=/opt/yangmind/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8003
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
systemctl daemon-reload
systemctl enable yangmind-api
systemctl start yangmind-api
systemctl status yangmind-api
```

看日志：

```bash
journalctl -u yangmind-api -f
```

---

## 8. 前端（推荐：Nginx 同域反代，不必对外暴露 8003）

浏览器只访问前端端口（如 **8081**），由 Nginx 把 `/api/` 转到本机 `8003`。这样校园网/公司网拦非标端口时也能注册登录。

### Nginx（`/etc/nginx/sites-available/yangmind`）

```nginx
server {
    listen 8081;
    server_name 你的公网IP;

    root /opt/yangmind/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8003;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8003/health;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
nginx -t && systemctl reload nginx
```

### 构建前端（同域，VITE_API_BASE 留空）

```bash
cd /opt/yangmind/frontend
export VITE_API_BASE=
export VITE_BASE=/
npm install
npm run build
```

验证：打开 `http://你的公网IP:8081/health` 应返回 JSON；注册时 Network 里请求应是 `8081/api/v1/...` 而不是 `:8003`。

若仍用直连后端：`VITE_API_BASE=http://你的公网IP:8003`，并确保安全组放行 8003。

管理员：`admin` / `1234asdF`。

---

## 9. 更新代码时

```bash
cd /opt/yangmind
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart yangmind-api
```

---

## 和 Zeabur 的关系（你看到的界面）

现在的 Zeabur Free 主要是：

- **绑定你自己的服务器**（阿里云也行），或  
- **向他们买服务器**

它**不再是**「点一下就送一台免费跑 Python 的机器」。  
所以你已经有阿里云时：**直接 SSH 部署更简单**，不必绕 Zeabur。

若仍想用 Zeabur 面板管阿里云：把这台 2C2G「添加为自有服务器」即可，本质还是跑在你机器上，规格一样够用。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 外网打不开 `/health` | 安全组放行 8003；`uvicorn` 必须 `--host 0.0.0.0` |
| 前端能开、注册提示连不上 | 优先用第 8 节 Nginx 同域反代；勿让浏览器直连 8003 |
| 启动报 SECRET_KEY | `APP_ENV=production` 时密钥不能用默认短密钥 |
| 连不上 Neon | URI 是否完整、是否 `sslmode=require`；服务器能否访问外网 |
| 内存不够 | 几乎不会；用 `free -h` 看一下；不要本机再装 Postgres |
| git clone 失败 | 用 HTTPS + token，或本机打包 scp 上传 |

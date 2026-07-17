# Neon 免费数据库：从注册到复制连接串（超详细）

给「第一次建云数据库、不知道版本选哪个」的同学。  
做完这一篇，你手里会有一串 `DATABASE_URL`，下一步再挂 Hugging Face 后端。

配套总流程：[`DEPLOY_HUGGINGFACE.md`](./DEPLOY_HUGGINGFACE.md)

---

## 0. 你要选什么？（先看结论）

创建项目时界面里常见选项，**照抄下面即可**：

| 选项 | 选什么 | 为什么 |
|------|--------|--------|
| **Postgres version（版本）** | **16** | 和咱们本地 Docker（`postgres:16`）一致，最省心。若列表没有 16，选 **17** 也完全可以。 |
| **Region（地区）** | **Asia Pacific (Singapore)** / `aws-ap-southeast-1` | 对中国访问通常更近。没有新加坡就选离亚洲近的。 |
| **Project name** | `yangmind` | 随便起，好认就行。 |
| **Database name** | 默认 `neondb` 即可 | 不用改。 |
| **Compute / 套餐** | Free / 默认免费档 | 不要选要绑卡的付费档。 |

> **版本会不会选错？**  
> 对本项目几乎不会。YangMind 用的是普通 SQLAlchemy 表，**16 / 17 / 18 都能跑**。  
> 唯一建议：本地 Docker 是 16，所以云上也优先 16，以后排错更一致。  
> **版本一旦建好不能改大版本**，选错了就新建一个项目再迁数据，所以第一次尽量选对。

---

## 1. 注册 Neon

1. 浏览器打开：https://console.neon.tech/signup  
   （或官网 https://neon.tech → **Sign up**）
2. 推荐用 **Continue with GitHub**（和你们仓库同一账号最省事）。  
   也可用邮箱注册。
3. 若弹出问卷（公司规模、用途）：随便选 **Personal / Hobby / Learning** 之类，点继续。
4. **一般不需要国外信用卡**。若强制要卡，停下来告诉我，我们换国内学生云方案。

登录成功后，应进入 Neon Console（控制台）。

---

## 2. 创建项目（重点：版本怎么选）

### 2.1 打开创建页

- 若是第一次：常会直接弹出 **Create a project**  
- 若已有项目：左上角 **Projects** → **New Project** / **Create project**

### 2.2 逐项填写

界面文案可能略有出入，按「意思」对应：

#### ① Project name（项目名）

填：

```text
yangmind
```

#### ② Postgres version（PostgreSQL 版本）

下拉里可能看到：`14` `15` `16` `17` `18`（默认有时是 **18**）。

**请手动改成 `16`。**

- 选 **16** ← 推荐  
- 没有 16 → 选 **17**  
- 实在只能默认 18 → **也可以**，不影响本项目使用  

不要纠结小版本（如 16.4、16.14），Neon 会自动管小版本更新，你只需选**大版本数字**。

#### ③ Region（区域）

优先：

```text
Asia Pacific (Singapore)
```

或 ID 类似：`aws-ap-southeast-1`

备选（从好到一般）：

1. Singapore  
2. 其它 Asia / Tokyo / Sydney（若有）  
3. 欧美区（能用但可能稍慢）

> 区域**建完不能改**，选新加坡最省事。

#### ④ 其它开关

若看到：

- **Enable autoscaling / Scale to zero**：保持默认（免费档通常会休眠，正常）  
- **Create branching / 示例分支**：默认即可  
- **Postgres 扩展**：不用勾选额外东西  

### 2.3 点创建

点 **Create Project** / **Create**。

等几秒，进入项目 Dashboard。

---

## 3. 复制连接串（DATABASE_URL）

1. 在项目首页找到 **Connection details** / **Connect** / **Connection string**
2. 连接方式选：
   - **Connection string** 或 **URI**
   - 驱动/角色若可选：选默认角色即可（常叫 `neondb_owner` 一类）
3. 勾选或确认带 **SSL**（URI 里通常有 `sslmode=require`）
4. 点复制按钮，得到类似：

```text
postgresql://neondb_owner:一长串密码@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

### 重要检查

| 检查 | 应该 |
|------|------|
| 开头 | `postgresql://` 或 `postgres://`（都行，后端会自动兼容） |
| 中间 | 有一长串密码，不要漏复制 |
| 结尾 | 有 `?sslmode=require`（强烈建议有） |
| 不要 | 不要选 “localhost” 那种本地示例 |

把整串粘到记事本保存，后面填到 Hugging Face 的 `DATABASE_URL`。

> 密码只显示一次或需点小眼睛查看。丢了可在 Console 里 **Roles** 重置密码，再复制新 URI。

---

## 4. （可选）在网页里确认库是空的、版本对

1. 左侧打开 **SQL Editor**
2. 运行：

```sql
SELECT version();
```

应看到类似 `PostgreSQL 16.x ...`（或你选的 17/18）。

3. 再运行：

```sql
SELECT current_database();
```

一般是 `neondb`。

此时表还是空的，正常：等后端第一次启动或跑迁移脚本才会建表。

---

## 5. （可选）把本地数据灌进 Neon

本机已有 `backend/yangmind.db` 时：

```powershell
cd D:\zzmin\Desktop\yangmind\backend
.\.venv\Scripts\Activate.ps1
python scripts\migrate_sqlite_to_postgres.py --sqlite .\yangmind.db --postgres "这里粘贴 Neon 整段 URI"
```

看到 `Done. Migrated ... rows` 即成功。

若你只要空库 + 管理员账号，**可跳过本步**：HF 后端第一次启动会自动建表并种子 `admin`。

---

## 6. 做完 Neon 之后干什么？

回到总教程继续第 2 步（建 Hugging Face Space）：

➡️ [`DEPLOY_HUGGINGFACE.md`](./DEPLOY_HUGGINGFACE.md)

把刚复制的 URI 填进 Space 环境变量：

```text
DATABASE_URL=（Neon 整段）
```

---

## 常见疑问

**Q：默认是 18，我必须改成 16 吗？**  
A：不必须。16 只是和本地 Docker 对齐。选 18 也能跑 YangMind。

**Q：选错版本了怎么办？**  
A：删掉/废弃该项目，新建一个选对版本。免费档多建一个项目通常没问题。

**Q：Free 和 Launch 有什么区别？**  
A：做课堂演示选 **Free**。Launch 是付费起步档，没外卡就别点。

**Q：Compute size 选 0.25 CU 还是更大？**  
A：默认最小即可。

**Q：提示要 Credit Card？**  
A：先换浏览器无无痕、或换 GitHub 登录再试；仍要卡就别用 Neon，改国内学生云 / 答辩当天本机隧道，告诉我帮你换文档路径。

**Q：连接串里的密码含特殊字符会不会坏？**  
A：从 Console 复制的 URI 一般已编码好，整段粘贴，不要手改。

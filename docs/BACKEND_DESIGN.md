# YangMind Lab 后端与数据库设计文档

> 状态：设计草案（不修改任何现有代码）  
> 范围：后端服务、数据库、项目架构演进  
> 约束：**现有前端行为与 UI 保持不变**；后端以「可对接」为原则设计，前端接入可另开阶段  
>  
> **小白白话 / 学习路线**请先读：[`BACKEND_LEARNING_GUIDE.md`](./BACKEND_LEARNING_GUIDE.md)  
> **默认技术栈（学习向）**：Python + FastAPI + PostgreSQL + JWT（详见学习指南 §6）

---

## 1. 目标与约束

### 1.1 产品目标

YangMind Lab 是人格测量（BFI-44）与合作博弈实验平台，需要：

- 真实账号体系（参与者 / 管理员）
- 问卷作答持久化与人格维度计算
- 博弈对局记录（轮次级）与实验完成判定
- 管理端数据查询、实验配置、账号与内容管理
- 排行榜与运营统计可基于真实数据聚合

### 1.2 硬约束

| 约束 | 说明 |
|------|------|
| 不改现有前端 | `index.html` / `styles.css` / `app.js` / `YangMind-Lab.html` 本期零改动 |
| 演示版可继续运行 | 当前双击打开 HTML 的本地演示路径保持可用 |
| 后端可独立演进 | 后端与数据库可先落地，前端对接作为后续阶段 |

### 1.3 设计原则

1. **前端契约先行**：以现有 `app.js` 的状态机与页面字段倒推 API / 表结构，保证未来接入成本最低。
2. **演示与生产分离**：演示前端继续纯本地；生产通过同一套 API，由后续「适配层」替换内存状态。
3. **研究数据优先**：问卷与对局数据按「可复现实验」标准设计（原始作答、轮次明细、时间戳、版本号）。
4. **渐进落地**：鉴权 → 问卷 → 博弈 → 管理/统计，分阶段上线。

---

## 2. 现状摘要（前端契约）

当前仓库仅为前端演示，无后端、无数据库。核心内存状态与隐含实体如下。

### 2.1 角色与路由

| 角色 | 进入条件（演示） | 主要视图 |
|------|------------------|----------|
| `user` | 非 `admin@` 邮箱登录 | `bfi` / `games` / `rank` |
| `admin` | 邮箱以 `admin@` 开头 | `users` / `experiments` / `accounts` / `pages` / `content` |

### 2.2 关键业务流（参与者）

```
注册/登录
  → BFI 理论导读
  → BFI-44（44 题，1–5 分，分 4 组）
  → 提交后解锁博弈
  → 猎鹿博弈：2 个必做场景 × 各 10 轮
  → 两场景均完成后计为实验完成
  → 排行榜展示累计得分等
```

### 2.3 猎鹿博弈收益矩阵（需后端一致实现）

| 你 \ 对方 | A | B |
|-----------|---|---|
| A | 10 / 10 | 0 / 6 |
| B | 6 / 0 | 6 / 6 |

- 场景：`task`（双人小组任务）、`travel`（出行安排）
- 「对方」当前为前端随机；后端需明确对局模式（见 §5.3）

### 2.4 管理端已暴露、待后端支撑的能力

- 用户列表、人格画像（E/A/C/N/O）
- 实验列表增删改序、开放状态
- 注册策略、登录安全、邀请码
- 页面管理、内容管理（问卷说明 / 场景文案 / 公告）

### 2.5 前端明确不持久化的点（后端必须补齐）

- 登录不校验密码、无会话
- 问卷答案仅在内存（`state.answers`）
- 博弈结果仅在内存（`state.stagResults`）
- 用户/排行榜/统计为写死 mock
- 对手选择为 `Math.random()`，非服务端权威

---

## 3. 目标架构（推荐）

在**不改前端**的前提下，建议把仓库演进为「前端静态资源 + 独立后端」的单体仓库（monorepo 式目录），而不是继续把逻辑塞进单个 HTML。

### 3.1 建议目录结构（未来落地时采用）

```
yangmind/
├── docs/                      # 设计与 API 文档（本文件所在）
│   └── BACKEND_DESIGN.md
├── frontend/                  # 现有前端原样迁入（或暂留根目录不动）
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── YangMind-Lab.html      # 可标记为 legacy 演示包
├── backend/                   # 新建后端（本期仅设计，不实现）
│   ├── src/
│   │   ├── main/              # 启动入口
│   │   ├── config/
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── users/
│   │   │   ├── surveys/
│   │   │   ├── games/
│   │   │   ├── experiments/
│   │   │   ├── ranking/
│   │   │   ├── admin/
│   │   │   └── content/
│   │   ├── common/            # 错误码、中间件、DTO
│   │   └── infra/             # DB、缓存、邮件（可选）
│   ├── migrations/            # SQL 迁移
│   ├── tests/
│   ├── package.json / pyproject.toml / go.mod  # 视选型而定
│   └── README.md
├── docker-compose.yml         # 本地 Postgres + 后端（可选）
└── README.md                  # 总览：演示前端 / 后端开发说明
```

**说明：**

- 现有 4 个前端文件可以**暂时继续留在仓库根目录**，避免任何移动带来的路径风险；正式拆分时再整体迁入 `frontend/`。
- `YangMind-Lab.html` 建议长期仅作「离线演示包」，生产以 `index.html` 三文件为准。

### 3.2 逻辑架构

```
┌─────────────────────────────────────────────┐
│  Browser（现有前端，本期不变）                │
│  app.js 内存状态机 / 本地演示                 │
└──────────────────┬──────────────────────────┘
                   │  后续阶段：HTTP/JSON API
                   ▼
┌─────────────────────────────────────────────┐
│  API Gateway / Backend                      │
│  Auth · Survey · Game · Admin · Rank        │
└──────────┬───────────────────┬──────────────┘
           │                   │
           ▼                   ▼
     ┌──────────┐        ┌──────────┐
     │ Postgres │        │ Redis*   │
     │ 主数据   │        │ 会话/限流 │
     └──────────┘        └──────────┘
* Redis 可选；MVP 可用 DB + JWT 无状态会话
```

### 3.3 推荐技术栈（学习项目已默认锁定）

| 层级 | 本项目默认（学习向） | 备选（熟悉 JS 全栈时可换） |
|------|----------------------|----------------------------|
| 语言 / 框架 | **Python + FastAPI** | Node.js + Fastify / Express |
| ORM | SQLAlchemy 2.x + Alembic | Prisma / Drizzle |
| 数据库 | **PostgreSQL 16** | MySQL 8（次选） |
| 鉴权 | **JWT**（Access；Refresh 可选） | Session Cookie |
| 密码 | bcrypt / Argon2 | — |
| 部署 | Docker Compose → 单机或云主机 | — |

选型原则：一人学习 + 正式可上线；优先可读性与 `/docs` 自测体验。不必上微服务。  
白话说明与关卡式学习路线见 `BACKEND_LEARNING_GUIDE.md`。

### 3.4 「不改前端」下的对接策略

分两阶段，避免现在就改 `app.js`：

| 阶段 | 做法 |
|------|------|
| A. 后端先行（本期） | 完成后端 + DB + OpenAPI；用 Postman / 集成测试验证 |
| B. 前端适配（后续） | 在 `app.js` 旁新增 `api-client.js`，把 `submitAccount` / `submitSurvey` / `playRound` 等改为调 API；或用薄适配层保持函数签名 |

本期设计保证：所有关键字段与业务流程能被现有 UI 直接消费，无需重新设计页面。

---

## 4. 领域模型

### 4.1 核心实体关系（概念）

```
User 1───1 Profile
User 1───* SurveyResponse ───* SurveyAnswer
User 1───* PersonalityScore（可由 SurveyResponse 派生）
User 1───* GameSession ───* GameRound
Experiment 1───* ExperimentScene
ExperimentScene 1───* GameSession
InviteCode *───* User（可选）
AdminAuditLog *─── User(admin)
ContentBlock / PageConfig（CMS 轻量）
```

### 4.2 角色

| role | 权限概要 |
|------|----------|
| `participant` | 问卷、博弈、看自己的结果与排行榜 |
| `admin` | 用户数据、实验配置、账号策略、内容/页面管理 |

演示里 `admin@*` 规则可映射为：`email` 域名或显式 `role` 字段；生产以 DB 角色为准，不用邮箱前缀硬编码。

---

## 5. 数据库设计

字符集：`utf8mb4`（MySQL）或默认 UTF-8（Postgres）。时间一律存 UTC（`timestamptz`）。

### 5.1 表清单

#### `users`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID / BIGSERIAL PK | 内部主键 |
| public_id | VARCHAR(32) UNIQUE | 展示用 ID，如 `U-1024` |
| email | CITEXT / VARCHAR UNIQUE | 登录邮箱 |
| password_hash | VARCHAR | Argon2id / bcrypt |
| nickname | VARCHAR(64) | 昵称 |
| role | ENUM(`participant`,`admin`) | 角色 |
| status | ENUM(`pending`,`active`,`locked`,`disabled`) | 账号状态 |
| email_verified_at | TIMESTAMPTZ NULL | 邮箱验证时间 |
| failed_login_count | INT DEFAULT 0 | 连续失败次数 |
| locked_until | TIMESTAMPTZ NULL | 锁定截止 |
| invite_code_id | FK NULL | 注册所用邀请码 |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`email`、`public_id`、`role+status`。

#### `invite_codes`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| code | VARCHAR UNIQUE | 邀请码 |
| max_uses / used_count | INT | 用量 |
| expires_at | TIMESTAMPTZ NULL | |
| enabled | BOOLEAN | |
| created_by | FK users | |

#### `auth_sessions`（若用服务端 Session；JWT 可省略或仅存 Refresh）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | FK | |
| refresh_token_hash | VARCHAR | |
| expires_at | TIMESTAMPTZ | |
| ip / user_agent | VARCHAR | 审计 |
| revoked_at | TIMESTAMPTZ NULL | |

#### `survey_instruments`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| code | VARCHAR UNIQUE | 如 `BFI-44` |
| version | VARCHAR | 题库版本，便于修订 |
| title | VARCHAR | |
| item_count | INT | 44 |
| config_json | JSONB | 分组、量表文案、质量规则 |

#### `survey_items`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| instrument_id | FK | |
| item_no | INT | 1–44 |
| stem | TEXT | 「我认为自己是一个…的人」中的描述 |
| dimension | CHAR(1) | E/A/C/N/O |
| reverse_scored | BOOLEAN | 反向计分题 |
| sort_order | INT | |

> 演示前端把 44 句写死在 `bfi` 数组；后端以题库表为准，便于修订且保留版本。

#### `survey_responses`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | FK | |
| instrument_id | FK | |
| instrument_version | VARCHAR | 提交时版本快照 |
| status | ENUM(`in_progress`,`submitted`,`invalid`) | |
| started_at / submitted_at | TIMESTAMPTZ | 用于质量：作答时长 |
| quality_flags | JSONB | 长串同选项、正反向不一致等 |
| quality_passed | BOOLEAN | |

唯一约束建议：`(user_id, instrument_id)` 在 `submitted` 态只允许一条有效记录（或允许多次但标记 `is_latest`）。

#### `survey_answers`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| response_id | FK | |
| item_no | INT | |
| value | SMALLINT | 1–5 |
| answered_at | TIMESTAMPTZ | |

唯一：`(response_id, item_no)`。

#### `personality_scores`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | FK | |
| response_id | FK | |
| e / a / c / n / o | NUMERIC(3,2) | 1.00–5.00 |
| summary_label | VARCHAR | 如「高开放 · 高宜人」 |
| computed_at | TIMESTAMPTZ | |

计分规则：按维度均分；反向题先转换 `6 - value`。具体题-维度映射需与标准 BFI-44 计分表对齐（实现阶段写入 `survey_items` + 服务逻辑）。

#### `experiments`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| code | VARCHAR UNIQUE | `stag_hunt` / `prisoner` |
| title | VARCHAR | |
| status | ENUM(`draft`,`active`,`archived`) | |
| sort_order | INT | 管理端排序 |
| rounds_per_scene | INT DEFAULT 10 | |
| config_json | JSONB | 收益矩阵、规则文案等 |

#### `experiment_scenes`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| experiment_id | FK | |
| scene_key | VARCHAR | `task` / `travel` |
| no | VARCHAR | `01` / `02` |
| title | VARCHAR | |
| short_desc | TEXT | |
| option_a / option_b | VARCHAR | |
| option_a_text / option_b_text | TEXT | |
| required | BOOLEAN DEFAULT TRUE | 必做 |
| sort_order | INT | |
| enabled | BOOLEAN | |

#### `game_sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | FK | 参与者 |
| experiment_id | FK | |
| scene_id | FK | |
| mode | ENUM(`bot`,`matched`,`scripted`) | 对局模式 |
| opponent_user_id | FK NULL | 真人时 |
| bot_policy | VARCHAR NULL | 如 `coop_0.64` |
| status | ENUM(`intro`,`playing`,`finished`,`abandoned`) | |
| current_round | INT | |
| my_score / opponent_score | INT | |
| started_at / finished_at | TIMESTAMPTZ | |

业务规则：同一用户同一 `scene` 可有多次 session；**完成判定**以「每个必做 scene 至少有一条 `finished`」为准（与前端 `stagResults` 语义一致）。

#### `game_rounds`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| session_id | FK | |
| round_no | INT | 1–10 |
| my_choice | CHAR(1) | A/B |
| opponent_choice | CHAR(1) | A/B |
| my_points / opponent_points | INT | |
| created_at | TIMESTAMPTZ | |

唯一：`(session_id, round_no)`。  
**权威计分在服务端**：客户端只提交 `my_choice`，服务端生成/获取 `opponent_choice` 并算分。

#### `leaderboard_snapshots`（可选，可先用视图/查询）

| 字段 | 类型 | 说明 |
|------|------|------|
| period | VARCHAR | `weekly` / `all` |
| user_id | FK | |
| rank | INT | |
| total_score | INT | |
| sessions_count | INT | |
| coop_rate | NUMERIC | |
| computed_at | TIMESTAMPTZ | |

MVP 可用 SQL 聚合实时查，不物化。

#### `account_events`（管理端「账号事件」）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| user_id | FK NULL | |
| event_type | VARCHAR | `email_verified` / `login_blocked` / `admin_status_change` … |
| payload | JSONB | |
| created_at | TIMESTAMPTZ | |

#### `content_blocks` / `page_configs`（CMS 轻量）

| 表 | 用途 |
|----|------|
| `content_blocks` | 问卷说明、场景规则、公告；`key` + `locale` + `body_md/html` + `version` |
| `page_configs` | 路由可见性、发布状态、面向角色 |

### 5.2 ER 简图

```
users ──┬── survey_responses ── survey_answers
        ├── personality_scores
        ├── game_sessions ── game_rounds
        └── account_events

experiments ── experiment_scenes ── game_sessions

survey_instruments ── survey_items
                   └── survey_responses
```

### 5.3 对局模式决策（影响表与 API）

| 模式 | 含义 | 适用 |
|------|------|------|
| `bot` | 服务端按策略生成对手选择（可复现随机种子） | MVP，对齐当前前端体验 |
| `matched` | 双人实时/异步匹配 | 真实验，后续增强 |
| `scripted` | 预录对手序列 | 控制实验条件 |

**MVP 建议：`bot` 模式**，策略参数可配置（例如当前前端约 64% 选 A）。随机种子写入 session，保证复现。

---

## 6. API 设计（REST，JSON）

基址建议：`/api/v1`  
鉴权：`Authorization: Bearer <access_token>`（除登录/注册）  
统一响应：

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

错误：`{ "ok": false, "error": { "code": "SURVEY_INCOMPLETE", "message": "..." } }`

### 6.1 Auth

| Method | Path | 说明 |
|--------|------|------|
| POST | `/auth/register` | 昵称、邮箱、密码、可选邀请码 |
| POST | `/auth/login` | 返回 token + user（含 role） |
| POST | `/auth/logout` | 吊销 refresh（如有） |
| GET | `/auth/me` | 当前用户资料 |

登录失败：累计 `failed_login_count`；达阈值锁定（演示 UI 文案：5 次 / 15 分钟）。

### 6.2 Survey（BFI-44）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/surveys/bfi-44` | 题库 + 说明（可分页组信息） |
| GET | `/surveys/bfi-44/my-response` | 当前进度 / 已提交结果 |
| PUT | `/surveys/bfi-44/answers` | 批量或单题保存草稿 |
| POST | `/surveys/bfi-44/submit` | 校验 44 题齐全 → 计分 → 解锁博弈 |

提交后返回：`personality_scores` + `quality_passed`。

### 6.3 Games

| Method | Path | 说明 |
|--------|------|------|
| GET | `/experiments` | 大厅列表（含是否解锁：依赖问卷） |
| GET | `/experiments/stag-hunt/scenes` | 场景列表 + 个人完成进度 |
| POST | `/experiments/stag-hunt/scenes/:key/sessions` | 开局 |
| GET | `/sessions/:id` | 当前局状态 |
| POST | `/sessions/:id/rounds` | body: `{ "choice": "A"|"B" }` |
| POST | `/sessions/:id/abandon` | 放弃 |

`POST .../rounds` 服务端返回：本轮双方选择、得分、累计分、是否结束。

### 6.4 Ranking

| Method | Path | 说明 |
|--------|------|------|
| GET | `/leaderboard?period=weekly` | 排行榜 |

字段对齐前端：昵称、public_id、排名、场次、人格摘要、总得分。

### 6.5 Admin

| Method | Path | 说明 |
|--------|------|------|
| GET | `/admin/users` | 分页搜索用户 |
| GET | `/admin/users/:id/personality` | 人格详情弹窗数据 |
| GET/PATCH | `/admin/experiments` | 列表 / 排序 / 增删改状态 |
| GET/PATCH | `/admin/settings/auth` | 注册策略、锁定策略、邀请码 |
| GET | `/admin/account-events` | 账号事件流 |
| GET/PUT | `/admin/content/:key` | 内容块 |
| GET/PUT | `/admin/pages/:key` | 页面配置 |
| GET | `/admin/stats/overview` | 总用户、问卷完成率、有效轮次、合作率 |

全部需 `role=admin`。

---

## 7. 与现有前端状态机的映射

便于后续改 `app.js` 时「函数级替换」，不改 UI 结构。

| 前端函数 / 状态 | 后端能力 |
|-----------------|----------|
| `submitAccount` / `enter(role)` | `POST /auth/login\|register` → 存 token |
| `state.answers` / `answer` | `PUT .../answers` |
| `submitSurvey` | `POST .../submit` |
| `state.survey` | `GET .../my-response` 的 submitted 态 |
| `stagScenes` | `GET .../scenes` + content |
| `openScene` / `beginRounds` | `POST .../sessions` |
| `playRound(mine)` | `POST .../rounds`（去掉本地 random） |
| `state.stagResults` | scenes 进度接口 |
| `users` / `personalityProfiles` | `/admin/users` + personality |
| `state.experiments` | `/admin/experiments` |
| `renderRank` | `/leaderboard` |
| `renderAccounts` | settings + account-events |

前端提示文案「答案仅保存在当前页面内存中」在接入后应改为服务端保存提示——属后续文案改动，不在本期。

---

## 8. 安全与研究合规

1. **密码**：Argon2id 或 bcrypt；禁止明文日志。
2. **传输**：生产强制 HTTPS。
3. **鉴权**：管理接口强制 RBAC；禁止仅靠前端隐藏。
4. **限流**：登录、注册、提交问卷按 IP/用户限流。
5. **数据最小化**：管理端导出需审计日志。
6. **知情同意**：可在 `survey_responses` 或独立 `consents` 表记录同意时间与版本。
7. **可复现**：对局 bot 策略与 seed 入库；问卷 instrument version 快照。
8. **演示账号**：种子数据中的 `researcher@` / 预设密码仅限开发环境。

---

## 9. 待决策清单

| # | 议题 | 状态 | 决定 |
|---|------|------|------|
| 1 | 后端语言/框架 | **已定** | Python + FastAPI + PostgreSQL |
| 2 | 对局模式 MVP | **已定** | `bot`（coop≈0.64，可配置） |
| 3 | 问卷是否允许重测 | **已定** | 默认不可覆盖；管理员可重置 |
| 4 | 囚徒困境是否本期入库 | **已定** | 表预留；逻辑后置 |
| 5 | 邮箱验证是否 MVP 必需 | **已定** | MVP 可跳过，直接 `active` |
| 6 | 前端何时迁入 `frontend/` | 待定 | 后端骨架稳定后再迁 |
| 7 | 是否需要实时双人 | **已定** | MVP 不做；预留 `matched` |

---

## 10. 分阶段落地计划（仍不改前端的前提下）

### Phase 0 — 文档与仓库约定（当前）

- [x] 本设计文档
- [ ] 技术栈确认（§9）
- [ ] OpenAPI 草案（可下一文档）

### Phase 1 — 基础设施

- 创建 `backend/`、Docker Compose（Postgres）
- 迁移脚本：§5 核心表
- 健康检查 `GET /health`

### Phase 2 — Auth + Users

- 注册/登录/JWT
- 种子管理员与若干演示用户
- 登录锁定策略

### Phase 3 — Survey

- BFI-44 题库种子
- 作答草稿、提交、计分、质量检查
- 与「解锁博弈」状态联动

### Phase 4 — Games

- 猎鹿两场景、bot 对局、轮次权威计分
- 完成进度与实验完成标记

### Phase 5 — Admin + Rank

- 用户/人格查询、实验 CRUD 排序
- 排行榜与 overview 统计
- 内容/页面配置最小实现

### Phase 6 — 前端对接（**首次允许改前端**）

- 引入 API client，替换内存写路径
- 保留离线演示开关（如 `?demo=1`）或保留 `YangMind-Lab.html` 纯本地

---

## 11. 架构重构建议（相对现状）

| 动作 | 是否改前端代码 | 建议时机 |
|------|----------------|----------|
| 新增 `docs/`、`backend/` | 否 | 立即（实现阶段） |
| 根目录前端迁到 `frontend/` | 否（仅移动文件） | Phase 1 末，需同步 README |
| 拆分 `app.js` 为模块 | 是 | Phase 6，与 API 接入一起做 |
| 删除或归档 `YangMind-Lab.html` | 视需求 | 生产上线后归档，勿早删 |
| 引入构建工具（Vite 等） | 是 | 非必须；静态三文件可继续由后端托管 |

**本期结论：** 架构上预留 `backend/` + `docs/` +（可选）`frontend/`；**现有前端文件内容零修改**，演示路径不变。

---

## 12. MVP 成功标准

1. 新用户可注册登录，token 鉴权有效。  
2. 完成 BFI-44 后人格五维可查询，且未完成不可开博弈。  
3. 猎鹿两场景各 10 轮服务端计分正确，进度与「实验完成」判定正确。  
4. 管理端可列出用户与人格，可调整实验排序/状态。  
5. 排行榜来自真实聚合，而非写死数组。  
6. 现有 `index.html` 演示仍可双击运行，互不影响。

---

## 13. 附录：前端字段对照速查

### 用户行（管理端 / 排行榜）

演示结构：`[姓名, public_id, 总得分, 场次, 人格摘要, 问卷状态]`  
→ 对应 `users.nickname`、`users.public_id`、聚合得分、聚合场次、`personality_scores.summary_label`、问卷 `submitted` 与否。

### 人格画像

`{ E, A, C, N, O }` 浮点 1–5，展示文案来自维度 band 规则（可放 `content_blocks` 或后端配置常量，与现 `personalityMeta` 对齐）。

### 猎鹿场景 key

`task` / `travel` —— 建议作为稳定 `scene_key`，勿仅用中文标题做主键。

---

**文档维护：** 技术栈与对局模式确认后，可增补 `docs/API_OPENAPI.yaml` 与 `docs/DB_MIGRATION_PLAN.md`。  
**本期承诺：** 仅产出设计，不修改任何业务代码。

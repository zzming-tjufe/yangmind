# YangMind 更新日志草稿（未上线）

> 范围：相对 `v0.3.x` / 质量控制基线，本轮本地已实现内容（含已提交 `v0.4.0前瞻` 与其后未推送的导出重构）。  
> 面向开发 / 部署核对；对外公告需另写短文案。

---

## 后端

### Auth / 用户模型
- `POST /api/v1/auth/login`：登录标识支持邮箱或昵称（`LoginRequest.email` 改为普通 `str`，查找逻辑归一化）。
- 注册昵称唯一：大小写不敏感；`db_fixes` 启动时处理历史重名并补唯一索引。
- `User` 增加 `is_debug`；`role` 扩展 `sudo`（高于 `super_admin`）。
- `UserOut` / Token 响应增加 `is_debug`、`is_sudo`。
- **已知坑**：`UserOut.email` 使用 `EmailStr`，`*.local` 邮箱会在登录序列化阶段 500；sudo 默认邮箱需用合法域名（如 `sudo@yangmind.cn`）。

### sudo 调试账号
- 配置项（`config.py` / `.env`）：`ENABLE_SUDO`、`SUDO_PASSWORD`、`SUDO_NICKNAME`、`SUDO_EMAIL`。
- 生产：`ENABLE_SUDO=true` 时必须设 `SUDO_PASSWORD`，否则拒绝启动。
- `seed_sudo_if_needed`：启动时创建/同步 sudo 用户（`role=sudo`、`is_debug=true`）。
- RBAC：`is_sudo` 可走总管接口；邀请码可打 `is_debug`；注册继承调试标记。
- 统计 / 排行榜 / 导出：非 sudo 默认排除 `is_debug`；sudo 导出带调试行与 `is_debug` 列。

### 演示模式（内存）
- 新路由前缀 `/api/v1/demo/*`（`demo.py` + `demo_store.py`）。
- 问卷草稿/提交、猎鹿场景、人机对局均走内存态；`POST /demo/reset` 清空。
- Bot 选择偏置约 60% 一侧；不落正式库、不进导出。

### 管理端与数据层
- 参与者列表：批量聚合问卷状态 / 博弈统计 / 人格，减少 N+1。
- 质量复核、授权重做、邀请码/子管、审计事件等既有能力保留；审计页独立。
- `users.is_debug`、`invite_codes.is_debug` 启动迁移（`db_fixes`）。

### 研究数据导出（相对旧三入口重写，工作区未提交部分）
- 新模块：`app/services/admin_export.py`。
- 统一入口：`GET /api/v1/admin/export/{kind}?format=csv|json&filename=`  
  - `users`：一人一行（完成状态、质量状态、E/A/C/N/O、摘要、场次、总分等）。  
  - `survey-answers`：一人一行宽表，`题1`…`题44`；含重做前归档。  
  - `survey-quality`：一人一行质量指标（拆列，中文表头）；JSON 保留嵌套 `quality_flags` 等。  
  - `runs`：一人一轮（场景、对局/轮次、双方选择与分、决策 ms、超时、双方问卷质量与理解测试、`analysis_eligible` 等）。
- CSV：UTF-8 BOM + 中文表头 + 布尔「是/否」；JSON：原始英文字段结构。
- 旧 `export/users.csv|surveys.csv|rounds.csv` 路径已从 `admin.py` 移除，改走上述 `kind`。

### 其它后端触点
- `game_engine` / 进度解锁：人格反馈仍依赖必做场景全部完成（`personality_feedback_unlocked`）。
- 问卷质量规则本身（`bfi_scoring.check_quality` v2026-07-v2）本轮未改判定阈值，仅导出与展示侧消费。

---

## 前端

### 壳层 / 路由 / 权限 UI
- 管理侧栏分组：实验运营 / 拉人与协作 / 站点配置 / 系统 / 账号；Lucide 图标。
- 「操作记录」独立 view=`audit`；「导出」独立 view=`export`（仅总管/sudo）。
- `ModalPortal`：管理模态挂 `body`，遮罩盖侧栏+顶栏。
- `SudoViewContext`：sudo 顶栏「总管 | 子管 | 参与者」切换 `effectiveRole`。
- `DemoContext`：演示进出/重置；演示态走 `/api/v1/demo/*`。

### 参与端
- 登录页：占位/校验改为账号（邮箱或昵称）。
- BFI：紧凑顶栏 + 量表矩阵 + 桌面右侧进度栏；提交后人格仍延迟解锁。
- 博弈结束页（无 successor 的 `finished`）：拉取 `my-response`，展示 `summary_label` 与五维分。

### 管理端页面
- `AdminUsersPage`：批量加载、质量复核弹层、去掉页内导出条。
- `AdminExportPage`：四块说明 + 模态选 CSV/JSON 与文件名（下载位置由浏览器决定）。
- 若干列表页：`AdminListStatus` 加载态；空列表全宽提示。

### 依赖
- 前端增加 `lucide-react`。

---

## 运维 / 配置

- 生产 `.env` 示例补充 sudo 变量；启用后需 `systemctl restart yangmind-api` 以 seed。
- 前端构建仍建议：`VITE_API_BASE=` + Nginx `:8081` 反代 `/api` → `8003`。
- 部署本轮导出改动需同时更新 backend（含 `admin_export.py`）与 frontend `dist`。

---

## 文件索引（便于 code review）

| 区域 | 主要路径 |
|------|----------|
| sudo / 角色 | `core/config.py`, `core/roles.py`, `services/seed.py`, `models/user.py` |
| 演示 | `api/demo.py`, `services/demo_store.py` |
| 导出 | `services/admin_export.py`, `api/admin.py`（export 段） |
| 登录 | `api/auth.py`, `schemas/auth.py` |
| 迁移 | `services/db_fixes.py` |
| 壳 / 导出页 | `AppShell.tsx`, `AdminExportPage.tsx`, `SudoViewContext.tsx`, `DemoContext.tsx` |
| BFI / 结束页 | `BfiPage.tsx`, `GamesPage.tsx` |

---

## 未包含 / 待确认

- 正式发版公告文案（本文件偏工程 changelog）。
- 导出块是否再增减、字段是否与分析同学最终表头逐字对齐（当前按约定草案实现）。
- `UserOut` 对调试邮箱的 `EmailStr` 放宽（可用改邮箱规避，代码层尚未改）。

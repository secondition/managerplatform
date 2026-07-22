# Manager Platform 开发文档

> 历史开发记录（三份源文件）已整合至本文。事实来源优先级：当前代码 > 本文档。

---

## 1. 文档范围与事实来源

本文为 Manager Platform 唯一开发参考。优先级：

1. **当前代码** — 实际实现优先于任何文档描述。
2. **本文档** — 整合后唯一规格。
3. **飞书应用接入与配置指引** — 飞书自建应用创建、权限申请、回调配置等操作步骤保持独立，本文不复制其详细步骤，仅链接引用。

> 飞书接入操作指引详见：[飞书应用接入与配置指引](./飞书应用接入与配置指引.md)。

---

## 2. 产品定位、角色与设计原则

### 2.1 系统定位

围绕员工"日、周、月"工作管理的内部协作平台：

- **日维度**：日报、工作清单、问题与解决方案、AI 日报评分、今日建议。
- **周维度**：红绿灯关键指标，按周录入，自动判定达标状态（on_target / missed）。
- **月维度**：OKR 目标与关键结果、月报、AI 质量评分与点评。
- **协作维度**：订阅同事、查看订阅日报和订阅 OKR。
- **AI 维度**：日报评分、周评分、今日建议、OKR 点评、月报评分（AI 大脑聊天/智能体后续规划）。
- **管理维度**：员工、部门、人员组、企业设置、AI 配置。

### 2.2 用户角色

| 角色 | 说明 | 核心能力 |
|---|---|---|
| Owner | 由 `OWNER_FEISHU_UNION_ID` 指定 | 绕过 `admin:*` 后台权限；`feature:*` 仍需权限行 |
| 管理员 | 拥有 `admin:*` 权限点的员工 | 管理指定后台模块 |
| 普通员工 | 默认业务用户 | 默认拥有全部 `feature:*`，无后台权限 |

### 2.3 设计原则

- 先核心闭环再增强体验。
- JSON 字段统一使用 SQLAlchemy `JSONText`（基于 TEXT 的 JSON 序列化/反序列化）。
- 前后端分层清晰：统计由后端聚合接口返回。
- AI 调用为请求内同步，`ai_tasks` 记录审计/状态。
- SQLite 当前唯一经验证路径；JSONText/BigInt 等兼容设计为 MySQL 迁移预留但不验证。
- 单企业自部署：表不带 `company_id`，企业信息存 `company_settings` 单行。

---

## 3. 技术栈、仓库结构、运行架构

### 3.1 技术栈

**前端**：React 18 + TypeScript + Vite + React Router + TanStack Query + Zustand + Tailwind v4 + dayjs + TipTap 富文本。

**后端**：FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 + PyJWT + APScheduler + httpx（AI Provider 调用）。

**数据库**：SQLite（当前唯一经验证路径；JSONText/BigInt 为 MySQL 迁移预留不验证）。

### 3.2 仓库结构

```
backend/
  app/
    main.py                   应用入口，lifespan 起停 APScheduler
    core/                     config.py, permissions.py, scheduler.py, security.py
    db/                       base.py, session.py
    api/v1/                   router.py + 路由模块
    models/                   user.py, daily.py, okr.py, traffic.py, org.py, ai.py, subscription.py
    schemas/                  请求/响应 Pydantic model
    services/                 业务逻辑层（含 ai/ provider 子包）
    utils/                    html_sanitize.py, crypto.py, time.py, dates.py, image_upload.py
  alembic/
    versions/                 所有迁移脚本（最高 0026）
  tests/                      pytest
  storage/                    上传文件目录（avatars/, logos/）

frontend/
  src/
    app/                      router.tsx
    api/                      client.ts + 按模块 API 文件
    components/               layout/, ui/, editor/
    features/                 admin/, auth/, daily/, groups/, okr/, people/, playground/,
                              settings/, subscription/, traffic/, workspace/
    lib/                      date.ts, num.ts
    stores/                   authStore.ts, themeStore.ts, playgroundStore.ts
    types/                    api.ts
```

### 3.3 运行架构

```
React 前端 → FastAPI REST API → SQLite
                              → 本地 storage/uploads（头像/Logo）
                              → 内嵌 APScheduler（定时生成评分/建议）
                              → 外部 AI Provider（OpenAI Chat/Responses + Anthropic Messages；DeepSeek 走 OpenAI 兼容配置）
```

无 SSE、无 Redis、无独立对象存储。

---

## 4. 信息架构与路由

### 4.1 前台导航（AppShell）

- 顶栏左侧 Logo/企业名称 → 点击进入 `/daily`。
- 顶栏右侧：通知按钮（disabled，置灰不可点）、管理后台入口（任一 `admin:*` 门控）、当前用户 pill（点击进入 `/people/me`）、登出。
- 第二行导航：日报 (`/daily`)、AI 大脑 (`/chat`，暂不可用)、红绿灯 (`/traffic-light`)、OKR (`/okr`)、订阅·日报 (`/subscription/daily`)、订阅·OKR (`/subscription/okr`)、人员组 (`/groups`)。

前台已占位 disabled 项：AI 大脑、灵感库、文档、知识库、多维表格（导航置灰不可点）。

### 4.2 管理后台导航

顶栏"返回工作台 | 管理后台"，右侧用户 pill/登出。后台 Tab：人员管理、同步记录、权限管理、部门管理、评分设置、智能体设置（disabled）、企业设置。

### 4.3 路由表

| 路由 | 页面 | 权限 |
|---|---|---|
| `/login` | 飞书扫码登录 | 匿名 |
| `/login/callback` | 登录回调 | 匿名 |
| `/chat` | AI 大脑（前端占位） | 无独立权限，仅占位 |
| `/daily` | 日报 | `feature:daily` |
| `/traffic-light` | 红绿灯 | `feature:traffic` |
| `/okr` | OKR | `feature:okr` |
| `/groups` | 人员组 | `feature:group` |
| `/subscription/daily` | 订阅日报 | `feature:daily` |
| `/subscription/okr` | 订阅 OKR | `feature:okr` |
| `/people/me` | 我的主页 | 登录用户 |
| `/people/:userId` | 他人主页 | 登录用户 |
| `/profile` | → 重定向到 `/people/me` | 兼容路由 |
| `/admin` | 跳转到首个有权限的后台页 | 至少一个 `admin:*` |
| `/admin/employees` | 人员管理 | `admin:employee` |
| `/admin/sync-history` | 同步记录 | `admin:employee` |
| `/admin/permissions` | 权限管理 | `admin:employee` |
| `/admin/departments` | 部门管理 | `admin:department` |
| `/admin/scoring-settings` | 评分设置 | `admin:ai` |
| `/admin/agent-settings` | 智能体设置（disabled） | `admin:ai` |
| `/admin/company-settings` | 企业设置 | `admin:settings` |

---

## 5. 身份认证、通讯录、组织与权限

### 5.1 唯一登录路径：飞书 OAuth

- 已废除自建密码体系：无 `password_hash`、无邮箱密码登录。
- 登录流程：飞书扫码组件 → OAuth callback → `POST /auth/feishu/callback` → 本系统签发 JWT + httpOnly Cookie + CSRF。
- 会话模型：双 Token（access 2h + refresh 14d 滑动），httpOnly Cookie + SameSite=Strict 下发，CSRF 双提交（非幂等请求 `X-CSRF-Token` 头）。
- `token_version` 递增实现全局会话失效。

### 5.2 花名册门控

- 首次部署必须配置 `OWNER_FEISHU_UNION_ID`。
- 空库仅 owner union id 登录可创建 owner。
- 非空库以 `feishu_union_id` 比对 `users` 表，未命中直接拒绝。
- 禁用用户（`status=disabled`）拒绝登录，禁用时 `token_version+1` 使旧会话失效。

### 5.3 飞书通讯录同步

- 入口：管理员后台 → 人员管理 → "从飞书同步通讯录"按钮（`admin:employee` 门控）。
- 获取 `tenant_access_token`（应用身份 HTTP POST，2h 缓存）。
- 部门：BFS 逐层拉取直接子部门，父 id = 当前查询部门，重建完整树形部门结构。
- 用户：逐部门拉取（飞书按部门只返回直属成员），累加每人的全部部门。`department_id` 择优：最外层（depth 最小）优先，同层按 `.env DEPARTMENT_PRIORITY` 名称顺序，均未列举按发现顺序。
- 幂等 upsert：部门按 `feishu_department_id`（冲突时复活软删行）；用户按 `feishu_union_id`。
- 新用户默认 `member`，owner union id 命中则为 `owner`。
- 已存在用户同步姓名、邮箱、头像、飞书 ID、部门、同步时间。
- 本地 active 但本次通讯录缺失的非 owner 用户 → `status=disabled` + `token_version+1` + 吊销全部 refresh token。
- Owner 不被同步降级、禁用或删除。
- `contact_sync_logs` 记录结果；同步异常先 `rollback` 再写失败日志。

### 5.4 组织模型

- **部门**（`departments`）：树形结构，`parent_id` 自引用，`feishu_department_id` 映射飞书。
- **人员组**（`groups` + `group_members`）：手动管理实体，替代已移除的岗位模型。来源标记 `manual`（手工建）或 `department`（从部门快照导入，导入后与部门解耦）。
- **岗位（position）已彻底移除**：`Position` 模型、`users.position_id`、相关 schema/service/api/前端类型全部删除。

### 5.5 权限模型

**功能权限**（前台模块门控，owner 同样按权限行判断，不绕过）：

| 权限点 | 模块 |
|---|---|
| `feature:daily` | 日报 + 订阅日报 |
| `feature:traffic` | 红绿灯 |
| `feature:okr` | OKR + 订阅 OKR |
| `feature:group` | 人员组 |

新同步员工默认获得全部 `feature:*`。

**后台权限**（owner 绕过后台权限点）：

| 权限点 | 模块 |
|---|---|
| `admin:employee` | 人员管理、同步记录、权限管理 |
| `admin:department` | 部门管理 |
| `admin:ai` | AI 评分设置、智能体设置 |
| `admin:settings` | 企业设置 |

**系统角色**：仅保留 `owner` / `member`（`role=admin` 在迁移 0022 归一为 `member`，权限由 `UserPermission` 行控制）。

---

## 6. 功能设计

### 6.1 日报

- 日期周条 + 日期选择，支持日/周/月视图。今日使用主题强调色高亮。
- **工作清单**：增删改、标记完成、5 分钟粒度时间。重复规则：每日（顺延下一工作日）/ 每周（顺延 7 天，落周末后跳）。每天 00:05 幂等补齐下一实例。
- **派发**：创建任务时指定 `assigned_to`，任务直接归被派发人所有。派发人仅保留 `assigned_by` 审计字段。派发自动建立发起人到被派发人的日报订阅。派发目标可展开人员组为成员 id 提交（`assigned_to_ids` 多值）。
- **协作者**（`daily_task_collaborators`）：可查看、标记完成，不可编辑/删除/管理成员。
- **私人任务**（`is_private`）：仅 owner 与明确协作者可见，订阅者/follower 不可见。
- **问题与解决方案**：增删改，TipTap 富文本 + 后端 `sanitize_html` 白名单清洗。

#### AI 评分

并列展示今日得分、昨日得分、上一完整自然周得分。维度：重要性（40）+ 工作质量（30）+ 饱和度（30） = 总分 0-100。定时每天 17:00 初评、23:50 终评，支持手动生成。周评分基于上一整周全部日报和问题方案综合。

#### 今日建议

"今日行动建议官" System 提示词，输入含近 30 天全公司数据片段、本人 OKR/清单、历史补充。输出 ≤ 5 条建议（red/amber/blue/green 类型）。接受即建 `source=suggestion` 的 DailyTask。支持带补充信息重生成。

### 6.2 红绿灯（周关键指标）

**v1.8 重构**：指标长期存在，不绑定月份；设统一**周目标**，无起点/月目标/累计。

- 时间列：最近 5 周滚动窗口，每周一自动新增待填列，可翻历史并用"回到最近"。
- 达标方向 2 种：`increase`（≥ 周目标绿）、`decrease`（≤ 周目标绿）。
- 每周状态自动判定：达标 → 绿（on_target），未达标 → 红（missed），未填 → 灰（empty）。
- 派生列：近 N 周平均（窗口内已填值均值）；指标行状态汇总（任一未达标周即红，全达标绿，全空灰）。
- 字段：`direction`（increase/decrease）、`weekly_target`（周目标值）、`north_star_target`（可选北极星目标）。
- 权限：仅指标 owner 可修改元信息、管理成员、删除指标。`editor`（可录入/修改周值）、`viewer`（只读）。Owner 若需录入周值也必须有显式 editor 成员行。
- 成员选择支持展开人员组为成员 id 提交。

### 6.3 OKR（月度目标）

- 目标与 KR 归属个人，仅本人可增删改。
- **KR progress**：人工标记（UI slider），0-100 整数或小数。Objective progress = 全部未删除 KR progress 的算术平均（包含 0）。
- **月报**：每月首次访问自动补 `performance`（业绩相关）和 `innovation`（本月创新）两板块空态。TipTap 富文本编辑，存 HTML + JSON。
- **AI 质量评分**：只评 O/KR 方向、描述，不读完成率/当前值/月报/日报。写入 `okr_reviews`。
- **月报评分**：聚合当月日报统计、清单原文、问题方案、OKR 进度、月报栏目。
- **排序**：`sort_order` 已实现拖拽（HTML5 native draggable），前端通过 `POST /okr/objectives/reorder?month=YYYY-MM` 提交全量 `ids` 列表。`POST /okr/objectives/{id}/key-results/reorder` 同理。

### 6.4 订阅

- `subscriptions` 表，`(subscriber_id, target_user_id)` active 唯一。
- 日报与 OKR 独立启用（`daily_enabled` / `okr_enabled`）。
- 订阅日报：follower 只读视图，`is_private=true` 任务过滤，所有写能力为 false。
- 订阅 OKR：只读目标/KR 进度 + 已建月报板块。
- 个人主页"二合一"订阅：同时开关日报和 OKR 订阅。
- 不可订阅自己；取消后不可读。
- 派发自动建立日报订阅关系。

### 6.5 个人主页

- **头图区域**：头像（目前后端上传 API 存在但前端仅显示姓名缩写）、姓名、角色、邮箱、部门、最近登录时间、粉丝/关注数。
- **个性签名**：`users.profile_signature`，本人实时编辑，他人只读。
- **日报日历**：月份日历（周日开头），工作日已填蓝点、未填红点，未来/非工作日无点。
- **本月概览**：日报存在数、缺少数、工作清单平均完成率（仅已结束工作日；今日 20:00 后纳入）。
- **AI 评分区**：日报评分卡 + OKR 质量评分卡，直接可查看不要求订阅。
- 订阅按钮（他人主页显示，本人不显示）：二合一动作，同时开关日报和 OKR。
- `/profile` 兼容跳转到 `/people/me`。

### 6.6 人员组

- 独立 `/groups` 页面，`feature:group` 门控。
- 组来源 `manual` / `department`；按部门导入为一次性快照，与部门解耦。
- 成员自由编辑（复用选人弹窗）。
- 红绿灯/派发选人时可展开人员组。

### 6.7 企业设置

- `admin:settings` 门控。
- 字段：`company_name`、`logo_url`（POST `/settings/company/logo` 上传）、`footer_text`。
- Logo 校验格式（PNG/JPG/WEBP）、大小（≤2MB）、魔数替换旧文件。

### 6.8 AI 能力

**已实现**：

- Provider 抽象（`services/ai/`：OpenAI Chat/Responses + Anthropic Messages HTTP 实现 + 工厂；DeepSeek 通过 OpenAI 兼容端点配置）。
- 密钥加密（`utils/crypto.py`，JWT secret 派生 Fernet key 对称加解密，API 回显 `sk-****abcd`）。
- 数据表：`ai_provider_configs`、`ai_feature_flags`、`prompt_configs`、`ai_tasks`、`ai_user_memory`、`daily_scores`、`weekly_scores`、`daily_suggestions`、`okr_reviews`、`monthly_report_scores`。
- 生成方式：请求内同步 httpx 调用 Provider，`ai_tasks` 记录审计/状态。
- 日报评分、周评分、今日建议、OKR 质量评分、月报评分已接 Provider 代码，待真实 API Key 联调。
- 定时任务（APScheduler BackgroundScheduler，`main.py` lifespan 起停）：07:50 建议、17:00/23:50 日报评分、周一 00:10 周评分、月末 23:30 OKR 质量/23:40 月报评分、03:00 清理 30 天前 `ai_tasks`；受 `scheduler_enabled` + 各功能开关门控。
- 输出校验：Pydantic schema 校验；JSON 截断自动重试一次；失败写 `ai_tasks.failed` 不覆盖旧评分。
- 后台 AI 配置（`admin:ai` 门控）：Provider 表单、功能开关、系统级提示词模板（5 类型 Tab + 数据变量 + 版本 + 恢复默认）。
- 个人主页评分：读 `daily_scores` / `okr_reviews` 真实最新记录。

**占位/未启用**：AI 大脑聊天 `/chat`、AI 智能体、Claude 额度授权（表未建，导航置灰）。

### 6.9 管理后台

| 页面 | 路由 | 权限 |
|---|---|---|---|
| 人员管理 | `/admin/employees` | `admin:employee` |
| 同步记录 | `/admin/sync-history` | `admin:employee` |
| 权限管理 | `/admin/permissions` | `admin:employee` |
| 部门管理 | `/admin/departments` | `admin:department` |
| 评分设置 | `/admin/scoring-settings` | `admin:ai` |
| 智能体设置（disabled 占位） | `/admin/agent-settings` | `admin:ai` |
| 企业设置 | `/admin/company-settings` | `admin:settings` |

### 6.10 主题与界面设置

- 顶栏主题入口支持 5 种强调色（blue / emerald / amber / rose / violet）、3 种字体族（system / yahei / serif）、3 档尺寸（compact / standard / large）。
- 设置保存在浏览器 `localStorage`（key `managerplatform-theme`），通过 `data-theme-accent` / `data-theme-font` / `data-theme-size` CSS 属性应用。
- 主题强调色覆盖导航/Tab 激活态、选择态、输入焦点、操作按钮、可点击文字、功能图标、进度条。
- 红绿灯红/绿/灰、成功/警告/错误、AI 分类色、协作身份色、同步状态色、品牌 Logo 保持固定语义色不变。

---

## 7. 数据模型与迁移

### 7.1 当前数据库迁移（最高：0026）

| 迁移 | 内容 |
|---|---|
| 0001 | MVP 基础表 |
| 0002 | `daily_tasks.assigned_by`、`daily_task_collaborators`、`traffic_metric_members` |
| 0003 | 飞书通讯录同步字段、`contact_sync_logs`、旧红绿灯 `editor`→`manager` 迁移 |
| 0004 | 删除 `positions` 表与 `users.position_id`；新增 `groups`、`group_members` |
| 0005 | 新增 `subscriptions` 表 |
| 0006 | 红绿灯重构：drop 重建表，去 month/start/target/agg，加 `weekly_target` |
| 0007 | 新增 `users.profile_signature` |
| 0008 | `company_settings` 单行表 |
| 0009 | OKR 三表 |
| 0010-0019 | AI 七表、提示词清理、功能权限拆分、变量落库、周评分、建议结构化、OKR 质量评分、月报评分 |
| 0020 | 日报重复系列标识、清理 Objective 旧评分字段、补全唯一约束 |
| 0021 | `okr_key_result_progress`、`okr_comments` |
| 0022 | `role=admin` 归一为 `member` |
| 0023 | 红绿灯新增 `north_star_target` 列 |
| 0024 | 红绿灯清理旧 `is_north_star`/`category`/`range` 列 + OKR 清理 |
| 0025 | OKR order normalization |
| 0026 | 日报任务私有字段 `is_private` |

### 7.2 当前已建表

| 模块 | 表 |
|---|---|
| 用户与组织 | `users`、`user_permissions`、`refresh_tokens`、`departments`、`groups`、`group_members`、`contact_sync_logs`、`company_settings` |
| 日报 | `daily_reports`、`daily_tasks`、`daily_task_collaborators`、`problem_solutions` |
| AI 评分与记忆 | `daily_scores`、`weekly_scores`、`daily_suggestions`、`okr_reviews`、`monthly_report_scores`、`ai_tasks`、`ai_user_memory`、`ai_provider_configs`、`ai_feature_flags`、`prompt_configs` |
| 红绿灯 | `traffic_metrics`、`traffic_metric_values`、`traffic_metric_members` |
| OKR | `okr_objectives`、`okr_key_results`、`okr_key_result_progress`、`okr_comments`、`monthly_report_sections` |
| 订阅 | `subscriptions` |

### 7.3 2.0 规划表（当前未建）

| 表 | 用途 |
|---|---|
| `user_privacy_settings` | 订阅隐私设置 |
| `subscription_audit_logs` | 订阅操作审计 |
| `company_setting_audit_logs` | 企业设置变更审计 |
| `notifications` | 通知中心 |
| `ai_agents`、`ai_agent_permissions` | AI 智能体 |
| `chat_conversations`、`chat_messages` | AI 大脑聊天 |
| `inspirations` | 灵感清单 |
| `files` | 通用文件存储 |

### 7.4 关键约束

| 对象 | 约束 |
|---|---|
| 日报 | 每人每天至多一份；`(user_id, report_date)` active 唯一 |
| 日报任务时间 | 分钟仅 00/05/.../55 |
| 订阅 | 不可订阅自己；`(subscriber, target)` active 唯一 |
| Owner | 不可删除、不可禁用、恒有全部 `admin:*` 权限 |
| 红绿灯周值 | `(metric_id, week_start)` 唯一；未结束的周拒绝录入 |
| 富文本 | 存 JSON + HTML；保存时后端 `sanitize_html` 白名单清洗 |
| 飞书 union_id | 账号绑定主键；`feishu_open_id` 也唯一；软删唯一索引 |

---

## 8. API 设计

### 8.1 通用规范

- Base URL: `/api/v1`
- 认证：httpOnly Cookie 自动携带；非 GET 请求需 `X-CSRF-Token` 头（CSRF 双提交）。
- 响应：直接返回 Pydantic model 或 list，无统一 `data/message/request_id` 信封。
- 错误：`{"detail": "message"}`（非通用壳）。
- 分页：视接口而定，无统一分页壳（同步日志 `limit` 参数等）。

### 8.2 当前端点清单

**认证**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/auth/feishu/login-config` | 返回扫码参数 + `state` |
| POST | `/auth/feishu/callback` | OAuth 回调，完成登录或 owner bootstrap |
| POST | `/auth/logout` | 登出（清 Cookie + 吊销 refresh） |
| GET | `/auth/me` | 当前用户 + 权限列表 |
| POST | `/auth/refresh` | 滑动续期 access/refresh |

**日报**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/daily?date=` | 获取指定日期本人日报 |
| GET | `/daily/range?start=&end=` | 获取日期范围摘要（≤42 天） |
| GET | `/daily/week?date=` | 获取指定日期所在周摘要 |
| POST | `/daily/tasks` | 创建事项（含派发/协作者/重复） |
| PATCH | `/daily/tasks/{id}` | 修改事项 |
| DELETE | `/daily/tasks/{id}` | 删除事项 |
| POST | `/daily/tasks/{id}/done` | 标记完成/未完成 |
| POST | `/daily/problems` | 添加问题与解决方案 |
| PATCH | `/daily/problems/{id}` | 修改问题 |
| DELETE | `/daily/problems/{id}` | 删除问题 |
| GET | `/daily/scores` | 获取评分（今日/昨日/上周/月报） |
| POST | `/daily/scores/generate` | 手动生成今日评分 |
| GET | `/daily/weekly-score` | 获取周评分 |
| POST | `/daily/weekly-score/generate` | 手动生成周评分 |
| GET | `/daily/suggestions` | 获取今日建议 |
| POST | `/daily/suggestions/generate` | 生成/重生成建议 |
| POST | `/daily/suggestions/{id}/accept` | 接受建议（建任务） |
| POST | `/daily/suggestions/{id}/reject` | 拒绝建议 |

**红绿灯**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/traffic/weeks?end=&count=` | 滚动窗口周列 |
| GET | `/traffic/metrics?end=&count=` | 指标列表 |
| POST | `/traffic/metrics` | 创建指标 |
| PATCH | `/traffic/metrics/{id}` | 修改指标元信息 |
| DELETE | `/traffic/metrics/{id}` | 删除指标 |
| PATCH | `/traffic/metrics/{id}/values/{week_start}` | 更新周值 |

**OKR**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/okr?month=` | 获取某月 OKR + 月报 + 点评 |
| POST | `/okr/objectives` | 添加目标 |
| PATCH | `/okr/objectives/{id}` | 修改目标 |
| POST | `/okr/objectives/reorder?month=` | 批量排序目标的 `ids` |
| DELETE | `/okr/objectives/{id}` | 删除目标 |
| POST | `/okr/objectives/{id}/key-results` | 添加 KR |
| PATCH | `/okr/key-results/{id}` | 修改 KR |
| POST | `/okr/objectives/{id}/key-results/reorder` | 批量排序 KR 的 `ids` |
| DELETE | `/okr/key-results/{id}` | 删除 KR |
| GET/POST | `/okr/key-results/{kr_id}/progress` | KR 进展记录 |
| GET | `/okr/review?month=` | 获取 OKR 质量点评 |
| POST | `/okr/review/generate?month=` | 生成 OKR 质量点评 |
| GET | `/okr/monthly-report/score?month=` | 获取月报评分 |
| POST | `/okr/monthly-report/score/generate?month=` | 生成月报评分 |
| PATCH | `/okr/monthly-report/sections/{id}` | 编辑月报板块 |
| GET | `/okr/objectives/{id}/comments` | 目标评论列表 |
| POST | `/okr/objectives/{id}/comments` | 添加目标评论 |
| GET | `/okr/key-results/{kr_id}/comments` | KR 评论列表 |
| POST | `/okr/key-results/{kr_id}/comments` | 添加 KR 评论 |
| PATCH | `/okr/comments/{cmt_id}` | 编辑评论 |
| DELETE | `/okr/comments/{cmt_id}` | 删除评论 |

**订阅**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST/DELETE | `/subscriptions/daily[/{target}]` | 日报订阅 CRUD |
| GET | `/subscriptions/daily/candidates?q=` | 日报订阅候选 |
| GET | `/subscriptions/daily/{target}/report?date=` | 读取订阅日报 |
| GET/POST/DELETE | `/subscriptions/okr[/{target}]` | OKR 订阅 CRUD |
| GET | `/subscriptions/okr/candidates?q=` | OKR 订阅候选 |
| GET | `/subscriptions/okr/{target}/report?month=` | 读取订阅 OKR |

**个人主页**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/people/me?month=` | 我的主页 |
| PATCH | `/people/me/signature` | 更新个性签名 |
| POST | `/people/me/avatar` | 上传头像 |
| GET | `/people/{id}?month=` | 他人主页 |
| POST | `/people/{id}/subscribe` | 二合一订阅 |
| DELETE | `/people/{id}/subscribe` | 取消订阅 |

**人员组**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/groups` | 列表 |
| GET | `/groups/import-sources` | 可导入的部门来源列表 |
| POST | `/groups` | 创建组 |
| PATCH | `/groups/{id}` | 编辑组 |
| DELETE | `/groups/{id}` | 删除组 |
| POST | `/groups/{id}/members` | 设置组成员（全量替换） |
| POST | `/groups/from-department` | 从部门导入建组 |
| GET | `/users/groups` | 用户所在组列表（选人弹窗用） |

**管理后台**

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/admin/employees` | `admin:employee` |
| PATCH | `/admin/employees/{id}` | 编辑员工 |
| POST | `/admin/employees/{id}/permissions` | 设置权限 |
| POST | `/admin/employees/{id}/status` | 启用/禁用 |
| DELETE | `/admin/employees/{id}` | 删除员工（软删） |
| POST | `/admin/feishu/sync-contacts` | 触发通讯录同步 |
| GET | `/admin/feishu/sync-logs?limit=` | 同步日志列表 |
| GET/POST | `/admin/departments` | 部门列表/创建 |
| PATCH/DELETE | `/admin/departments/{id}` | 部门修改/删除 |

**企业设置**

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/settings/public` | 公开 |
| GET | `/settings/company` | `admin:settings` |
| PATCH | `/settings/company` | `admin:settings` |
| POST | `/settings/company/logo` | `admin:settings`，上传 Logo |

**AI 管理**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/ai/provider` | 获取 Provider 配置 |
| PATCH | `/admin/ai/provider` | 更新 Provider 配置 |
| POST | `/admin/ai/provider/test` | 测试 Provider 连通 |
| GET | `/admin/ai/features` | 获取功能开关 |
| PATCH | `/admin/ai/features` | 更新功能开关 |
| GET | `/admin/ai/prompts` | 提示词列表 |
| PATCH | `/admin/ai/prompts/{prompt_type}` | 更新提示词 |
| POST | `/admin/ai/prompts/{prompt_type}/restore-default` | 恢复系统默认提示词 |

**AI 通用**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/ai/features` | 当前用户可见的 AI 功能开关（前台用） |
| GET | `/ai/tasks` | 我的 AI 任务列表 |
| GET | `/ai/tasks/{id}` | AI 任务详情 |

---

## 9. 当前实现状态

### 9.1 完成度

| 模块 | 完成度 | 说明 |
|---|---|---|
| 认证与会话 | 85% | OAuth state 绑定浏览器、refresh 滑动轮换、禁用吊销完成；需真实飞书扫码回归 |
| 花名册准入 | 85% | 代码完成；需 owner bootstrap 与拒登真实验证 |
| 飞书通讯录同步 | 85% | BFS 部门树/归属择优/事务回滚已本地验证；中文名依赖飞书权限 |
| 人员后台 | 90% | 员工列表/启用禁用/权限/部门 CRUD/同步日志列表完成 |
| 工作日报 | 95% | CRUD/协作/派发/资源权限/重复任务完成 |
| 红绿灯 | 85% | 滚动 5 周、increase/decrease 方向、editor/viewer 角色完成；需页面回归 |
| 订阅日报 | 80% | 订阅/取消/按人按日只读完成；缺聚合流（P0），通知见 P1 |
| 个人主页 | 90% | 头像/签名/评分/订阅/日历/概览完成；头像上传后端有 API 但前端仅显示姓名缩写 |
| 企业设置 | 75% | 名称/Logo/页脚完成；缺审计日志与品牌扩展 |
| OKR | 82% | 目标/KR CRUD、人工进度、月报富文本、sort_order 拖拽排序完成；AI 点评代码完成 |
| 订阅 OKR | 80% | 订阅/取消/按月只读完成；与二合一订阅联通 |
| AI | 78% | 日报/周评分、建议、OKR 点评、月报评分、Provider、密钥、定时、后台配置完成；代码已接 Provider 但待真实密钥联调 |
| 人员组 | 90% | 建组/改名/删组/成员编辑/从部门导入完成 |
| 主题设置 | 90% | 5 种强调色、3 字体族、3 尺寸档完成；CSS 变量已覆盖大部分模块 |

### 9.2 占位 / 未启用

| 功能 | 状态 |
|---|---|
| AI 大脑聊天 `/chat` | 前端占位，表未建，导航置灰 |
| AI 智能体 / Claude 额度 | 表未建，导航置灰 |
| 通知中心 | 表未建，导航置灰 |
| 灵感清单 | 表未建，导航置灰 |
| 文档 / 知识库 / 多维表格 | 前端占位，导航置灰 |
| OKR 重要度 `o1/o2/o3` | 未实现，纳入 2.0 P0 |
| 订阅权限隐私设计 | 缺审批/关闭/撤销，纳入 2.0 P0 |
| 企业设置审计日志 | 未实现，纳入 2.0 P0 |

---

## 10. 2.0 路线图

### 10.1 P0：1.0 收口必补

#### 10.1.1 OKR 重要度与拖拽排序

**数据模型**

`okr_objectives` 新增字段 `importance varchar(10)`，允许值 `o1/o2/o3`，默认 `o2`。

既有 Objective 回填默认 `o2`。服务层校验拒绝非法值。

排序规则：`importance asc -> sort_order asc -> id asc`（O1 排最前）。

**API**

| 当前 | 2.0 调整 |
|---|---|
| `GET /okr?month=` | Objective 返回 `importance` |
| `POST /okr/objectives` | 支持传入 `importance`，默认 `o2` |
| `PATCH /okr/objectives/{id}` | 支持修改 `importance` |
| `POST /okr/objectives/reorder` | 当前提交 `{ids}` 升级为 `{month, items: [{id, importance, sort_order}]}` |

请求体：

```json
{
  "month": "2026-07",
  "items": [
    { "id": 101, "importance": "o1", "sort_order": 1 },
    { "id": 102, "importance": "o1", "sort_order": 2 }
  ]
}
```

**前端交互**

- Objective 卡片头部显示重要度 badge。
- 新建/编辑时可选择重要度。
- OKR 列表按 O1/O2/O3 排序展示。
- 拖拽：同重要度内更新 `sort_order`，跨重要度同时更新 `importance` 与目标组 `sort_order`（使用现有 HTML5 draggable，不引入 dnd-kit）。

**验收**

1. 新建 Objective 不传 `importance` 默认为 `o2`。
2. O1 始终排在 O2/O3 前。
3. 同组拖拽后刷新顺序一致；跨组拖拽后重要度与排序同时落库。
4. 订阅 OKR 只读视图使用同样排序，不提供拖拽。
5. AI 质量评分按同样顺序组装上下文。
6. 非法值被服务层拒绝。

#### 10.1.2 订阅权限与隐私设计

**当前**：主动订阅模型，无审批/关闭/撤销/审计。

**设计目标**

- 订阅是针对"人 + 内容类型"的授权关系，日报和 OKR 独立授权。
- 被订阅人应能控制日报/OKR 是否允许被订阅。
- 管理员不默认绕过个人内容隐私。

**数据模型**

新增 `user_privacy_settings`：

| 字段 | 说明 |
|---|---|
| `user_id` | 用户（唯一） |
| `daily_visibility` | `open` / `approval_required` / `closed` |
| `okr_visibility` | `open` / `approval_required` / `closed` |

默认 `daily_visibility=open, okr_visibility=open`（不破坏 1.0 既有体验）。

`subscriptions` 表扩展字段：

| 字段 | 说明 |
|---|---|
| `daily_status` | `none/pending/approved/rejected/revoked`（`daily_enabled` 由 `approved` 派生） |
| `okr_status` | `none/pending/approved/rejected/revoked` |
| `approved_by` | 最近批准人 |
| `approved_at` | 最近批准时间 |
| `rejected_at` | 最近拒绝时间 |
| `revoked_at` | 最近撤销时间 |

新增 `subscription_audit_logs`：

| 字段 | 说明 |
|---|---|
| `actor_id` | 操作人 |
| `subscriber_id` | 订阅人 |
| `target_user_id` | 被订阅人 |
| `content_type` | `daily` / `okr` |
| `action` | `request` / `approve` / `reject` / `revoke` / `cancel` / `auto_grant` |
| `reason` | 可选原因 |
| `created_at` | 操作时间 |

**授权矩阵**

| `daily_status` / `okr_status` | 能否读取对应内容 |
|---|---|
| `approved` | 是 |
| `pending` | 否 |
| `rejected` | 否 |
| `revoked` | 否 |
| 无关系 | 否 |

**隐私策略行为**

| `visibility` | 发起订阅 | 结果 |
|---|---|---|
| `open` | 其他 active 员工 | 直接 approved（保持 1.0 行为） |
| `approval_required` | 其他 active 员工 | 创建 pending，通知待审批 |
| `closed` | 其他 active 员工 | 403，不可订阅 |
| 任何 | 自己 | 不可订阅自己（不变） |

**派发自动订阅规则**

1. 被派发人 `daily_visibility=open` → 自动 approved 订阅。
2. `daily_visibility=approval_required` → 创建 pending，通知审批。
3. `daily_visibility=closed` → 不自动订阅，仅保留 `assigned_by` 审计。

**前端**

- 个人主页他人页：订阅按钮按隐私策略显示"订阅" / "申请订阅" / "暂不可订阅" / "待对方确认"。
- 新增个人隐私设置入口（配置日报/OKR 可见性 + 待审批申请列表）。
- 订阅列表只展示 approved；候选列表展示申请状态。

**API**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/privacy/me` | 获取我的订阅隐私设置 |
| PATCH | `/privacy/me` | 修改日报/OKR 订阅可见性 |
| GET | `/subscriptions/requests` | 待我审批的订阅申请 |
| POST | `/subscriptions/{id}/approve` | 批准 |
| POST | `/subscriptions/{id}/reject` | 拒绝 |
| POST | `/subscriptions/{id}/revoke` | 撤销已批准 |

现有订阅接口调整：创建时根据对方隐私策略决定是否直接 approved。

**非回归约束**

- 个人主页评分摘要不受订阅限制，直接可查看。
- 订阅关系只控制日报/OKR 明细视图，不控制评分摘要。
- 已批准订阅不影响评分摘要可见性。
- 派发自动订阅遵守被派发人日报隐私策略。

**验收**

1. `approval_required` 下，申请人在批准前无法读取日报/OKR。
2. `closed` 下，普通员工无法发起订阅。
3. 被订阅人可批准、拒绝、撤销。
4. 撤销后订阅者立即不能读取明细。
5. 所有订阅状态变化写入审计日志。

#### 10.1.3 订阅聚合流

**目标**：将已 approved 的订阅日报和订阅 OKR 更新整合为"关注动态"页面，减少逐个点人成本。

**设计原则**

- 不新增持久化聚合表，实时从已 approved 订阅关系中聚合。
- 不提供编辑能力。
- 不绕过订阅隐私状态，不展示未获授权的日报/OKR 明细。

**路由**：新增 `/subscription/feed`。

**API**

`GET /subscriptions/feed`，查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `content_type` | `daily` / `okr` / 空（全部） | 按内容类型筛选 |
| `target_user_id` | int / 空 | 按被订阅人筛选 |
| `cursor` | string / 空 | 游标（`updated_at,id` 编码） |
| `limit` | int | 每页条数，默认 20，≤ 50 |

返回统一卡片字段：

```json
{
  "items": [
    {
      "content_type": "daily",
      "target_user_id": 5,
      "target_name": "张三",
      "period": "2026-07-22",
      "summary": "完成了3项工作…",
      "updated_at": "2026-07-22T18:30:00Z",
      "detail_url": "/subscription/daily/5?date=2026-07-22"
    }
  ],
  "next_cursor": "eyJ0IjoiMjAyNi0wNy0yMlQxODozMDo…"
}
```

`summary` 截取订阅日报任务列表前几项文本，或订阅 OKR 的目标标题。排序按 `updated_at desc` + 稳定 id 游标分页。

**前端**

- 固定页面，顶部筛选（内容类型下拉 + 人员选择 + 日期/月份）。
- 卡片列表，每项点击进入现有关注只读详情。
- 空态：暂无已订阅同事的更新。

**权限**

- 仅展示当前用户已 approved 的订阅内容。
- 日报聚合过滤 `is_private=true` 任务。

**验收**

1. 只展示已 approved 订阅的日报/OKR。
2. 筛选条件独立生效。
3. 游标翻页不遗漏不重复。
4. 点击进入现有关注只读页。
5. 聚合流不提供编辑入口。

#### 10.1.4 企业设置审计日志

**当前**：企业设置（名称/Logo/页脚）可修改，但无审计。

**数据模型**

新增 `company_setting_audit_logs` 表：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `actor_id` | 操作人 |
| `action` | `company_settings.update` / `company_settings.logo_upload` |
| `field_name` | 变更字段 |
| `old_value` | 旧值摘要 |
| `new_value` | 新值摘要 |
| `created_at` | 操作时间 |

**API**

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/admin/company-settings/audit-logs?limit=` | `admin:settings` |

**前端**

后台企业设置页面底部增加审计日志列表展示，按操作时间倒序，显示操作人、字段、旧值/新值摘要、时间。

**验收**

1. 修改企业名称后列表中显示对应记录。
2. 上传/替换 Logo 后产生一条 logo_upload 记录。
3. 未修改时不产生无关日志。

### 10.2 P1：2.0 新增体验

#### 10.2.1 通知中心

订阅隐私 P0 阶段不依赖通知中心：待审批申请通过站内"订阅申请列表"页面处理，无需推送。通知中心作为 P1 统一加入推送能力。

**通知类型与触发场景**

| 类型 | 接收人 | 触发场景 |
|---|---|---|
| `subscription.requested` | 被订阅人 | 有人申请订阅我的日报/OKR |
| `subscription.approved` | 申请人 | 订阅申请通过 |
| `subscription.rejected` | 申请人 | 订阅申请被拒绝 |
| `subscription.revoked` | 订阅者 | 对方撤销订阅授权 |
| `daily.assigned` | 被派发人 | 有日报任务派发给我 |
| `daily.score_ready` | 本人 | 日报评分生成完成 |
| `okr.review_ready` | 本人 | OKR 点评生成完成 |

**数据模型**

`notifications` 表：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `user_id` | 接收人 |
| `title` | 标题 |
| `content` | 内容 |
| `type` | 类型码（见上表） |
| `read_at` | 已读时间，null 表示未读 |
| `extra_json` | 扩展（预留 channel 扩展位） |

**API**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/notifications?unread=&cursor=&limit=` | 通知列表（游标分页，可选仅未读） |
| GET | `/notifications/unread-count` | 未读数 |
| POST | `/notifications/{id}/read` | 标记已读 |
| POST | `/notifications/read-all` | 全部已读 |

**行为**

- AI 类通知在任务 `succeeded` 时由 `notification_service` 触发。
- 订阅相关通知在隐私状态变更时触发。
- 站内为主；邮件/IM 推送为后续扩展位。

#### 10.2.2 灵感清单

首版只支持本人私有灵感 CRUD 和"转为日报任务"，不做 OKR/月报转换。

**数据模型**

`inspirations` 表：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `user_id` | 所属员工 |
| `content` | 灵感内容 |
| `tags_json` | 标签列表 |
| `status` | `active` / `converted` / `archived` |
| `converted_task_id` | 转换成的日报任务 ID |
| `created_at` / `updated_at` / `deleted_at` | 审计时间 |

**API**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/inspirations` | 我的灵感列表 |
| POST | `/inspirations` | 新建灵感 |
| PATCH | `/inspirations/{id}` | 编辑灵感 |
| DELETE | `/inspirations/{id}` | 删除灵感 |
| POST | `/inspirations/{id}/convert-to-daily-task` | 转为日报任务，body `{date}` |

转换逻辑：同事务创建指定日期 `DailyTask`（`source=inspiration`），记录 `converted_task_id`，更新 `status=converted`。重复转换请求幂等拒绝。

**路由**：新增 `/inspirations`。

**权限**：仅本人可查看/编辑/转换自己的灵感。

**前端**

- 灵感列表页，支持新建/编辑/删除/转换。
- 转换时选择目标日期，完成后跳转到对应日报。

**验收**

1. 新建灵感后出现在列表中。
2. 转换后灵感标记已转换，目标日报出现对应事项。
3. 重复转换同一灵感返回幂等结果。
4. 他人不可查看自己的灵感。

#### 10.2.3 品牌设置扩展

登录页说明、页脚链接、默认头像/Logo、品牌色。

### 10.3 P2：后续上线能力

- AI 大脑聊天、AI 智能体、Claude 额度授权、多模型额度统计。
- 组织监管视图。
- 邮件/飞书 IM 推送（`notifications.extra_json` 预留 channel）。

### 10.4 2.0 非回归约束

**评分隐私**

个人主页评分接口当前只返回：`status`、`score`、`summary`、`updated_at`。前端只展示分数、评价摘要、生成日期。未来若增加"评分详情"，也只能展示维度分、等级、摘要、建议等 AI 输出，不得混入原始日报任务、问题、OKR Objective、KR、月报正文等业务明细。

**主题约束**

- 强调色覆盖所有交互态，新增普通交互禁止直接使用固定 `blue-*`，须读 `--theme-accent` 系列变量。
- 红绿灯红/绿/灰、成功/警告/错误、AI 分类色、协作身份色、同步状态色、品牌 Logo 等语义色不随主题变化。
- 字号档位禁止使用不联动的固定像素高度；日期卡、标题栏、任务行、Tab 等使用 `rem` 或主题尺寸变量。

---

## 11. 本地开发、测试与验收

### 11.1 环境启动

```powershell
# 后端
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload

# 前端
cd frontend
npm run dev
```

### 11.2 配置要点

- `backend/.env` 配置飞书应用凭证、`OWNER_FEISHU_UNION_ID`。
- 登录前确保空库已 `alembic upgrade head`。
- 空库先由 owner 扫码登录，再到人员管理执行"从飞书同步通讯录"。

### 11.3 数据库迁移

```powershell
cd backend
..\.venv\Scripts\python -m alembic upgrade head
```

### 11.4 联调待验证

- 飞书 `tenant_access_token`、部门树、用户归属择优（已本地脱敏测试验证）。
- 部门中文名依赖飞书 `contact:department.base:readonly` 权限并发版。
- 空库 owner bootstrap 真实扫码验证。
- 同步后普通员工扫码登录验证。
- 通讯录缺失/禁用后 `token_version+1` 验证。

### 11.5 相关文档

- 后端 README：`backend/README.md`
- 前端 README：`frontend/README.md`
- 飞书接入：`飞书应用接入与配置指引.md`

### 11.6 测试

- 后端：pytest（mock Provider），覆盖 service 编排 + API 全链路（密钥加密/脱敏、JSON 截断重试、周评分边界、今日建议上下文、OKR 无进度质量评分、月报整月聚合）。
- 前端：tsc + build 校验。
- 验收：每个路由空态/按钮/筛选项一致；越权用户不可访问受限数据；富文本不执行脚本。

---

## 12. 文档维护规则

1. **事实来源优先级**：当前代码 > 本文档 > 飞书接入指引。
2. **更新原则**：功能实现或设计变更后修改本文档对应章节，不再保留补丁式表述。
3. **删除机制**：被替代的历史设计从本文档移除，不作为并行路径保留。
4. **版本标记**：未实现功能标注规划优先级（P0/P1/P2）或当前占位状态。
5. **链接维护**：内部锚点保持有效；飞书接入指引仅链接引用，不复制详细步骤。
6. **规范**：产品名称统一使用 `Manager Platform`；不引入特定组织、个人或外部来源信息。

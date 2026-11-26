**当前版本：v0.4（实施状态校订：2026-11-26）**

**项目阶段：Phase 0、Phase 1 已完成，Phase 2 Tasks、Phase 3 Focus、Phase 4 Journal、Phase 5 Notes、Phase 6 Documents、Phase 7 Dashboard、Phase 8 Statistics 已实现。下一业务阶段为 Phase 9 Tools。**

> 2026-11-26 用户授权管理员扩展：已实现 user/admin 角色、可信服务器命令创建独立管理员、只读注册与用户统计、近 5 分钟会话去重在线、可见页面心跳、菜单及后端权限检查。私人正文保持原有用户归属校验。本机数据库迁移至 `0019_admin_and_presence` 并验证记录数保留；生产服务器更新和真实管理员创建尚待执行。[管理员代码与部署说明](docs/ADMINISTRATION.md)。此扩展不自动推进 Phase 9 Tools。

> 2026-11-02 用户确认的扩展已实现：每周重复日程、单次/后续修改、固定起止时间计时、全局右侧状态与提醒设置。数据库迁移为 `0011_weekly_schedules`，实现契约与代码清单见 `docs/WEEKLY_SCHEDULES.md`。这记录 2026-11-02 的日程/专注扩展状态；2026-11-03 已继续完成 Phase 7 工作台，详见 `docs/PHASE7_DASHBOARD.md`。

> 2026-11-04 用户授权扩展：问题备忘已实现，支持今日/历史/已解决分类、解决时间记录、编辑、搜索分页和 Markdown 导出；迁移至 `0012_problem_memos`。详见 `docs/PROBLEM_MEMOS.md`，下一业务阶段仍为 Phase 8 Statistics。

> 2026-11-04 笔记问题关联已实现：按类型筛选并选择一个问题，关联随笔记保存；迁移为 `0013_note_problem_link`，详见 `docs/NOTE_PROBLEM_LINKS.md`。

> 2026-11-04 隐私改造需求已整理，尚未开发：日记默认保存在用户绑定的真实本地目录，受保护内容逐步支持云端加密或本地保存；平台负责自身的数据流、账号隔离和密钥管理，用户本机的额外保密工作不纳入本轮。分步计划见 [隐私保护需求与实施计划](docs/PRIVACY_STORAGE_PLAN.md)。本次仅整理文档，未修改业务代码或数据库，不自动启动该计划或 Phase 8。

> 2026-11-05 已按用户指示完成隐私改造第一步：存储接口与默认本地来源、设置入口、旧云端日记主动只读查看，以及工作台排除日记信息的查询选项。当前本地目录未接入，新版前端暂不支持新增/保存日记；加密、导入、迁移及后端模式禁写尚未实现。无数据库迁移，版本仍为 `0013_note_problem_link`。详见 [第一步契约与代码清单](docs/PRIVACY_STORAGE_STEP1.md)。不自动进入第二步或 Phase 8。

> 2026-11-05 第二步已按用户指示实施：本地目录选择与账号绑定、权限检查、解绑不删文件、独立测试文件读写与冲突保护，接入登录/会话生命周期。前端 54 项测试与构建通过，原生 OPFS/IndexedDB 及真实磁盘适配器验证通过；真实用户文件夹授权仍待桌面浏览器复验。正式日记编辑、导入、加密及迁移尚未实现，无数据库变化。详见 [第二步代码清单与验证边界](docs/PRIVACY_STORAGE_STEP2.md)。不自动进入第三步或 Phase 8。

**技术栈：Vue 3 + TypeScript + FastAPI + MySQL**

> 2026-11-05 隐私改造第三步已按用户指示实现：正式日记接入本地年月 Markdown 文件，支持编辑、列表、本地搜索与安全预览；工作台本地合并今日状态；后端统一禁止旧云端写入/删除，旧记录需显式历史访问头。无数据库迁移或用户数据迁移。前端 62 项测试与构建通过，后端 181 项通过、9 项跳过，真实磁盘及 OPFS 产品页面验收通过；真实用户目录授权仍待复验。详见 [第三步修改清单与代码流程](docs/PRIVACY_STORAGE_STEP3.md)。不自动进入第四步或 Phase 8。

> 2026-11-05 第四步已按用户指示实现：Markdown 日记导入、日期与冲突预览、历史云端日记复制并读回、本地进度与恢复，以及独立确认的单篇在线云端副本清理。复制默认保留来源，无用户真实数据迁移、无表结构变化；前端 74 项、后端 185 项测试通过（另 9 项跳过），构建与 Ruff 通过。隔离页面已验证导入、迁移、刷新恢复和账号隔离，取消清理后原件全部保留；真实用户目录授权仍待复验。详见 [第四步代码清单与验证边界](docs/PRIVACY_STORAGE_STEP4.md)。第五步云端加密与 Phase 8 均未开始。

> 2026-11-05 第五步已按用户指示实现：内容认证加密、独立 DEK 与 KEK 包裹、可信对象上下文校验、外部受限密钥文件，以及平台检查/轮换/备份恢复命令。新增 54 项测试，完整后端 239 项通过、9 项跳过，Ruff 通过。没有业务加密接入、正式密钥生成、实际配置或数据库变更；现有内容不会自动加密。下一项为第六步笔记等模块接入，Phase 8 尚未开始。详见 [第五步代码清单与接入方案](docs/PRIVACY_STORAGE_STEP5.md)。

> 2026-11-08 第六步首批开放笔记普通云端与云端加密两种模式。新建可选择，已有笔记可逐篇切换。加密标题只在打开详情时显示。本机 MySQL 已迁移至 `0014_note_encryption` 并配置独立开发密钥。文档、日记的可选加密及笔记本地目录留待后续接入。详见 [第六步修改与验证](docs/PRIVACY_STORAGE_STEP6.md)。

> 2026-11-08 第六步收尾开放独立加密日记及文档原件、文件名、标题和预览加密，完成笔记本地目录评估。本机 MySQL 已应用 `0016_document_encryption`。下一步为历史迁移和副本清理。 [第六步收尾修改与验收](docs/PRIVACY_STORAGE_STEP6_COMPLETION.md)

> 2026-11-11 隐私改造第七步接入按账号和明确选择的记录分批迁移、读回后清除在线明文、事务回执及隔离恢复验证。本机 MySQL 已应用 `0017_content_migration_receipts`。实际历史迁移、备份和日志处置待部署运维执行。下一步是平台隐私验收与正式部署收尾。 [第七步操作和代码说明](docs/PRIVACY_STORAGE_STEP7.md)

> 2026-11-11 隐私改造第八步完成本地代码和隔离浏览器验收。修复同源标签页退出、旧会话响应、日记预览外部资源和通用错误日志问题。数据库架构无变化。正式部署环境、生产备份恢复及 Windows 文件夹授权仍待验收。 [第八步验收与部署检查](docs/PRIVACY_STORAGE_STEP8.md)

> 2026-11-14 日程扩展新增按周另存模板、周日确认和默认沿用。周视图增删改只影响目标周。本机 MySQL 已应用 `0018_schedule_templates`。 [日程模板修改清单](docs/SCHEDULE_TEMPLATES.md)

> 2026-11-18 Phase 8 Statistics 已实现专注时长、完成次数、每日趋势、模式分布和期间新建任务的当前状态汇总，支持本周、本月及自选日期。新增只读统计接口并复用现有表。 [统计口径、代码清单与验收](docs/PHASE8_STATISTICS.md)

> 产品规划来源于 Obsidian 的《FocusNest 项目说明书.md》。项目副本 `D:\FocusNest\PROJECT_SPEC.md` 于 2026-11-01 更新 Phase 6 实施进展；Obsidian 产品原文保留，本次未覆盖。详细契约与验证边界见 `docs/PHASE2_TASKS.md` 、`docs/PHASE3_FOCUS.md` 、`docs/PHASE4_JOURNAL.md` 、`docs/PHASE5_NOTES.md` 和 `docs/PHASE6_DOCUMENTS.md`，异步数据库改造仍未实施。
>
> 原版说明书、原 PROJECT_SPEC.md 与原 README.md 已按原始字节保存在 `D:\FocusNest\docs\archive\2026-09-29-170311\`，历史内容仅供追溯，不覆盖本版阶段顺序。

---

# 1. 项目定位

FocusNest 是一个面向个人使用的：

**Personal Workspace + Productivity Tools + Privacy-first AI**

中文可以理解为：

**个人数字工作台 / 个人效率与知识管理平台。**

它不是单纯的：

Todo List。

计时器。

Markdown 编辑器。

AI 聊天网站。

而是把这些能力组合成一个统一的个人工作空间。

核心工作流：

```
计划
↓
任务
↓
专注
↓
阅读
↓
笔记
↓
日记
↓
复盘
↓
AI 辅助
```

FocusNest 的目标是成为一个可以长期使用、长期迭代的个人项目。

---

# 2. 项目核心原则

FocusNest 需要遵守几个长期原则。

## 2.1 非 AI 功能本身必须可用

即使完全关闭 AI，FocusNest 仍然应该是一个完整可用的个人效率网站。

AI 只是增强功能，而不是网站存在的前提。

---

## 2.2 AI 默认不能访问私人工作区

普通 Chat AI 默认只能访问：

当前聊天。

用户主动上传的文件。

用户主动粘贴的内容。

默认禁止访问：

Tasks。

Journal。

Notes。

Documents。

Focus Sessions。

其他私人工作区数据。

---

## 2.3 用户必须明确授权 AI 使用数据

未来如果 AI 需要读取工作区数据，应采用：

用户主动选择。

用户明确授权。

Tool Calling 权限控制。

而不是 AI 自动扫描全部私人数据。

---

## 2.4 写操作需要更高权限

在用户已提供内容或已明确授权的数据范围内，AI 可以自动：

搜索。

读取。

总结。

分析。

生成建议。

但以下操作原则上需要用户确认：

创建任务。

修改任务。

修改笔记。

修改日记。

删除数据。

执行 Agent Action。

---

## 2.5 项目避免过度设计

项目不应该为了“看起来高级”而一开始加入：

Multi-Agent。

Redis。

Elasticsearch。

复杂消息队列。

微服务。

大量第三方框架。

先把简单可靠的系统做好。

---

# 3. 技术架构

整体采用前后端分离。当前已实现 Vue → HTTP → FastAPI → SQLAlchemy Session / PyMySQL → MySQL，以及 Authentication、Tasks、Focus、Journal、Notes 和 Documents。下图展示完整规划；SSE、Tools 和 AI 尚未实现。

```
Browser
   │
   ▼
Vue 3 + TypeScript
   │
   │ HTTP / SSE
   ▼
FastAPI
   │
   ├── Authentication
   ├── Tasks
   ├── Focus
   ├── Journal
   ├── Notes
   ├── Documents
   ├── Tools
   └── AI
          │
          ▼
        MySQL
```

---

# 4. 技术栈

## 4.1 前端

Vue 3。

TypeScript。

Vite。

Vue Router。

Pinia。

Axios。

Element Plus（当前已按需引入 2.13 系列）。

后期考虑：

ECharts。

Markdown 编辑器。

PDF Reader。

---

# 4.2 后端

Python。

FastAPI。

Pydantic 2。

Pydantic Settings。

SQLAlchemy 2.x。

当前实现：同步 Session、create_engine、PyMySQL。

目标异步方案：AsyncSession、asyncmy（尚未实现）。后续需作为独立技术改造范围统一调整连接、依赖、Repository、Service 和测试，不能将该目标写成已完成事实，也不在本次文档同步中修改代码。

Alembic。

Uvicorn。

---

# 4.3 数据库

MySQL。

字符集：

utf8mb4。

数据库迁移：

Alembic。

---

# 4.4 后期技术

后续根据实际需求逐步加入：

Redis。

Docker。

Nginx。

SSE。

Embedding。

RAG。

Tool Calling。

Agent。

MCP。

这些不属于当前阶段。

---

# 5. 整体产品结构

最终 FocusNest 建议形成：

```
FocusNest
│
├── Dashboard
│
├── Workspace
│   ├── Tasks
│   ├── Focus
│   ├── Journal
│   ├── Notes
│   └── Documents
│
├── Tools
│   ├── Calculator
│   ├── Markdown Preview
│   ├── Coding Tools
│   └── 其他工具
│
├── AI
│   ├── Chat AI
│   └── Workspace Agent
│
├── Statistics
│
└── Settings
    ├── Account
    ├── Appearance
    ├── AI Provider
    └── Privacy
```

---

# 6. Dashboard

Dashboard 是用户登录之后的主页面。

应该用于展示最重要的信息。

例如：

今日任务。

今日专注时间。

最近笔记。

日记状态。

最近文档。

快捷开始专注。

后期可以加入：

AI Daily Review。

自定义 Widget。

Dashboard 不应该成为所有功能的堆积页面。

---

# 7. Tasks

Task 是核心模块之一。

用户可以：

创建任务。

编辑任务。

完成任务。

删除任务。

设置优先级。

设置截止日期。

安排到某一天。

设置预计耗时。

后续可以加入 Project。

---

# 8. Focus

Focus 是任务执行层。

支持：

Pomodoro。

倒计时。

正计时。

自定义时间。

每次专注形成一条：

FocusSession。

FocusSession 可以关联 Task。

例如：

```
Task

学习 FastAPI

Focus Sessions

45 min
50 min
30 min

Total

125 min
```

以后可以用于统计：

预计时间。

实际时间。

学习习惯。

任务耗时误差。

---

# 9. Journal

Journal 代表每天的个人记录。

建议：

一个用户每天默认一篇。

内容采用 Markdown。

例如：

```
今天完成了什么

今天学到了什么

遇到了什么问题

今天值得记录什么

明天准备做什么
```

Journal 与 Note 的定位不同。

Journal：

**记录今天。**

---

# 10. Notes

Notes 用于：

知识记录。

学习笔记。

想法。

代码笔记。

长期知识。

内容采用 Markdown。

Note：

**记录知识和想法。**

未来支持：

Folder。

Pin。

Search。

Markdown Preview。

Read Mode。

---

# 11. Documents

Documents 用于：

保存外部资料。

阅读资料。

管理文件。

未来 AI 分析。

优先支持：

Markdown。

TXT。

后期支持：

PDF。

Document：

**表示外部或独立文档资源。**

因此：

```
Journal
= 今天发生了什么

Note
= 我记录的知识

Document
= 我正在阅读的资料
```

三者不能混在一起。

---

# 12. Tools

Tools 是 FocusNest 的可扩展区域。

这里放：

独立。

轻量。

不属于核心工作流。

的小工具。

例如：

Calculator。

JSON Formatter。

Timestamp Converter。

Markdown Preview。

Base64。

Text Diff。

Regex Tester。

UUID Generator。

Coding Playground。

部分工具可以只运行在 Vue 前端，不需要 FastAPI。

这一模块可以随着个人学习不断增加。

---

# 13. Appearance

FocusNest 是个人工作台，因此允许一定程度的个性化。

未来支持：

Light。

Dark。

System。

主题颜色。

背景图片。

渐变背景。

紧凑布局。

舒适布局。

Dashboard Widget 自定义。

但视觉个性化不应该影响核心功能稳定性。

---

# 14. 用户系统

虽然主要面向自用，但仍然按照多用户架构设计。

这样：

可以部署给朋友使用。

未来小程序可以共用。

AI 权限隔离更容易。

核心：

Register。

Login。

JWT。

Refresh Token。

Current User。

Profile。

Settings。

---

# 15. 用户数据关系

核心关系：

```
User
│
├── Tasks
│   └── FocusSessions
│
├── Journals
│
├── Notes
│
├── Documents
│
├── ChatConversations
│
├── AIConfigs
│
└── Preferences
```

所有私人资源必须有：

user_id。

后端必须验证资源归属。

---

# 16. AI 总体设计

AI 不作为一个单一模块。

FocusNest 未来分成三种 AI 能力。

```
1. Platform Chat AI

2. Private AI

3. Workspace Agent
```

---

# 17. Platform Chat AI

这是 FocusNest 提供的普通聊天 AI。

使用：

网站自己的 AI API。

适合：

普通聊天。

公开知识。

普通文件分析。

代码问题。

普通学习问题。

界面必须明确提示：

**不要上传敏感隐私信息。**

同时应该告诉用户：

当前使用的是平台提供的模型。

---

# 18. Platform AI 数据权限

默认只能访问：

当前 Conversation。

当前消息。

用户主动上传的附件。

不能自动访问：

Journal。

Notes。

Tasks。

Documents。

Focus Data。

Workspace。

---

# 19. 聊天附件

用户可以主动：

上传 PDF。

上传 Markdown。

上传 TXT。

上传图片。

粘贴文本。

然后请求：

总结。

解释。

分析。

问答。

AI 只能分析当前用户主动提供的内容。

---

# 20. Private AI

除了平台 AI，FocusNest 应该允许用户：

使用自己的 AI Provider。

用户可以配置：

Provider。

Model。

Base URL。

API Key。

例如：

OpenAI。

Anthropic。

Gemini。

DeepSeek。

OpenAI Compatible API。

本地模型。

---

# 21. API Key 模式

未来可以提供不同隐私级别。

## 模式一

用户 API Key 由服务器加密保存。

体验最好。

服务器仍具备使用 Key 的能力。

---

## 模式二

Key 只在当前 Session 使用。

不长期保存。

隐私更强。

---

## 模式三

本地 AI。

例如：

Ollama。

LM Studio。

用户自己的 OpenAI Compatible Server。

敏感内容可以尽可能留在用户自己的环境中。

---

# 22. AI Provider 层

业务代码不能绑定某一个模型厂商。

建议：

```
AI Service
    │
    ▼
Provider Interface
    │
    ├── PlatformProvider
    ├── OpenAIProvider
    ├── GeminiProvider
    ├── AnthropicProvider
    ├── OllamaProvider
    └── CustomProvider
```

以后 Chat、RAG 和 Agent 都使用这一层。

---

# 23. AI 隐私规则

AI 模块必须遵守：

默认不读取私人数据。

只发送当前功能所必需的数据。

日志不能保存完整敏感 Prompt。

日志不能打印 API Key。

AI Key 不进入 Vue 源码。

AI Key 不出现在浏览器 Bundle。

用户应该知道本次请求发送了什么数据。

---

# 24. AI 上下文提示

未来 Chat 页面可以显示：

```
AI 当前可以访问

✓ 当前聊天
✓ database.pdf

AI 当前不能访问

✗ Journal
✗ Notes
✗ Tasks
✗ Workspace Documents
```

这比单纯写隐私政策更明确。

---

# 25. Workspace Agent

Workspace Agent 与普通 Chat AI 完全不同。

Agent 是高级功能。

只有用户明确进入 Agent 模式之后，才允许通过 Tools 使用工作区数据。

例如：

```
list_tasks

get_focus_statistics

search_notes

read_document

read_journal
```

---

# 26. Agent 权限

Tool 分级。

## Read Tool

例如：

list_tasks。

search_notes。

get_focus_stats。

可以根据用户设置自动执行。

## Write Tool

例如：

create_task。

update_task。

需要确认。

## Destructive Tool

例如：

delete_document。

delete_note。

必须强确认。

---

# 27. Agent 架构

未来：

```
User
 ↓
Agent
 ↓
Tool
 ↓
Service
 ↓
Repository
 ↓
MySQL
```

Tool 不能直接写数据库。

Agent 和 REST API 共用 Service 层。

---

# 28. 非 AI 开发顺序

当前项目先完成非 AI 部分。

开发顺序：

```
Phase 0
基础框架

Phase 1
Authentication

Phase 2
Tasks

Phase 3
Focus

Phase 4
Journal

Phase 5
Notes

Phase 6
Documents

Phase 7
Dashboard

Phase 8
Statistics

Phase 9
Tools

Phase 10
部署
```

---

# 29. 当前实现状态

## Phase 0：已完成

- Vue 3、TypeScript、Vue Router、Pinia、Axios、Element Plus 基础框架。
- FastAPI、Pydantic Settings、SQLAlchemy 2.x 同步 Session、PyMySQL、MySQL、Alembic。
- Health API、CORS、统一响应及异常处理。
- 前端工作台基础页面与服务状态检查。当前不是完整的业务 Dashboard。

已经验证 Vue → Axios → FastAPI → SQLAlchemy → MySQL 基础链路。

当前 Health API 契约：

`GET /api/v1/health` 不查询数据库，返回：

```json
{
  "code": 0,
  "message": "success",
  "data": { "status": "ok", "database": "not_checked" }
}
```

`GET /api/v1/health?check_database=true` 执行 SELECT 1，成功时 data.database 为 connected，连接失败返回 HTTP 503 和 code 50301。

## Phase 1：已完成

- User 与 AuthSession 模型、Pydantic Schema、Alembic 迁移。
- 注册、用户名或邮箱登录、退出登录。
- Argon2id 密码哈希、HS256 JWT Access Token。
- HttpOnly / SameSite=Strict Cookie 刷新令牌，数据库只保存刷新摘要。
- 刷新原子轮换、重放拒绝、会话到期及撤销检查。
- Current User 依赖、本人资料读取和修改、权限隔离测试。
- 前端注册登录页、路由守卫、内存访问令牌、刷新恢复登录及账号设置。

新增接口：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | /api/v1/auth/register | 注册 |
| POST | /api/v1/auth/login | 登录 |
| POST | /api/v1/auth/refresh | 刷新令牌 |
| POST | /api/v1/auth/logout | 撤销当前会话 |
| GET | /api/v1/users/me | 读取本人资料 |
| PATCH | /api/v1/users/me | 修改昵称、头像链接及 IANA 时区 |

Phase 1 引入 users、auth_sessions 与 alembic_version，迁移为 0002_users_auth。

## Phase 2：已实现（2026-10-11）

- Task 模型、Schema、Repository、Service、Router，迁移 0003_tasks 已应用到本机 MySQL。
- 创建、分页列表、详情、编辑、删除、完成与恢复待办。
- 状态 todo/doing/done，优先级 low/medium/high，计划日期、截止日期和预计耗时。
- 今日任务按用户 IANA 时区计算，包含计划日期或截止日期为今天的任务；可组合状态、优先级和日期过滤。
- 所有读写使用当前认证用户限定所属关系；他人任务与不存在任务均返回 404。
- 前端 /tasks 任务页、侧边栏入口、编辑表单、空状态与删除确认。
- MySQL 57 项测试通过；SQLite 56 项通过、1 项跳过；Ruff、Alembic check、前端构建通过。
- 浏览器已验证创建、编辑、完成、恢复、筛选、重新打开恢复会话，以及删除确认框打开和取消。实际删除经前端代理的 HTTP 请求验证，临时用户、任务和会话均已清理。

当前表为 users、auth_sessions、tasks、focus_sessions、journals、notes、note_folders、documents、alembic_version。迁移链：0001_baseline → 0002_users_auth → 0003_tasks → 0004_focus_sessions → 0005_focus_timer_precision → 0006_journals → 0007_notes → 0008_note_folders → 0009_documents → 0010_document_formats。

Phase 3 于 2026-10-16 实现：三种计时模式、自定义时长、暂停/继续、完成/取消、任务关联、持久化恢复与历史分页；用户级并发锁及唯一约束保证单一活动计时。MySQL 全量 78 项通过，详情见 docs/PHASE3_FOCUS.md。

Phase 4 于 2026-10-23 实现：用户每日唯一日记、Markdown 编辑预览、历史检索、版本冲突保护及删除确认；MySQL 全量 95 项通过，详情及代码清单见 docs/PHASE4_JOURNAL.md。

## 已有验证记录与边界

2026-09-28 已验证本机独立 MySQL 实例：127.0.0.1:3307/focusnest，数据目录 D:\MySQL-FocusNest\Data。在线迁移达到 0002_users_auth；真实 MySQL 测试 36 项通过，默认隔离测试 35 项通过、1 项跳过；前端构建和浏览器认证流程通过。

2026-09-28 的结果为 Phase 1 历史验收记录；2026-10-11 的 Phase 2 新验证见上节和 docs/PHASE2_TASKS.md。运行命令见 README.md。

AsyncSession/asyncmy 改造尚未完成；邮箱验证、密码找回/修改、登录限流、自动清理过期会话、完整主题设置仍未实现。笔记、文档、Tools 和 AI 尚未开发。

---

## Phase 5：已实现（2026-10-30）

- 私人 Markdown 笔记增删改查、置顶、搜索分页、阅读模式与安全预览。
- 用户归属校验、修改/删除版本冲突保护、未保存提示。
- 新增 notes 表，迁移 0007_notes 接在 0006_journals 后，已应用本机 MySQL。
- MySQL 116 项通过；SQLite 111 项通过、5 项跳过；Ruff、Alembic check、前端构建、3 项 Markdown 测试通过。
- 浏览器与 HTTP 代理验收完成，具体范围及限制见 docs/PHASE5_NOTES.md；初始实现未包含 Folder；2026-10-30 追加嵌套文件夹、重命名、归类和保留笔记的目录删除，见 docs/PHASE5_NOTE_FOLDERS.md。标签、自动保存、版本历史仍未实现。

- 文件夹追加：迁移 0008_note_folders 已应用；MySQL 全量 127 项及追加并发 1 项分别通过，SQLite 122 项通过、6 项跳过；前端构建及 5 项测试通过。本次浏览器验收受审批服务用量限制，尚未执行。

## Phase 6：已实现（2026-11-01）

- UTF-8 Markdown/TXT 上传、元数据列表、标题/文件名搜索、类型筛选、分页、阅读、原件下载、标题重命名和删除。
- 原始字节保存在 MySQL documents 表；迁移 0009_documents 已应用。文本上传最大 512 KB、正文最多 100000 字符；追加 PDF/Office 原件最大 10 MB，预览按部分截取。
- 用户归属校验、版本冲突保护、no-store 与附件下载；没有正文编辑、资料文件夹或 AI。2026-11-01 追加 PDF、DOCX、PPTX、XLSX/XLS 内容预览，Office 复杂版式不完整还原；旧 DOC/PPT 暂不支持。
- MySQL 147 项通过；SQLite 139 项通过、8 项跳过；Ruff、pip check、Alembic check 和前端构建、10 项前端测试通过。
- 独立账号真实 HTTP 全流程通过，测试数据已清理；浏览器仅验收入口、筛选控件和空状态，写操作及下载落盘未逐项验收。
- 详细文件清单、知识语法与边界见 docs/PHASE6_DOCUMENTS.md。

- 多格式追加迁移为 0010_document_formats；MySQL 最终 158 项通过，SQLite 150 项通过、8 项跳过；文件清单、解析限制和验证边界见 docs/DOCUMENT_FORMAT_PREVIEWS.md。

# 30. 下一业务阶段

**Phase 7 Dashboard 已于 2026-11-03 实现，Phase 8 Statistics 已于 2026-11-18 实现。下一业务阶段为 Phase 9 Tools。**

当前工作台已整合任务、专注、日记状态、最近笔记/文档、快捷专注及日程。统计页提供专注趋势及任务概况，新增只读接口并复用现有表。详见 [Phase 8 说明](docs/PHASE8_STATISTICS.md)。

AsyncSession/asyncmy 仍是独立待实施改造。完成一个阶段后不自动进入下一阶段。

---

# 31. 为什么 Authentication 优先

未来所有数据：

Tasks。

Focus。

Journal。

Notes。

Documents。

Chat。

AI Config。

Agent。

都必须知道：

```
当前用户是谁？
```

因此 Authentication 是所有业务模块的基础。

---

# 32. Web 优先策略

项目首先开发：

Web 版本。

原因：

开发体验好。

调试方便。

浏览器工具完善。

更容易理解前后端通信。

当前：

```
Vue
↓
FastAPI
↓
MySQL
```

先完整开发。

---

# 33. 小程序扩展

未来可以加入微信小程序。

架构变成：

```
Vue Web ──────┐
              │
微信小程序 ────┼── FastAPI ── MySQL
              │
未来 App ─────┘
```

小程序复用：

FastAPI。

MySQL。

业务 Service。

AI。

Agent。

不重新开发核心后端。

---

# 34. 小程序登录

Web 可以使用：

账号密码。

JWT。

小程序未来可以：

微信登录。

然后 FastAPI 返回自己系统的 Token。

这一阶段未来单独设计。

---

# 35. 服务器部署

未来服务器结构：

```
Internet
   ↓
Nginx
   │
   ├── Vue dist
   │
   └── /api
         ↓
      FastAPI
         ↓
       MySQL
```

后期可以使用：

Docker。

Docker Compose。

---

# 36. 部署原则

Vue 正式环境使用：

build 后的静态文件。

不能长期使用 Vite dev server。

FastAPI 运行在内部服务。

MySQL 不应该直接暴露公网。

需要：

HTTPS。

环境变量。

数据库备份。

防火墙。

日志。

进程管理。

---

# 37. AI 开发顺序

非 AI 系统稳定以后：

```
AI Provider
↓
普通 Chat
↓
Streaming
↓
文件分析
↓
Structured Output
↓
Document AI
↓
Embedding
↓
RAG
↓
Tool Calling
↓
Single Agent
↓
Human Approval
↓
Tracing
↓
Evaluation
↓
MCP
↓
Multi-Agent（如果真的需要）
```

---

# 38. AI Full Stack 和 Agent 的关系

FocusNest 不应该一开始就是 Agent 项目。

建议经历：

```
普通 Full Stack
↓
AI Full Stack
↓
Tool Calling
↓
Agent
```

这样可以清楚理解每一层。

---

# 39. RAG

未来文档 AI：

```
Document
↓
Parser
↓
Chunk
↓
Embedding
↓
Vector Search
↓
LLM
```

MySQL 始终负责：

业务数据。

用户。

文档 Metadata。

Chunk Metadata。

向量检索未来可以使用独立方案。

---

# 40. Privacy-first 定位

FocusNest 后期可以将产品定位进一步明确为：

**Privacy-first Personal AI Workspace**

核心不是：

“AI 可以看到用户的一切。”

而是：

“AI 默认什么都不能看。”

用户每一次授权决定：

AI 可以看到什么。

AI 可以做什么。

AI 是否可以修改数据。

---

# 41. Chat 与 Agent 的区别

必须在 UI 和后端都明确区分。

```
Chat AI

当前聊天
+
主动上传内容
```

和：

```
Workspace Agent

明确授权
+
Tools
+
Workspace Data
```

不能混成一个 AI。

---

# 42. 项目最终价值

FocusNest 最终应该同时体现：

前端开发。

后端开发。

数据库设计。

REST API。

认证授权。

文件系统。

Markdown。

PDF。

搜索。

统计。

Docker。

部署。

LLM API。

Streaming。

RAG。

Tool Calling。

Agent。

隐私与权限设计。

---

# 43. 项目最终目标

最终 FocusNest 应该是：

可以实际使用。

可以长期使用。

可以部署。

可以给其他用户使用。

可以扩展小程序。

可以加入 AI。

可以加入 Agent。

可以作为 GitHub 项目。

可以写入简历。

可以在面试中完整解释。

---

# 44. 当前项目定位总结

FocusNest 当前最准确的定义是：

> FocusNest 是一个以个人任务、专注、日记、笔记和文档为核心的个人数字工作台，同时提供可扩展工具箱和隐私优先的 AI 能力。普通聊天 AI 默认与私人工作区隔离，只有用户主动上传或授权的数据才能进入 AI 上下文；未来 Workspace Agent 通过受控 Tool Calling 操作个人工作区。

---

# 45. 当前开发重点

目前暂时忽略：

AI。

Agent。

RAG。

小程序。

Redis。

复杂部署。

当前只关注：

```
Authentication
↓
Tasks
↓
Focus
↓
Journal
↓
Notes
↓
Documents
↓
Dashboard
↓
Statistics
```

先把 FocusNest 做成一个真正好用的非 AI 个人工作台。

---

# 46. 版本历史

## v0.1

最初设计。

定位：

校园综合生活平台。

主要包括：

用户。

帖子。

评论。

课程。

二手交易。

后来放弃这一方向。

---

## v0.2

FocusNest 初版。

项目从校园平台调整为：

个人效率系统。

主要模块：

Task。

Focus。

Journal。

Notes。

Documents。

AI。

---

## v0.3

AI Workspace 版本。

加入：

RAG。

Tool Calling。

Agent。

Personal AI OS。

并明确：

先 Full Stack。

再 AI Full Stack。

最后 Agent。

---

## v0.4

当前版本。

进一步确定：

FocusNest 是：

**个人数字工作台 + 可扩展工具箱 + Privacy-first AI。**

新增或明确：

Tools 模块。

Appearance。

Web 优先。

未来微信小程序。

平台共享 AI。

用户自带 AI。

本地模型。

Chat AI 与 Workspace Agent 分离。

AI 默认不得读取私人工作区。

用户主动上传或授权后才能分析数据。

当前阶段继续优先完成非 AI 部分。

---

# 47. 下一版本计划

预计文档版本：**v0.5**。

Authentication 代码已经完成。下一版计划在已有实现基础上整理并补全认证设计文档，包括 User / AuthSession 字段说明、JWT 与刷新生命周期、权限模型、前后端流程、API 和数据库 ER Diagram。README 已有接口与认证摘要，独立完整设计文档和 ER 图仍待补充。

产品下一业务阶段为 Phase 9 Tools。文档版本更新与功能阶段推进分别管理。

---

# 48. 实施与工作记录约定

- 开发前阅读当前项目代码与本说明书，只执行用户指定阶段。
- 数据库结构修改通过 Alembic Migration，禁止以应用启动时 create_all 代替正式迁移。
- 后端职责按 Router → Service → Repository → Database 划分；未来 Agent Tool 复用 Service。
- 所有私人资源必须在后端核验所属用户；AI 授权不能替代用户数据隔离。
- AI 与普通业务解耦，遵循最小上下文、明确授权、写入确认及删除强确认。
- 重要功能添加对应测试；阶段完成后报告改动、数据库/API 变化、运行方式、验证结果、限制和下一阶段。
- 每次工作按 AGENTS.md 写 Markdown 记录到指定 Obsidian 目录，不包含密码或密钥。
- 历史阶段说明与本版冲突时，以本版产品原则和阶段排序为准；完成状态仍需以实际代码与验证记录为依据。

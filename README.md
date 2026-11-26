# FocusNest

**2026-11-26 管理员扩展已实现。** 支持独立管理员控制台创建命令、角色权限、用户列表、注册人数和近 5 分钟在线统计，数据库版本为 `0019_admin_and_presence`。 [管理员使用、文件清单和更新步骤](docs/ADMINISTRATION.md)

Vue 3 + FastAPI + MySQL 个人智能工作台。已实现 **Phase 1 用户系统、Phase 2 任务系统、Phase 3 专注模块、Phase 4 日记模块、Phase 5 笔记模块、Phase 6 文档资料库、Phase 7 工作台与 Phase 8 统计**。统计支持专注趋势、模式分布、任务概况和日期筛选。 [统计模块使用与代码说明](docs/PHASE8_STATISTICS.md)

ER 图、数据字典、索引和 SQL 练习见 [数据库结构与学习指南](docs/DATABASE_GUIDE.md)。

专注支持番茄钟、倒计时、正计时，以及指定起止时间；并加入每周复用日程、全局状态栏与提醒，见 [日程扩展说明](docs/WEEKLY_SCHEDULES.md) 和 [Phase 3 说明](docs/PHASE3_FOCUS.md)。

**2026-11-05 日记本地化已实现至第四步。**本地 Markdown 日记支持编辑、搜索、工作台状态、文件导入和历史云端迁移。迁移先预览、复制并读回，来源默认保留。单篇在线云端副本清理需独立确认和再次校验。真实用户目录授权仍需在支持的桌面浏览器中复验。 [第三步本地日记](docs/PRIVACY_STORAGE_STEP3.md) · [第四步代码清单、流程及验证边界](docs/PRIVACY_STORAGE_STEP4.md)

**2026-11-08 笔记已开放普通云端和云端加密。**新建笔记可选择保存方式，已有笔记可单独确认切换。加密笔记在列表及工作台显示占位，打开详情时读取标题和正文。本机已应用迁移 `0014_note_encryption` 并配置独立开发密钥。其他环境先升级数据库，再配置外部密钥并重启后端。 [第六步使用和代码说明](docs/PRIVACY_STORAGE_STEP6.md) · [第五步密钥管理](docs/PRIVACY_STORAGE_STEP5.md)

笔记支持 Markdown 编辑与阅读、置顶、搜索分页、嵌套文件夹及版本冲突保护，见 [Phase 5 文件清单、流程与知识语法说明](docs/PHASE5_NOTES.md)。

**第六步收尾已交付。** 日记默认本地，可单独进入云端加密视图并逐篇复制。文档可加密上传和切换保存方式，保护原件、标题、文件名与预览。本机已升级到 `0016_document_encryption`。 [第六步收尾修改与验收](docs/PRIVACY_STORAGE_STEP6_COMPLETION.md)

**2026-11-11 隐私改造第七步已接入运维命令。** 历史笔记、文档和云端日记可按账号选定记录迁移，校验后清除在线明文副本。隔离恢复使用可信清单比对和密文读回检查。本机 MySQL 已升级到 `0017_content_migration_receipts`。 [历史迁移和恢复操作](docs/PRIVACY_STORAGE_STEP7.md)

**隐私改造第八步已完成本地验收。** 补齐同源标签页会话隔离、日记预览的外部资源限制和通用异常日志处理，已用隔离 Chrome 验证本地日记的网络请求及原生 OPFS 文件读写。正式域名、代理日志和 Windows 文件夹授权需在发布环境补验。 [用户说明与部署检查](docs/PRIVACY_STORAGE_STEP8.md)

## 项目说明书与路线图（实施进展更新于 2026-11-18）

产品说明采用 v0.4 规划。项目根目录 `PROJECT_SPEC.md` 已更新 Phase 8 进展。本 README 记录实际运行与实现细节。

- 当前数据库访问方式为同步 SQLAlchemy Session + PyMySQL；AsyncSession + asyncmy 是尚未实施的异步目标。
- 前端已使用 Element Plus；首页 Dashboard 已汇总任务、专注、日记、最近笔记/文档和日程，详见 [Phase 7 说明](docs/PHASE7_DASHBOARD.md)。
- 当前已完成 Phase 0、Phase 1，已实现 Phase 2 Tasks、Phase 3 Focus、Phase 4 Journal、Phase 5 Notes、Phase 6 Documents、Phase 7 Dashboard 与 Phase 8 Statistics。下一业务阶段为 Phase 9 Tools。
- 后续顺序：Phase 2 Tasks → 3 Focus → 4 Journal → 5 Notes → 6 Documents → 7 Dashboard → 8 Statistics → 9 Tools → 10 部署。
- 非 AI 核心先完成；普通聊天 AI 默认只使用当前聊天和用户主动提供的内容。Workspace Agent 必须在明确授权范围内通过 Tool → Service 操作，写入需确认。
- Tools、Appearance、AI Provider 和未来小程序属于新版规划，不代表当前已实现。
- 同步前文档备份：`docs/archive/2026-09-29-170311/`。原说明书内容完整保留在归档中。

## 本机运行

本机项目数据库连接为 `127.0.0.1:3307/focusnest`，此前确认数据目录为 `D:\MySQL-FocusNest\Data`。2026-11-01 已迁移至 `0010_document_formats`，原 3306 实例未修改。本机 JWT 密钥保存在被 Git 忽略的 `backend/.env`，不要分享或提交该文件。

PowerShell 终端一：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\init_auth_secret.py
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

PowerShell 终端二：

```powershell
cd D:\FocusNest\frontend
npm ci
npm run dev
```

打开 http://127.0.0.1:5173/register 创建自己的账号。没有预置用户或默认账号密码。

已有账号可打开 http://127.0.0.1:5173/focus 使用专注计时。http://127.0.0.1:5173/journals 连接本地目录后可编辑正式日记，文件为 `YYYY/MM/YYYY-MM-DD.md`；旧云端记录通过独立只读入口查看。需同时运行更新后的前后端，旧客户端日记写入将被拒绝。笔记入口为 http://127.0.0.1:5173/notes 。

已有账号登录后点击侧边栏“任务”，或打开 http://127.0.0.1:5173/tasks 。任务仅属于当前账号。

- 前端：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health
- 数据库检查：http://127.0.0.1:8000/api/v1/health?check_database=true

前后端开发服务需要同时运行。推荐始终使用 `127.0.0.1`，避免与 `localhost` 切换造成 Cookie 所属主机不同。

## 新环境配置

需要 Python 3.11+、Node.js 20.19+ 或 22.12+、MySQL 8.0+。本机验证环境为 Python 3.14、Node 20.19.5、MySQL 8.0.44。

首次安装需先在 `backend` 执行 `python -m venv .venv`。将 `backend/.env.example` 复制为 `.env`，填入数据库连接配置。已有 `.env` 不要覆盖。数据库与账号需由管理员创建，例如：

```sql
CREATE DATABASE focusnest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'focusnest'@'localhost' IDENTIFIED BY 'replace-with-your-own-password';
GRANT ALL PRIVILEGES ON focusnest.* TO 'focusnest'@'localhost';
```

配置项：

| 变量 | 含义 |
| --- | --- |
| `MYSQL_HOST` / `MYSQL_PORT` | 数据库主机和端口；模板默认 3306，本机独立实例为 3307 |
| `MYSQL_DATABASE` / `MYSQL_USER` / `MYSQL_PASSWORD` | 数据库名、账号和密码 |
| `JWT_SECRET` | 至少 32 字符的随机签名密钥；用初始化脚本生成 |
| `ACCESS_TOKEN_MINUTES` | 访问令牌寿命，默认 15 分钟 |
| `REFRESH_TOKEN_DAYS` | 登录会话绝对寿命，默认 7 天；刷新不会延长此期限 |
| `COOKIE_SECURE` | 本地 HTTP 为 false，HTTPS 部署设为 true |
| `CORS_ORIGINS` | 允许的前端来源 JSON 数组 |

`init_auth_secret.py` 仅生成缺失的密钥，不输出密钥、不替换已有密钥、不改数据库配置。修改 `.env` 后需重启后端。未配置合格签名密钥时，登录及刷新返回 503。

前端 `VITE_API_BASE_URL` 默认为 `/api/v1`。Vite 开发代理转发至后端 8000；生产或静态预览需要独立反向代理/正确的 API 地址与 CORS。任何 `VITE_` 变量都不得包含密码或密钥。

## API

统一响应格式：`{ "code": 0, "message": "success", "data": ... }`。失败保留相应 HTTP 状态码，返回业务错误码和通用消息，不回显请求内的密码。

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/api/v1/health` | 应用检查；`check_database=true` 增加 MySQL 检查 |
| POST | `/api/v1/auth/register` | 注册，JSON: username、email、password，返回 201 |
| POST | `/api/v1/auth/login` | 登录，JSON: username、password；username 可填用户名或邮箱 |
| POST | `/api/v1/auth/refresh` | 使用 HttpOnly Cookie 换取访问令牌，并轮换刷新令牌 |
| POST | `/api/v1/auth/logout` | 撤销当前 Cookie 对应的登录会话并清除 Cookie |
| GET | `/api/v1/users/me` | 使用 Bearer 访问令牌获取本人资料 |
| PATCH | `/api/v1/users/me` | 修改本人昵称、头像 URL 和 IANA 时区 |

注册用户名为 3–32 位 ASCII 字母、数字或下划线；用户名保留输入的大小写用于显示，登录和重复检查忽略大小写；邮箱统一转小写，用户名与邮箱分别唯一。密码 10–128 字符且区分大小写。登录错误统一提示，不区分账号不存在和密码错误。邮箱当前只校验格式，不发送验证邮件。

个人资料 PATCH 接受 `nickname`、`avatar_url`、`timezone`。可选昵称和头像支持传 null 清除；省略字段保持不变。时区必须为有效 IANA 名称，例如 `Asia/Shanghai`、`UTC`。拒绝客户端提交 id、password_hash、username 等非允许字段。头像仅保存 HTTP(S) URL，当前不自动访问该地址或展示远程图像。

Swagger 使用 JSON 登录；复制响应内 access_token 到 Authorize 的 HTTP Bearer 输入框即可访问 `/users/me`。浏览器会保存刷新 Cookie；API 客户端测试刷新流程必须启用 Cookie 管理。

## 认证与隔离

- 密码使用 Argon2id 哈希，不存明文。
- JWT 使用 HS256，验证签名、有效期、签发者、受众、令牌类型以及必需字段。
- JWT 包含用户 id 和会话 id；每次访问 `/users/me` 时再检查会话未撤销、未过期且属于该用户。
- 随机刷新令牌仅放在 HttpOnly、SameSite=Strict Cookie 中，路径为 `/api/v1/auth`；数据库只存 SHA-256 摘要。
- 刷新采用条件 UPDATE 原子轮换，旧刷新令牌不能重复使用；会话寿命不会因刷新无限延长。
- 退出登录使当前会话的访问令牌与刷新令牌失效，其他设备会话不受影响。
- 浏览器访问令牌只放内存，不存 localStorage；页面重载用 Cookie 恢复会话，401 时单次刷新后重试。
- 支持 Web Locks 的浏览器中，多个标签页的 Cookie 轮换与退出请求串行化。
- 认证入口校验浏览器 Origin 与跨站请求标记；CORS 允许指定来源携带凭据。开发代理、同源 Swagger 均可用。生产建议同站部署并启用 HTTPS。
- 私人接口返回 `Cache-Control: no-store`。
- 当前只提供本人接口，没有根据客户端指定用户 id 访问他人资料的接口。后续业务资源必须继续按已认证用户过滤。

## 代码结构

```text
frontend/src/
  api/           Axios、认证、任务、专注、日记、笔记、文档与健康接口
  stores/        用户会话和服务状态
  router/        登录路由及访问守卫
  layouts/       导航、账号及退出按钮
  views/         注册登录、工作台、任务、专注、日记、笔记、文档、账号设置、404
  types/         API、用户、任务、专注、日记、笔记与文档类型
  assets/        样式
backend/
  app/api/       请求入口、Bearer 认证和数据库依赖
  app/services/  认证、资料、任务、专注、日记、笔记与文档业务
  app/repositories/  用户、会话、任务、专注、日记、笔记与文档数据访问
  app/models/    User、AuthSession、Task、FocusSession、Journal、Note、NoteFolder、Document
  app/schemas/   Pydantic 输入输出校验
  app/core/      配置、密码/JWT、异常
  app/db/        SQLAlchemy Base、连接池、Session
  app/ai/        后续阶段预留
  alembic/       版本化迁移
  scripts/      本地签名密钥初始化
  tests/        健康、认证、任务、专注、日记、笔记与文档测试
```

`models` 描述数据库表，`schemas` 描述接口结构，Alembic 修改实际表结构。业务按 Router → Service → Repository 分层。应用启动不执行 `create_all`，只有隔离的 SQLite 测试环境使用它。

数据库新增：

- `users`：UUID id、唯一用户名/邮箱、密码哈希、昵称、头像链接、时区、UTC 创建/更新时间。
- `auth_sessions`：UUID id、用户外键、唯一刷新摘要、创建时间、过期时间、撤销时间。外键删除级联。
- `tasks`：任务字段、用户外键、完成时间及按用户和日期的索引；具体字段见 Phase 2 说明。
- `focus_sessions`、`journals`：专注与日记数据，见对应阶段文档。
- `notes`：私人 Markdown 笔记、置顶、版本标识与更新时间，见 Phase 5 文档。
- `alembic_version` 当前为 `0010_document_formats`。

## 验证与测试

默认测试使用隔离的内存 SQLite，不需要数据库账号，也不会修改真实数据库：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
.\.venv\Scripts\python.exe -m alembic check
```

需要在已完成迁移的本机 MySQL 上验证时：

```powershell
$env:FOCUSNEST_TEST_MYSQL='1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:\FOCUSNEST_TEST_MYSQL
```

常规认证测试在外层事务及保存点内运行，完成后回滚测试用户与会话。并发刷新测试使用独立临时账号，在 finally 中按精确用户 id 清理，不触及其他账号。不要对生产数据库运行开发测试。`alembic check` 需要在线数据库连接。

```powershell
cd D:\FocusNest\frontend
npm run build
```

测试覆盖注册校验、唯一约束、密码哈希、登录失败、用户隔离、资料校验、JWT 过期/篡改/声明错误、刷新轮换与重放拒绝、退出失效、会话过期、跨站拒绝、缺失密钥，以及原有健康接口。

## 当前边界

Phase 1 提供账号资料设置，主题/语言、计时器偏好、日记模板和 AI 设置在对应功能阶段实现。尚无邮件验证、密码找回、改密、登录限流、会话清理定时任务；当前用于本机开发，公开部署前需完成相应加固。过期和撤销会话不会自动删除。

测试依赖仍有两条上游弃用提示（Starlette/httpx 和 AnyIO），不影响当前通过结果。

下一阶段是 Phase 7 Dashboard，需明确指令后继续。工作总结按 `AGENTS.md` 在结束当天对话或明确要求时写入指定 Obsidian 目录。

参考：[FastAPI JWT 与密码哈希](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)、[PyJWT](https://pyjwt.readthedocs.io/en/latest/usage.html)。

## Phase 1 历史验收（2026-09-28）

- 真实 MySQL：36 项测试通过，包括并发刷新竞争；临时数据已清理。
- 默认隔离测试：35 项通过、1 项跳过（仅 MySQL 执行并发测试）。
- Ruff、pip check、Alembic current/check、前端 TypeScript 和生产构建通过。
- 浏览器：注册自动登录、资料保存、刷新保留会话、退出、邮箱重新登录均通过；未发现浏览器控制台错误。
- 数据库确认位于 D 盘，迁移版本 `0002_users_auth`；验收结束时用户和会话均为 0，没有测试账号留存。
- 页面截图：`docs/screenshots/phase1-login.png`。

## Phase 2 验证（2026-10-11）

- MySQL：57 项通过；SQLite：56 项通过、1 项跳过；保留两条原有上游弃用提示。
- Ruff、Alembic upgrade/check、前端类型检查与生产构建通过，迁移版本 0003_tasks。
- 浏览器验证创建、编辑、完成、恢复、组合筛选、会话恢复、删除确认框打开及取消。
- 实际删除通过开发代理的 HTTP 请求验证，临时测试用户、任务和会话已清理。
- 功能规则、API、文件和调用流程：[Phase 2 实施说明](docs/PHASE2_TASKS.md)。
- 桌面截图：`docs/screenshots/phase2-tasks.jpg`（临时验收数据）。

## Phase 5 验证（2026-10-30）

- MySQL 116 项通过；SQLite 111 项通过、5 项跳过；保留两条原有上游弃用提示。
- Ruff、Alembic upgrade/current/check、前端类型检查及生产构建通过；Markdown 测试 3 项通过。
- 浏览器验证新建、置顶、编辑、搜索、刷新后读取、阅读模式、未保存提示及取消删除；实际删除经开发代理 HTTP 验证。临时账号和数据已清理。
- [完整新增修改清单、代码流程及知识语法总结](docs/PHASE5_NOTES.md)。

## 笔记文件夹追加（2026-10-30）

支持自建嵌套目录、折叠、重命名、按目录筛选和笔记归类。删除叶子目录后笔记保留在未分类；有子目录时需先处理子目录。现有笔记和内容保持不变。

新增 note_folders 表与 notes.folder_id，当前迁移 0008_note_folders。MySQL 全量 127 项通过，追加并发测试单独 1 项通过；SQLite 122 项通过、6 项跳过；前端构建和 5 项测试通过。浏览器自动验收因审批服务用量限制未执行。

[文件清单、流程与知识语法说明](docs/PHASE5_NOTE_FOLDERS.md)。

## 本机外观设置（2026-11-01）

设置页支持本地 JPG / PNG / WebP 背景（最大 10 MB）、柔化调节及恢复默认。按钮、面板与侧栏使用磨砂玻璃样式。图片经前端缩小后存放当前来源的 IndexedDB，不上传服务器，不跨设备同步；同一浏览器中的账号共用外观。清除网站数据会清除背景。详见 [外观实现说明](docs/APPEARANCE.md)。

## 笔记导入（2026-11-01）

笔记页“导入文档”支持 UTF-8 的 .md / .markdown / .txt，单个文件不超过 512 KB、正文不超过 100000 字符。导入为当前文件夹中的新草稿，预览后手动保存；已有未保存输入需先确认。PDF/Word 暂需导出为 Markdown/TXT。见 [文件清单、流程与知识点](docs/NOTE_IMPORT.md)。

## Phase 6 文档资料库（2026-11-01）

访问 http://127.0.0.1:5173/documents 或点击“文档”。支持 UTF-8 的 .md / .markdown / .txt，上传即保存原件，最大 512 KB、正文最多 100000 字符。左侧搜索标题/原文件名并按类型筛选，右侧阅读 Markdown 或纯文本，支持取回原件、改名和删除。与“笔记导入”分开管理。

新增 documents 表，原件以 MEDIUMBLOB 存于 MySQL，迁移为 0009_documents；新增 python-multipart 上传依赖。下载保持原始字节和原文件名。尚不支持 PDF、Word、正文编辑、文件夹和 AI。

- MySQL 147 项通过；SQLite 139 项通过、8 项跳过；Ruff、pip check、Alembic upgrade/check/current 通过。
- 前端类型检查、生产构建、10 项测试通过；独立临时账号经前端代理的完整 HTTP 流程通过，临时数据已清理。
- 浏览器验收导航、列表筛选控件与空状态；写操作和下载落盘未逐项进行浏览器验收。
- [完整文件清单、API、流程、知识与语法说明](docs/PHASE6_DOCUMENTS.md)。下一业务阶段为 Phase 7 Dashboard，尚未开始。

## PDF 与 Office 预览追加（2026-11-01）

资料库支持 PDF 按页图片预览、DOCX 段落/表格、PPTX 幻灯片内容、XLSX/XLS 工作表，原件可下载。PDF/Office 最大 10 MB；MD/TXT 继续为 UTF-8、512 KB。Office 预览不还原图片、复杂排版、动画或图表，不执行公式/宏。旧 DOC/PPT 需另存为 DOCX/PPTX/PDF，本机未配置 LibreOffice。

迁移已更新为 0010_document_formats，增加 preview_data JSON 和新类型/大小约束。更新环境需重新安装 requirements-dev.txt 并执行 alembic upgrade head。详见 [格式能力、文件清单、流程及知识点](docs/DOCUMENT_FORMAT_PREVIEWS.md)。前述 Phase 6 的 Markdown/TXT 章节属于初版记录。

多格式最终验证：MySQL 158 项通过，SQLite 150 项通过、8 项跳过；前端构建与 10 项测试通过。浏览器组件验收 Word/PPT 内容和 Excel 工作表切换，实际资料库新格式入口确认可用；PDF 页图片经真实 HTTP 与自动测试验证。

外观追加：面板白底调整到 36%、模糊 6px，普通按钮白底 22%、模糊 4px，侧栏和页头同步轻透。背景图片与用户柔化偏好保持原值。[本轮修改与代码说明](docs/DOCUMENT_FORMATS_AND_LIGHTER_GLASS.md)。

## 动态背景（2026-11-01）

设置与外观支持 GIF、MP4、WebM、OGV 背景：图片/GIF 最大 10 MB，视频最大 50 MB，受浏览器编码支持限制。视频静音循环，动态背景可暂停并记住状态，刷新后恢复；图片设置兼容旧数据。所有媒体仅保存在当前浏览器。[文件清单、流程与验证说明](docs/DYNAMIC_BACKGROUNDS.md)。

## 透明导航与字体样式（2026-11-01）

导航、文件夹栏、页头及普通按钮改为透明，FocusNest 品牌保留轻微磨砂，正文为约 14% 底色和 2px 模糊。设置中新增字号比例 80%–150%、文字颜色、磨砂底色及默认恢复，保存到当前浏览器，兼容原有图片/视频背景。[代码与验证说明](docs/TRANSPARENT_APPEARANCE.md)。
## 每周日程与全局计时（2026-11-02）

2026-11-14 新增日程模板、周日确认与未选择时自动沿用。本机 MySQL 已升级到 `0018_schedule_templates`。 [使用方式与修改清单](docs/SCHEDULE_TEMPLATES.md)

左侧“日程”可建立每周复用的安排，并选择仅修改本次或修改本次及后续；“专注”新增指定起止时间模式。非专注页面右侧可查看日程、计时内容和剩余时间，中小屏通过右下角按钮展开。“设置与外观”新增提醒声音与系统通知选项。

本机 MySQL 已升级到 `0011_weekly_schedules`；其他环境先在 `D:\FocusNest\backend` 运行 `.\.venv\Scripts\python.exe -m alembic upgrade head`。提醒依赖网站运行，关闭浏览器或休眠时不保证准点提醒。完整文件清单、数据库/API 变化、流程与知识点见 [每周日程修改说明](docs/WEEKLY_SCHEDULES.md)。


## Phase 7 工作台（2026-11-03）

首页现已提供今日任务完成、专注汇总、今日日记状态、最近笔记/文档直达、25 分钟快捷专注与接下来的日程。新增 `GET /api/v1/dashboard`，无数据库迁移。代码清单、统计口径及验证结果见 [Phase 7 工作台说明](docs/PHASE7_DASHBOARD.md)。

## 问题备忘（2026-11-04）

左侧“问题备忘”记录遇到的问题，勾选解决后自动记录解决时间；未解决的旧问题按个人时区归入历史。支持编辑、搜索分页和导出 Markdown 文档。MySQL 当前迁移为 `0012_problem_memos`，其他环境先运行 `alembic upgrade head`。文件清单、规则与验证见 [问题备忘说明](docs/PROBLEM_MEMOS.md)。

## 笔记关联问题（2026-11-04）

笔记支持按问题类型筛选、搜索并选择关联问题，保存后可查看问题状态；选择“不关联问题”并保存可解除。MySQL 迁移为 `0013_note_problem_link`。代码清单与验证见 [笔记问题关联说明](docs/NOTE_PROBLEM_LINKS.md)。

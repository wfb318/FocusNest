# 管理员账号与运营后台

实现日期：2026-11-26。属于用户单独授权的管理员扩展，不自动推进 Phase 9 Tools。

## 功能与边界

- 新增应用角色 `user`、`admin`，已有账号迁移后仍为普通用户。
- 提供服务器控制台命令创建独立管理员；未内置默认账号或默认密码。
- 管理后台地址 `/admin`，登录管理员后左侧出现“管理后台”。
- 概览显示总注册人数、今日/本周/本月新增、管理员数量、近期在线人数。
- 用户列表支持按用户名、邮箱、昵称搜索，按角色和在线状态筛选，以及分页。
- 展示账号、邮箱、昵称、角色、注册时间、最近登录和最近活动时间。
- 本版后台只读；网页不提供角色修改、账号删除、密码查看或私人正文读取接口。
- 独立管理员也是一个独立用户。原个人账号的任务、笔记等仍归原账号；管理员的个人工作区不会自动显示其他账号的内容。
- 用户名保留注册或管理员创建时输入的大小写，页面原样展示；登录、账号重复检查和 CLI 角色操作忽略大小写。邮箱继续统一小写，密码保持大小写敏感。

私有日记、笔记及文档继续执行原有用户归属校验，管理员身份不绕过这些业务接口。管理员概览和用户列表仅查询账号与会话元数据，不读取业务正文；本地日记仍在用户电脑上。

当前云端加密是服务端持有内容密钥的存储加密，不应把管理员界面的权限限制解释为平台技术上不能解密或端到端加密。

## 统计口径

| 指标 | 口径 |
|---|---|
| 总注册人数 | `users` 的账号总数，包含独立管理员 |
| 今日新增 | 管理员账号时区的当天零点至服务器当前时刻 |
| 本周新增 | 管理员账号时区本周一零点至当前时刻 |
| 本月新增 | 管理员账号时区本月一日零点至当前时刻 |
| 管理员数量 | `role=admin` 的账号数 |
| 近期在线 | 最近 300 秒有有效登录活动/心跳，且会话未撤销、未过期的去重用户数 |
| 最近登录 | 此用户现存会话记录中最近的创建时间 |
| 最近活动 | 最近已记录的会话活动时间，不等同于用户正在操作某个具体页面 |

日期边界分别从管理员本地零点换算成 UTC，周从周一开始。新增人数排除创建时间在服务器当前时刻之后的异常记录。

登录成功记录一次活动。已登录页面可见时，约每 60 秒发送空心跳；后台标签页不持续发送，切回页面后按限频规则恢复。服务器对同一会话的心跳写入间隔限制约 30 秒，多个设备和标签页按用户去重。

关闭页面后可能最多延迟约 5 分钟才退出在线统计。退出登录使该会话立即失效；如果其他设备仍在线，这个用户仍计为 1 人。自动刷新登录令牌本身不更新活动时间。

历史会话的 `last_seen_at` 初始为 NULL，升级后首次登录或可见页面心跳才进入近期在线统计。不能直接使用 `auth_sessions` 行数或未过期会话数量代替在线人数。

## 数据库迁移

版本：`0019_admin_and_presence`，上一个版本为 `0018_schedule_templates`。

| 变化 | 说明 |
|---|---|
| `users.role` | 非空字符串，默认 `user`；约束仅允许 `user`、`admin` |
| `auth_sessions.last_seen_at` | 可为空的 UTC 活动时间 |
| `ix_auth_sessions_last_seen_at` | 最近活动时间索引 |

不新增业务正文表，不自动赋予第一个账号管理员权限，不以用户名 `admin` 判断权限。降级前如果仍有管理员账号，迁移会拒绝降级，需先用服务器命令撤销角色。

本机开发库已在受限备份后应用 `0019`，全部表行数保持一致，Alembic 模型检查通过。保留的原账号仍是 `user`；本轮没有在本机真实库创建管理员。线上库需要通过下方更新步骤迁移，不能把本机旧 SQL 重新导入线上。

## API

| 方法与路径 | 权限 | 用途 |
|---|---|---|
| `GET /api/v1/admin/overview` | 管理员 | 注册与在线概览 |
| `GET /api/v1/admin/users` | 管理员 | 账号元数据分页列表 |
| `POST /api/v1/users/me/heartbeat` | 当前登录用户 | 更新自己的有效会话活动时间 |
| 原有登录、刷新和 `/users/me` | 保持原有权限 | 用户资料额外返回 `role` |

用户列表参数：`page`（1–100000）、`page_size`（1–100）、`search`（最多 100 字符）、`role`（user/admin）、`online`（布尔值）。搜索中的 `%`、`_` 作为普通字符处理，不扩大成任意匹配。

心跳发送 `{}` 或空请求体；不接受客户端指定用户、会话、活动时间或页面内容。用户及会话身份来自服务端验证过的 JWT。

管理员接口在后端逐次检查数据库中的角色，普通用户返回 `40340`；未登录或失效会话返回 401。角色不由前端或 JWT 中自行添加的 `role` 决定。撤销管理员后，即使旧访问令牌尚未到期，新请求也会被拒绝。

管理员接口响应均为 `Cache-Control: no-store`。公开注册和资料修改继续禁止额外字段，不能借请求体中的 `role` 或 `is_admin` 提权。

## 创建独立管理员

需要先完成数据库迁移。生产服务器执行：

```bash
sudo -u focusnest /srv/focusnest/backend/.venv/bin/python /srv/focusnest/backend/scripts/manage_admin.py create
```

依次填写新的管理员用户名、邮箱、密码和密码确认。密码全程隐藏；没有密码命令行参数，也无需发给助手。

用户名为 3–32 位字母、数字或下划线，邮箱需有效，密码为 10–128 字符。独立管理员的用户名和邮箱需要与已有账号不同。

也可以先指定非密码字段：

```bash
sudo -u focusnest /srv/focusnest/backend/.venv/bin/python /srv/focusnest/backend/scripts/manage_admin.py create --username focusnest_admin --email '<独立管理员邮箱>'
```

这里的邮箱是占位符，不是默认账号。脚本通过与普通注册相同的 Argon2 密码哈希保存密码；验证失败、两次密码不一致、用户名或邮箱重复时，不创建新账号。

创建后在网站退出原个人账号，用这个独立账号登录，再进入 `/admin`。本步骤创建的是网站账号，不会修改 MySQL 连接账号或 Linux 服务账号。

仅在本机开发环境创建管理员时，在 Windows PowerShell 执行：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe scripts/manage_admin.py create
```

本机和线上数据库相互独立；本机新建管理员不会自动同步到线上。

### 授予或撤销已有账号的角色

以下是可信服务器控制台的管理命令，没有对应的公开网页写入接口：

```bash
sudo -u focusnest /srv/focusnest/backend/.venv/bin/python /srv/focusnest/backend/scripts/manage_admin.py grant --identity '<用户名或邮箱>'
```

```bash
sudo -u focusnest /srv/focusnest/backend/.venv/bin/python /srv/focusnest/backend/scripts/manage_admin.py revoke --identity '<用户名或邮箱>'
```

操作后刷新账号资料或重新登录。后台已加载时如权限被撤销，下一次请求会拒绝访问，前端清除列表并返回工作台。

## 本次服务器更新包

最新包名：`focusnest-admin-case-update-20261126.zip`，包含管理员功能及用户名大小写修正；它替代先前的 `focusnest-admin-update-20261126.zip`。已安装旧包也可以使用新包更新，不会重新创建管理员。

上传到服务器 `/home/ubuntu` 后执行：

```bash
cd /home/ubuntu
unzip -n focusnest-admin-case-update-20261126.zip
```

```bash
sudo /srv/focusnest/backend/.venv/bin/python /home/ubuntu/focusnest-admin-case-update/install_admin_update.py
```

出现提示后，隐藏输入 **MySQL `focusnest_migrate` 迁移账号密码**；这不是刚准备创建的网站管理员密码。

更新程序仅针对当前 `/srv/focusnest`、本机 MySQL 3306 的 `focusnest` 库，接受数据库版本 `0018` 或 `0019`。它会：

1. 检查运行文件与数据库目标，先验证迁移账号连接，版本不符时退出。
2. 在 `/var/backups/focusnest/admin-...` 创建 root 受限备份目录。
3. 暂停后端，记录各表行数，备份当前服务器数据库和原代码、前端。
4. 更新 app、迁移、维护脚本及 Alembic 配置，设置服务可读的源码权限。
5. 用临时迁移凭据执行 `alembic upgrade head`，不把日常 `.env` 改成迁移账号。
6. 比较现有表行数，确认迁移没有删除或新增既有业务记录。
7. 启动后端并检查数据库健康，再安装新的静态资源、最后切换前端入口。

临时数据库客户端凭据在备份结束后清除。`.env`、`.venv`、原内容密钥、证书和 MySQL 账号密码保持原样；备份不包含 `.env` 或内容密钥。实际数据库备份包含账号哈希和云端业务数据，受限保存，不是可公开分享的文件。

更新期间后端短暂不可用。成功标志为：

```text
ADMIN_UPDATE_READY: schema 0019, backend healthy, frontend installed.
```

只有成功后才执行前面的 `manage_admin.py create`。更新程序不预先创建真实管理员，也不输出默认密码。

如果更新中途失败，保留终端错误和备份位置。数据库升级可能包含不可回滚的 DDL，因此程序不会擅自恢复旧 SQL 或降级；代码已经变化但迁移未确认成功时，后端会保持停止，先排查。它不是不受版本限制的通用部署器，也没有在本轮实际执行于线上服务器。

## 文件与代码清单

| 文件 | 改动和作用 |
|---|---|
| `backend/alembic/versions/0019_admin_and_presence.py` | 新增角色、活动时间和索引，保留既有用户与会话 |
| `backend/app/models/user.py`、`auth_session.py` | 映射新字段与角色约束 |
| `backend/app/schemas/user.py`、`schemas/admin.py` | 输出角色、统计、列表及心跳数据，白名单限制字段 |
| `backend/app/repositories/users.py` | 用小写值比较账号身份和重复名称，同时保留原始用户名用于显示 |
| `backend/app/services/auth.py` | 保留验证过的用户与会话身份；登录记录活动 |
| `backend/app/api/deps.py` | 后端管理员权限依赖和心跳身份依赖 |
| `backend/app/repositories/admin.py` | 账号聚合、元数据分页、去重在线及条件活动更新 |
| `backend/app/services/admin.py` | 时区边界、在线口径、可信 CLI 创建和角色管理 |
| `backend/app/api/v1/endpoints/admin.py` | 两个只读管理员接口 |
| `backend/app/api/v1/endpoints/users.py` | 当前会话心跳入口 |
| `backend/app/api/v1/router.py`、`app/main.py` | 注册后台路由和私有响应缓存策略 |
| `backend/scripts/manage_admin.py` | 隐藏输入创建管理员、授予或撤销角色 |
| `frontend/src/views/AdminView.vue` | 概览、搜索筛选、分页、自动刷新、过期响应清理 |
| `frontend/src/api/admin.ts`、`types/admin.ts` | 后台请求和 TypeScript 数据类型 |
| `frontend/src/components/PresenceHeartbeat.vue`、`utils/presence.ts` | 可见页面的限频空心跳，不读取日记或页面内容 |
| `frontend/src/api/auth.ts`、`types/auth.ts`、`stores/auth.ts` | 角色资料、资料重载、心跳 API |
| `frontend/src/router/index.ts`、`layouts/AppLayout.vue` | 管理入口、路由保护和心跳生命周期 |
| `frontend/src/api/client.ts` | 管理员权限错误提示 |
| `backend/tests/test_admin.py`、`test_admin_migration.py` | 权限、统计口径、隐私、CLI 和保留数据迁移测试 |
| `frontend/tests/presence.test.mjs`、`frontend/package.json` | 心跳限频、可见状态、停止和错误恢复测试 |
| `releases/admin-update-20261126/install_admin_update.py` | 服务器备份、迁移及更新工具 |

## 涉及的知识与语法

- `Literal['user', 'admin']`：明确 API 允许的角色值；数据库 CheckConstraint 同时限制存储值。
- `Annotated[..., Depends(...)]`：复用身份验证和权限检查；前端菜单不是权限边界。
- `@dataclass(frozen=True)`：把已验证的用户和会话放入不可重新赋值的身份对象。
- SQLAlchemy `case`、`func.count(distinct(...))`：条件统计以及同一用户多会话去重。
- 条件 `UPDATE`：只有有效、且超过写入间隔的会话才更新时间，限制心跳写放大。
- 时区转换：数据保留 UTC，按管理员本地零点计算注册时间范围。
- `getpass`：服务器隐藏输入，不把密码放到命令行参数或输出中。
- Vue `watch`、`onUnmounted` 和请求版本号：账号切换或权限失效后，不让旧请求恢复后台数据。
- 先安装 assets、再切换 `index.html`：前端引用的新资源先到位，保留旧资源支持尚未刷新的标签页。

## 本轮验证与限制

- 后端完整回归：289 通过、9 项仅真实并发环境适用的测试跳过。
- 本机 MySQL 角色、登录及 CLI 相关验证：32 通过，测试账号在事务中回滚。
- 新角色迁移保留数据测试通过；本机 MySQL 升级后各表行数保持一致，`alembic check` 无新增差异。
- Ruff 检查通过，前端类型检查、85 项测试及生产构建通过。
- 使用虚构账号和独立 SQLite 的本机页面检查：管理员概览、用户筛选、刷新恢复、普通账号菜单和管理员路由保护通过。
- 页面预览脚本位于 releases，仅用于本机隔离检查，不进入生产包；早期单连接内存预览的并发冲突已通过独立 SQLite 连接消除，不涉及真实用户数据。
- 服务器更新工具通过语法和静态检查，尚未在生产服务器执行；真实独立管理员需由用户在服务器创建，线上创建与界面仍待验证。
- 本轮没有在 Obsidian 自动生成每日工作记录；此文档是功能使用与部署说明。

## 用户名大小写修正（2026-11-26）

原先 `Registration.normalize_identity` 同时将用户名和邮箱转成小写，导致页面无法展示用户原本输入的大写字母。现在仅由 `normalize_email` 规范化邮箱，用户名原样保存。前端原本就直接展示 API 返回的用户名，本次不需要改动前端。

账号检索和查重改为 `func.lower(User.username)` / `func.lower(User.email)` 与输入的小写形式比较。这样 `FocusNest_Admin`、`focusnest_admin` 和 `FOCUSNEST_ADMIN` 都能登录同一个账号，也不能注册成三个不同账号；比较不会改写数据库保存的显示名称。现有 MySQL 用户名唯一约束使用忽略大小写的排序规则，仍提供并发注册时的数据库保护。

涉及修改：`backend/app/schemas/user.py`、`backend/app/repositories/users.py`、`backend/tests/test_auth.py`、`backend/tests/test_admin.py` 及本说明。没有数据库结构变化，版本仍为 `0019_admin_and_presence`。

验证：登录与管理员相关 43 项测试通过；真实本机 MySQL 的注册、显示、忽略大小写登录、大小写重复拒绝和管理员创建/角色操作 3 项专项测试通过，虚构数据在事务中回滚；Ruff 通过。测试覆盖登录、当前用户、刷新令牌和管理列表返回原始大小写，以及密码仍区分大小写。

已保存为小写的历史用户名无法推断原始大小写，本次不会擅自修改。现有用户可在设置里编辑“昵称”来自定义首页和左侧账号显示名称；昵称不改变登录用户名。后续新建账号会直接保留用户名大小写。

最新更新包沿用原备份、迁移与自动重启流程，支持服务器当前为 `0018` 或 `0019`。本次只在本机完成开发和验证，线上尚待用户上传新包并运行更新脚本。

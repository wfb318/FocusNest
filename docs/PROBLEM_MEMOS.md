# 问题备忘：功能、修改清单与代码说明

日期：2026-11-04。用户明确要求的问题记录扩展；下一业务阶段仍为 Phase 8 Statistics，未因本次扩展推进。

## 使用方式与归类规则

刷新后左侧进入“问题备忘”（`/problems`），填写问题内容并点击“记录问题”。支持多行文字，最多 10000 字符；可以补充现象、疑问、已经尝试过的方法。

- **今日问题**：当前个人时区中，今天记录且未解决的问题。
- **历史问题**：今天以前记录且仍未解决的问题，保留原记录时间；次日自然归入，无需手动移动。
- **已解决**：勾选问题前的复选框后进入，解决时间由服务端自动保存。
- **全部**：查看所有问题，方便一次导出。

历史问题同样可以勾选解决。取消已解决的勾选会重新打开问题、清除本次解决时间，并按原创建日期回到今日/历史问题。再次解决会记录新的解决时间。编辑正文保留最初记录日期和已有解决时间；更新日期单独显示。没有实现历史解决事件流水或硬删除入口。

支持内容搜索和分页，每页 20 条；分类数字随已应用的搜索条件变化。列表约每分钟、切回页面、恢复联网或检测到本地跨日时更新；即使网站在午夜关闭，下次打开也会直接按新日期正确分类。当天/历史不是反复复制的数据表，而是根据未解决状态与创建时间即时查询，因此原始问题只有一条。

未保存的输入在离开页面或刷新时提示。网络或版本冲突不会清空正文草稿，勾选以服务端成功结果为准。

## 文档导出

点击右上角导出按钮，将当前分类、已应用搜索条件下的**全部匹配记录**导出为 Markdown `.md` 文档，而非只导出当前分页。切到“全部”后可导出全部分类。

文件使用 UTF-8 BOM，便于 Windows 中文编辑器和 Obsidian 打开。每条包含问题原文、可读勾选状态、分类、记录时间、更新时间，以及适用时的解决时间；所有时间附带个人时区对应的 UTC 偏移。

问题内容放入长度动态选择的 Markdown 代码围栏，避免用户原文中的标题、三反引号改变导出结构。第一版导出格式为 Markdown，尚未提供 DOCX/PDF。导出最多 1000 条、4 MiB（含 BOM），超限明确提示缩小分类/搜索范围，不静默截断。

## 新增源代码及测试文件（10 个）

| 文件 | 作用 |
| --- | --- |
| [models/problem.py](/D:/FocusNest/backend/app/models/problem.py) | Problem 数据模型；状态、解决时间、创建/更新时间、版本与所属用户 |
| [schemas/problem.py](/D:/FocusNest/backend/app/schemas/problem.py) | ProblemCreate/Edit/Status/Read/Page；内容与严格布尔值校验 |
| [repositories/problems.py](/D:/FocusNest/backend/app/repositories/problems.py) | 用户隔离、日期分类、搜索字面量转义、数量聚合和排序 |
| [services/problems.py](/D:/FocusNest/backend/app/services/problems.py) | 创建/编辑/勾选、服务端时间、版本检查、Markdown 导出与大小限制 |
| [endpoints/problems.py](/D:/FocusNest/backend/app/api/v1/endpoints/problems.py) | HTTP 接口、分页参数、登录依赖、下载响应 |
| [0012_problem_memos.py](/D:/FocusNest/backend/alembic/versions/0012_problem_memos.py) | 新增 problems 表、索引和状态/解决日期检查约束 |
| [test_problems.py](/D:/FocusNest/backend/tests/test_problems.py) | 跨天、重新打开、权限、冲突、搜索/分页、导出中文和围栏、超限验证 |
| [test_problem_concurrency.py](/D:/FocusNest/backend/tests/test_problem_concurrency.py) | MySQL 同版本的编辑与解决同时提交，仅一个成功 |
| [api/problems.ts](/D:/FocusNest/frontend/src/api/problems.ts) | 前端类型与 CRUD/状态/导出请求；Blob 错误转换为通用错误提示 |
| [ProblemsView.vue](/D:/FocusNest/frontend/src/views/ProblemsView.vue) | 记录输入框、分类、复选框、编辑框、时间展示、搜索分页与下载 |

## 修改已有源代码（6 个）

| 文件 | 修改 |
| --- | --- |
| [models/__init__.py](/D:/FocusNest/backend/app/models/__init__.py) | 注册 Problem 模型 |
| [API router.py](/D:/FocusNest/backend/app/api/v1/router.py) | 注册 `/problems` 路由 |
| [main.py](/D:/FocusNest/backend/app/main.py) | 问题和导出响应设置 `Cache-Control: no-store` |
| [AppLayout.vue](/D:/FocusNest/frontend/src/layouts/AppLayout.vue) | 左侧新增“问题备忘” |
| [router/index.ts](/D:/FocusNest/frontend/src/router/index.ts) | 新增 `/problems` 页面 |
| [api/client.ts](/D:/FocusNest/frontend/src/api/client.ts) | 内容校验、版本冲突、导出超限等中文提示 |

另同步 README 和 PROJECT_SPEC 中的功能入口，新增本说明和验收截图，无新增依赖。

## 数据库与 API

已实际应用迁移：`0011_weekly_schedules` → `0012_problem_memos`。

`problems` 字段：`id`、`user_id`、`content`、`is_resolved`、`resolved_at`、`revision`、`created_at`、`updated_at`。时间以 UTC 保存，MySQL 使用微秒精度。复合索引按用户、解决状态、创建时间和 ID 建立。

检查约束确保未解决时 `resolved_at` 为空，已解决时必须有解决时间。删除用户会级联删除其问题；本次业务 API 不暴露删除功能。降级时若仍有问题数据则拒绝执行，防止静默丢失。

全部 API 以 `/api/v1` 为前缀且要求登录：

| 方法与路径 | 行为 |
| --- | --- |
| GET `/problems?bucket=today/history/resolved/all&q=...&page=1&page_size=20` | 分类列表、数量、今天日期及个人时区 |
| POST `/problems` | `{content}` 新建，服务端设置时间 |
| PUT `/problems/{id}` | `{content, expected_revision}` 更新正文 |
| PATCH `/problems/{id}/status` | `{is_resolved, expected_revision}` 解决或重新打开 |
| GET `/problems/export?bucket=all&q=...` | 下载当前过滤范围的 Markdown 文档 |

所有查询和写入都限制当前用户。客户端不能填写创建/解决时间或所属用户。写入锁定用户和问题行，并检查 UUID 版本；冲突返回 409，不用旧页面覆盖最新内容。重复提交相同状态不会改变原解决时间。

## 流程与知识点

```text
记录：ProblemsView.add → api.createProblem → endpoint.create
  → service.create → Problem → MySQL

勾选：ProblemsView.toggle → setProblemStatus → endpoint.status
  → 用户/问题行锁 → revision 校验 → 服务端 resolved_at → 保存并刷新分类

归档：service.context 算个人时区今天的两个午夜 → 转 UTC
  → repository.buckets 按 created_at + is_resolved 查询

导出：ProblemsView.download → exportProblems → service.export_markdown
  → 查询匹配记录 → 勾选状态/时间/原文 → UTF-8 BOM 文档 → 浏览器下载
```

- 分类使用日期边界查询，无需午夜后台任务；分别计算两个本地午夜，可以处理夏令时日并非固定 24 小时的情况。
- 原始时间、更新时间、解决时间承担不同作用，编辑时不覆盖原创建日期。
- `Field(strict=True)` 防止把字符串或整数当成勾选布尔值；`extra="forbid"` 拒绝客户端传入时间或用户字段。
- `SUM(CASE...)` 统计各分类数量；搜索转义 `%`、`_`、`!`，将其作为问题文字匹配。
- UUID `revision` 和行锁共同避免多窗口状态/正文互相覆盖。
- Blob 成功响应和 JSON 错误响应在下载时需要分别处理；Object URL 在下载后释放。
- Vue 的 `onBeforeRouteLeave` / `beforeunload` 保护未保存输入，组件卸载清理定时器与监听。

## 已执行验证

- 新增 SQLite 接口测试 9 项通过；真实 MySQL 全量回归 **193 项通过**，含并发编辑/解决用例。
- 前端 **29 项测试通过**；Vue/TypeScript 类型检查与生产构建通过。新增后端文件 Ruff 检查通过。
- `alembic upgrade head` 成功；`alembic check` 显示模型与数据库无遗漏操作。
- 浏览器临时账号实际验证新增、多行内容、勾选解决、自动解决日期、历史列表、编辑历史问题后保留原记录时间。
- 已实际下载“全部”文档，并读取文件确认三条问题的勾选状态、中文原文、创建/更新/解决时间完整。
- 跨午夜自动归类由受控时钟接口测试验证，没有等待真实午夜。所有移动端/字号/背景组合尚未逐项浏览器验收。
- 验收账号使用 localhost，与用户正在使用的 127.0.0.1 来源隔离；未向用户真实账号写入测试问题。临时账号、示例数据库记录、脚本与元数据已清理。

截图：[问题备忘页面](/D:/FocusNest/docs/screenshots/problem-memos.png)。

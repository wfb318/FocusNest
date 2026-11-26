# Phase 7 工作台：首页汇总、代码清单与知识点

实施日期：2026-11-03。范围：PROJECT_SPEC.md 中 Dashboard 核心功能。没有进入 Phase 8 Statistics，也没有实现 AI Review、自定义 Widget 或新的统计报表。

## 已实现内容

登录后点击“工作台”（`/`），可以查看：

- 今日任务已完成数/总数、逾期任务数量，以及最多 5 项未完成的今日任务；可以直接完成一项任务。
- 今日开始的专注累计时长与完成段数，正在进行的专注会实时更新；休息与取消的记录不计入。
- 今日日记是否已写，提供进入日记页继续查看/编辑的入口。
- 最近更新的 3 篇笔记、3 份文档，点击具体条目直接打开对应内容。
- 一键开始 25 分钟番茄钟；已有任何活动计时（含等待、休息、暂停）时显示已有计时，不创建第二个。
- 今天尚未结束的日程，最多展示 3 项，复用已有全局运行器，不启动第二套日程轮询。

首页替换原来的服务检查占位内容，保留已有后端健康接口和 system store，没有删除诊断实现。界面沿用透明标题、浅磨砂面板、用户设置的字体大小和颜色。工作台内容每分钟刷新一次，切回页面、恢复联网、时区或计时发生相关变化时同步，也可以手动刷新。错误时保留旧内容并标明可能过期。

## 统计口径

### 今日任务

使用个人资料的 IANA 时区确定今天。任务的 `scheduled_date` 或 `due_date` 等于今天即属于今日安排；两个字段都等于今天也只计一次。

总数包括已完成任务，完成数只统计这些今日任务中的 done。未完成列表按“进行中优先 → 优先级高到低 → 创建时间 → ID”排序。逾期数单独统计 `due_date < today` 且未完成的任务，不自动混入今日任务列表。

### 专注时长

界面明确命名为“今日开始的专注”：按会话 `started_at` 所属本地日期归组，累计真实记录秒数；包含正在运行与暂停的专注，不包含休息、取消或尚未开始的未来时段。跨日会话归入开始日，**没有按午夜拆分每个暂停片段**。现有模型没有独立的历史运行段表，不能把无法准确重建的跨日暂停时长假装成精确自然日统计。

普通倒计时和固定时段即使超过结束点、尚未由专注接口结算，汇总也只计算到目标长度，并将其视为已经到点。`GET /dashboard` 本身不修改会话状态；它只读取数据和计算展示值。

后端返回汇总时的活动专注 ID 和累计秒数。前端仅在全局当前计时 ID 匹配时，把运行器的实时增量加到汇总值上，避免每 250ms 重查数据库或把休息时间加进去。

### 最近内容与日程

最近笔记、文档按 `updated_at DESC, id DESC`，置顶只是标记，不改变“最近更新”的排序。汇总不返回笔记/日记正文、文档原件或 Office 预览数据，点击具体内容后才调用原有详情接口。

日程根据实际开始时刻在当前个人时区中所属的日期筛选今天，按实际 UTC 起点排序；具体卡片仍注明日程保存的时区。已跳过、无效时区时段或已经结束的安排不列出。跨日开始于昨天且仍在进行的安排，仍可在原有右侧状态栏看到。

## 新增文件（7 个源代码/测试文件）

| 文件 | 作用与主要入口 |
| --- | --- |
| [schemas/dashboard.py](/D:/FocusNest/backend/app/schemas/dashboard.py) | `DashboardRead` 响应结构；精简任务、最近笔记/文档模型与 UTC 序列化 |
| [repositories/dashboard.py](/D:/FocusNest/backend/app/repositories/dashboard.py) | `task_overview`、`focus_overview`、`journal_title`、`recent_notes/documents`；用户隔离、聚合、排序和限制数量 |
| [services/dashboard.py](/D:/FocusNest/backend/app/services/dashboard.py) | `overview`；个人时区的本地午夜转 UTC，计算活动计时并组装响应 |
| [endpoints/dashboard.py](/D:/FocusNest/backend/app/api/v1/endpoints/dashboard.py) | 登录后 `GET /api/v1/dashboard`，依赖 CurrentUser 与 DBSession |
| [tests/test_dashboard.py](/D:/FocusNest/backend/tests/test_dashboard.py) | 空数据、认证、任务排序/数量、完成任务、元数据与用户隔离、专注状态、午夜边界、未来时段测试 |
| [types/dashboard.ts](/D:/FocusNest/frontend/src/types/dashboard.ts) | 前端汇总结构与精简任务类型 |
| [api/dashboard.ts](/D:/FocusNest/frontend/src/api/dashboard.ts) | `getDashboard`，统一通过已有 Axios 客户端请求与认证 |

另新增本说明和 `docs/screenshots/dashboard-overview.png` 验收截图。

## 修改文件（5 个已有源代码文件）

| 文件 | 修改内容 |
| --- | --- |
| [backend router.py](/D:/FocusNest/backend/app/api/v1/router.py) | 注册 dashboard 路由 |
| [backend main.py](/D:/FocusNest/backend/app/main.py) | 工作台接口响应加入 `Cache-Control: no-store` |
| [DashboardView.vue](/D:/FocusNest/frontend/src/views/DashboardView.vue) | 占位首页改为业务汇总；`load`、`finishTask`、`quickFocus`；监听与页面卸载处理；布局与空状态 |
| [NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 进入页面时读取 `?note=ID`，调用原有 `openNote`，以阅读模式打开指定笔记 |
| [DocumentsView.vue](/D:/FocusNest/frontend/src/views/DocumentsView.vue) | 进入页面时读取 `?document=ID`，调用原有 `open`，打开对应阅读器 |

同步 README.md 和 PROJECT_SPEC.md 的阶段进展。没有修改现有模型、迁移、密码配置、外观偏好或业务数据格式。

## API 和数据库

新增只读接口：`GET /api/v1/dashboard`，要求登录，无需传 user_id。响应 data 包括：

```text
today / timezone / server_now
task_total / task_done / overdue_tasks / tasks
focus_seconds / focus_completed / active_focus_id / active_focus_seconds
journal_written / journal_title
recent_notes / recent_documents
```

所有查询都限制为当前用户，不接受客户端指定查询其他用户。最近条目只投影需要的字段，数量有固定上限；不会为了显示首页读取全部 Markdown 正文、文档 BLOB 或所有历史记录。

完成任务复用 `POST /tasks/{id}/complete`；快捷专注复用 `POST /focus/sessions` 与既有单一活动计时约束，名称为“快速专注”，25 分钟，不关联任务。不会覆盖或自动取消已有计时。

**没有数据库迁移**：MySQL 继续使用 `0011_weekly_schedules`，无需执行新建表或增加列指令。

## 代码流程

```text
进入首页
  DashboardView.onMounted → load → api/dashboard.getDashboard
  → endpoints/dashboard.read_dashboard
  → services/dashboard.overview
  → repositories/dashboard 各汇总查询
  → DashboardRead → 首页卡片

完成任务
  finishTask → 原 tasks.completeTask API → 刷新首页汇总

快捷专注
  quickFocus → runtime.mutate（防止旧轮询覆盖新操作）
  → 原 startFocus → 后端用户锁/唯一活动约束
  → runtime.current → 首页计时 + 右侧状态栏
  → reminders.notify → 统一的开始提示

打开最近内容
  RouterLink('/notes?note=...') / RouterLink('/documents?document=...')
  → 页面初次挂载读取 query → 原详情接口 → 原阅读器
```

`load` 保留 loading、请求版本与 disposed 标记。组件卸载后清理分钟定时器和事件监听，旧响应不会重新写入已离开的首页。完成任务/启动计时期间禁用重复操作，结束后重新读取服务端结果；网络请求失败时不会直接把界面当作成功。

详情跳转仍由原接口校验所有权；过期或他人的 ID 只显示原有错误，不绕过权限。查询参数只用于页面进入时选择内容，未重构笔记/文档内部所有选择操作的 URL 同步。

## 本次知识点

1. **聚合接口**：首页通过一个 API 获取多个模块的概要，前端无需各自下载完整内容再做统计。
2. **数据库聚合**：`COUNT` 计数，`SUM(CASE WHEN … THEN 1 ELSE 0 END)` 条件计数，`COALESCE` 把空结果变成 0。
3. **字段投影**：`select(Note.id, Note.title, …)` 只查询需要的列；`.mappings()` 把结果作为字段映射交给 Pydantic。
4. **时区日界线**：分别构造今天与明天的本地午夜，再转 UTC；不能直接把任何一天都看成 UTC 中固定的 24 小时。
5. **复用领域计算**：通过已有 `focus.elapsed` 计算当前时长，保留暂停、目标封顶与固定结束点的语义；首页读取不等于提交结算。
6. **响应结构与模型隔离**：数据库里有正文和原件，不代表首页响应应该包含它们。精简 schema 同时明确类型与数据边界。
7. **实时增量**：服务端汇总提供基准，全局运行器计算增量；用 ID 匹配保证增量加在正确的一次专注上。
8. **路由查询参数**：`RouterLink` 的 `{path, query}` 与 `useRoute().query` 配合，将最近条目链接到具体内容。
9. **Vue 生命周期**：`onMounted` 启动刷新，`watch` 监听时区/活动计时/日期变化，`onUnmounted` 清理事件与阻止旧响应。
10. **类型复用**：`Pick<Task, …>` 从既有任务类型选择首页需要的字段，减少重复定义。

## 验证

- 新增后端测试 6 项通过（SQLite）；真实 MySQL 全量 **183 项通过**。
- 前端既有 **26 项测试通过**，没有为静态布局添加重复实现式测试；类型检查与生产构建通过，新增/修改的后端文件 Ruff 检查通过。
- 临时账号浏览器实际验证：今日 1/3 任务完成后变为 2/3；快捷专注启动后倒计时推进、汇总专注时长增长；两个最近内容入口分别打开了对应笔记正文和文档预览。
- 默认 1280px 宽度下页面没有根节点横向溢出；实际验收页没有 console error。所有手机尺寸、任意字体/背景组合、后台冻结/离线后所有恢复时序未逐项人工验收。
- 浏览器使用 `localhost:5173` 临时账号，与用户正在使用的 `127.0.0.1:5173` 登录和外观隔离；测试示例不属于用户真实内容。临时账号、示例记录、脚本和元数据文件已经清理。

截图：[工作台首屏](/D:/FocusNest/docs/screenshots/dashboard-overview.png)。

本阶段完成后，下一业务阶段为 Phase 8 Statistics，尚未实施。

# 每周日程、固定时段计时与全局状态栏：修改清单和代码说明

2026-11-14 更新后的周视图使用当周编辑、独立模板与周日确认。参见 [日程模板操作及修改清单](SCHEDULE_TEMPLATES.md)。

实施日期：2026-11-02。本次是用户审核通过后的日程与专注扩展，不代表启动完整 Phase 7 Dashboard；原有任务、日记、笔记、文档功能保留。

## 1. 已实现的行为

### 每周日程

左侧“日程”进入 `/schedule`，以周一至周日展示安排，可以切换上一周、下一周和本周。

每项包含名称、备注、星期、开始/结束时间、时区、可选任务、自动计时开关、开始/结束提醒开关。一次创建后每周重复，直到从某次起移除。

- **仅本次编辑**：覆盖所选日期，不改变其他周；星期不能单独移动，时间和内容可以修改。
- **仅跳过本次**：保留卡片并标记跳过；可以再次编辑恢复。
- **本次及后续编辑**：截断旧版本，从所选日期起建立新版本，可更改星期；所选日期以前的安排保留。新版本会重置后续旧的单次例外，编辑框中已说明。
- **本次及后续移除**：截断旧版本，保留此前安排及所有已产生的专注记录。
- 过去日期只读；当天仍允许编辑计划，但已经启动的计时使用原始快照，不随计划变化。
- 允许安排重叠，右栏会显示所有当前日程；同一账号仍只允许一个活动计时，包含暂停中或等待开始的计时。
- 每项周日程限当天，支持结束时间 24:00；跨日安排拆成两项。第一版采用表单编辑，没有实现拖拽、月视图或提醒提前量。

### 指定起止时间计时

“专注”保留番茄钟、倒计时、正计时，新增 `scheduled` 模式。填写计时内容、开始日期时间、结束日期时间；时间按个人资料时区解释，而不是直接采用电脑时区。

未来创建的计时先进入 `scheduled`（等待开始），到点转为 `running`，到结束点结算为 `completed`。未来开始不超过 31 天，时段实际长度为 60–86400 秒，结束必须晚于当前时间。该模式不提供暂停/继续，可提前结束或取消；尚未开始时只允许取消。

```text
计划 19:00–20:30，18:50 创建：
18:50 等待开始，累计为 0 → 19:00 开始 → 20:30 结束。

计划 19:00–20:30，19:20 才打开并启动：
保留计划 19:00–20:30，但实际 started_at 为 19:20。
到 20:30 最多累计 70 分钟，不补记错过的 20 分钟。
```

日程勾选自动计时时，登录后的全局运行器检测到正在进行的安排，再请求后端启动剩余时段。关闭网站时没有后台任务替用户创建新计时，已经错过且结束的日程不会补建专注记录。已明确创建的活动计时则会在关闭页面后继续按时段计算，恢复访问时由服务端结算。

这只是时间记录，不检测鼠标、键盘活动，也不能证明用户一直在实际学习。

### 非专注页面的右栏

任务、笔记、文档、日记、设置等登录后页面共用一个运行器，在右侧显示当前日程、计时内容/剩余时间、下一项日程。正计时显示已用时间。专注页面隐藏重复的小计时卡，日程信息仍可查看。

宽屏右栏占独立空间；不超过 1450px 时改为右下角可展开面板，默认收起，避免挤压正文。折叠偏好保存在当前浏览器。周视图手机端按天纵向排列，大字号或空间不足时可在周视图区横向滚动。

已有活动计时时，日程提示冲突，不取消、不覆盖当前计时。处理当前计时后，运行器可以检测并启动仍在时间范围内且尚未执行的日程。单次日程已经结束/取消过计时后，不会自动重启。

### 提醒

- 开始、结束的站内提示，在所有登录后页面生效；提示可手动关闭，最多展示最近 4 条。
- 设置页增加提示音和系统通知选项，偏好按浏览器与账号保存。
- 提示音需点击“启用 / 试听声音”；刷新后可能需要再次点击，界面会说明。
- 系统通知需用户点击授权；被拒绝后通过浏览器网站权限调整，通知不可用时站内提示仍工作。
- 同一事件通过持久化事件键去重；浏览器支持 Web Locks 时，跨标签页串行检查，减少重复声音/通知。无 Web Locks 或本机存储不可用时，跨标签页去重会退化。
- 日程关联计时以日程的提醒为准，避免到同一个时间点连续发两次提示。
- 检测依赖网站仍在运行。关闭浏览器、电脑休眠、后台冻结或离线时不保证准点提醒。超过检测窗口的旧提醒不会集中补发。

## 2. 新增文件清单（18 个源代码/测试文件）

以下路径均在 `D:\FocusNest\` 下。

| 文件 | 主要职责 |
| --- | --- |
| `backend/app/models/schedule.py` | `WeeklySchedule` 周计划版本；`ScheduleException` 单次覆盖/跳过 |
| `backend/app/schemas/schedule.py` | 日程请求与返回结构，校验标题、分钟、星期、时区、修改范围 |
| `backend/app/services/schedules.py` | 周展开、时区换算、创建、单次覆盖、未来版本拆分、日程启动计时 |
| `backend/app/api/v1/endpoints/schedules.py` | 将 HTTP 请求连接到日程服务，并沿用登录用户依赖 |
| `backend/alembic/versions/0011_weekly_schedules.py` | MySQL 新表、计时字段、约束和唯一键迁移 |
| `backend/tests/test_schedules.py` | 重复、例外、删除范围、版本冲突、权限、固定时段和夏令时测试 |
| `backend/tests/test_schedule_concurrency.py` | 真实 MySQL 同一日程并发启动、同版本并发编辑测试 |
| `frontend/src/types/schedule.ts` | 周计划、单次日程和接口返回的 TypeScript 类型 |
| `frontend/src/api/schedules.ts` | 日程查询、新增、编辑、移除、启动计时请求 |
| `frontend/src/utils/scheduleTime.ts` | 日期运算、周起点、时长格式化、个人时区墙上时间转 UTC |
| `frontend/src/stores/workspaceRuntime.ts` | 全局日程/计时状态、同步、时钟、自动启动、冲突提示与生命周期 |
| `frontend/src/stores/reminders.ts` | 提醒偏好、站内队列、声音、系统通知、事件去重 |
| `frontend/src/views/ScheduleView.vue` | 周视图与新增/编辑/移除表单、任务选择、范围选择 |
| `frontend/src/components/WorkspaceStatus.vue` | 跨页面右栏、折叠面板与站内提示展示 |
| `frontend/src/components/ReminderSettings.vue` | 提示音试听、系统通知授权与开关说明 |
| `frontend/tests/scheduleTime.test.mjs` | 日期跨月/年、时区转换、夏令时及时间显示测试 |
| `frontend/tests/workspaceRuntime.test.mjs` | 使用真实状态模块与模拟传输/时钟，验证计时推进、冲突、退出隔离和写操作竞态 |
| `frontend/tests/reminders.test.mjs` | 使用真实提醒模块验证持久化去重、账号隔离与损坏记录恢复 |

另新增本文与验收截图；临时账号脚本不属于交付代码，已在验收结束后移除。

## 3. 修改文件清单（13 个已有源代码/配置文件）

| 文件 | 修改内容 |
| --- | --- |
| `backend/app/models/focus_session.py` | 新模式/状态，新增标题、计划起止时间与单次日程唯一键，调整检查约束 |
| `backend/app/models/__init__.py` | 注册两个日程模型，供 ORM 与 Alembic 发现 |
| `backend/app/schemas/focus.py` | `FocusCreate.valid_timer` 校验固定时段；`FocusRead` 返回新字段及 UTC 时间 |
| `backend/app/services/focus.py` | `elapsed/reconcile/start/transition/read` 支持等待、固定结束、晚启动与幂等；无自定义标题时保存关联任务标题快照 |
| `backend/app/api/v1/router.py` | 注册日程路由 |
| `backend/app/main.py` | 日程响应同样设置 `Cache-Control: no-store` |
| `frontend/src/types/focus.ts` | 新计时模式、等待状态与起止时间/标题字段 |
| `frontend/src/api/client.ts` | 日程输入、版本冲突、定时规则等中文错误提示 |
| `frontend/src/views/FocusView.vue` | 接入全局状态，增加标题和起止时间输入，移除页面私有时钟/轮询，保留历史记录和操作 |
| `frontend/src/layouts/AppLayout.vue` | 增加“日程”导航，随登录用户启停运行器，接入全局右栏 |
| `frontend/src/views/SettingsView.vue` | 接入提醒设置组件 |
| `frontend/src/router/index.ts` | 新增 `/schedule` 页面路由 |
| `frontend/package.json` | 加入三组新前端测试，没有引入新运行依赖 |

同步 README、PROJECT_SPEC 与旧专注文档中的说明入口，不覆盖原有历史解释。

## 4. 数据库与迁移

迁移：`0010_document_formats` → `0011_weekly_schedules`。

`weekly_schedules`：

- `id/user_id`：日程和所属用户。
- `title/notes/weekday/start_minute/end_minute/timezone`：每周规则，星期为 0（周一）至 6（周日）。例如 09:30 用分钟 570 表示；24:00 用 1440 表示。
- `effective_from/effective_until`：版本生效区间，结束为空表示继续复用。
- `task_id/timer_enabled/remind_start/remind_end`：任务与计时/提醒选项。
- `revision`：并发编辑版本号。

`schedule_exceptions`：

- `schedule_id + occurrence_date` 唯一，确保一天只有一个例外。
- `skipped` 表示跳过；其余内容字段保存这一次的完整覆盖值。
- 外键关联周计划，用户删除时经周计划级联清理；任务删除只清空关联。

`focus_sessions` 新增：

| 字段 | 用途 |
| --- | --- |
| `title` | 保存计时内容快照，旧记录默认空串 |
| `window_start/window_end` | 计划起止 UTC 时刻，MySQL 保留微秒 |
| `occurrence_key` | `日程版本UUID:日期`，唯一且可为空，防止同次日程重复建立计时 |

`started_at` 对固定计时保存真正开始累计的时刻，可能晚于 `window_start`。原有 `active_user_id` 唯一约束继续保证一个活动计时。

执行迁移的命令：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

本次迁移中发现并修正过 Alembic 约束命名重复前缀的问题。使用 `op.f(完整约束名)` 告诉 Alembic 名称已经完成转换，避免再次应用命名规则。MySQL DDL 不能整体回滚，所以升级时检查本迁移的表、字段、索引是否已经创建，支持中断后继续；没有通过删除现有业务数据恢复。

降级存在保护：数据库中仍有周计划或新模式计时记录时拒绝降级，避免静默丢失数据。升级已经执行，不需要用户再创建表。

## 5. API 契约

全部路径在 `/api/v1` 下，要求登录，数据按当前用户隔离。

| 方法 | 路径 | 含义 |
| --- | --- | --- |
| GET | `/schedules?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | 展开指定日期区间，最多 32 个自然日，返回日程与 `server_now` |
| POST | `/schedules` | 创建每周规则，返回日程 ID |
| PUT | `/schedules/{id}` | 完整字段、`scope=single/future`、`occurrence_date`、`revision`；修改一次或拆分后续版本 |
| POST | `/schedules/{id}/remove` | 传范围、日期、版本号；跳过单次或截断后续 |
| POST | `/schedules/{id}/start?occurrence_date=YYYY-MM-DD` | 校验本次处于进行中且启用计时，幂等启动剩余时段 |

原 `/focus/current`、`/focus/sessions`、暂停/继续/结束/取消路径保留。创建固定时段示例：

```json
{
  "mode": "scheduled",
  "kind": "focus",
  "title": "阅读 Python 教程",
  "duration_seconds": null,
  "task_id": null,
  "window_start": "2026-11-02T19:00:00+08:00",
  "window_end": "2026-11-02T20:30:00+08:00"
}
```

示例日期仅说明格式，实际调用需满足未来结束时间。客户端不能填写 `occurrence_key`、实际累计时间、用户或状态。

写入先锁定用户行；编辑检查 `revision`，过期版本返回 409。启动同一日程还使用加锁查询读取最新记录，避免 MySQL Repeatable Read 的旧快照漏掉另一个请求刚创建的计时。测试证明两个请求返回同一条记录，同版本的两个编辑只有一个成功。

## 6. 主要代码调用流程

### 创建和查看周计划

```text
ScheduleView.open / save
  → api/schedules.createSchedule
  → endpoints/schedules.create
  → services/schedules.create
  → WeeklySchedule → MySQL

ScheduleView.load
  → listSchedule → endpoints.week → services.list_week
  → occurs 判断星期/生效区间
  → occurrence 合并 ScheduleException
  → local_time 按日程时区转 UTC → 返回周列表
```

周计划没有预先生成未来每一周的数据库行；查询时展开。单次调整才增加例外行，未来调整才建立新版本，因此不会每周无限复制。

### 跨页面检测与日程计时

```text
AppLayout 监听登录账号
  → runtime.start
  → sync：读取当前计时 + 当前附近的日程（每 5 秒）
  → scan：依据服务端校时后的时钟更新显示（每 250ms）
  → 当前日程开启计时且没有活动计时
  → startOccurrence → 后端用户锁/唯一键/时段校验
  → focus.start → started_at=max(当前时间, 计划开始时间)
  → runtime.current → WorkspaceStatus 与 FocusView 共用
```

`mutate` 会等待已有同步完成，在写操作期间阻止新轮询，避免旧查询响应把刚创建/结束的计时覆盖。退出登录增加 `generation`，旧异步响应不能恢复前一账号的私人状态。

浏览器只是实时展示并请求检测；后端 `reconcile` 按真实结束点结算，超过结束时间再打开也不会超记。前端同步失败时提示状态可能过期，连续超过 30 秒未同步时停止基于旧数据发新提醒。切回窗口或恢复联网会重同步。

### 提醒

`scan` 检测上次扫描与当前时间之间的开始/结束边界，调用 `reminders.notify`。事件键由日程/计时 ID、日期和边界类型构成。去重记录保留近期 7 天、最多 1000 项；本次账号的站内消息与声音/系统通知统一经过这个入口。

## 7. 新知识与语法

1. **重复规则与例外**：保存“每周一”的规则，只对某个日期存例外，避免整周复制。`effective_from/until` 是时间版本控制，保留历史。
2. **计划时间与实际时间**：`window_start` 是预定开始，`started_at` 是实际累计开始。两者分开才能处理迟到启动，而不虚增记录。
3. **UTC 与墙上时间**：`09:00` 本身不说明时区；周计划保留 IANA 时区，具体日期展开为 UTC。夏令时不存在的时间标为警告，不自动计时；重复时间采用第一次。夏令时导致启用计时的时段超出允许实际长度时也标记警告。
4. **`@model_validator(mode="after")`**：Pydantic 单字段校验以后检查多个字段的关系，例如结束晚于开始、定时模式不能填写普通时长。
5. **`Mapped[T]` / `mapped_column`**：同时描述 Python 属性类型和数据库列；`ForeignKey`、`UniqueConstraint`、`CheckConstraint` 约束不同类型的数据关系。
6. **幂等性**：同一请求重复到达仍返回同一个业务结果。日程唯一键既应对多标签页，也应对网络重试。
7. **悲观锁与乐观版本号**：`with_for_update` 串行修改；`revision` 识别用户拿旧页面提交的内容。两者解决的问题不同。
8. **全局 Pinia 状态**：路由页面切换只卸载页面组件，全局运行器留在布局层；两个页面读同一个计时，不各自启动一份。
9. **`computed/ref/watch`**：`ref` 保存状态，`computed` 推导当前日程/剩余秒数，`watch` 随账号变化启动/停止工作。运行器的时钟是响应式依赖，数字才能持续变化。
10. **单调时钟**：`performance.now()` 推进服务端返回时刻之间的显示，轮询重新校准；避免每次都直接信任浏览器系统时间。
11. **异步失效检查**：`generation` 标记当前会话；请求返回时版本不同就丢弃，避免退出后旧数据重新出现。
12. **CSS Grid 与响应式右栏**：周视图用七列网格，窄屏改纵向；右栏在中小屏变为可折叠浮层，沿用浅磨砂和可配置字体颜色。

通知与音频 API 的约束参考：[MDN Notifications 使用说明](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API)、[MDN Web Audio 实践](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices)。系统通知授权与声音播放需要用户交互，具体效果也取决于浏览器和系统设置。

## 8. 验证结果

已实际执行：

- MySQL 全量后端回归 **177 passed**，包含同一日程同时启动仅一条记录、同版本并发编辑仅一次成功。
- SQLite 全量 **168 passed / 9 skipped**；跳过项为仅真实 MySQL 适用的并发验证。
- 前端 **26 项测试通过**；Vue/TypeScript 类型检查与 Vite 生产构建通过；本次后端新增/修改文件 Ruff 检查通过。
- `alembic upgrade head` 已成功应用到项目 MySQL；版本为 `0011_weekly_schedules`，`alembic check` 显示没有遗漏的升级操作。
- 浏览器在独立临时账号上实际创建周计划，切到下周仍有相同安排；将下周改成单次标题后，本周仍保持原标题。
- 周日程到点后在笔记页显示当前日程、计时内容与剩余秒数，并出现开始提示；刷新可从后端恢复，不生成重复计时。较计划开始晚几秒启动时，仅累计实际启动后的部分。
- 独立固定计时实际验证等待开始、切换设置/任务页、开始提示、结束提示；专注历史中记录为已完成、累计 **60 秒**。
- 默认 1280×720 浏览器视口下检查了七天周视图和浮动右栏，页面根节点没有横向溢出；这不等同于所有手机尺寸均已验收。
- 验收页未记录到控制台 error。系统通知授权与实际系统弹窗、扬声器听感、浏览器关闭/休眠场景以及所有字号/手机组合未逐项人工验证；相关限制已在界面说明。
- 最终复核补充跨时区排序：周视图按日程本地日期展示，右栏“下一项”和自动计时优先顺序按真实 UTC 起点排序；已用不同时区用例验证，避免直接用本地时钟文本比较。

浏览器测试通过 `localhost:5173` 的临时账号隔离用户正在使用的 `127.0.0.1:5173` 登录与外观。临时账号、其日程/计时记录、临时脚本及测试元数据已清理。未更改用户真实日程或专注记录。最初尝试的独立 5174 端口被既有来源校验拒绝；没有放宽认证来源配置，该临时服务已停止。

截图均来自临时验收账号：

- [完整周视图](/D:/FocusNest/docs/screenshots/weekly-schedule.png)
- [非专注页面中的日程与计时](/D:/FocusNest/docs/screenshots/schedule-global-timer.png)
- [独立计时开始与结束提示](/D:/FocusNest/docs/screenshots/schedule-timer-reminders.png)

没有新增生产依赖、后台常驻任务、浏览器推送服务或桌面程序；没有进入下一业务开发阶段。后续如需关闭网页也能准点提醒，需另行设计后台推送或桌面常驻能力。

## 2026-11-04 计时结束提示音更新

- 新增独立 `endSound` 偏好，默认开启；与原有“其他日程 / 开始提示音”分开控制。结束播放约 1.5 秒的三声铃音（660/830/990Hz），也支持手动结束；取消计时不发结束音。
- 新增 `frontend/src/components/TimerSoundControl.vue`，在专注页与提醒设置中提供开关、试听及声音就绪状态。
- 修改 `frontend/src/stores/reminders.ts`：真实指针/键盘操作时准备或恢复 AudioContext，刷新后开始计时等操作即可准备声音；通过短淡入/淡出与播放后断开节点避免突兀和资源积累。
- 修改 `frontend/src/stores/workspaceRuntime.ts`：手动完成接入统一结束事件；日程到点与已到期计时的完成操作共用结束事件键，避免双响。
- 修改 `frontend/src/views/FocusView.vue`、`frontend/src/components/ReminderSettings.vue` 接入控件；两份相关前端测试增加默认开启、静音持久化、三声调度、重复抑制、未准备声音的标签页不消耗其他页音频事件、手动结束/取消与日程共用键用例。
- 前端测试最终 **29 项通过**。浏览器隔离验收页确认 AudioContext 就绪、两秒结束事件、开关和刷新后的关闭状态；未声称实际检查了用户扬声器音量或听感。临时验收 HTML 已移除，没有修改用户的真实计时记录。
- 浏览器仍需要真实操作来允许音频；网站静音、系统音量关闭、浏览器休眠或网站关闭时不能保证听到。参考 [MDN Web Audio 用户交互与播放控制](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices)。
- 此次无数据库、API 或依赖变化。日程关联计时仍遵从该日程的结束提醒开关。

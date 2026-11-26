# Phase 3 Focus 使用与实现说明

> **2026-11-02 扩展说明**：本文下方保留 Phase 3 初始实现记录。当前版本已增加 `scheduled` 固定时段、等待状态、全局跨页面计时及提醒，不再局限于专注页面轮询；每周日程与最新契约见 [WEEKLY_SCHEDULES.md](WEEKLY_SCHEDULES.md)。原“没有系统通知”的说明仅描述初版。MySQL 当前迁移为 `0011_weekly_schedules`。

实施日期：2026-10-16。范围为专注模块，下一阶段 Journal 尚未实施。

## 使用

启动方式沿用 README，登录后点击侧栏“专注”，地址 `/focus`。

- 番茄钟：默认专注 25 分钟，休息 5 分钟，可自定义。专注和休息分别手动开始，不自动循环。
- 倒计时：自定义 1–1440 整数分钟。
- 正计时：从零累计，手动结束，不指定目标时间。
- 可关联当前账号的任务；任务下拉超过 100 条时可继续加载。
- 支持暂停、继续、结束并保存、确认取消。取消保留记录和已用时间，状态为 cancelled。
- 记录分页显示，包含专注与休息，按开始时间倒序排列。显示时区使用用户设置。

## 计时契约

MySQL 保存计时状态，浏览器只渲染实时数字。已用时间由累计秒数加当前运行段时长组成；暂停期间不累计。页面每 5 秒同步一次，切回页面或恢复联网时重新同步。刷新、关闭页面不会自动暂停；正计时持续到手动结束。

倒计时到点后，下一次查询或操作会结算为 completed，已用时间封顶于目标时长，结束时间是实际到期点，不是重新打开页面的时刻。没有后台常驻调度器、系统通知或自动下一轮。离线时不能保证立即收到到期确认，联网后由后端恢复真实状态。

同一用户最多一个 running/paused 记录。启动和状态变更锁定用户行，并以 nullable unique active_user_id 保证单一活动记录。重复暂停/继续不重置时长；已结束或取消的记录不会因延迟请求重新开始。

完成专注不会自动完成任务。任务删除后 task_id 设为 NULL，专注记录保留；删除用户时级联清理其记录。仅能关联自己的任务，所有读写校验当前身份。

## 数据库

新增 focus_sessions 表，字段包括 id、user_id、active_user_id、task_id、mode、kind、status、duration_seconds、elapsed_seconds、started_at、segment_started_at、ended_at、updated_at。

- `0004_focus_sessions`：创建表、外键、约束、唯一键和历史查询索引。
- `0005_focus_timer_precision`：MySQL 时间列升级为 DATETIME(6)，累计秒数使用 DOUBLE。真实 MySQL 测试发现默认 DateTime 丢失小数秒，故保留独立修复迁移。

当前迁移 head：0005_focus_timer_precision。本机已应用，Alembic check 通过。新环境在 backend 运行 `.\.venv\Scripts\python.exe -m alembic upgrade head`。正式建表不使用 create_all；SQLite 仅用于隔离测试。

## API

统一前缀 `/api/v1/focus`，要求 Bearer 身份，响应禁止缓存。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /current | 当前计时，无活动计时时 data=null |
| GET | /sessions | 记录列表，page/page_size，默认每页 10、最多 100 |
| POST | /sessions | 开始计时，成功 201 |
| POST | /sessions/{id}/pause | 暂停 |
| POST | /sessions/{id}/resume | 继续 |
| POST | /sessions/{id}/finish | 结束并保存 |
| POST | /sessions/{id}/cancel | 取消并保留记录 |

创建参数：mode=pomodoro/countdown/stopwatch，kind=focus/break，可选 task_id。计时模式的 duration_seconds 范围为 60–86400；正计时不得填写。break 仅用于 pomodoro，不能关联任务。未声明字段被拒绝，客户端不能填写累计时间、所属用户或状态。

重复启动返回 409/code 40902，未授权记录返回 404/code 40402；不属于自己的关联任务返回 404/code 40401。读取 current/history 会在需要时持久化到期结算。

## 文件

新增后端：models/focus_session.py、schemas/focus.py、repositories/focus.py、services/focus.py、api/v1/endpoints/focus.py（均在 backend/app 下），以及两个迁移文件和 tests/test_focus.py、tests/test_focus_concurrency.py。

新增前端：frontend/src/types/focus.ts、api/focus.ts、views/FocusView.vue。

修改模型注册、后端路由、响应缓存头、前端路由、侧栏、首页入口和错误提示。未增加依赖。

调用链：FocusView → api/focus.ts → endpoints/focus.py → services/focus.py → repositories/focus.py → MySQL。Service 的 elapsed/reconcile 负责计时计算和到期结算，transition 负责状态转换。

## 验证

真实 MySQL 全量测试：78 passed，含认证、任务、专注以及两个并发测试。覆盖小数秒暂停/继续、刷新恢复、长时间离开后到期结算、结束重复请求、跨用户隔离、关联任务删除后记录保留、非法参数、分页、匿名请求拒绝。

SQLite 隔离测试：76 passed、2 skipped（两个 MySQL 专属并发用例）。Ruff 静态检查、TypeScript 检查和 Vite 生产构建均通过。

浏览器使用独立临时账号实际验证：登录导航、一分钟番茄钟、暂停后刷新恢复、继续、到期自动结算为 60 秒、休息独立记录、提前结束、正计时及确认取消。任务关联和删除保留记录经 API 自动测试验证，不将其记作已完成的浏览器点击验证。

原有 Starlette/httpx 与 AnyIO 弃用提示仍存在。本次没有实现专注统计面板、声音/桌面提醒、自动番茄循环、记录编辑或删除。

浏览器临时账号及其专注记录、认证会话已按唯一用户 ID 清理，未修改真实用户数据。

原 README 和 PROJECT_SPEC 保存在 docs/archive/2026-10-16-phase3。未覆盖 Obsidian 产品说明，也未自动生成每日工作总结。

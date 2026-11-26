# FocusNest 工作记录 · 日程模板与周日确认

实施日期 2026-11-14（北京时间）。

2026-11-26 后续扩展：创建日程可选临时或每周重复，移除重复规则可选单次或本次及以后；自动沿用模板会保留另外新增的每周规则。以下保留 11-14 的实施说明，最新行为见 [日程重复方式与移除范围](SCHEDULE_REPEAT_OPTIONS.md)。

## 使用方式

1. 在「日程」页选一周，添加安排或调整、跳过现有安排。页面的增删改只影响那一周。
2. 点击「另存为新模板」并输入名称。模板保存该周实际可用的安排，包含临时新增和修改，跳过的条目不写入。一个账号可保存多个模板。
3. 切到要安排的周，点击「应用模板」并确认。新选模板会替换该周尚未开始的安排。已开始的安排和既有计时记录保留。已有的模板快照和其他周已经选定的模板继续保留。
4. 每周日按账号时区，在已登录的工作区显示下周提醒。进入后可沿用本周模板、选择其他模板，或确认下周已经安排好的模板。确认后本周的提醒消失。
5. 周日未确认时，进入新一周后，工作区首次同步日程会自动沿用最近生效的模板。已经为目标周选好的模板优先，本周临时变动不进入下一周模板，目标周预先新增的单次安排继续保留。从未用过模板的账号继续使用原有重复规则。

**使用边界**。周日提示依赖已登录的网页。网站关闭期间没有后台推送，也没有提前生成周计划；下次打开工作区时补齐当前周。可以提前明确给未来某周应用模板。自动沿用时对目标周已存在的单次安排、旧规则的单次例外和已关联计时做保留处理。创建模板本身只保存快照，需要至少应用一次才会成为之后的沿用来源。

## 修改文件和代码逻辑

| 文件 | 作用 |
| --- | --- |
| `D:/FocusNest/backend/app/models/schedule.py`、`D:/FocusNest/backend/app/models/__init__.py` | 新增并注册模板快照和每周计划模型，单次例外增加模板替换标记。 |
| `D:/FocusNest/backend/app/schemas/schedule.py` | 新增模板、应用和周日确认的请求与响应结构。现有创建接口增加可选 `repeat_weekly`，周视图返回模板 ID 和每条安排是否属于重复规则。 |
| `D:/FocusNest/backend/app/services/schedule_templates.py` | `save()` 从该周有效安排生成快照；`apply()` 校验归属和目标周后应用；`review_due()`、`keep_week()` 管理周日确认；`ensure_current_week()` 负责自动沿用。 |
| `D:/FocusNest/backend/app/services/schedules.py` | 抽出日期范围展开逻辑，支持只在一天生效的日程；隐藏被模板替换的单次安排，并拒绝为其启动计时。原 API 调用方仍可创建或修改重复规则。 |
| `D:/FocusNest/backend/app/api/v1/endpoints/schedules.py` | 注册模板、应用、沿用和周日确认接口，复用账号认证。 |
| `D:/FocusNest/backend/alembic/versions/0018_schedule_templates.py` | 创建两张表并为日程例外增加列。 |
| `D:/FocusNest/frontend/src/views/ScheduleView.vue` | 周视图展示当前模板、另存为新模板、应用确认，以及仅当周的日程编辑。 |
| `D:/FocusNest/frontend/src/components/ScheduleTemplateReminder.vue`、`D:/FocusNest/frontend/src/layouts/AppLayout.vue` | 在全局工作区展示周日提示并链接到下周。 |
| `D:/FocusNest/frontend/src/stores/workspaceRuntime.ts` | 每个账号在本地周切换或首次打开时，先尝试补齐当周模板，再读取日程用于右侧状态栏和自动计时。 |
| `D:/FocusNest/frontend/src/api/schedules.ts`、`D:/FocusNest/frontend/src/types/schedule.ts`、`D:/FocusNest/frontend/src/api/client.ts` | 封装模板请求、类型与错误文案。 |
| `D:/FocusNest/backend/tests/test_schedule_templates.py`、`D:/FocusNest/backend/tests/test_schedule_concurrency.py`、`D:/FocusNest/frontend/tests/workspaceRuntime.test.mjs` | 覆盖快照与当周编辑隔离、自动沿用、周日按账号时区确认、提前选模板、跨账号隔离和既有计时并发。 |

## 数据库和 API

本机 MySQL 8.0.44 已应用 `0018_schedule_templates`。升级前后 `weekly_schedules` 和 `schedule_exceptions` 的记录数一致。

- `schedule_templates` 保存账号、模板名称和 JSON 日程快照。模板复制星期、时段、备注、时区和提醒设置。原关联任务已被删除时，应用后该项不带任务关联。
- `schedule_week_plans` 以账号和周一日期为联合主键，记录该周所用模板及是否完成周日确认。
- `schedule_exceptions.replaced` 标记在目标周被模板替换的旧安排。旧规则和计时仍可按原标识追溯。

| 方法与路径（均在 `/api/v1/schedules` 下） | 用途 |
| --- | --- |
| `GET /templates` · `POST /templates` | 列出模板、从选中周另存新模板。 |
| `POST /templates/{id}/apply` | 应用到指定周，核对客户端读取的原模板 ID，避免覆盖其他页面的新选择。 |
| `POST /templates/carry` | 补齐当前周；已存在周计划时重复调用不会生成重复日程。 |
| `GET /template-review` · `POST /template-review/{week_start}/keep` | 查询周日提示、确认沿用或保留已选计划。 |

其他数据库环境更新代码后，在后端运行 `python -m alembic upgrade head`，再重启旧后端进程并更新前端。

## 涉及的知识

- **快照与实例**。模板里的星期和时间用于生成目标周的单次日程。编辑的是生成后的安排，模板 JSON 只有另存为新模板时才会生成新副本。
- **联合主键与幂等**。每个账号每周只有一条周计划。自动沿用通过账号行锁和事务提交，避免同一浏览器多个标签页重复生成安排。
- **时区和日期**。周日以账号 IANA 时区计算，周一日期作为周计划键。每条日程继续使用自身时区将本地钟点换算为开始和结束时间。

## 验证

- 后端完整测试 257 项通过、9 项跳过。Ruff 通过。
- 本机 MySQL 的日程、模板和并发相关测试 22 项通过。
- 前端 80 项测试通过，类型检查和生产构建通过。
- 隔离 Chrome 使用虚构账号和临时 SQLite，验收了添加日程、另存模板、应用到下一周、显示周日提醒，以及周日未选择时周一自动沿用。

# Phase 3 专注模块：新增、修改文件清单与代码解释

文档日期：2026-10-17；对应开发日期：2026-10-16。

范围：上次实现的 Focus 专注模块。本次只核对源码、整理说明，没有修改业务逻辑或数据库，也没有重新运行测试。文件清单依据上次实际修改和当前源码整理，不是 Git 自动差异报告。

## 一、改了哪些文件

共 **12 个新增代码/测试文件、7 个修改的代码文件**，另有项目说明和归档。

### 新增：后端 9 个

| 文件（相对 D:\FocusNest） | 作用 |
| --- | --- |
| backend/app/models/focus_session.py | 定义专注记录的数据库模型 |
| backend/app/schemas/focus.py | 校验创建参数，定义响应格式 |
| backend/app/repositories/focus.py | 查询记录、锁定用户、分页读取 |
| backend/app/services/focus.py | 计算时长、处理到期、开始和转换状态 |
| backend/app/api/v1/endpoints/focus.py | 向浏览器提供专注 HTTP 接口 |
| backend/alembic/versions/0004_focus_sessions.py | 创建 focus_sessions 表 |
| backend/alembic/versions/0005_focus_timer_precision.py | 修复 MySQL 小数秒精度 |
| backend/tests/test_focus.py | 测试功能、权限、计时和参数校验 |
| backend/tests/test_focus_concurrency.py | 在真实 MySQL 上测试并发操作 |

### 新增：前端 3 个

| 文件（相对 D:\FocusNest） | 作用 |
| --- | --- |
| frontend/src/types/focus.ts | 定义 TypeScript 数据类型 |
| frontend/src/api/focus.ts | 封装后端请求 |
| frontend/src/views/FocusView.vue | 专注页面、表单、计时展示、操作按钮和历史列表 |

### 修改：代码 7 个

| 文件 | 具体变化与原因 |
| --- | --- |
| backend/app/models/__init__.py | 导入 FocusSession 并加入 __all__，集中加载模型时登记新表 |
| backend/app/api/v1/router.py | 导入 focus 并 include_router，启用后端接口 |
| backend/app/main.py | 私人响应缓存规则加入 /api/v1/focus/，返回 Cache-Control: no-store |
| frontend/src/router/index.ts | 加入 /focus 路由，懒加载 FocusView，复用登录守卫 |
| frontend/src/layouts/AppLayout.vue | 将“专注”从待开发项改为可点击的 RouterLink |
| frontend/src/views/DashboardView.vue | 增加“开始一段专注”入口，更新首页介绍 |
| frontend/src/api/client.ts | 增加专注参数错误、活动计时冲突、记录不存在的中文提示 |

### 文档及其他文件

- 修改 `README.md`：补充专注入口、说明链接、当前迁移版本和下一阶段。
- 修改 `PROJECT_SPEC.md`：同步 Phase 3 实施进展，下一业务阶段改为 Phase 4 Journal。
- 新增 `docs/PHASE3_FOCUS.md`：功能、接口、数据规则和验证结果。
- 新增 `docs/archive/2026-10-16-phase3/README.md` 与 `PROJECT_SPEC.md`：保留修改前原文。
- 本次新增本文 `docs/PHASE3_CODE_WALKTHROUGH.md`，并保存一份到 Obsidian。

编译产生的 frontend/dist、Python 缓存不列入手写代码清单。测试临时账号信息文件已在上次清理。没有新增依赖，也没有重新实现登录认证。

## 二、先理解整体流程

```text
FocusView.vue：用户点击开始
  → api/focus.ts：发送 POST 请求
  → endpoints/focus.py：接收参数和登录身份
  → services/focus.py：检查业务规则、创建计时
  → repositories/focus.py：数据库查询与锁
  → MySQL focus_sessions：持久化
  → FocusRead / ApiResponse：整理响应
  → FocusView.vue：显示计时，定期同步
```

三个容易混淆的文件：Model 描述数据库表，Schema 描述接口输入输出，前端 types 描述 TypeScript 对象。三者分别服务于不同层。

## 三、后端逐文件解释

### 1. models/focus_session.py：一条计时记录保存什么

源码：[focus_session.py](D:/FocusNest/backend/app/models/focus_session.py)

`class FocusSession(Base)` 继承 SQLAlchemy 模型基类；`__tablename__ = "focus_sessions"` 指定表名。

| 字段 | 含义 |
| --- | --- |
| id | 本条计时的唯一 UUID |
| user_id | 所属用户 |
| active_user_id | 活动计时占位：运行/暂停时为用户 ID，结束后为 NULL |
| task_id | 可选关联任务 ID |
| mode | pomodoro 番茄钟、countdown 倒计时、stopwatch 正计时 |
| kind | focus 专注、break 休息 |
| status | running、paused、completed、cancelled |
| duration_seconds | 目标时长，正计时为空 |
| elapsed_seconds | 已结算的累计秒数，支持小数 |
| started_at | 整条计时第一次开始的时刻 |
| segment_started_at | 当前运行段开始时刻，暂停/结束时为空 |
| ended_at | 最终结束时刻 |
| updated_at | 最近更新时刻 |

`started_at` 和 `segment_started_at` 不相同：第一次开始时相同，暂停后继续只重设后者。

```python
active_user_id: Mapped[str | None] = mapped_column(String(36), unique=True)
```

`Mapped[...]` 声明 ORM 属性；`str | None` 允许为空；`unique=True` 建立唯一约束。MySQL 唯一索引允许多条 NULL，但不能同时出现两条相同用户 ID。因此历史记录可以很多，同一用户的活动计时只能有一条。暂停也占用这个位置。

`user_id` 外键使用 CASCADE：用户删除时删除其记录；`task_id` 使用 SET NULL：任务删除后保留专注记录，只清空关联。关联权限还需要 Service 校验，外键本身不能判断任务是否属于当前用户。

`CheckConstraint` 限制模式、状态、累计时长和活动字段组合；`Index` 为按用户及开始时间查询建立索引。API 还会进行更具体的参数校验。

```python
PRECISE_TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")
```

表示普通数据库使用 DateTime，MySQL 使用精确到六位小数秒的 DATETIME(6)。累计时间用 Double，避免以低精度浮点数保存。时间按 UTC 存储，用户时区用于页面显示。

### 2. schemas/focus.py：合法的请求和响应

源码：[focus.py](D:/FocusNest/backend/app/schemas/focus.py)

| 定义 | 作用 |
| --- | --- |
| FocusMode / FocusStatus | 用 Literal 限制合法字符串 |
| FocusCreate | 接收 mode、kind、duration_seconds、task_id |
| FocusRead | 返回一条记录及当前计算出的已用时间 |
| FocusPage | 返回 items、total、page、page_size |

`extra="forbid"` 拒绝额外字段。客户端不能自己提交 user_id、status 或 elapsed_seconds 来伪造归属和时长。

`Field(ge=60, le=86400, strict=True)` 限制目标时长为 60–86400 的整数秒，拒绝布尔值、数字字符串及小数。前端使用整数分钟并乘以 60；API 本身允许范围内任意整数秒，例如 90 秒。

`valid_timer()` 使用 `@model_validator(mode="after")`，在字段校验后检查参数组合：

- 正计时的目标时长必须为空。
- 其他模式未提供目标时长时，专注默认 1500 秒，休息默认 300 秒。
- 休息只能使用 pomodoro，且不能关联任务。

`serialize_time()` 将 UTC 时间输出为 ISO 字符串。`replace(tzinfo=timezone.utc)` 附加 UTC 标记，依赖存入的值本来就是 UTC；它不是时区换算。

响应里的 `server_now` 是本次后端计算时刻，不是数据库列。`elapsed_seconds` 在响应中由 Service 动态计算，因此可能比数据库保存的“已结算累计值”大。当前前端用返回的累计时间和本地单调时钟显示数字，没有直接用 server_now 计算客户端时钟偏差。

### 3. repositories/focus.py：数据库查询与并发锁

源码：[focus.py](D:/FocusNest/backend/app/repositories/focus.py)

| 函数 | 作用 |
| --- | --- |
| lock_user(db, user_id) | 使用 SELECT ... FOR UPDATE 锁定用户行 |
| active(db, user_id) | 读取并锁定用户当前活动计时 |
| owned(db, user_id, session_id) | 同时按用户和记录 ID 查询并锁定 |
| history(db, user_id, page, page_size) | 查询总数及分页记录 |

为什么先锁用户？第一次开始计时时，还没有 FocusSession 行可锁，但用户行已经存在。两个页面同时开始时，锁同一用户行使请求排队；后一个请求看到已有计时后返回冲突。

`with_for_update()` 将查询变为锁定读取。锁属于数据库事务，提交或回滚后释放。该并发行为在真实 MySQL 测试，不能仅凭 SQLite 测试判断。

`history()` 按 started_at 降序，再按 id 降序排序，以 offset 和 limit 分页。所有查询都限定用户，前端隐藏其他用户记录不能代替这个条件。

### 4. services/focus.py：计时核心

源码：[focus.py](D:/FocusNest/backend/app/services/focus.py)

**elapsed(session, now)：计算现在已经用了多少秒。**

```python
seconds = session.elapsed_seconds
if session.status == "running" and session.segment_started_at:
    seconds += max(0, (now - session.segment_started_at).total_seconds())
return min(seconds, session.duration_seconds) if session.duration_seconds else seconds
```

运行时：已用时间 = 已结算时间 + 当前运行段时长。暂停后：只返回已结算时间。倒计时以目标时长封顶，正计时不封顶。`max(0, ...)` 防止负的运行段时长，`total_seconds()` 将时间差转成秒。

例如先运行 10 秒、暂停 30 秒、继续运行 5 秒，已用时间是 15 秒。第一次暂停保存 10，继续时重设 segment_started_at，后面再加 5，暂停的 30 秒不会加入。

**reconcile(session, now)：检查到期并结算。**

仅处理运行中的定时计时。如果 elapsed 已达到目标，就设置 completed、清空活动占位和运行段起点，并把累计值设为目标时长。

结束时刻使用：

```python
session.segment_started_at + timedelta(
    seconds=session.duration_seconds - session.elapsed_seconds
)
```

例如目标 25 分钟，关闭页面一小时后回来，记录仍按 25 分钟结算，结束时间是理论到期时刻。后端没有每秒运行的常驻计时线程；查询或操作触发结算，浏览器打开时的定期请求推动及时同步。

**read(session, now)：组装返回数据。**

显式构造 FocusRead，用 elapsed() 填入当前累计时长，加上 server_now。没有把 user_id、active_user_id 等内部字段返回给页面。

**current(db, user)：恢复当前计时。**

锁用户 → 查活动计时 → 处理到期 → 返回活动记录或 None → commit。即便是 GET，也可能保存到期结算结果。

**list_sessions(db, user, page, page_size)：读取历史。**

先锁用户并结算活动记录，再 flush，使后续查询看到更新；读取分页并转换为 FocusRead，最后提交。列表包括正在运行、暂停、完成和取消的记录，也包括休息。

**start(db, user, payload)：开始计时。**

1. 锁用户，读取并结算可能已到期的旧计时。
2. 如果仍有运行/暂停记录，返回 409 冲突。
3. 如有关联任务，按 task_id 与当前 user.id 同时验证所属关系。
4. flush 旧记录变化，释放已结束计时的唯一占位。
5. 创建 FocusSession，状态 running、累计值 0，并设置开始时刻。
6. add → flush → 构造响应 → commit。
7. 若插入/提交发生 IntegrityError，rollback 后返回冲突提示。

`flush()` 将待处理操作发送到数据库，但不等于永久提交；`commit()` 提交事务；`rollback()` 撤销未提交的事务变化。`**payload.model_dump()` 将经过校验的请求字典展开成构造参数。

**transition(db, user, session_id, action)：统一处理按钮操作。**

| action | 目标状态 | 关键变化 |
| --- | --- | --- |
| pause | paused | 结算已用秒数，清空运行段起点 |
| resume | running | 保留累计值，新运行段从现在开始 |
| finish | completed | 结算已用时间，写结束时刻，释放活动占位 |
| cancel | cancelled | 同样保留已用时间并释放占位，标记取消 |

先核验所属用户并处理到期，再判断状态。重复 pause/resume 不重置累计值；已经 completed/cancelled 的记录直接返回现状，延迟到达的请求不能将其复活。取消是保留一条 cancelled 记录，不是删除。

### 5. api/v1/endpoints/focus.py：HTTP 入口

源码：[focus.py](D:/FocusNest/backend/app/api/v1/endpoints/focus.py)

端点文件只有四个函数，但 transition 覆盖四种操作，因此提供七种实际接口操作。所有路径统一加前缀 `/api/v1/focus`。

| 方法与后缀 | 端点函数 → Service |
| --- | --- |
| GET /current | current → current |
| GET /sessions | history → list_sessions |
| POST /sessions | start → start |
| POST /sessions/{session_id}/pause | transition → transition |
| POST /sessions/{session_id}/resume | transition → transition |
| POST /sessions/{session_id}/finish | transition → transition |
| POST /sessions/{session_id}/cancel | transition → transition |

`@router.post(...)` 把函数注册成接口。`CurrentUser` 注入已经验证的用户，`DBSession` 注入数据库会话；这两者复用已有认证与数据库依赖。action 使用 Literal，只允许四种操作。

### 6. 两个迁移文件：怎么真的创建数据库属性

源码：[0004](D:/FocusNest/backend/alembic/versions/0004_focus_sessions.py)、[0005](D:/FocusNest/backend/alembic/versions/0005_focus_timer_precision.py)

0004 的 `upgrade()` 用 `op.create_table()` 创建表，用 `sa.Column()` 定义每个字段，例如：

```python
sa.Column("duration_seconds", sa.Integer())
```

这表示 duration_seconds 是一个整数列。`op.create_index()` 创建索引；唯一约束和外键也在迁移里建立。

0005 的 `upgrade()` 使用 `op.alter_column()` 改时间精度和累计秒数类型。它来自真实 MySQL 测试发现的问题：默认时间列会丢掉小数秒，暂停/继续后累计不准确，因此改用 DATETIME(6) 和 DOUBLE。

实际应用这些迁移的终端命令是在 backend 目录运行：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

模型中的 mapped_column 描述映射；迁移中的 Column 描述建表字段；upgrade head 才是执行待应用迁移的命令。本次文档工作没有再次执行它。

`downgrade()` 是回退：0004 删除表，0005 降低精度，会有数据或精度损失，不是日常启动步骤。

### 7. 两个测试文件

源码：[test_focus.py](D:/FocusNest/backend/tests/test_focus.py)、[test_focus_concurrency.py](D:/FocusNest/backend/tests/test_focus_concurrency.py)

test_focus.py 复用已有认证 fixture。account 准备临时用户并通过 monkeypatch 固定 Service 的时间，因此能在几次调用中模拟经过两小时或一天，不必真的等待。

测试范围：暂停/继续与重复操作、到期封顶、当前记录恢复、取消保留时间、活动计时冲突、默认休息时长、用户隔离、任务删除后保留记录、参数校验、分页和未登录拒绝。参数化测试会把不同非法输入展开成多项用例。

test_focus_concurrency.py 使用 ThreadPoolExecutor 发出两个并发请求，用 Barrier 让它们尽量同时开始。检查只能创建一条活动计时，以及 pause 与 finish 竞争后最终保持完成。它需要真实 MySQL，在 SQLite 测试中跳过。临时账号在 finally 中清理。

## 四、前端逐文件解释

### 1. types/focus.ts：数据类型

源码：[focus.ts](D:/FocusNest/frontend/src/types/focus.ts)

- FocusMode：三种计时方式。
- FocusAction：四种状态操作。
- FocusInput：开始请求的字段。
- FocusSession：在输入字段基础上增加 ID、状态、已用时间与时间戳。
- FocusPage：历史列表分页结构。

`extends` 表示接口继承；`string | null` 表示字符串或空值；`Promise<FocusSession>` 表示异步得到一条记录。TypeScript 帮助开发时检查类型，HTTP 输入仍由后端 Schema 检查。

### 2. api/focus.ts：请求封装

源码：[focus.ts](D:/FocusNest/frontend/src/api/focus.ts)

| 函数 | 请求 |
| --- | --- |
| currentFocus() | GET /focus/current，允许返回 null |
| focusHistory(page) | GET /focus/sessions，前端每页 10 条 |
| startFocus(input) | POST /focus/sessions |
| changeFocus(id, action) | POST /focus/sessions/{id}/{action} |

统一 apiClient 添加 `/api/v1` 前缀，复用访问令牌和刷新逻辑。这里没有新增登录方式。Axios 的 response.data 是响应体，响应体里面的 data 才是业务对象，因此代码会读取两层 data。

### 3. views/FocusView.vue：页面主要状态和函数

源码：[FocusView.vue](D:/FocusNest/frontend/src/views/FocusView.vue)

| 状态 | 用途 |
| --- | --- |
| current | 当前活动计时，null 表示可以开始新的 |
| records / page / total | 历史记录、页码和总数 |
| tasks / taskPage / taskTotal | 任务选项及分批加载状态 |
| ready / syncing / busy | 是否恢复成功、是否同步中、是否操作中 |
| error / taskError / notice | 操作错误、任务加载错误、成功提示 |
| form | 计时方式、专注分钟、休息分钟和任务 ID |
| tick / receivedAt | 浏览器渲染时间的参考值 |
| generation / disposed | 忽略旧异步结果和卸载后的结果 |

`ref()` 创建响应式值，脚本用 `.value` 访问。`reactive()` 包装表单对象，直接修改属性。`computed()` 根据其他值计算当前已用时间、剩余时间、进度和总页数。

| 函数 | 说明 |
| --- | --- |
| duration(seconds) | 将秒格式化成 HH:MM:SS |
| localTime(value) | 按用户时区显示时间戳 |
| taskName(id) | 在已加载任务中查标题，否则显示占位说明 |
| applyCurrent(value) | 更新活动记录并重置本地显示参考时刻 |
| sync() | 读取当前记录与历史，更新页面，处理同步错误 |
| loadTasks(more) | 首次加载或继续加载每批最多 100 个任务 |
| start(kind) | 校验分钟、转换秒数、调用开始接口，再同步 |
| act(action) | 暂停/继续/结束/取消，接收实际状态，再同步 |
| changePage(value) | 切换历史页码后同步 |
| visible() | 页面可见或联网恢复时尝试同步 |
| closeCancel() | 操作未进行时关闭取消确认框 |

当前数字的显示逻辑：后端最近返回的 elapsed_seconds，加上从收到结果至今的本地经过时间。使用 `performance.now()` 这种单调计时值，避免仅依赖浏览器时钟的手动调整。暂停时不加这段时间；倒计时显示目标减累计值。

页面有两个不同频率：每 250 毫秒更新显示，每 5 秒向后端同步。不会每 250 毫秒写 MySQL。前端显示有网络同步间隔，实际结算以服务端为准。

`onMounted()` 初始化同步、加载任务、启动定时器、监听页面可见和联网事件。`onUnmounted()` 清除定时器与监听器，防止离开页面后继续重复请求。离开页面只停止界面刷新，不结束数据库中的计时。

模板的 `v-model` 绑定输入；`@submit.prevent` 阻止表单整页刷新；`:disabled` 根据 busy/syncing 状态禁用按钮；`v-if` 决定显示设置表单还是当前计时。取消使用 dialog，确认后才调用 act('cancel')。

当前自定义输入是组件状态，页面刷新后表单回到默认值；已经开始的计时参数会从数据库恢复。没有实现跨页面持久化的个人计时偏好设置。

## 五、按操作顺序看完整调用链

### 开始并关联任务

1. 登录后 router/index.ts 允许进入 /focus，FocusView 挂载。
2. sync → currentFocus 恢复现有计时；loadTasks → listTasks 取得自己的任务选项。
3. 选择任务及 25 分钟，点击开始：FocusView.start 将分钟乘以 60。
4. api.startFocus 发送 POST；FastAPI 验证 FocusCreate 和 CurrentUser。
5. endpoints.start 调用 services.start，锁用户、检查活动记录、验证任务归属。
6. 保存 FocusSession 并提交，返回 FocusRead。
7. applyCurrent 显示当前计时，随后 sync 更新记录列表。

### 暂停、刷新、继续

1. 暂停按钮 → act('pause') → changeFocus → endpoints.transition → services.transition。
2. 后端结算当前运行段，清空 segment_started_at，保存 paused。
3. 刷新页面后 currentFocus 取回同一记录，页面显示“继续计时”。
4. 点击继续 → transition('resume')，保留累计秒数，运行段起点改为现在。

### 到点、手动完成、取消

倒计时到点后，下一次 current/history 或相关操作调用 reconcile，设置完成；前端同步后回到开始表单。没有自动进入休息或下一轮。

手动完成调用 transition('finish')，即使提前结束，也记录实际时长并标记完成。取消调用 transition('cancel')，保留实际时长但状态为取消。两者都会释放 active_user_id，允许开始新计时；都不会自动改变关联任务的状态。

## 六、验证记录与当前边界

以下为 **2026-10-16** 已执行结果，2026-10-17 本次讲解未重新测试：

| 检查 | 结果 |
| --- | --- |
| 真实 MySQL 全量测试 | 78 passed，包含认证、任务、专注和并发验证 |
| SQLite 隔离测试 | 76 passed，2 skipped（MySQL 并发用例） |
| Ruff / TypeScript / Vite 构建 | 通过 |
| Alembic | head=0005_focus_timer_precision，check 通过 |
| 浏览器 | 暂停刷新恢复、继续、1 分钟到期、休息记录、提前结束、正计时取消已验证 |
| 任务关联与删除保留记录 | API 自动测试通过；未声称完成浏览器关联点击验证 |

原有 Starlette/httpx、AnyIO 弃用提示仍存在。临时账号及测试记录已在开发完成后清理。

尚未实现自动多轮番茄钟、桌面/声音提醒、统计面板、记录编辑和删除。下一业务阶段为 Journal，本文不代表开始下一阶段。

建议阅读顺序：先看第五节，再看 Service 的 elapsed、reconcile、transition，最后对照 Model 的三个时间字段。掌握“累计值 + 当前运行段”后，暂停恢复和刷新恢复就容易理解。

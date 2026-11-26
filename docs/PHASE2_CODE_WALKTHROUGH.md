# FocusNest Phase 2：新增与修改文件及代码详解

编写日期：2026-10-12。对应开发日期：2026-10-11。

本次需求：列出上次任务系统新增、修改的文件，解释代码，并形成文档。本文依据当前源码和 `docs/PHASE2_TASKS.md` 编写；项目没有可用于比较的 Git 历史，因此清单是上次实施记录与当前文件的核对结果，不是自动生成的 Git diff。

今天实际执行的是源码核对与文档编写，没有修改业务代码、重新迁移数据库或开始 Phase 3。测试结果在文末单独注明发生日期。

## 1. 先认识这次功能

Phase 1 解决“你是谁”：注册、登录、身份认证。Phase 2 在此基础上解决“你要做什么”：创建自己的任务、查看任务、编辑、完成、恢复待办、删除，以及日期/状态/优先级筛选和分页。

一次操作跨越这些层：

```text
浏览器中的 TasksView.vue：按钮、表单、列表
  → frontend/src/api/tasks.ts：发送 HTTP 请求
  → backend/app/api/v1/endpoints/tasks.py：接收请求
  → backend/app/services/tasks.py：执行任务业务规则
  → backend/app/repositories/tasks.py：构造数据库操作
  → MySQL 的 tasks 表
  → 后端整理响应 → 前端更新列表
```

贯穿其中的三类定义：`schemas/task.py` 校验请求和组织响应；`models/task.py` 映射数据库表；`types/task.ts` 为前端提供 TypeScript 类型。它们分工不同，不能互相替代。

## 2. 完整文件清单

以下路径以 `D:\FocusNest\` 为根目录，共 **10 个新增代码/测试文件，7 个修改的代码文件**。文档和截图另外列出。

### 2.1 新增代码与测试

| 文件 | 用一句话说明作用 |
| --- | --- |
| `backend/app/models/task.py` | Task 数据库模型，定义字段、外键、约束和索引 |
| `backend/app/schemas/task.py` | 创建、修改、返回、分页的数据格式及校验 |
| `backend/app/repositories/tasks.py` | 查询当前用户任务，以及添加、删除数据库对象 |
| `backend/app/services/tasks.py` | 控制所属用户、完成时间、今日判断及事务提交 |
| `backend/app/api/v1/endpoints/tasks.py` | 提供六个 HTTP 接口 |
| `backend/alembic/versions/0003_tasks.py` | 通过数据库迁移创建 tasks 表 |
| `backend/tests/test_tasks.py` | 自动验证任务功能、数据隔离和输入校验 |
| `frontend/src/types/task.ts` | 前端任务相关类型 |
| `frontend/src/api/tasks.ts` | 前端调用任务接口的函数 |
| `frontend/src/views/TasksView.vue` | 用户实际操作的任务页面 |

### 2.2 修改的代码

| 文件 | 本次修改 |
| --- | --- |
| `backend/app/models/__init__.py` | 导入、导出 Task 模型 |
| `backend/app/api/v1/router.py` | 注册任务接口路由 |
| `backend/app/main.py` | 任务响应加入禁止缓存的处理 |
| `frontend/src/router/index.ts` | 增加 `/tasks` 页面路由 |
| `frontend/src/layouts/AppLayout.vue` | 启用侧边栏“任务”入口 |
| `frontend/src/views/DashboardView.vue` | 更新工作台文案，增加任务入口 |
| `frontend/src/api/client.ts` | 增加任务校验失败、任务不存在的中文提示 |

### 2.3 文档与其他产物

| 文件 | 状态与作用 |
| --- | --- |
| `README.md` | 修改：更新已实现功能、任务入口、数据库版本和运行说明 |
| `PROJECT_SPEC.md` | 修改：同步 Phase 2 进展，明确下一阶段是 Phase 3 Focus |
| `docs/PHASE2_TASKS.md` | 新增：实施范围、接口契约、验证结果与限制 |
| `docs/screenshots/phase2-tasks.jpg` | 新增：任务页面截图，内容为临时测试数据 |
| `docs/archive/2026-10-11-phase2/README-before-phase2.md` | 新增：修改前 README 的备份 |
| `docs/archive/2026-10-11-phase2/PROJECT_SPEC-before-phase2.md` | 新增：修改前项目说明书的备份 |

上次另外保存了 Obsidian 笔记 `2026-10-11-144033 工作记录 - Phase1学习问题与完整流程总结.md`。本次新增本文 `docs/PHASE2_CODE_WALKTHROUGH.md`，并另存到指定 Obsidian 目录。

`frontend/dist` 属于构建产物，Python 缓存和测试缓存也不算手写业务代码。上次没有修改 `AGENTS.md`、认证测试文件、环境配置或依赖文件；任务页面样式写在自身组件中。

## 3. 后端逐文件讲解

### 3.1 models/task.py：Python 对象如何对应数据库表

源码：[task.py](D:/FocusNest/backend/app/models/task.py)

`class Task(Base)` 声明 SQLAlchemy 模型；`__tablename__ = "tasks"` 指定对应的表。

```python
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
```

- `Mapped[str]` 表示这是 ORM 管理的字符串属性。
- `mapped_column(...)` 描述数据库列，`String(36)` 是最大长度 36 的字符串列。
- `primary_key=True` 表示主键，唯一识别一条任务。
- `lambda: str(uuid4())` 是无参数函数，插入时为不同任务生成不同 ID，不是在导入文件时只生成一个 ID。
- `ForeignKey("users.id")` 表示每条任务必须关联一个已有用户。
- `ondelete="CASCADE"` 表示删除用户时数据库级联删除其任务；删除一条任务不会反向删除用户。

| 字段 | 含义与约定 |
| --- | --- |
| `id` | 服务端生成的任务 UUID |
| `user_id` | 所属用户，由登录身份决定 |
| `title` | 必填标题，最多 200 字符 |
| `description` | 可空说明，API 最多接受 10000 字符 |
| `status` | todo 待办、doing 进行中、done 已完成；默认 todo |
| `priority` | low 低、medium 中、high 高；默认 medium |
| `scheduled_date` | 计划日期，可空 |
| `due_date` | 截止日期，可空 |
| `estimated_minutes` | 预计耗时，分钟，可空；1～10080 |
| `completed_at` | 完成时刻，未完成时为空 |
| `created_at` | 创建时刻 |
| `updated_at` | 修改时刻 |

`Mapped[str | None]` 中的 `| None` 表示可以为空。`Date` 只存年月日；`DateTime` 存日期与时刻。当前项目的时刻字段按 UTC 保存，API 再补上 UTC 标记输出。

`__table_args__` 中包含三类内容：

1. `CheckConstraint`：限制状态、优先级和耗时范围，数据库再做一层检查。
2. `Index`：建立用户与创建时间、计划日期、截止日期的组合索引，服务于用户任务查询。索引不会自动完成权限检查。
3. `mysql_charset` / `mysql_collate`：指定 utf8mb4 字符集及排序规则。

模型中的 `default`、`onupdate` 是 SQLAlchemy 侧的设置，不等于 MySQL `DEFAULT`。直接手写 SQL 插入时，不能假定数据库会补齐这些字段。写好模型也不会自动创建正式数据库表，建表由 Alembic 完成。

### 3.2 schemas/task.py：允许用户传什么，后端返回什么

源码：[task.py](D:/FocusNest/backend/app/schemas/task.py)

| 类/定义 | 作用 |
| --- | --- |
| `TaskStatus` / `TaskPriority` | 用 `Literal[...]` 限定合法字符串 |
| `TaskFields` | 创建和修改共用的额外字段限制、标题校验 |
| `TaskCreate` | 创建请求，标题必须提供，其余字段有默认值 |
| `TaskUpdate` | 修改请求，只更新明确提交的字段 |
| `TaskRead` | 返回前端的一条任务，不暴露 user_id |
| `TaskPage` | 分页结果：items、total、page、page_size |

`ConfigDict(extra="forbid")` 拒绝未声明的输入字段。因此用户不能在请求中自行塞入 `user_id` 或 `completed_at`。

```python
@field_validator("title", check_fields=False)
@classmethod
def clean_title(cls, value: str | None) -> str | None:
```

`@...` 是装饰器：在函数声明上附加行为。这里 `@classmethod` 让方法接收类参数 `cls`；`@field_validator` 告诉 Pydantic 在校验 title 时调用它。`check_fields=False` 是因为父类 TaskFields 自身没有声明 title，字段由子类声明。函数用 `strip()` 去掉标题两端空白，再拒绝纯空白标题；返回值是校验后使用的值。

`Field(ge=1, le=10080, strict=True)` 中，ge 是“大于等于”，le 是“小于等于”；严格整数校验会拒绝小数、布尔值和数字字符串。

修改请求最重要的区别：

| 请求内容 | 意思 |
| --- | --- |
| `{}` | 不修改任何字段 |
| `{"description": null}` | 清空说明 |
| `{"description": "新说明"}` | 替换说明 |
| `{"title": null}` | 非法，标题不能清空为 null |

`reject_null_required_fields()` 用 `@model_validator(mode="after")` 在模型字段校验后检查整份数据。`self.model_fields_set` 记录请求实际提交过哪些字段；`getattr(self, name)` 按字段名取值。这样可以允许“不传 title”，同时拒绝“显式传 title=null”。状态和优先级也一样。

`TaskRead` 中 `from_attributes=True` 允许 Pydantic 从 `task.title` 等对象属性读取数据，因此 `TaskRead.model_validate(task)` 能接收 SQLAlchemy 对象。

`serialize_time()` 在输出时间字段时执行：`replace(tzinfo=timezone.utc).isoformat()`。这里 `replace` 是附加时区标记，不是时区换算；它依赖项目已经按 UTC 存储时间的约定。`None` 保持为空。

### 3.3 repositories/tasks.py：怎样查、增、删数据

源码：[tasks.py](D:/FocusNest/backend/app/repositories/tasks.py)

| 函数 | 做什么 |
| --- | --- |
| `find_owned(db, user_id, task_id)` | 按任务 ID 和所属用户同时查询一条任务 |
| `list_owned(...)` | 当前用户范围内筛选、计数、排序、分页 |
| `add(db, user_id, values)` | 构造 Task，加入 Session，flush 后返回 |
| `remove(db, task)` | 将指定任务标记为删除 |

权限条件的核心相当于：

```sql
SELECT * FROM tasks
WHERE id = :task_id AND user_id = :current_user_id;
```

这不是拼接用户输入的 SQL 示例，而是帮助理解 ORM 查询的等价条件。即使知道别人的任务 ID，也不能通过该查询获取它。

`list_owned()` 先建立 `Task.user_id == user_id` 条件，再按非空参数添加筛选。普通条件之间是 AND；今日条件内部是“计划日期是今天 OR 截止日期是今天”。因此“今日+高优先级”表示二者都满足。

总数单独用 `count` 查询；列表使用 `offset((page - 1) * page_size)` 和 `limit(page_size)`。例如第 2 页每页 10 条，跳过前 10 条。排序是 `created_at` 降序，再以 `id` 降序处理时间相同的情况。总数是符合条件的全部数量，不只是本页数量。

常见语法：

- `db.scalar(...)` 取单个结果，例如一条 Task 或一个计数。
- `db.scalars(...).all()` 取多条模型对象。
- 函数参数中的独立 `*` 要求其后的参数使用名称传递。
- `.where(*filters)` 将列表中的条件展开成多个参数。
- `Task(user_id=user_id, **values)` 将字典展开成命名参数。
- `db.flush()` 将待处理改动发送给数据库，但还没有提交事务；最终 `commit()` 在 Service 中执行。

这里没有单独的更新函数：Service 修改从 Session 查询出的对象属性后，SQLAlchemy 会跟踪变化并在提交时写回数据库。

### 3.4 services/tasks.py：业务规则集中在哪里

源码：[tasks.py](D:/FocusNest/backend/app/services/tasks.py)

| 函数 | 业务职责 |
| --- | --- |
| `local_today(user)` | 将当前 UTC 时刻转换到用户的 IANA 时区，再取日期 |
| `get_task(...)` | 查当前用户的任务，找不到统一报 404 |
| `list_tasks(...)` | 计算今日条件，调用 Repository，再组装 TaskPage |
| `create_task(...)` | 设置完成时间、创建任务、提交并刷新 |
| `update_task(...)` | 校验所有权、应用部分修改、维护时间、提交 |
| `complete_task(...)` | 复用 update_task，把状态设为 done |
| `delete_task(...)` | 校验所有权、删除、提交 |

`get_task()` 对“任务不存在”和“任务属于别人”统一返回 `AppError(404, 40401, "Task not found")`，不透露他人资源是否存在。

创建时 `payload.model_dump()` 把校验后的模型转成字典，`user.id` 来自已验证的身份。若初始状态就是 done，直接记录完成时刻，否则为空。`db.commit()` 提交事务，`db.refresh(task)` 重新读取数据库中的对象状态。

修改时最关键的是：

```python
values = payload.model_dump(exclude_unset=True)
if "status" in values and values["status"] != task.status:
    task.completed_at = utcnow() if values["status"] == "done" else None
for name, value in values.items():
    setattr(task, name, value)
```

`exclude_unset=True` 排除请求未提供的字段，避免修改标题时顺便清空说明。`setattr(task, "title", value)` 相当于 `task.title = value`，适用于逐个应用修改。

状态从 todo/doing 进入 done 时设置完成时间；离开 done 时清空；重复完成保留原完成时间。不过只要提交了字段，代码仍会更新 `updated_at`，所以“重复完成”不是整条记录完全不变。空 PATCH 不主动更新修改时间。

`complete_task()` 直接调用 `update_task(..., TaskUpdate(status="done"))`，这样完成按钮和普通编辑共用同一套业务规则。

### 3.5 api/v1/endpoints/tasks.py：浏览器能调用哪些入口

源码：[tasks.py](D:/FocusNest/backend/app/api/v1/endpoints/tasks.py)

`APIRouter(prefix="/tasks")` 为这些路由统一加上 `/tasks`。主应用再加 `/api/v1`，合起来就是实际接口地址。

| HTTP | 完整路径 | 入口函数 | 请求/响应 |
| --- | --- | --- | --- |
| GET | `/api/v1/tasks` | `list_tasks` | 查询参数 → TaskPage |
| POST | `/api/v1/tasks` | `create_task` | TaskCreate → TaskRead，201 |
| GET | `/api/v1/tasks/{task_id}` | `get_task` | 路径 ID → TaskRead |
| PATCH | `/api/v1/tasks/{task_id}` | `update_task` | TaskUpdate → TaskRead |
| POST | `/api/v1/tasks/{task_id}/complete` | `complete_task` | 路径 ID → TaskRead |
| DELETE | `/api/v1/tasks/{task_id}` | `delete_task` | 删除成功返回 200，data=null |

`@router.get/post/patch/delete(...)` 把函数绑定到请求方法和路径。`response_model=ApiResponse[TaskRead]` 表示外层使用统一响应结构，里面的 data 是 TaskRead。

`user: CurrentUser` 和 `db: DBSession` 是已有依赖的类型别名：FastAPI 调用相应依赖取得登录用户和数据库 Session，不需要前端传入 Python 对象。

`Annotated[int, Query(ge=1)]` 为整数参数附加查询校验。页码最小 1，每页数量最大 100，API 默认 20；前端主动传 10。参数校验和依赖解析都发生在进入端点函数体之前，不必理解成函数体内手写的固定先后步骤。

这些端点主要负责接收参数和包装响应，真正业务在 Service 中，避免接口文件承担所有工作。

### 3.6 alembic/versions/0003_tasks.py：真正创建表

源码：[0003_tasks.py](D:/FocusNest/backend/alembic/versions/0003_tasks.py)

`revision = "0003_tasks"` 是本次版本；`down_revision` 指向上一版 `0002_users_auth`，形成迁移链。

- `upgrade()`：调用 `op.create_table()` 创建 tasks，包含用户外键、检查约束；通过 `op.create_index()` 创建查询索引。
- `downgrade()`：调用 `op.drop_table("tasks")` 删除本次表，属于会丢失任务数据的回退操作，不是日常启动命令。

`op` 是 Alembic 的迁移操作接口，`sa.Column` 等 SQLAlchemy 对象描述列。模型描述“程序希望表是什么样”，迁移描述“如何把数据库升级到这个样子”。

上次已执行迁移至 0003_tasks。今天只读代码，没有再次执行迁移。任务表新增不改变原用户和认证会话表结构。

### 3.7 tests/test_tasks.py：自动验证，不是正式使用入口

源码：[test_tasks.py](D:/FocusNest/backend/tests/test_tasks.py)

测试会模拟注册、登录和接口请求，并断言结果是否正确。真实用户仍在网页注册登录、创建自己的任务，不需要通过测试使用系统。

文件复用了认证测试中的 `context` fixture 及注册/登录辅助函数。`@pytest.fixture` 为测试准备客户端和账号；`@pytest.mark.parametrize` 让同一测试函数使用不同输入运行多次，因此函数数量不等于测试用例数量。

覆盖的内容包括：任务完整生命周期；不同用户的数据隔离；非法标题/日期/枚举/耗时及伪造字段；分页与组合筛选；跨时区的今日判断；六个接口未登录拒绝。当前该文件共展开为 21 项任务用例。

时区测试固定服务器时刻，验证 UTC 日期和用户所在地日期不同时仍按用户日期查询。MySQL 普通事务测试通过回滚隔离；SQLite 用于另外的测试环境，不代表正式项目改用了 SQLite。

## 4. 前端逐文件讲解

### 4.1 types/task.ts：规定数据的形状

源码：[task.ts](D:/FocusNest/frontend/src/types/task.ts)

`TaskStatus = 'todo' | 'doing' | 'done'` 是联合类型，只接受列出的字符串。这里的 `|` 表示“或”。

| 类型 | 用途 |
| --- | --- |
| `TaskInput` | 表单提交数据，包含标题、说明、状态、优先级、日期、耗时 |
| `Task extends TaskInput` | 在输入字段基础上增加 ID 和服务端时间字段 |
| `TaskPage` | 列表和分页信息 |
| `TaskQuery` | 列表查询参数，`?` 表示参数可省略 |

`description: string | null` 表示字段值可以为空，不等于字段可以省略。TypeScript 类型主要在编译和编辑时帮助发现错误，不能代替后端对真实 HTTP 请求的校验。

### 4.2 api/tasks.ts：页面如何发请求

源码：[tasks.ts](D:/FocusNest/frontend/src/api/tasks.ts)

`listTasks/getTask/createTask/updateTask/completeTask/deleteTask` 分别对应六个后端接口。它们复用现有 `apiClient`，所以认证头、超时和登录刷新规则无需每个函数重新编写。

```typescript
export async function updateTask(id: string, input: Partial<TaskInput>): Promise<Task>
```

这表示导出一个异步函数：接收字符串 ID 和部分任务字段，最终返回 Task。`Partial<TaskInput>` 将全部属性变为可选，所以只传 `{ status: 'todo' }` 也可以。`Promise<Task>` 表示结果需要等待，`await` 用于等待请求完成，不会把浏览器主线程同步锁住。

`unwrap<T>()` 检查业务 code 是否为 0、data 是否非空，并取出真正的数据。Axios 的 `response.data` 是整个响应体，其中还包含项目自己定义的 `data`，因此需要再拆一层。

`listTasks()` 用 `{ params: query }` 生成查询字符串。删除接口成功时 data 本来就是 null，所以 `deleteTask()` 不调用要求非空数据的 unwrap，仅等待 HTTP 请求成功。

### 4.3 views/TasksView.vue：页面的核心

源码：[TasksView.vue](D:/FocusNest/frontend/src/views/TasksView.vue)

单文件组件包含三部分：`<script setup lang="ts">` 编写逻辑；`<template>` 描述页面；`<style scoped>` 定义组件局部样式。

**状态变量如何理解：**

| 变量 | 用途 |
| --- | --- |
| `items/total/page/pageSize` | 当前列表、总数、页码，每页固定 10 条 |
| `loading/saving` | 区分加载列表与提交修改，显示状态、禁用相关按钮 |
| `error/formError/deleteError` | 列表或操作错误、表单错误、删除错误 |
| `notice` | 成功提示 |
| `editorOpen/editingId` | 编辑器是否显示；ID 为空表示新建，否则表示修改 |
| `filters/form` | 筛选条件对象、表单对象 |
| `titleInput/deleteDialog` | 实际输入框和 dialog 元素引用 |
| `deleteTarget` | 等待用户确认删除的任务 |
| `pages/requestId` | 计算总页数；识别列表请求的新旧 |

`ref()` 创建响应式值，脚本里通过 `.value` 读写；模板一般自动解包。`reactive()` 包装对象，直接修改属性即可触发更新。`computed()` 表示派生值，例如总页数由总数计算，不用手动到处同步。

**每个函数的作用：**

| 函数 | 实际逻辑 |
| --- | --- |
| `todayDate()` | 按用户时区格式化浏览器当前日期，用于新建默认日期和逾期样式 |
| `load()` | 请求列表，写入 items/total，处理错误和越界页码，忽略旧请求响应 |
| `changePage(value)` | 改页码，再加载 |
| `resetFilters()` | 清空筛选，由 watch 触发重新加载 |
| `focusEditor()` | 等待 DOM 更新后聚焦标题输入框 |
| `startCreate()` | 清空旧表单，设置默认值，打开新建表单 |
| `edit(task)` | 先 GET 最新详情，再填表并打开编辑器 |
| `save()` | 组装输入，按 editingId 决定创建或修改，成功后重新加载第一页 |
| `toggle(task)` | 未完成则完成，已完成则改回 todo，随后刷新列表 |
| `requestDelete(task)` | 保存待删除对象，打开确认框，此时尚未删除 |
| `cancelDelete()` | 关闭确认框并清空目标，不发删除请求 |
| `remove()` | 用户确认后发 DELETE，成功关闭弹窗并刷新列表 |

**列表加载的两个细节：**

`watch(filters, ..., { immediate: true })` 首次进入立即加载；监听 reactive 对象，筛选变化后回到第一页并重新查询。`void load()` 表示这里不等待 Promise，错误由 load 内部处理。

每次 load 先执行 `const current = ++requestId`。返回后若 `current !== requestId`，说明已有更晚请求，忽略旧结果。例如先选“全部”、再选“高优先级”，即使“全部”更晚返回，也不能覆盖新筛选。它不会取消网络请求，只是不使用过期响应。

如果删除最后一页唯一任务导致页码超过总页数，load 会调整到有效页再查询。`Math.max(1, ...)` 保证空列表仍显示第 1 页。

**表单保存的细节：**

`save()` 去除标题两端空格，把空说明/日期转成 null，把耗时转换成数字。它明确列出可提交字段，不直接把详情对象整体发回，因此不会带上 ID、完成时间等只读字段。

后端支持只 PATCH 少数字段；当前编辑表单提交的是整组可编辑字段，而“恢复待办”只提交 status。保存后保留当前筛选，所以新任务不符合筛选时可能不会出现，页面已有提示。

`await nextTick()` 等 Vue 将编辑器渲染到 DOM 后才聚焦。`?.focus()` 表示元素存在时才调用；`?? ''` 仅在值为 null/undefined 时使用空字符串，与所有假值都替换的 `||` 有区别。

**模板语法：**

- `v-model="form.title"`：输入框与变量双向绑定。
- `@click="startCreate"`：点击调用函数。
- `@submit.prevent="save"`：阻止表单默认刷新页面，改为调用 save。
- `v-if` / `v-else-if`：根据状态显示编辑器、加载提示、空列表或结果。
- `v-for="task in items" :key="task.id"`：循环显示任务，ID 帮助 Vue 识别对应元素。
- `:disabled="saving"`：动态禁用，降低重复提交的机会。
- `{{ task.title }}`：插值显示文本，不把任务内容当 HTML 执行。
- `<dialog>` 配合 `showModal()/close()` 实现删除确认；Esc 的 cancel 事件交给 cancelDelete，不会触发删除。

样式控制卡片、完成划线、优先级颜色、逾期提示、弹窗背景和窄屏布局。目前没有新增任务 Pinia Store，任务页面状态保存在组件内；登录信息仍复用已有 auth Store。

后端今日筛选使用服务器时钟计算用户日期；前端 todayDate 使用浏览器时钟进行显示和默认填值。两者职责不同，最终查询依据后端。

## 5. 七个修改文件为什么必须改

| 文件 | 关键修改与意义 |
| --- | --- |
| [models/__init__.py](D:/FocusNest/backend/app/models/__init__.py) | `from app.models.task import Task` 并加入 `__all__`，使模型包包含 Task，集中导入模型时能够登记到 metadata |
| [api/v1/router.py](D:/FocusNest/backend/app/api/v1/router.py) | 导入 tasks 并执行 `api_router.include_router(tasks.router)`；只有定义端点而不注册，应用不会提供这些路径 |
| [main.py](D:/FocusNest/backend/app/main.py) | `private_response_headers()` 的匹配前缀加入 `/api/v1/tasks`，为任务列表和详情等响应设置 `Cache-Control: no-store` |
| [router/index.ts](D:/FocusNest/frontend/src/router/index.ts) | 增加 tasks 子路由，懒加载 TasksView；复用已有 beforeEach 登录守卫，未登录跳转登录页 |
| [AppLayout.vue](D:/FocusNest/frontend/src/layouts/AppLayout.vue) | 从待开发清单移除任务，添加指向 `/tasks` 的 RouterLink，页面显示在既有 RouterView 内 |
| [DashboardView.vue](D:/FocusNest/frontend/src/views/DashboardView.vue) | 更新为当前工作台文案，提供“安排值得投入的事”任务入口；没有实现完整统计 Dashboard |
| [api/client.ts](D:/FocusNest/frontend/src/api/client.ts) | `errorMessage()` 对 tasks 的 42200 显示任务输入规则，增加 40401 提示；原登录请求/响应拦截器继续复用 |

前端守卫提升使用体验，但用户数据隔离必须由后端查询条件保证；仅隐藏页面不能保护接口。

## 6. 按真实操作串起文件与函数

### 6.1 登录后打开任务页面

1. `AppLayout.vue` 的 RouterLink 跳转 `/tasks`。
2. `router/index.ts` 的已有 `beforeEach` 调用 `auth.initialize()`，确认登录状态，加载 TasksView。
3. `TasksView.vue` 的 watch 立即调用 `load()`。
4. `api/tasks.ts → listTasks()` 调用 `api/client.ts`，请求拦截器添加访问令牌的 Bearer 认证头。
5. 后端已注册的 `endpoints/tasks.py → list_tasks()` 接收请求。既有 `api/deps.py → get_current_user()` 通过认证服务取得用户，`get_db` 提供 Session。
6. `services/tasks.py → list_tasks()` 计算日期条件，调用 `repositories/tasks.py → list_owned()`。
7. MySQL 返回当前用户的任务；Service 组装 TaskPage，端点包成 ApiResponse。
8. 前端 unwrap 后返回给 load，更新 items、total，模板自动刷新。

`api/deps.py`、`services/auth.py`、`db/session.py`、`stores/auth.ts` 是此次复用的已有文件，不属于新增文件。

### 6.2 创建一条“学习 SQL”任务

```text
点击“新建任务”
→ TasksView.startCreate：打开空表单
→ 输入标题、预计 30 分钟，点击保存
→ TasksView.save：构造 TaskInput
→ api/tasks.createTask：POST /api/v1/tasks
→ FastAPI 解析身份和 TaskCreate 请求数据
→ endpoints.create_task
→ services.create_task：由登录身份确定 user_id、设置完成时间
→ repositories.add：Task(...) → add → flush
→ services.create_task：commit → refresh
→ endpoints：TaskRead.model_validate → ApiResponse
→ TasksView.save：关闭编辑器 → load 刷新列表
```

前端请求只包含任务输入，不能自行决定任务归属。写进 MySQL 后，页面刷新仍可通过查询取回，不是仅保存在浏览器变量中。

### 6.3 查看并修改任务

`TasksView.edit(task)` → `api.getTask(id)` → `endpoints.get_task` → `services.get_task` → `repositories.find_owned`，拿到最新详情填表。

保存时 `TasksView.save()` → `api.updateTask(id, input)` → `TaskUpdate` 校验 → `endpoints.update_task` → `services.update_task`。Service 再次核验归属，应用字段变化并提交；前端重新查询列表。读取详情和提交更新是两次请求，不能因为之前读过就省略更新时的权限检查。

### 6.4 完成与恢复待办

完成：`TasksView.toggle` → `api.completeTask` → `endpoints.complete_task` → `services.complete_task` → `services.update_task(status="done")` → 提交状态及完成时间。

恢复：`TasksView.toggle` → `api.updateTask(id, {status: 'todo'})` → `endpoints.update_task` → `services.update_task` → 清空完成时间并提交。前端再次 load 后显示最新状态。

### 6.5 删除任务

`requestDelete(task)` 只打开确认框。点击取消调用 `cancelDelete()`，不发 HTTP 删除请求。

确认后：`TasksView.remove` → `api.deleteTask` → `endpoints.delete_task` → `services.delete_task` → `get_task` 核验所属用户 → `repositories.remove` → Service commit → HTTP 200 → 前端关闭弹窗并 load。

当前是真删除，没有回收站。弹窗失败会保留错误信息，而不会假装删除成功。

## 7. 数据库/API 变化、验证和边界

数据库本次业务变化是新增 tasks 表及其外键、检查约束和索引，迁移版本为 0003_tasks；新增六个任务 API，均要求登录。字段错误通常为 HTTP 422，未登录为 401，不存在或他人任务统一为 404。

以下结果来源于 **2026-10-11 的实施记录，2026-10-12 本次文档工作没有重新运行测试**：

| 验证 | 已记录结果 |
| --- | --- |
| MySQL 后端测试 | 57 passed，包含认证回归及 21 项任务用例 |
| SQLite 后端测试 | 56 passed、1 skipped；跳过 MySQL 专属并发刷新用例 |
| Ruff / TypeScript / Vite 构建 | 通过 |
| Alembic upgrade / check | 通过，迁移至 0003_tasks |
| 浏览器操作 | 创建、编辑、完成、恢复、筛选、重新打开后保留任务已验证 |
| 删除确认框 | 打开、取消后保留任务已验证；未通过浏览器点击最终确认删除 |
| 真实删除请求 | 另经前端代理发送 HTTP 验证：删除成功、详情 404、列表为空 |

原测试记录有 Starlette/httpx、AnyIO 两条上游弃用提示。测试临时账号、任务、会话已在上次清理；不能将临时截图中的数据当成用户真实数据。

当前边界：今日任务不会自动排除 done，需配合状态筛选；计划和截止日期独立，不强制先后关系；尚无分组、重复任务、子任务、提醒、拖拽排序、批量操作、回收站或专注计时。

本次只补充解释文档。下一业务阶段为 Phase 3 Focus，本文不代表已经开始实现。

## 8. 建议的阅读顺序

先看第 6 节的一次创建流程，再按 `TasksView.vue → api/tasks.ts → endpoints/tasks.py → services/tasks.py → repositories/tasks.py → models/task.py` 打开源码。最后对照 `schemas/task.py` 理解数据校验，阅读迁移文件和测试文件理解“表怎么建立”“规则如何验证”。

学习时始终区分三个动作：前端函数发请求、后端函数处理业务、数据库持久化数据。同名的前后端 createTask/create_task 并不是直接互相调用，中间经过了 HTTP。

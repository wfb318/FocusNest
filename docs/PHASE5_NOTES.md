# Phase 5 Notes：新增修改清单、代码流程与知识点

> 后续更新：同日追加文件夹功能，当前目录能力与迁移版本见 [文件夹补充说明](PHASE5_NOTE_FOLDERS.md)。下文保留初始 Notes 阶段记录。

工作日期：2026-10-30。范围：个人 Markdown 笔记；未进入 Phase 6 Documents。

## 1. 本次实际完成

- 创建、读取、修改、删除本人笔记。同一天可以创建多篇，允许同名，通过 UUID 区分。
- 标题必填，1–200 字符；正文必填，1–100000 字符，不能全为空白。
- Markdown 双栏预览、独立阅读模式；共用原有安全渲染器。
- 置顶及取消置顶：编辑页勾选后点击保存。列表先置顶，再按更新时间倒序、ID 倒序。
- 标题/正文关键词搜索、只看置顶、分页。列表不发送正文，打开单篇才读取全文。
- 用户隔离、编辑/删除版本检查、未保存修改提示、失败时保留输入。
- MySQL 新增 notes 表，已执行迁移到 `0007_notes`。

Folder 在项目书中属于未来支持。本次先完成可用的平铺笔记；没有文件夹、标签、附件、自动保存、版本历史、全文索引或 AI。

## 2. 文件清单

本次新增 **11 个代码/测试文件**，修改 **7 个已有代码文件**。未修改依赖文件。项目未使用 Git 差异作为清单来源，以下依据本次实际写入记录。

### 新增后端 8 个

| 文件 | 职责与主要对象 |
| --- | --- |
| [app/models/note.py](/D:/FocusNest/backend/app/models/note.py) | `Note`：描述 notes 表、字段、外键、组合索引 |
| [app/schemas/note.py](/D:/FocusNest/backend/app/schemas/note.py) | `NoteCreate` / `NoteUpdate`：输入校验；`NoteSummary` / `NoteRead` / `NotePage`：输出结构 |
| [app/repositories/notes.py](/D:/FocusNest/backend/app/repositories/notes.py) | `find_owned` 查本人单篇；`list_owned` 搜索、排序、分页 |
| [app/services/notes.py](/D:/FocusNest/backend/app/services/notes.py) | `owned`、`get_note`、`list_notes`、`persist`、`create`、`check_revision`、`update`、`delete_note` |
| [app/api/v1/endpoints/notes.py](/D:/FocusNest/backend/app/api/v1/endpoints/notes.py) | 五个 HTTP 接口，接收认证用户、数据库会话及参数 |
| [alembic/versions/0007_notes.py](/D:/FocusNest/backend/alembic/versions/0007_notes.py) | `upgrade` 创建表和索引；`downgrade` 删除该表（会丢笔记，不作为日常运行指令） |
| [tests/test_notes.py](/D:/FocusNest/backend/tests/test_notes.py) | 生命周期、用户隔离、校验、搜索、分页、置顶、长 Unicode 正文、未登录访问 |
| [tests/test_note_concurrency.py](/D:/FocusNest/backend/tests/test_note_concurrency.py) | 两个真实 MySQL 会话同时编辑，以及修改与删除竞争 |

### 新增前端 3 个

| 文件 | 职责 |
| --- | --- |
| [src/types/note.ts](/D:/FocusNest/frontend/src/types/note.ts) | 定义 `NoteInput`、`NoteSummary`、`Note`、`NotePage`、`NoteQuery`，帮助 TypeScript 检查字段 |
| [src/api/notes.ts](/D:/FocusNest/frontend/src/api/notes.ts) | `listNotes`、`getNote`、`createNote`、`updateNote`、`deleteNote`，封装 HTTP 请求 |
| [src/views/NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 编辑器、阅读模式、列表、搜索、分页、置顶、确认框及页面状态 |

### 修改已有代码 7 个

| 文件 | 修改内容与原因 |
| --- | --- |
| [backend/app/models/__init__.py](/D:/FocusNest/backend/app/models/__init__.py) | 导入并导出 `Note`，使表进入 SQLAlchemy 元数据，供迁移及测试发现 |
| [backend/app/api/v1/router.py](/D:/FocusNest/backend/app/api/v1/router.py) | 注册 `notes.router`，让应用能够接收笔记请求 |
| [backend/app/main.py](/D:/FocusNest/backend/app/main.py) | 私人响应的 `no-store` 范围增加 `/api/v1/notes` |
| [frontend/src/api/client.ts](/D:/FocusNest/frontend/src/api/client.ts) | 增加笔记输入、40404、40904 的中文提示 |
| [frontend/src/router/index.ts](/D:/FocusNest/frontend/src/router/index.ts) | 增加 `/notes` 路由，沿用登录守卫 |
| [frontend/src/layouts/AppLayout.vue](/D:/FocusNest/frontend/src/layouts/AppLayout.vue) | 笔记从“待开发”变为可点击导航 |
| [frontend/src/views/DashboardView.vue](/D:/FocusNest/frontend/src/views/DashboardView.vue) | 增加笔记快捷入口；尚未建设完整 Dashboard |

### 文档与复用项

- 新增本说明 `docs/PHASE5_NOTES.md`，同步副本到用户指定 Obsidian 目录。
- 更新 `README.md`、`PROJECT_SPEC.md` 的实施状态与入口，修正 README 中旧迁移版本和下一阶段文字。
- 修改前两份文档原样备份于 `docs/archive/2026-10-30-phase5/`。
- `frontend/src/utils/markdown.ts`、`frontend/tests/markdown.test.mjs` 直接复用，**没有修改**。
- 原认证、任务、专注、日记业务代码没有修改；之前提出的标题长度练习也没有实际改动。

## 3. 数据库与 API

notes 字段：

| 字段 | 用途 |
| --- | --- |
| id | UUID 主键，区分每篇笔记 |
| user_id | 所属用户，引用 users.id，删除用户时级联删除 |
| title | 最多 200 字符的标题 |
| content | Markdown 原文，MySQL 使用 MEDIUMTEXT |
| pinned | 布尔值，是否置顶 |
| revision | UUID 版本标识，每次更新重新生成 |
| created_at / updated_at | UTC 时间；MySQL DATETIME(6) 保留微秒 |

组合索引 `ix_notes_user_pinned_updated(user_id, pinned, updated_at, id)` 配合按用户筛选和列表排序。它不等于全文索引；正文 contains 搜索数据量大时仍有性能边界。

| 方法 | 路径（统一前缀 /api/v1） | 输入与结果 |
| --- | --- | --- |
| GET | /notes | page、page_size、q、pinned 可选；返回摘要分页 |
| POST | /notes | title、content、pinned（默认 false）；成功 201 |
| GET | /notes/{note_id} | 返回本人单篇全文 |
| PUT | /notes/{note_id} | title、content、pinned、expected_revision；成功 200 |
| DELETE | /notes/{note_id}?revision=... | 必须提供已读版本；成功 200 |

所有接口需要登录。资源不存在或不属于本人统一 404 / 40404；旧版本修改/删除返回 409 / 40904；输入问题返回 422 / 42200。响应使用已有 `{code,message,data}` 格式。

PUT 是完整内容更新：前端总是提交标题、正文、置顶值和版本。API 调用者省略 pinned 时按默认 false 处理，不是“保留原来的置顶状态”。没有 PATCH 接口。

## 4. 从点击到数据库：完整调用流程

### 4.1 创建笔记

1. `NotesView.vue`：`v-model` 把输入写入 `form`；`dirty` 比较输入与已保存状态。
2. 点击保存，`@submit.prevent="save"` 调用页面 `save()`。
3. `save()` 检查非空、设置 busy，尚无 saved 时调用 `api/notes.ts → createNote({...form})`。
4. 公共 `apiClient` 自动附带内存中的访问令牌，POST `/api/v1/notes`。
5. `endpoints/notes.py → create()`：`CurrentUser` 认证，`NoteCreate` 校验输入；用户 id 不从浏览器取。
6. `services/notes.py → create()`：构造 `Note(user_id=user.id, **payload.model_dump())`，`db.add(note)`。
7. `persist()`：`flush()` 发出 INSERT，生成的 id、revision、时间可以读取；`NoteRead.model_validate` 转成响应对象；`commit()` 提交。
8. 返回前端，`apply(note)` 更新 saved 和 form；清除脏状态；`loadList()` 重新加载列表。

### 4.2 搜索、打开、阅读

1. 页面挂载或点击查询 → `loadList()` → `listNotes(query)`。
2. 后端 `list_notes()` → repository `list_owned()`。
3. 查询始终带 user_id，按需叠加置顶和关键词条件；统计总数，查询摘要列并分页。
4. 页面显示摘要；点击某篇 → `openNote(id)`。
5. 有未保存内容时先等待 `mayDiscard()`；允许后调用 `getNote(id)`。
6. 后端 `get_note()` → `owned()` → `find_owned()`，核验本人资源。
7. 前端 `apply(note)`，进入阅读模式。此模式仅切换显示，没有额外保存动作。

### 4.3 编辑与置顶

1. 点击“编辑笔记”，修改 form；勾选置顶也只是修改 form。
2. 保存时已有 saved，调用 `updateNote(saved.id, {...form}, saved.revision)`。
3. 后端 `update()` 用 `owned(..., lock=True)` 读取并锁住该行。
4. `check_revision()` 对比数据库版本与 expected_revision。
5. 一致：更新内容、置顶、revision、updated_at，再 `persist()` 提交；不一致：返回 409。
6. 409 时前端只显示错误，不调用 apply，因此输入保留。用户可先复制，再重新载入。

例：A、B 都读到版本 r1；A 保存成功变为 r2；B 仍携带 r1 保存，被拒绝。数据库行锁让检查与写入处于同一事务中，避免两个请求同时检查通过。

### 4.4 删除

1. 页面打开确认框，取消只关闭弹窗。
2. 确认后 `remove()` → `deleteNote(id, revision)`。
3. 后端 `delete_note()`：锁定本人记录 → 检查版本 → `db.delete()` → commit。
4. 成功后清空编辑器并刷新列表；失败保留输入。没有回收站。

### 4.5 未保存保护

`mayDiscard()` 返回 Promise。弹窗中的两个按钮调用 `resolveDiscard(false/true)`，决定是否继续新建、切换笔记或离开路由。刷新/关闭页签由 `beforeunload` 请求浏览器提示，浏览器是否显示取决于其策略。

这不是自动备份。会话失效、退出登录、浏览器崩溃时仍可能失去草稿；退出时认证被清空后路由守卫允许去登录页。阅读模式里看到的也可能是未保存内容，页面会注明。

## 5. 本次值得掌握的知识

这些是本次实现中出现的知识，不代表都首次进入项目；行锁、版本校验、Markdown 安全等在前面阶段已使用。

### 5.1 独立资源 ID 与“每天一篇”的区别

Journal 用“用户 + 日期”限定唯一；Note 用 id 标识，没有日期唯一约束。创建走 POST 集合地址，编辑走 PUT 单篇地址。相同标题可以属于不同笔记。业务规则决定表约束和 API 形状。

### 5.2 三态布尔筛选

`pinned: bool | None` 有三种含义：True 只看置顶、False 只看未置顶、None 不限制。

```python
if pinned is not None:
    filters.append(Note.pinned == pinned)
```

不能写 `if pinned`，否则 False 会被当成“不筛选”。前端当前只提供“全部 / 只看置顶”，API 还支持 false。

### 5.3 稳定排序与分页

```python
query.order_by(Note.pinned.desc(), Note.updated_at.desc(), Note.id.desc())
```

先比较置顶，再比较更新时间，最后用唯一 id 打破时间相同的平局。`offset((page - 1) * page_size)` 跳过前面记录；`limit(page_size)` 限制条数。

这是偏移分页。查询期间有笔记更新或置顶，跨页内容仍可能移动；稳定的最后排序键不代表冻结整个列表快照。

### 5.4 悲观锁与乐观版本检查配合

`with_for_update()` 请求 MySQL 行锁，串行处理针对同一记录的写操作；revision 则判断浏览器读到的是否还是当前版本。锁在提交或回滚后释放，不会在用户整个编辑期间保持。

SQLite 测试不能证明 MySQL 行锁行为，所以增加两个独立数据库会话的并发测试。更新/更新、更新/删除均只能一方使用旧版本成功。

### 5.5 摘要与全文分开

`NoteSummary` 不含 content；`NoteRead` 才增加 content。Repository 的列表查询也只取摘要列，既减少数据库到后端传输，又减少后端到浏览器响应体。

### 5.6 搜索转义与参数化是两件事

`contains(q, autoescape=True)` 把 `%`、`_` 等作为普通搜索文字处理，避免变成 LIKE 通配符。SQLAlchemy 绑定参数负责避免直接拼接用户输入成 SQL；不要将 autoescape 等同于全部 SQL 注入防护。

### 5.7 数据库字段与输入规则

MEDIUMTEXT 的容量按字节，而接口上限按字符。中文和 emoji 比 ASCII 占更多 UTF-8 字节，因此正文不能仅凭“10 万字符”使用小容量 TEXT。新增长 Unicode 往返测试验证保存后内容不变。

`Field(strict=True)` 用于 pinned，JSON 的 true/false 合法，字符串 "true"、数字 1 不接受。输入校验不是数据库迁移，改 Field 不会改变 MySQL 表结构。

### 5.8 前端保存基线与请求先后顺序

`saved` 保存服务器最近确认的数据；`form` 保存正在编辑的草稿。`dirty` 比较二者。只有成功返回后才更新 saved，所以失败时不会假装“已保存”。

`requestId` 给列表请求编号；响应回来时仅接受最新编号，避免慢的旧搜索覆盖新的结果。`disposed` 防止卸载后的响应更新页面。这些检查不取消已经发送的网络请求。

`busy` 阻止同一页面重复点击提交，但不是服务器级幂等键。若创建已提交而响应丢失，重试 POST 仍可能新建重复笔记；可先查列表确认。

### 5.9 安全 Markdown 复用

共用 `utils/markdown.ts`：关闭 HTML、自动识别链接和图片渲染；显式链接使用 markdown-it 的协议检查，链接添加 noopener/noreferrer。`v-html` 只接收这条受限渲染流程的结果，不能直接接收用户原文。该模块不向 AI 发送笔记。

## 6. Python / SQLAlchemy 语法速查

| 写法 | 在本次代码中的意思 |
| --- | --- |
| `class NoteUpdate(NoteCreate)` | 类继承，保留创建时的字段和校验，额外要求 expected_revision |
| `Mapped[bool]` | SQLAlchemy 映射属性的类型声明，帮助工具理解字段类型 |
| `mapped_column(Boolean, default=False)` | 声明数据库布尔列和 ORM 插入默认值；不是数据库 server_default |
| `default=lambda: str(uuid4())` | 每次创建对象并插入时调用函数生成新 UUID；不能提前调用一次后复用同一个字符串 |
| `str \| None` | 值可以是字符串或 None |
| `*, lock=False` | 星号后的参数必须用名字传，例如 lock=True |
| `**payload.model_dump()` | 把校验模型转字典，再展开为函数关键字参数 |
| `where(*filters)` | 把条件列表展开为多个位置参数，这些条件按 AND 组合 |
| `or_(a, b)` | SQL 条件 OR，用于标题命中或正文命中 |
| `[NoteSummary.model_validate(item) for item in items]` | 列表推导式，把每条查询结果转为响应模型 |
| `@field_validator(...)` + `@classmethod` | 注册字段校验函数；cls 是类，value 是待校验值 |
| `Annotated[int, Query(ge=1)]` | 整数类型附加 FastAPI 参数限制，最小值为 1 |
| `ApiResponse[NoteRead]` | 泛型响应，data 的结构为 NoteRead |
| `flush()` / `commit()` | flush 将改动发给数据库但未最终提交；commit 提交事务 |
| `raise AppError(...)` | 中断当前业务，由公共异常处理转换成 HTTP 错误 |

正文校验只用 strip 判断是否全空白，返回原文，避免破坏 Markdown 的缩进代码和行尾空格；标题则返回 strip 后的值。

## 7. TypeScript / Vue 语法速查

| 写法 | 在本次代码中的意思 |
| --- | --- |
| `interface Note extends NoteSummary` | 继承摘要字段并增加正文；类型定义在编译阶段检查，不代替运行时后端校验 |
| `import type` | 只导入类型，不作为运行时对象使用 |
| `ref<Note \| null>(null)` | 响应式引用，开始没有已保存笔记；脚本里用 `.value` |
| `reactive({title:'', ...})` | 响应式表单对象，通过属性读写 |
| `computed(() => ...)` | 根据依赖计算 dirty、preview 或总页数，依赖变化时更新 |
| `saved.value?.title ?? ''` | `?.` 在对象为空时停止访问；`??` 只对 null/undefined 使用默认值 |
| `{ ...form }` | 展开对象生成本次请求的字段快照 |
| `async` / `await` | 等待网络或用户选择的 Promise，在得到结果后继续函数 |
| `Promise<boolean>` | 最终产生 true/false 的异步结果，用于放弃修改确认 |
| `condition ? a : b` | 三元表达式，例如已有笔记时更新，否则创建 |
| `void loadList()` | 调用异步函数但此处不等待；函数内部负责捕获错误 |
| `v-model` | 表单控件与响应式字段双向同步 |
| `v-if` / `v-else` | 切换阅读区域和编辑表单 |
| `:disabled="busy"` | 动态绑定 disabled 属性 |
| `@submit.prevent="save"` | 拦截表单原生提交刷新，调用 save |
| `v-for` + `:key="note.id"` | 循环渲染，并为每一项提供稳定身份 |
| `onMounted` / `onUnmounted` | 挂载时加载列表和注册事件；卸载时解除事件和失效旧响应 |
| `:deep(pre)` | 在 scoped CSS 中为 v-html 生成的内部代码块设置样式 |

## 8. 验证记录与实际边界

2026-10-30 实际执行：

- Ruff：全部通过；新增 Python 文件使用 Ruff 格式化。
- Alembic upgrade head、current、check：成功，当前 `0007_notes (head)`，无模型差异。
- MySQL 完整回归：**116 passed**，包括本次两个竞争测试。
- SQLite 完整回归：**111 passed / 5 skipped**；跳过的为 MySQL 专用并发测试。
- 前端 vue-tsc + Vite 生产构建通过；Markdown 测试 **3 passed**。
- 原有两条 Starlette/httpx 与 AnyIO 弃用提示仍存在，没有在本阶段调整依赖。
- 浏览器使用独立临时账号验证：登录、新建、置顶保存、编辑保存、刷新后恢复登录和读取笔记、阅读模式、Markdown 标题/列表/加粗/代码块、关键词+置顶筛选、离开路由时提示、继续编辑、删除弹窗打开与取消。检查时未记录到页面控制台 error。
- 实际删除通过 Vite 代理的 HTTP 请求验证，删除后列表为空。没有声称在浏览器点击了“确认删除”。
- 临时账号、会话、笔记已精确清理；未更改真实用户内容。
- 截图工具捕获失败，因此本次没有可交付页面截图；DOM 交互验收与 API 测试结果不受影响。窄屏视觉效果未单独验收。
- 受限执行环境曾阻止本机数据库连接，默认 SQLite 测试也无输出；停止该测试后，在正常授权执行环境重跑成功。

限制：没有自动保存、草稿恢复、文件夹、标签、历史版本、回收站；不会记住刷新前选中的笔记，刷新后从列表重新打开；前端 maxlength 按 UTF-16 单元计数，emoji 的可输入数量可能比后端字符上限更保守；没有新增依赖或后端异步改造。

## 9. 运行与下一阶段

本机数据库已迁移。若服务未运行，在两个 PowerShell 窗口分别执行：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd D:\FocusNest\frontend
npm run dev
```

打开 http://127.0.0.1:5173/notes，使用自己的账号登录；验收账号已清理。服务若已在运行，不要在相同端口重复启动。

下一阶段为 Phase 6 Documents，尚未开始，需用户继续授权。推荐代码阅读顺序：Schema → Model → Service → Repository → Endpoint → api/notes.ts → NotesView.vue；用上述创建流程把各文件联系起来。

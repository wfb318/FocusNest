# Phase 4 Journal：实施说明、新增修改清单与代码解释

实施与编写日期：2026-10-23。

本次需求：完成下一阶段，并形成新增、修改代码清单和解释。实际范围为 PROJECT_SPEC 的 Phase 4 Journal：每天的个人记录、每个用户每天一篇、Markdown 内容。Phase 5 Notes 尚未开始。

## 1. 已完成的功能

- 登录后通过侧栏“日记”或 `/journals` 打开日记页。
- “今天”按后端当前时间及用户 IANA 时区计算。可选择其他日期补记或提前记录，日期范围为 1000-01-01 至 9999-12-31。
- 同一用户、同一日期最多一篇；不同用户同一天互不影响。
- 标题可选，最多 200 字符；正文不能为空或全空白，最多 100000 字符。保留 Markdown 缩进和行尾空格。
- Markdown 编辑与实时预览，支持标题、列表、强调、引用、代码块、表格、链接；可插入每日回顾模板。
- 手动保存、读取、修改、确认删除；历史按日期倒序分页，支持日期区间和标题/正文关键词组合查询。
- 未保存时切换日期、页面内导航会提示；刷新/关闭窗口使用浏览器 beforeunload 提示。
- 使用 revision 防止多页面旧内容覆盖新内容。冲突时保留编辑框输入，并提示先复制保留，再重新载入。

边界：没有自动保存、离线草稿、附件上传、远程图片预览、版本历史、回收站、AI 或情绪统计。删除是永久删除。浏览器异常关闭、会话失效或退出账号时不能保证保存草稿；重要内容应先手动保存。已保存日记的日期不提供“移动”接口，切换日期是打开另一篇。

## 2. 完整文件清单

共 **13 个新增代码/测试文件、7 个修改代码文件**，另修改两个依赖文件和项目文档。清单根据本次实际操作整理，不是 Git diff 导出。

### 新增后端 8 个

| 文件（根目录 D:\FocusNest） | 作用 |
| --- | --- |
| backend/app/models/journal.py | 日记 ORM 模型，用户与日期唯一约束 |
| backend/app/schemas/journal.py | 创建/更新输入、详情、列表摘要及日期响应 |
| backend/app/repositories/journals.py | 用户锁、按日期查询、搜索和分页 |
| backend/app/services/journals.py | 时区日期、内容保存、版本冲突和删除规则 |
| backend/app/api/v1/endpoints/journals.py | 五个 HTTP 接口 |
| backend/alembic/versions/0006_journals.py | 创建 journals 表 |
| backend/tests/test_journals.py | 功能、权限、校验、时区、长正文和冲突测试 |
| backend/tests/test_journal_concurrency.py | 真实 MySQL 并发创建/修改测试 |

### 新增前端 5 个

| 文件 | 作用 |
| --- | --- |
| frontend/src/types/journal.ts | 日记相关 TypeScript 类型 |
| frontend/src/api/journals.ts | 封装读取、搜索、保存和删除请求 |
| frontend/src/utils/markdown.ts | Markdown 解析器配置与安全预览 |
| frontend/src/views/JournalView.vue | 编辑器、预览、历史列表和确认弹窗 |
| frontend/tests/markdown.test.mjs | Markdown 排版与安全测试 |

### 修改代码 7 个及依赖

| 文件 | 修改及原因 |
| --- | --- |
| backend/app/models/__init__.py | 导入并导出 Journal，登记数据库模型 |
| backend/app/api/v1/router.py | 注册 journals.router，使接口可访问 |
| backend/app/main.py | CORS 允许 PUT；日记响应添加 Cache-Control: no-store |
| frontend/src/router/index.ts | 新增 /journals，懒加载页面，复用登录守卫 |
| frontend/src/layouts/AppLayout.vue | 启用侧栏“日记”，移出待开发清单 |
| frontend/src/views/DashboardView.vue | 添加“记下今天”入口 |
| frontend/src/api/client.ts | 添加日记校验、40403 不存在、40903 版本冲突中文提示 |
| frontend/package.json | 加入 markdown-it、@types/markdown-it 和 npm test 命令 |
| frontend/package-lock.json | 锁定新增依赖版本与依赖树 |

另修改 README.md、PROJECT_SPEC.md 同步阶段进展；原文保存在 `docs/archive/2026-10-23-phase4/`。新增本文和 `docs/screenshots/phase4-journal.jpg`。截图是未保存测试草稿，不代表真实日记。构建缓存和 dist 不计入手写源码。

## 3. 数据库与接口契约

新增 `journals`，迁移版本 `0006_journals`，前置版本为 `0005_focus_timer_precision`。本机已执行升级，Alembic check 通过。

| 字段 | 含义 |
| --- | --- |
| id | UUID 主键 |
| user_id | 所属用户，外键关联 users.id，删除用户时级联删除 |
| entry_date | 日记所属日期，不是创建时间 |
| title | 可空字符串标题，API 默认空字符串，不接受 null |
| content | Markdown 原文；MySQL 使用 MEDIUMTEXT |
| revision | 每次保存更新的 UUID 版本标识 |
| created_at / updated_at | UTC 时间，MySQL DATETIME(6) 保留微秒 |

用户 ID 与日期的组合唯一键 `uq_journals_user_date` 保证一天一篇，也支持按用户、日期检索。使用 MEDIUMTEXT 是因为普通 TEXT 的字节容量不足以存储允许的十万字符中文正文。

所有接口要求登录，前缀 `/api/v1/journals`：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | /today | 返回用户时区的日期和该日 entry；没有记录时 entry=null |
| GET | 空后缀 | 查询列表，支持 page/page_size/start_date/end_date/q |
| GET | /{entry_date} | 读取指定日期；没有记录时 entry=null |
| PUT | /{entry_date} | 新建或更新；成功均返回 200 和完整详情 |
| DELETE | /{entry_date}?revision=... | 删除指定版本，成功 200、data=null |

PUT 提交 title、content、expected_revision。新建时 expected_revision=null；修改时必须提交读到的 revision。服务端版本不匹配、旧页面提交已删除记录，都返回 409/code 40903。删除不存在日记返回 404/code 40403。非法字段、日期或搜索范围返回 422/code 42200；未登录返回 401。

列表默认每页 10、最大 100，返回摘要不返回正文；搜索内容只查询当前用户范围。日期范围为包含起止日。关键词中的 `%` 和 `_` 作为普通字符匹配，不变成 SQL 通配符。空关键词不筛选。

## 4. 后端逐文件与关键语法

### models/journal.py

源码：[journal.py](D:/FocusNest/backend/app/models/journal.py)

`class Journal(Base)` 声明 ORM 模型，`__tablename__` 指定表名。`Mapped[str] = mapped_column(...)` 将 Python 属性映射为数据库列。

`UniqueConstraint("user_id", "entry_date", ...)` 限制两个字段的组合唯一。`default=lambda: str(uuid4())` 在创建对象写入时生成 UUID；revision 采用新的 UUID，因此删除后重建不会重新从数字 1 开始，旧页面不能误把重建的日记当成旧版本。

`Text().with_variant(MEDIUMTEXT(), "mysql")` 表示 MySQL 使用 MEDIUMTEXT，隔离测试中的其他数据库使用 Text。模型描述结构，实际建表由迁移完成。

### schemas/journal.py

源码：[journal.py](D:/FocusNest/backend/app/schemas/journal.py)

| 类/函数 | 作用 |
| --- | --- |
| JournalSave | 验证 title、content、expected_revision |
| clean_title | 清除标题两端空白 |
| nonblank_content | 拒绝全空白正文，但返回原文，不破坏 Markdown 格式 |
| JournalSummary | 列表摘要：ID、日期、标题、版本和时间 |
| JournalRead | 继承摘要，加上正文 |
| JournalDay | 日期与可空详情，用于打开尚未写的日期 |
| JournalPage | 摘要列表和分页数据 |
| serialize_time | 为 UTC 时间附加时区标记，输出 ISO 格式 |

`ConfigDict(extra="forbid")` 拒绝客户端塞入 user_id、revision、entry_date 等未声明字段。日期来自 URL，用户来自认证依赖。

`@field_validator` 告诉 Pydantic 调用字段校验方法；`@classmethod` 使方法的第一个参数是类 cls。`from_attributes=True` 允许从 ORM 对象或查询结果的属性构造响应。

### repositories/journals.py

源码：[journals.py](D:/FocusNest/backend/app/repositories/journals.py)

- `lock_user()`：用 SELECT FOR UPDATE 锁用户行。在当天还没有日记时也能锁住已有用户，避免两个创建请求同时通过检查。
- `find_day()`：始终同时限定 user_id 和 entry_date。lock=True 时使用锁定读取。
- `list_owned()`：添加日期、关键词条件，查询总数，再按日期倒序分页。SELECT 只取摘要字段，减少长正文传输。

`contains(q, autoescape=True)` 生成绑定参数的模糊查询，同时转义 LIKE 通配符。`or_()` 表示标题或正文任意一项匹配，其他日期/用户条件与之是 AND 关系。

`offset((page - 1) * page_size)` 跳过前面页的数据；`limit(page_size)` 限制本页数量。用户锁在事务提交/回滚后释放，不是永久锁住账号。

### services/journals.py

源码：[journals.py](D:/FocusNest/backend/app/services/journals.py)

| 函数 | 业务作用 |
| --- | --- |
| today(user) | UTC 当前时刻转换到用户时区后取日期 |
| valid_date(value) | 拒绝早于 1000 年的日期，匹配 MySQL 日期范围 |
| get_day(...) | 查自己的日记，返回日期和详情或空值 |
| list_entries(...) | 检查日期范围顺序，查询并转换分页摘要 |
| conflict() | 统一创建版本冲突异常 |
| save(...) | 处理新建、更新、版本检查和事务 |
| delete_entry(...) | 验证用户、日期和版本后删除 |

保存过程：先锁用户，再锁当天记录。不存在时仅允许 expected_revision=null；存在时要求 expected_revision 与记录 revision 相同。更新内容后换一个新 revision，并设置 updated_at。

`db.flush()` 将改动发给数据库，获得默认 ID/时间等数据；构造 JournalRead 后 `db.commit()` 提交。遇到数据库完整性冲突，rollback 并返回 409，避免暴露底层数据库细节。

例如两个页面都读到版本 A：页面一保存后生成版本 B；页面二携带 A 保存时，服务端发现 A≠B，返回冲突，不覆盖页面一。删除也检查版本，避免删掉别人刚在另一页面更新的内容。

### api/v1/endpoints/journals.py

源码：[journals.py](D:/FocusNest/backend/app/api/v1/endpoints/journals.py)

五个函数分别为 today、list_entries、get_day、save、delete_entry。路由只解析参数、调用 Service、包装 ApiResponse，业务不堆在接口层。

`@router.put("/{entry_date}")` 将保存函数注册为 PUT 接口；日期会被解析为 Python date。`Annotated[int, Query(ge=1)]` 给查询整数加最小值约束；分页大小另有限制。

`CurrentUser`、`DBSession` 复用已有依赖，自动提供经过认证的用户和数据库会话。`/today` 在日期路径之前注册，避免被当成日期解析。

### alembic/versions/0006_journals.py

源码：[0006_journals.py](D:/FocusNest/backend/alembic/versions/0006_journals.py)

`upgrade()` 使用 op.create_table、sa.Column、外键和组合唯一约束创建表；`downgrade()` 删除该表，属于会丢失数据的回退操作。

新环境在 backend 下执行 `.\.venv\Scripts\python.exe -m alembic upgrade head` 应用迁移。本机本次已经执行。仅修改模型文件不会直接更新 MySQL 表结构。

### 后端测试文件

源码：[test_journals.py](D:/FocusNest/backend/tests/test_journals.py)、[test_journal_concurrency.py](D:/FocusNest/backend/tests/test_journal_concurrency.py)

test_journals.py 的 account fixture 复用原认证测试环境，模拟登录用户。测试涵盖新建、读取、更新、删除、删除重建后的旧版本冲突、账号隔离、输入校验、中文与 emoji 长正文、分页、通配字符搜索、时区和未登录访问。monkeypatch 固定时钟，验证洛杉矶和 UTC 日期不同的情况。

并发测试使用两个独立 Session 和线程，Barrier 让请求同时开始。第一轮竞争创建，第二轮携同一版本竞争更新，两轮都只允许一个成功。它仅在 MySQL 执行，finally 精确清理自己创建的测试用户。

## 5. 前端逐文件解释

### types/journal.ts 与 api/journals.ts

源码：[类型](D:/FocusNest/frontend/src/types/journal.ts)、[请求](D:/FocusNest/frontend/src/api/journals.ts)

JournalSummary/Journal/JournalDay/JournalPage 对应后端返回结构；JournalInput 是保存输入；JournalQuery 是列表查询参数。

getJournal、todayJournal、listJournals、saveJournal、deleteJournal 对应五个接口。共享 apiClient 负责 API 前缀、认证头和登录刷新。data() 从 ApiResponse 取出业务数据；删除响应 data=null，不调用这个要求非空的函数。

### utils/markdown.ts 与 tests/markdown.test.mjs

源码：[渲染器](D:/FocusNest/frontend/src/utils/markdown.ts)、[安全测试](D:/FocusNest/frontend/tests/markdown.test.mjs)

markdown-it 解析原文。`html:false` 让原始 HTML 作为文本显示；`disable('image')` 禁止生成图片元素，避免日记预览触发远程请求。链接在新标签打开并带 noopener noreferrer，危险协议由解析器校验阻止。

页面的 v-html 只接收该配置渲染后的结果，不把日记原文直接当 HTML 插入。没有公式执行、脚本执行或 HTML 插件。

测试使用 Node 自带 test 模块，借助项目已有 TypeScript 编译器加载实际渲染函数，不新增测试框架。验证标题/列表/代码/强调、原始 HTML 转义、禁用图片、危险链接和普通链接属性。运行 `npm test`。

### views/JournalView.vue

源码：[JournalView.vue](D:/FocusNest/frontend/src/views/JournalView.vue)

| 变量 | 用途 |
| --- | --- |
| selectedDate | 实际已打开并用于保存的日期 |
| dateInput | 日期输入框内容；加载失败或取消切换时复原 |
| saved | 服务端最后读到/保存的完整日记与 revision |
| form | 当前编辑内容 |
| dirty | 比较 form 与 saved，判断是否未保存 |
| preview | 用 renderMarkdown 计算预览 HTML |
| ready/busy/loading | 编辑器就绪、请求操作中、历史加载中 |
| filters/page/total/records | 搜索条件与历史分页 |
| requestId/disposed | 忽略过期历史响应和页面卸载后的响应 |

| 函数 | 作用 |
| --- | --- |
| applyDay | 成功读取/保存后同步日期、saved 和编辑框 |
| mayDiscard | 有未保存内容时等待用户在 dialog 中选择 |
| resolveDiscard | 关闭弹窗并完成上面的 Promise |
| openDay | 先确认未保存内容，再读指定日期或今天；失败保留原编辑内容 |
| loadHistory | 查询摘要，防止旧请求覆盖新筛选，删除末页时调整页码 |
| save | 提交正文及 saved.revision；成功同步新版本，失败保留输入 |
| remove | 携带 revision 删除，成功清空当前表单并刷新列表 |
| search/changePage | 搜索回第一页/切页后加载历史 |
| beforeUnload | 对刷新、关窗请求浏览器提示 |
| closeDelete | 非操作中时允许关闭删除弹窗 |

`ref()` 管理单值，`reactive()` 管理表单，`computed()` 自动计算 dirty 和预览。`v-model` 实现输入绑定，`@submit.prevent` 阻止整页刷新，`fieldset :disabled="busy"` 避免保存请求过程中继续改变提交内容。

`onBeforeRouteLeave()` 等待 mayDiscard，用户选继续编辑则取消导航。`onUnmounted()` 清理事件与等待状态。模板仅在正文为空时允许插入，不覆盖已有输入。

## 6. 按实际操作串起调用链

### 打开今天

侧栏 RouterLink → router/index.ts 登录守卫 → JournalView.onMounted → openDay → todayJournal → endpoints.today → services.today 算用户日期 → services.get_day → repository.find_day → JournalDay → applyDay。

没有记录时返回 entry=null，显示空编辑器，不因打开页面自动创建空日记。

### 首次保存与修改

点击保存 → JournalView.save → api.saveJournal PUT → JournalSave 校验 → endpoints.save → services.save 锁用户/记录、核对版本 → Journal 模型写入 MySQL → commit → 返回新 revision → applyDay → loadHistory。

首次保存 expected_revision=null；再次修改使用最新 saved.revision。若其他页面已更改，返回 409，页面保留原输入。重新载入前应自行复制需要保留的内容，系统不自动合并正文。

### 查看历史与删除

输入日期范围/关键词 → search → listJournals → Service 校验范围 → Repository 查询自己的摘要 → 渲染列表。点击日期 → openDay，在存在草稿时先询问是否放弃。

点击删除只打开确认框；确认后 remove → deleteJournal → services.delete_entry 校验版本 → db.delete/commit → 清空编辑器并刷新列表。

## 7. 本次验证及清理结果

| 检查 | 实际结果 |
| --- | --- |
| MySQL 全量回归 | 95 passed，包含三个模块并发测试（认证刷新、专注、日记） |
| SQLite 隔离回归 | 92 passed、3 skipped；跳过真实 MySQL 并发用例 |
| Markdown 测试 | 3 passed |
| Ruff | 通过 |
| TypeScript + Vite | 生产构建通过 |
| Alembic upgrade/check | 通过，新增迁移 0006_journals |
| 浏览器 | 日记导航、Markdown 预览、离开提示、继续编辑、放弃草稿已验证 |
| 真实 HTTP（经 Vite 代理） | 独立临时账号创建、重读、更新、旧版本冲突、删除、列表恢复为空通过 |

浏览器已有用户登录，因此只使用未保存测试草稿检查界面，最后已清空，没有写入该用户日记。没有把浏览器“保存/删除按钮点击”记为已执行。临时 HTTP 测试账号、认证会话和日记已按唯一 ID 清理。原有 Starlette/httpx、AnyIO 两条弃用提示仍存在。

截图：`docs/screenshots/phase4-journal.jpg`。本说明和代码清单另存到指定 Obsidian 目录，不覆盖现有笔记和产品说明。

## 8. 下一阶段

下一业务阶段为 Phase 5 Notes。日记偏向按天记录，Notes 偏向长期知识与想法。本次不自动进入下一阶段。

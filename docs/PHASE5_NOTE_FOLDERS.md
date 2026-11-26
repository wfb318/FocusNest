# 笔记文件夹：新增修改清单与知识语法说明

日期：2026-10-30。属于 Phase 5 Notes 的追加开发，未开始 Phase 6。

## 1. 实现与使用

笔记页新增文件夹侧栏，支持根文件夹、嵌套子文件夹、展开/折叠、重命名，以及按文件夹查看笔记。

1. 点击“新建文件夹”，填写名称，选择上级目录；根目录表示创建顶层文件夹。
2. 先选择已有文件夹再新建时，默认把它作为上级，可以形成“学习 / Python / FastAPI”。
3. 点击分类后，列表显示该文件夹的直属笔记，不递归包含子文件夹。搜索、置顶和分页在当前分类范围内生效。
4. 编辑笔记时，通过“所属文件夹”下拉框移动笔记，点击保存才写入数据库；选择“未分类”可移出文件夹。
5. 选择文件夹后点击“新建笔记”，新草稿默认选用该文件夹。
6. 选择文件夹后可以重命名。同一层不允许同名，不同层允许同名。
7. 删除文件夹需要确认：直属笔记保留并移到未分类；含有子文件夹时拒绝删除，先处理子文件夹。

既有笔记全部保留，迁移时新字段为 NULL，显示为未分类。这里只实现应用内的分类目录，数据仍在 MySQL；不会在 D 盘为每个分类创建真实文件夹，也不会同步 Obsidian Vault。

当前没有拖拽、移动整个文件夹、批量移动笔记、目录导入导出。文件夹父节点创建后不修改，重命名接口不接受 parent_id，因此不会通过改父节点形成循环。

## 2. 新增文件：11 个代码/测试文件

| 文件 | 作用 |
| --- | --- |
| [backend/app/models/note_folder.py](/D:/FocusNest/backend/app/models/note_folder.py) | `NoteFolder` 模型：id、user_id、parent_id、name、revision |
| [backend/app/schemas/note_folder.py](/D:/FocusNest/backend/app/schemas/note_folder.py) | `FolderName`、`FolderCreate`、`FolderRename`、`FolderRead`，校验名称和版本 |
| [backend/app/repositories/note_folders.py](/D:/FocusNest/backend/app/repositories/note_folders.py) | 锁用户、查本人目录、查同级名称、判断子目录、查目录内笔记 |
| [backend/app/services/note_folders.py](/D:/FocusNest/backend/app/services/note_folders.py) | 文件夹创建、改名、删除、归属与版本检查 |
| [backend/app/api/v1/endpoints/note_folders.py](/D:/FocusNest/backend/app/api/v1/endpoints/note_folders.py) | 文件夹列表、创建、重命名、删除四个接口 |
| [backend/alembic/versions/0008_note_folders.py](/D:/FocusNest/backend/alembic/versions/0008_note_folders.py) | 创建目录表，为 notes 添加 folder_id、索引和外键 |
| [backend/tests/test_note_folders.py](/D:/FocusNest/backend/tests/test_note_folders.py) | 嵌套、改名、归类、保留笔记删除、权限、重名、非法名称测试 |
| [backend/tests/test_folder_concurrency.py](/D:/FocusNest/backend/tests/test_folder_concurrency.py) | 两个 MySQL 会话同时创建同名根文件夹，只允许一个成功 |
| [frontend/src/api/noteFolders.ts](/D:/FocusNest/frontend/src/api/noteFolders.ts) | `NoteFolder` 类型，以及四类目录请求 |
| [frontend/src/utils/folderTree.ts](/D:/FocusNest/frontend/src/utils/folderTree.ts) | `folderRows()` 把平铺目录数据转换为树形显示行、深度、完整路径、可见状态 |
| [frontend/tests/folderTree.test.mjs](/D:/FocusNest/frontend/tests/folderTree.test.mjs) | 折叠后代、路径和 2000 层迭代遍历测试 |

## 3. 修改文件：11 个代码文件及 1 个测试配置

| 文件 | 修改内容 |
| --- | --- |
| [backend/app/models/note.py](/D:/FocusNest/backend/app/models/note.py) | 增加 nullable folder_id，外键 SET NULL 与索引 |
| [backend/app/models/__init__.py](/D:/FocusNest/backend/app/models/__init__.py) | 注册 NoteFolder 到元数据加载入口 |
| [backend/app/schemas/note.py](/D:/FocusNest/backend/app/schemas/note.py) | 输入和响应增加 folder_id |
| [backend/app/repositories/notes.py](/D:/FocusNest/backend/app/repositories/notes.py) | 列表摘要包含 folder_id，支持指定文件夹或未分类筛选 |
| [backend/app/services/notes.py](/D:/FocusNest/backend/app/services/notes.py) | 写入先锁用户；验证目标目录归属；移动笔记；兼容旧客户端省略字段 |
| [backend/app/api/v1/endpoints/notes.py](/D:/FocusNest/backend/app/api/v1/endpoints/notes.py) | 列表接口增加 folder_id、unfiled 查询参数 |
| [backend/app/api/v1/router.py](/D:/FocusNest/backend/app/api/v1/router.py) | 注册文件夹路由 |
| [backend/app/main.py](/D:/FocusNest/backend/app/main.py) | 文件夹接口响应增加 no-store |
| [frontend/src/types/note.ts](/D:/FocusNest/frontend/src/types/note.ts) | 笔记、表单、列表查询类型增加目录字段 |
| [frontend/src/api/client.ts](/D:/FocusNest/frontend/src/api/client.ts) | 目录不存在、重名、版本冲突、含子目录与非法名称的中文提示 |
| [frontend/src/views/NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 目录树、筛选、管理弹窗、笔记归类、目录路径及响应式布局 |
| [frontend/package.json](/D:/FocusNest/frontend/package.json) | npm test 同时运行 Markdown 与目录树测试，没有新增依赖 |

另新增本说明，更新 README、PROJECT_SPEC 中当前迁移和功能状态。历史 Phase 5 说明仍保留，并添加指向本次补充的提示。Obsidian 产品说明原文不覆盖。

## 4. 数据库与 API 变化

迁移链新增 `0007_notes → 0008_note_folders`，已在本机 MySQL 应用。

`note_folders`：

- id：UUID 主键。
- user_id：用户外键，所有业务查询限定本人。
- parent_id：指向同表 id 的可空外键；NULL 表示根目录，RESTRICT 防止直接删除仍有子节点的目录。
- name：最多 100 字符，去除首尾空白，不能全空白、仅为 `.`/`..`、包含 `/`、`\` 或低位控制字符。
- revision：改名后更新的 UUID，用于识别过期请求。
- 索引 `(user_id, parent_id)` 支持按用户与上级目录查找。

`notes.folder_id` 是可空外键，ON DELETE SET NULL；已有记录保持 NULL。业务删除还会显式移出笔记并更新笔记版本，不能仅依靠数据库 SET NULL，因为外键动作不会自动更新业务 revision。

| 接口（前缀 /api/v1） | 作用 |
| --- | --- |
| GET /note-folders | 获取本人全部文件夹的平铺数组 |
| POST /note-folders | name、可选 parent_id；创建成功 201 |
| PATCH /note-folders/{id} | name、expected_revision；改名 |
| DELETE /note-folders/{id}?revision=... | 删除无子文件夹的目录，保留笔记 |
| GET /notes?folder_id=... | 只查该文件夹直属笔记 |
| GET /notes?unfiled=true | 只查未分类笔记 |
| POST /notes、PUT /notes/{id} | 支持 folder_id；null 表示未分类 |

folder_id 与 unfiled=true 同时提供返回 422。更新笔记省略 folder_id 时保留原分类；显式发送 null 时移到未分类，旧客户端因此不会意外移出笔记。

错误码：40405 目录不存在或不属于本人；40905 同级重名；40906 目录版本过期；40907 有子目录不能删除。原笔记 40904 仍用于笔记版本冲突。

## 5. 对应函数的代码流程

### 创建与重命名

`NotesView.showFolderDialog()` 准备表单 → `submitFolder()` → `api/noteFolders.createFolder()` 或 `renameFolder()` → 后端 Endpoint → Service。

Service 先 `lock_user()` 锁住用户行；创建时核验父目录归属；`unique_name()` 调用 Repository `sibling()` 检查同一 parent_id 下的名称；创建或改名后 flush、构造响应、commit。改名还会 `check_revision()`，成功后生成新 revision。

前端刷新目录，选择返回的文件夹，加载该分类笔记。目录加载失败单独显示 folderError，不清空笔记草稿。

### 树形显示

`refreshFolders()` 接收平铺数据 → computed `tree` 调用 `folderRows(folders, collapsed)`。

`folderRows()` 先用 Map 将记录按 parent_id 分组，再使用栈逐层遍历，产生每行的 folder、depth、path、hasChildren、visible。界面只渲染 visible 为真的行，但目录下拉框使用全部行，因此折叠不会让归类目标消失。

`toggleFolder()` 修改 Set 中的折叠节点 id，computed 自动更新。`chooseFolder()` 只改变列表筛选，不丢弃正在编辑的草稿。

### 移动笔记

表单选择 folder_id → `save()` → 原 `updateNote()` 将表单与 expected_revision 发给后端 → `notes.update()` 锁用户、锁笔记、检查笔记版本、确认目标目录属于本人，再修改 folder_id 并提交。

笔记保存后，如果不再属于当前筛选的文件夹，它会从该列表消失；编辑器仍保留已保存的笔记。

### 删除目录

`removeFolder()` → `deleteFolder()` → `note_folders.delete_folder()`。

后端锁用户 → 查本人目录并检查 revision → `has_children()` 阻止删除非叶子目录 → `contained_notes()` 锁住直属笔记 → 每篇设置 folder_id=None、新 revision 和 updated_at → flush → 删除目录 → commit。

笔记不会被删除，目录删除和笔记移出属于同一事务。当前打开的旧编辑器不会自动覆盖为新版本；页面保留草稿并提示重新载入，旧 revision 的保存被后端拒绝。

## 6. 本次知识点与语法

### 邻接表与自引用外键

树形结构不需要为每一级创建不同的表。每行只保存 parent_id，父子关系就能组成树：根目录的 parent_id 为 NULL，子目录记录父目录的 id。这种结构叫邻接表。显示完整路径需要沿着树累计名称。

### NULL 与省略字段的区别

```python
if "folder_id" in payload.model_fields_set:
    note.folder_id = payload.folder_id
```

`model_fields_set` 是 Pydantic 记录的“请求实际提供了哪些字段”。省略表示不修改；提供 null 表示主动清空。仅检查 `payload.folder_id is not None` 无法表达移出目录。

查询时 `Note.folder_id.is_(None)` 生成 SQL `IS NULL`，不是字符串比较，也不是 `= NULL`。

### 并发保护与统一锁顺序

同一用户的笔记和目录写操作先锁 users 行，再检查具体资源。这样“有人移动笔记，有人删除目标目录”能按顺序处理；同名目录创建也不能同时通过检查。

同级唯一性由 Service 在用户锁内查询保障，没有额外创建组合唯一约束。MySQL 的 NULL 在唯一约束中的行为，使 `(user_id,parent_id,name)` 不能直接保证根目录重名被拒绝。目录的名称比较沿用 MySQL utf8mb4_unicode_ci 排序规则，大小写/部分重音视为等价；SQLite 的默认比较可能不同，以 MySQL 为实际行为。

写事务中的目录查询使用 `with_for_update()` 做当前读取，避免 MySQL 可重复读的旧快照导致等待锁后仍看不到刚提交的同名目录。锁会在提交或回滚时释放。

这会串行化同一用户的短写事务，适合当前个人工作台规模；不应在持锁期间等待用户操作。

### Map、Set 与迭代遍历

```typescript
const children = new Map<string | null, NoteFolder[]>()
const visited = new Set<string>()
```

Map 将父 id 对应到子目录数组；Set 存放折叠状态或已访问 id，方便判断是否包含某项。

栈通过 `push()` 入栈、`pop()` 出栈，替代函数递归遍历。深层目录不会不断增加 JavaScript 函数调用栈。`reverse()` 保证后进先出的栈仍按期望顺序显示；先复制数组再反转，避免改动原数据。

`stack.pop()!` 的感叹号是 TypeScript 非空断言：while 已确认栈不为空，因此这里告诉类型检查器结果存在。它不是运行时校验。

### Vue 绑定对象值

```vue
<option :value="null">未分类</option>
```

冒号表示绑定 JavaScript null；如果写 `value="null"`，得到的是字符串 "null"，后端不会把它当空值。

computed 基于 folders 和 collapsed 自动重建树。`:class="{selected: ...}"` 条件高亮选中目录；`:style` 根据 depth 计算缩进；`:title` 显示完整路径。缩进最多按 8 层计算，仅限制视觉宽度，不限制真实层数。

### 原子事务与版本失效

目录删除不仅修改目录表，也修改所属笔记。一次 commit 让这些操作共同成功；如果中途出错，会话结束时回滚。更新笔记 revision 使之前打开的编辑器失效，避免把已移出的笔记无声移回旧目录。

## 7. 验证结果

实际执行：

- Alembic upgrade head 和 check 成功；已应用 `0008_note_folders`，模型无新增迁移差异。
- Ruff 检查通过。
- MySQL 完整回归 **127 passed**；之后新增的文件夹并发测试单独运行 **1 passed**。没有把两次运行描述成一次全量 128 项。
- SQLite 完整回归 **122 passed / 6 skipped**，跳过 MySQL 专用并发测试。
- 前端 TypeScript 检查、Vite 生产构建通过。
- npm test **5 passed**：原 3 项 Markdown 测试与 2 项目录树测试。
- 原有两条 Starlette/httpx、AnyIO 弃用提示仍存在。
- 后端与前端开发服务已启动，分别在 8000、5173。

本次浏览器打开页面被自动审批系统拒绝：审批服务用量已达上限，审批未完成，并非判定页面不安全。因此**没有完成浏览器点击验收、截图或窄屏视觉验收**，也没有绕过该限制。此前笔记模块的浏览器测试不能充当本次文件夹功能的浏览器测试。

## 8. 下一步与使用入口

打开 http://127.0.0.1:5173/notes。已有草稿先保存，再刷新以加载新界面。左侧创建文件夹，编辑笔记时选择“所属文件夹”并保存。

数据库无需手动重建。其他开发环境更新代码后执行 `python -m alembic upgrade head`，不要使用 downgrade 作为启动步骤。后续可以单独增加目录拖拽/移动和批量归类；本次未自动开展。

## 2026-11-01 列表布局追加

笔记列表、搜索、置顶筛选和分页已从编辑器下方移入左侧文件夹栏，展示当前文件夹直属笔记，当前打开项高亮。右侧正文容器限高并独立滚动；切换文档时使用不同的 Vue key 重建滚动容器，配合 nextTick 和 scrollTo 回到顶部，避免继承上一篇阅读位置。保留原有未保存确认。

本次仅修改 frontend/src/views/NotesView.vue，无数据库或 API 变更。浏览器实测长文容器约 438px、内部内容超过 37000px；滚到底部后从左侧切换另一篇，scrollTop 回到 0。实际只读取现有文档，没有修改或保存其内容。窄屏单栏与限高样式已实现，未单独进行手机视觉验收。截图：docs/screenshots/notes-sidebar-layout.png。

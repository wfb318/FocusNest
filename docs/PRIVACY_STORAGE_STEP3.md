# 隐私改造第三步：正式本地日记与工作台接入

实施日期：2026-11-05

状态：第三步代码已实现，完成下述自动化、真实磁盘及浏览器 OPFS 页面验证。真实用户文件夹的系统选择授权仍需在支持的桌面浏览器中复验。本次不实施第四步导入/迁移，也不开发云端加密。

## 1. 具体完成了什么

### 1.1 日记恢复正式编辑能力，内容写入本地文件

- 绑定目录后，可以按日期读取、新建、编辑、保存和删除正式日记。
- 保存位置固定为绑定根目录下的 `YYYY/MM/YYYY-MM-DD.md`，例如 `2026/11/2026-11-05.md`。年月目录按需创建，标题不能变成文件路径。
- 文件按第一步确定的 UTF-8 Markdown v1 格式保存：元信息包含日期、标题、时区、创建时间和修改时间，下面为原样保留的正文。
- 日期使用账号设置的时区；“今天”不依赖服务器或浏览器的默认时区。
- 保存完成后读回校验，通过后才显示成功；失败保留页面输入。
- 标题最多 200 个 Unicode 字符，正文非空白且最多 100000 个 Unicode 字符；Markdown 的缩进、尾部空格和换行保留。
- 删除是明确的独立操作，需要页面确认，会删除磁盘中的对应 `.md` 文件，不经过 FocusNest 回收站。版本不匹配时拒绝删除，不清理其他文件或空年月目录。

### 1.2 列表、搜索与预览全部在本地完成

- 按日期倒序列出本地日记，提供日期范围、标题/正文关键词及分页。
- 搜索词、日记标题、正文、文件版本和目录信息不发给后端。
- 使用原有安全 Markdown 渲染器：HTML 不执行，远程图片不自动加载。
- 恢复每日回顾模板按钮；模板只填入编辑框，不自动保存。
- 连接目录后收起冗长的存储说明，使编辑区域更靠前；设置页仍展示完整目录配置。

### 1.3 工作台从本地合并今日状态

- 服务器只返回普通任务、专注等工作台数据，不读取云端日记标题。
- 浏览器根据当前账号绑定的目录读取今天的本地文件，显示“已记录 / 尚未记录”。
- 未绑定、缺权限、文件无效或读盘失败分别显示未连接或暂不可读，不误报成“今天没写”。
- 本地标题只用于当前页面展示，不回传工作台 API。

### 1.4 后端真正关闭旧云端写入

- 当前阶段所有日记统一采用本地模式；日记云端加密尚未开放，因此不存在可写的云端日记模式。
- 原有日记 PUT、DELETE 路由现在统一拒绝，返回 HTTP 403 / `40321`；客户端自行伪造保存方式或历史访问标识也不能绕过。
- 日记服务层的 `save()`、`delete_entry()` 同样拒绝，防止未来内部调用意外继续写云端。
- PUT 不再声明日记正文的请求模型，拒绝旧客户端请求时不解析并回显草稿；全局异常响应继续不回显输入。旧客户端主动发送的正文仍会抵达 HTTP 服务，平台不能替旧客户端阻止网络传输，但不会把它写入日记表或回显。
- 旧数据保留在 `journals` 表中；没有迁移、加密、删除用户记录。

### 1.5 旧云端内容只能通过明确的历史入口读取

- 旧日记 GET 需要 `X-FocusNest-Journal-Access: legacy-migration`；没有或错误的标识返回 HTTP 403 / `40320`。
- 新版只读历史入口主动附加该标识；本地日记页面和本地工作台不调用云端日记 API。
- 标识表达读取历史记录的意图，不是授权凭证。后端仍要求登录，并按用户归属隔离数据。
- CORS 配置放行这一自定义请求头，避免前后端分域时历史只读入口无法使用。

## 2. 用户实际怎么使用

1. 使用支持目录访问 API 的浏览器打开日记页，在“目录绑定、权限与隐私说明”中选择日记文件夹并授权。
2. 页面载入账号时区下今天的文件。没有对应文件时显示“这一天尚未记录”。
3. 输入标题和 Markdown 正文，点击“保存本地日记”。成功后可到所选目录查看真实文件。
4. 通过日期切换和“回看本地记录”查看其他日期；外部编辑器修改后，可手动刷新目录或重新载入磁盘版本。
5. 未保存时离开页面、切换日期或退出登录会提醒；取消后保留输入。保存/放弃前不能更换或解绑目录，但允许恢复原目录权限。
6. 旧云端日记仍通过单独只读入口查看，迁移入口留到第四步。

本次只识别标准年月目录内的 FocusNest v1 日记。普通 Markdown、Obsidian 其他日记格式或放在别处的文件不会被自动当作正式日记导入；不做全盘扫描。

## 3. 从点击保存到落盘的完整流程

```text
JournalView.vue
  → LocalJournalEditor.vue：打开日期、保存前检查当前状态
  → useJournalStorage().local()：取得当前账号绑定的目录连接
  → createLocalJournalRepository()：读取旧文件、核对 expected_revision
  → serializeJournal()：校验日期/长度/时区并生成 Markdown v1
  → folder()：只访问或创建该日期对应的年、月目录
  → writeLocalFile()：权限、版本、暂存流、提交前检查、提交后读回
  → parseJournal()：将读回文件转为日记对象
  → 编辑器更新保存基线和列表
```

整个过程不经过 Axios、FastAPI 或 MySQL。页面只在明确打开旧云端记录时使用 `cloudJournalTransport`。

读取流程由同一个本地仓库的 `getDay()` / `today()` 完成。列表的 `list()` 只枚举四位年、两位月目录内的日期 Markdown 文件，逐篇解析后在本地筛选，不持久化额外正文索引。

## 4. 冲突、权限与账号保护

- 继续使用完整文件原始字节的 SHA-256 作为版本指纹。更新或删除必须与用户打开时的版本相符。
- `expected_revision = null` 仅用于不存在的新文件，不能覆盖已存在的原件。
- 文件被其他编辑器改写、删除，或文件格式不合法时停止操作。不会为了“保存成功”而覆盖未识别的普通 Markdown。
- 同源写入使用统一 Web Lock，读取旧版本、验证和提交处于同一个应用锁内；单文件写入复用第二步的独占流和读回校验。
- 外部程序不受网站锁管理，最终版本校验与提交之间仍存在极小竞态；不承诺操作系统级原子 compare-and-swap。
- 目录连接附带当前账号、操作代次和句柄身份检查。换账号、解绑、换目录或其他标签页刷新绑定后，旧连接失效。
- `bindingVersion` 区分真正更换目录和仅恢复权限：同一目录恢复权限时保留草稿并可重试；更换目录后禁止把旧草稿直接写入新目录，需用户先保留输入并重新载入。
- 编辑器卸载、退出或会话失效会清空当前内容及列表；工作台卡片独立处理迟到响应，不能恢复前一账号的标题。
- 草稿只在当前页面内存中，未添加本地持久化草稿缓存，也不自动上传。

列表保护边界：一次枚举最多 10000 个条目，单个日期范围最多处理 2000 篇日记；超过时要求使用专用目录或缩小日期范围。单文件读写上限仍为 1 MiB。遇到标准日期位置中的无效日记会提示错误，不静默覆盖或隐藏损坏文件。

## 5. 新增与修改文件清单

以下路径相对于项目根目录 `D:\FocusNest`。

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `frontend/src/services/journalMarkdown.ts` | 新增 | Markdown v1 编解码、真实日期/时区/时间戳及内容长度校验；使用受限 JSON 字面量元信息，不执行 YAML 标签 |
| `frontend/src/services/localJournalRepository.ts` | 新增 | 正式日记的日期目录、读取、保存、删除、列表、本地搜索与分页 |
| `frontend/src/components/LocalJournalEditor.vue` | 新增 | 编辑器、模板、预览、日期切换、历史列表、保存与删除提示、草稿保护 |
| `frontend/src/components/LocalJournalStatus.vue` | 新增 | 工作台今日状态与标题的本地读取与清理 |
| `frontend/src/services/journalDraftGuard.ts` | 新增 | 当前日记编辑器向退出登录流程提供未保存检查，卸载时释放 |
| `frontend/src/types/localJournal.ts` | 修改 | 子目录枚举/删除能力、连接上下文和目录绑定版本 |
| `frontend/src/services/localJournalStorage.ts` | 修改 | 增加受控 `connection()` 和绑定版本；保持第二步的基础文件保护 |
| `frontend/src/stores/journalStorage.ts` | 修改 | 增加 `local()`，根据有效连接创建本地日记仓库 |
| `frontend/src/types/journalStorage.ts` | 修改 | 增加 `ready` 状态与本地存储实现注入类型 |
| `frontend/src/services/journalStorage.ts` | 修改 | 可接受明确的本地实现，未绑定/未实现来源仍不向云端回退 |
| `frontend/src/views/JournalView.vue` | 修改 | 接入正式编辑器，将草稿状态传给目录设置；保留独立历史入口 |
| `frontend/src/components/JournalStorageSettings.vue` | 修改 | 更新日记已可编辑的说明，连接后折叠设置，传递目录操作锁定状态 |
| `frontend/src/components/LocalJournalDirectorySettings.vue` | 修改 | 草稿未处理时禁换目录/解绑，仍允许检查和恢复权限 |
| `frontend/src/layouts/AppLayout.vue` | 修改 | 退出登录前等待日记未保存确认 |
| `frontend/src/views/DashboardView.vue` | 修改 | 用本地日记状态组件替换过渡卡片 |
| `frontend/src/types/dashboard.ts` | 修改 | 明确服务器来源为 local、日记是否已写为未知 null |
| `frontend/src/api/journals.ts` | 修改 | 历史云端 GET 添加明确访问意图头 |
| `frontend/src/api/client.ts` | 修改 | 对 40320、40321 给出明确中文提示 |
| `backend/app/api/v1/endpoints/journals.py` | 修改 | 显式历史 GET；统一禁止旧 PUT/DELETE，不解析草稿请求体 |
| `backend/app/services/journals.py` | 修改 | 保留历史读取与过滤，内部云端写入/删除也拒绝；移除旧写入实现 |
| `backend/app/api/v1/endpoints/dashboard.py` | 修改 | 兼容参数默认不包含日记，服务层始终排除云端日记 |
| `backend/app/services/dashboard.py` | 修改 | 不调用云端日记查询，返回未知本地状态 |
| `backend/app/schemas/dashboard.py` | 修改 | `journal_source: local`、`journal_written: null` 的响应契约 |
| `backend/app/main.py` | 修改 | CORS 放行历史访问请求头 |
| `frontend/tests/helpers/loadTs.mjs` | 新增 | 测试中加载实际 TypeScript 服务及其依赖 |
| `frontend/tests/localJournals.test.mjs` | 新增 | 8 项格式、真实磁盘 CRUD/搜索、冲突、权限、账号、时区与退出保护测试 |
| `frontend/tests/browser/localJournals.html` | 新增 | 仅供隔离测试账号准备 OPFS 目录，用正常产品页面验收，不进入生产构建 |
| `frontend/package.json` | 修改 | 新测试加入现有命令，无新增依赖 |
| `backend/tests/test_journals.py` | 修改 | 将旧可写云端契约测试替换为显式读取、归属隔离、禁写、不回显及不改表数据的测试 |
| `backend/tests/test_journal_concurrency.py` | 修改 | 旧 MySQL 云端写入竞争测试改为并发写入全部拒绝，无数据库访问 |
| `backend/tests/test_dashboard.py` | 修改 | 即使 include_journal=true 也不能查询或返回旧日记；未知状态为 null |
| `docs/PRIVACY_STORAGE_STEP3.md` | 新增 | 本文：具体修改、调用流程、知识点和验证边界 |
| `docs/PRIVACY_STORAGE_PLAN.md`、`PROJECT_SPEC.md`、`README.md` | 修改 | 同步第三步完成情况与当前使用说明 |
| `docs/screenshots/privacy-storage-step3-editor.png` | 新增 | 正常日记页面的本地文件编辑及列表验收截图 |
| `docs/screenshots/privacy-storage-step3-dashboard.png` | 新增 | 工作台合并本地日记标题的截图 |

## 6. 数据库和 API 契约变化

数据库：无建表、改表、Alembic 新版本或用户数据迁移，版本仍为 `0013_note_problem_link`。`journals` 表仅保留历史数据供显式读取。

| API | 现在的行为 |
| --- | --- |
| `GET /api/v1/journals`、`/today`、`/{date}` | 登录并携带历史访问意图头才可读取，仍按账号隔离 |
| `PUT /api/v1/journals/{date}` | HTTP 403 / 40321，禁止云端写入 |
| `DELETE /api/v1/journals/{date}` | HTTP 403 / 40321，禁止删除历史数据；清理历史副本留待第四步的显式迁移流程 |
| `GET /api/v1/dashboard` | `journal_source="local"`、`journal_written=null`、`journal_title=null`，不查询旧日记 |

旧的 `include_journal` 参数仍可解析，以免旧请求报参数错误，但即使 true 也不再返回日记。这是有意收紧隐私契约，不保留旧客户端自动读写日记的行为。

## 7. 本次新增的知识与语法

- 存储适配器/仓库：同样的 `getDay/list/save/delete` 接口，底层可以是 HTTP 或本地目录；当前编辑器只拿到本地仓库。
- `for await...of`：枚举浏览器目录的异步迭代器，每次等待后检查账号上下文。
- `Pick<...>` 与接口组合：复用日记类型，不把原数据库 UUID 长度要求套在本地文件 SHA-256 版本上。
- `JSON.stringify / JSON.parse`：为固定格式的元信息编码字符串，安全表示引号、冒号、换行等；不使用能执行代码的 YAML 扩展。
- SHA-256 与 `expected_revision`：先读版本，再按版本写入；指纹提供冲突检查，不提供内容加密。
- `bindingVersion`、请求版本和连接闭包：同时处理账号变化、目录变化和异步迟到；一个布尔 loading 状态不足以隔离旧请求。
- `watch` 多个独立数据源：只在绑定版本或权限状态真正改变时处理，避免每次提示文字更新都使编辑连接失效。
- `onBeforeRouteLeave`、`beforeunload`、退出 guard：分别处理站内导航、关闭页面和显式退出登录。
- `null` 与 `false`：服务器不知道本地是否已写，应返回 null；false 只用于浏览器确认“该日文件不存在”。
- 访问意图头与鉴权不同：请求头只控制是否明确进入旧数据流程，不能替代账号和归属验证。

## 8. 验证结果与实际限制

已执行：

- 前端 `npm test`：62 项通过，其中本次新增 8 项。
- 前端 `npm run build`：类型检查与生产构建通过。
- 后端完整 `pytest -q`：181 项通过、9 项跳过；跳过项要求 MySQL 等独立条件。Ruff 检查通过。旧云端 CRUD 契约已关闭，因此旧相关测试被更新，测试数量不能直接与旧版本作增减对比。
- 真实磁盘适配器：创建年月文件、读回、更新、搜索、分页、删除、外部修改拒绝覆盖、未识别 Markdown 不覆盖。
- 原生浏览器 OPFS + 真实产品界面：新建并保存日记、刷新重开、列表与搜索、安全预览、未保存导航提醒、退出提醒、工作台本地标题、账号 B 未绑定且不显示账号 A 的标题。
- 保存、刷新和工作台显示这段验收的云端日记 API 请求为 0；最后主动查看历史列表产生 1 条只读 GET，没有日记写入/删除请求，也没有测试标题、正文、搜索词和目录名进入后端访问日志。
- 浏览器验收后，以只读方式检查隔离 SQLite，`journals` 行数为 0；页面已保存的日记没有进入服务器表。用户 MySQL 未连接或修改。
- 本次独立验收服务已停止，临时脚本、代理配置、隔离数据库和日志已清理；保留正式测试、开发验收页与截图。隔离站点 OPFS 中保留无真实私密信息的测试日记，不涉及用户文件。

限制：

- 真实用户文件夹的系统选择授权仍待支持的桌面浏览器人工复验；浏览器验收使用明确标注的 OPFS 测试目录，产品没有增加 OPFS 自动降级模式。
- 浏览器中没有执行不可撤销的删除按钮，删除与冲突路径通过真实临时磁盘测试验证。
- 未在真实用户目录中人为撤销授权或制造外部写入竞态；相关基础服务已有模拟测试，权限恢复时保留草稿的页面逻辑经过类型检查。
- 没有本次 MySQL 实例复验，没有部署服务器、云端加密、普通 Markdown 导入或历史迁移。
- 这是登录后网页的本地文件能力，不是已经实现可离线首次打开的 PWA 或独立桌面客户端。

下一步仍按原计划进行第四步导入与历史迁移，不自动执行，不自动上传或删除历史副本。

目录枚举和删除 API 的依据：[MDN values()](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemDirectoryHandle/values)、[MDN removeEntry()](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemDirectoryHandle/removeEntry)。这些 API 的使用不代表所有浏览器都支持真实用户目录授权。

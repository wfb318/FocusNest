# Phase 6 文档资料库：实施说明、代码清单与知识点

> 后续多格式能力已追加，当前支持与验证范围见 [PDF 与 Office 预览说明](DOCUMENT_FORMAT_PREVIEWS.md)。下文保留初版 Markdown/TXT 实施记录。

实施日期：2026-11-01。范围按 PROJECT_SPEC.md 的 Documents 规划：保存和阅读外部 Markdown/TXT 资料。下一业务阶段是 Phase 7 Dashboard，尚未开始。

## 1. 实际完成的功能

- 登录后在“文档”入口进入 `/documents`，上传 UTF-8 的 `.md`、`.markdown`、`.txt`。
- 上传即写入资料库，文件最大 512 KB，正文不超过 100000 Unicode 码点且不能全为空白。
- 左侧分页资料列表，按标题/原文件名关键词搜索、按 Markdown/TXT 筛选。
- 右侧限高阅读区：Markdown 安全预览与原文切换；TXT 按纯文本显示。
- 下载原始字节，保留 UTF-8 BOM、CRLF、行尾空格、原文件名。
- 重命名显示标题，保持原文件名及内容；版本检查拒绝旧页面改名或删除。
- 删除确认、用户归属检查、私人响应 no-store、下载 nosniff。
- 复用现有背景、玻璃面板、认证、响应和安全 Markdown 渲染。

文档资源独立存于 documents 表，与笔记导入不同：笔记导入先生成草稿，保存后可编辑；文档上传立即保存原件，阅读中不提供正文编辑。相同文件名或内容可多次上传，生成不同 id，没有去重或替换原件功能。

当前没有 PDF/Word、目录分类、附件图片加载、批量上传、全文搜索、OCR、AI/RAG、云对象存储或公开分享。搜索仅匹配标题与文件名，不搜索正文。

## 2. 新增与修改文件清单

新增 **11 个代码/测试文件**；修改 **8 个已有代码/依赖配置文件**。未依赖 Git diff，清单依据本次实际创建与编辑记录。

### 新增后端 8 个

| 文件 | 主要作用 |
| --- | --- |
| [app/models/document.py](/D:/FocusNest/backend/app/models/document.py) | Document ORM：元数据、原始字节、用户外键、版本、时间、约束与索引 |
| [app/schemas/document.py](/D:/FocusNest/backend/app/schemas/document.py) | DocumentRename、DocumentSummary、DocumentRead、DocumentPage |
| [app/repositories/documents.py](/D:/FocusNest/backend/app/repositories/documents.py) | find_owned、list_owned；本人查询、搜索、筛选、分页 |
| [app/services/documents.py](/D:/FocusNest/backend/app/services/documents.py) | validate_file、owned、read、upload、get_document、list_documents、check_revision、rename、delete_document |
| [app/api/v1/endpoints/documents.py](/D:/FocusNest/backend/app/api/v1/endpoints/documents.py) | 六个路由：上传、列表、详情、下载、改名、删除 |
| [alembic/versions/0009_documents.py](/D:/FocusNest/backend/alembic/versions/0009_documents.py) | documents 表、索引和检查约束的正式迁移 |
| [tests/test_documents.py](/D:/FocusNest/backend/tests/test_documents.py) | 生命周期、原件一致、权限、格式/编码/大小、列表与校验测试 |
| [tests/test_document_concurrency.py](/D:/FocusNest/backend/tests/test_document_concurrency.py) | MySQL 两会话改名/改名与改名/删除竞争测试 |

### 新增前端 3 个

| 文件 | 主要作用 |
| --- | --- |
| [src/types/document.ts](/D:/FocusNest/frontend/src/types/document.ts) | DocumentSummary、WorkspaceDocument、DocumentPage、DocumentQuery 类型 |
| [src/api/documents.ts](/D:/FocusNest/frontend/src/api/documents.ts) | listDocuments、getDocument、uploadDocument、renameDocument、deleteDocument、downloadDocument |
| [src/views/DocumentsView.vue](/D:/FocusNest/frontend/src/views/DocumentsView.vue) | 上传控件、列表、搜索、阅读、下载、改名和删除弹窗 |

### 修改代码与配置 8 个

| 文件 | 修改 |
| --- | --- |
| [backend/requirements.txt](/D:/FocusNest/backend/requirements.txt) | 加入 python-multipart>=0.0.20,<1；本机安装 0.0.33 |
| [backend/app/models/__init__.py](/D:/FocusNest/backend/app/models/__init__.py) | 注册 Document 到元数据入口 |
| [backend/app/api/v1/router.py](/D:/FocusNest/backend/app/api/v1/router.py) | 注册 documents.router |
| [backend/app/main.py](/D:/FocusNest/backend/app/main.py) | documents 响应加入 Cache-Control:no-store |
| [frontend/src/api/client.ts](/D:/FocusNest/frontend/src/api/client.ts) | 文档专用校验、大小、格式、404 和版本冲突中文提示 |
| [frontend/src/router/index.ts](/D:/FocusNest/frontend/src/router/index.ts) | 注册登录保护下的 /documents 页面 |
| [frontend/src/layouts/AppLayout.vue](/D:/FocusNest/frontend/src/layouts/AppLayout.vue) | 文档由“待开发”改为导航入口 |
| [frontend/src/views/DashboardView.vue](/D:/FocusNest/frontend/src/views/DashboardView.vue) | 追加资料库入口，尚未建设 Phase 7 的完整 Dashboard |

另更新 README、PROJECT_SPEC，新增本说明和 `docs/screenshots/phase6-documents.png` 空状态验收截图。修改前两份项目文档备份于 `docs/archive/2026-11-01-phase6/`，Obsidian 产品说明原文不覆盖。

未修改已有用户认证、Tasks、Focus、Journal、Notes 的业务处理；Markdown 渲染器和 10 项前端测试直接复用，没有新增前端依赖。

## 3. 数据库结构

迁移链追加 `0008_note_folders → 0009_documents`，本机已应用到 `0009_documents (head)`，Alembic check 无模型差异。

| 字段 | 类型与作用 |
| --- | --- |
| id | UUID 字符串主键，每份资料独立标识 |
| user_id | users.id 外键，按用户隔离；用户删除级联删除文档 |
| title | VARCHAR(200)，可修改的展示标题 |
| filename | VARCHAR(255)，上传原文件名的安全化末段，下载使用它 |
| kind | markdown 或 text，数据库有检查约束 |
| size_bytes | 原件字节数，约束 1–524288 |
| raw_content | 原始 bytes；MySQL 使用 MEDIUMBLOB，不是本地文件路径 |
| revision | 每次改名生成的新 UUID，修改和删除必须携带版本 |
| created_at / updated_at | UTC 时间；MySQL DATETIME(6) 保留微秒 |

索引 `(user_id, created_at, id)` 支持本人按上传时间分页。标题搜索 uses LIKE，因此没有全文索引能力。

原件保存在项目所连接的 MySQL 中，沿用既有数据库位置；本阶段未迁移 MySQL 数据目录。没有在工程目录生成上传文件树，也没有把用户文件名拼成磁盘路径。保存在数据库意味着备份数据库时也包含原件。

## 4. API 契约

统一前缀 `/api/v1`，所有接口需要当前账号认证。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | /documents | page>=1、page_size 1–100、q<=100、kind=markdown/text；返回摘要分页 |
| POST | /documents | multipart/form-data 的 file 字段；成功 201，返回详情 |
| GET | /documents/{id} | 返回摘要字段和解码后的 content |
| GET | /documents/{id}/download | 返回原件二进制，不套 ApiResponse JSON |
| PATCH | /documents/{id} | JSON title、expected_revision；只修改显示标题 |
| DELETE | /documents/{id}?revision=... | 当前版本匹配才删除，成功 200 |

普通接口使用 `{code,message,data}`。下载返回 application/octet-stream、attachment、nosniff；Content-Disposition 中用 UTF-8 filename* 支持中文文件名，ASCII 兼容回退名为 document.txt。

错误码：41301 超过 512 KB；41501 不支持扩展名；42206 文件名、正文、编码或字符数不合法；40406 不存在或不属于本人；40908 文档版本过期；普通参数/schema 错误仍用 42200。

同名上传不覆盖旧资料。文件名中的 `/` 和 `\` 按分隔符取末段，控制字符拒绝；百分号编码在文件名元数据中保持字面值，不解码成路径或控制字节。

## 5. 上传到数据库的完整过程

1. `DocumentsView.upload(event)` 取得选中的 File，重置控件，检查扩展名与字节数。
2. `api/documents.uploadDocument(file)` 创建 FormData，append('file', file)，POST /documents；浏览器自动生成 multipart 边界，代码不手写 Content-Type。
3. FastAPI 使用 python-multipart 解析文件；CurrentUser/DBSession 提供认证用户和数据库会话。
4. Endpoint 从 UploadFile 的 file 对象最多读取 512 KB+1 字节，将文件名和 bytes 交给 Service。
5. `validate_file()` 独立检查末段文件名、扩展名、大小、utf-8-sig 解码、非空、控制字符和 100000 字符上限。不能只依赖前端检查。
6. `upload()` 自动生成展示标题，构造 Document，将原始 bytes 存入 raw_content；db.flush 后构建响应，commit 提交。
7. 前端显示新文档，清除搜索过滤回到第一页并刷新列表，提示“已上传并保存”。

utf-8-sig 在阅读时移除 BOM，但保存的 raw_content 保留 BOM；因此预览适合阅读，下载能保持字节一致。

## 6. 列表、阅读、下载、修改的过程

### 列表与阅读

`loadList()` → listDocuments() → Endpoint → Service → Repository。Repository 只 SELECT 摘要列，不包含 raw_content 或正文，并始终过滤 user_id；关键词同时匹配展示标题或原文件名，autoescape=True 按字面搜索 % 与 _。

点击资料 → `open(id)` → getDocument() → owned() → find_owned() → read() 解码正文。单篇查询显式 undefer 原件，保证获取元数据和原件在同一次 SELECT 中完成。Markdown 调用现有 renderMarkdown，TXT 通过 Vue 插值放到 pre 中，不作为 HTML 注入。

listRequest 和 detailRequest 分别标识最新列表请求与最新详情请求，旧响应不覆盖新结果；disposed 防止卸载后响应继续更新界面。切换文档用 id 作为 key、nextTick 和 scrollTo 重置右侧滚动位置。

### 下载

`download()` → downloadDocument(id) → 下载路由 → owned() 核验归属 → Response(raw_content)。前端接收 Blob，创建临时 URL，使用带 download 文件名的 a 标签发起下载，稍后释放 URL。

异常路径的响应仍然是 JSON，但 Axios 设置了 responseType:'blob'。api 包装捕获异常后尝试读取 Blob 中的 JSON，让公共 errorMessage 能正确显示 404/认证等错误；不能把所有 Blob 都当下载成功。

### 重命名与删除

改名弹窗输入标题，PATCH 携带读取时的 revision；Service 用 SELECT FOR UPDATE 锁定本人记录，检查版本，修改 title、revision、updated_at，提交。原 filename、raw_content 不改。

删除弹窗确认后带 revision 发 DELETE，同样锁行并检查版本，再删除提交。两个旧页面同时改名，或一个改名、一个删除，旧版本只能一方成功。

资料库没有编辑正文，因此没有正文草稿离开提醒；写操作进行中暂阻止普通路由离开。强行刷新、关闭或会话失效仍可能中断客户端等待，已提交的上传也可能需要在列表里确认。

## 7. 本次知识点与语法

| 概念/写法 | 含义与本次作用 |
| --- | --- |
| File / UploadFile / bytes / Blob | 浏览器选中文件、服务端上传对象、Python 原始字节、浏览器下载数据 |
| FormData / multipart | 同一次请求携带文件名、类型和二进制文件内容；需要 multipart 解析依赖 |
| `Annotated[UploadFile, File()]` | FastAPI 将 file 字段作为上传文件接收 |
| 有界 read(MAX+1) | 不将文件内容无限读入业务内存，超过上限多读 1 字节便能识别；这不是整个 HTTP 请求的总流量限制 |
| `raw.decode('utf-8-sig')` | 严格读取 UTF-8，并在阅读文本中处理可选 BOM |
| MEDIUMBLOB 与 MEDIUMTEXT | 前者保存原始字节，后者存文本；本次需要精确保留下载原件，使用前者 |
| `deferred=True` / undefer | 标记大字段默认延迟加载；单篇查询显式包含原件，摘要查询只选择小字段 |
| `Literal['markdown','text']` | 限制类型参数为允许值，其他类型返回校验错误 |
| `quote(filename,safe='')` | 把中文和特殊字符编码后放入下载响应头，避免拼接原始换行等字符 |
| Content-Disposition attachment | 告诉浏览器按附件处理文件；filename* 传递 UTF-8 文件名 |
| nosniff | 告诉浏览器遵守声明类型，不猜测原件是否可作为活动内容执行 |
| `responseType:'blob'` | 下载响应按二进制接收，错误 JSON 也可能变成 Blob，需额外处理 |
| revision 与行锁 | 版本判断客户端是否过期，行锁让检查和写入处于同一事务 |
| `<pre>{{ content }}</pre>` | 保留文本换行与空白，Vue 自动转义 HTML |
| Markdown 安全预览 | 共用关闭 HTML、图片加载等能力的渲染器；显式链接仍可由用户点击打开 |
| 请求编号 / disposed | 解决晚返回旧请求、卸载后异步结果更新问题 |
| 改名标题与原文件名分离 | 展示名称属于可修改元数据，原文件名属于原件信息，下载保持原名 |

## 8. 实际验证记录

2026-11-01：

- 已安装 python-multipart 0.0.33，pip check 无依赖冲突。
- Ruff 检查通过；新增 Python 文件格式化。
- Alembic upgrade head、check、current 通过，当前 0009_documents。
- **MySQL 完整回归 147 passed**，包含文档改名/删除竞争与原有全部回归。
- **SQLite 完整回归 139 passed / 8 skipped**，跳过 MySQL 专用并发测试。
- 保留原有两条 Starlette/httpx、AnyIO 弃用提示，没有在本阶段做额外依赖升级。
- 前端类型检查与 Vite 生产构建通过；原有 10 项前端测试通过。
- 测试覆盖：中文、BOM、CRLF 和空格的精确下载；同名独立上传；400000 字节 Unicode 原件；用户隔离；分页和转义搜索；错误格式/编码/大小；旧版本拒绝；文件名路径与控制字符处理。
- 独立临时账号经 Vite 代理真实 HTTP 验证上传、读取、字节一致下载、改名、搜索、旧版本 409、删除、空列表。临时账号、资料、会话已精确清理。
- 浏览器只读验证登录后的新导航、资料库页面、搜索/类型控件、空状态与布局，未记录控制台 error。未改变用户原有账号或私人资料。
- **浏览器未完成上传成功、下载落盘、改名提交及确认删除按钮的逐项点击验收**。这些业务通过真实 HTTP 和自动测试验证，不能把它们写成已进行浏览器操作。
- 没有重新运行所有屏幕尺寸的视觉测试，窄屏样式存在但未单独截图验收。

首次测试中，大文件参数自动生成的超长用例名称导致 Windows 测试环境错误，已为用例提供简短 id。另核实 HTTP 客户端会把 multipart 文件名里的控制字节转义为字面 `%01`，相应测试区分客户端转义和服务端直接收到控制字符两种情况。修正后完整回归全部通过。

## 9. 当前边界

- 当前使用 MySQL 保存小型原件，限制单文件 512 KB；没有账号总容量配额、上传限速、病毒扫描、独立对象存储。
- UploadFile 在 multipart 解析阶段可能已接收或暂存较大请求，有界读取只限制业务读取。公开部署仍需统一的请求体大小和并发/上传治理；不能声称本次已完成部署加固。
- 上传没有幂等键。服务器已经保存但响应丢失时，重试可能产生重复资料，可先查列表确认。
- 不提供修改原文、文件替换、历史版本、文件夹、正文搜索、PDF/Word、AI 和资料间链接重写。
- 删除不可从产品内恢复，确认前可下载原件。

## 10. 运行

本机已更新依赖与数据库，后端已重启加载接口。其他环境需执行：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd D:\FocusNest\frontend
npm run dev
```

已有服务不必重复启动相同端口。访问 http://127.0.0.1:5173/documents ，上传会立即保存，请使用希望保留在资料库中的文件。

下一阶段是 Phase 7 Dashboard，需要明确指令后继续。

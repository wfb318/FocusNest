# PDF、Word、PPT、Excel 文档预览扩展

日期：2026-11-01。扩展现有 Phase 6 资料库，未开始新业务阶段。

## 支持范围

| 文件 | 当前浏览方式 | 边界 |
| --- | --- | --- |
| PDF `.pdf` | 按页生成图片，上一页/下一页浏览，保留原页视觉布局 | 最多 300 页；不执行 PDF 脚本；页面图片不提供文字选择、全文搜索或可点击链接 |
| Word `.docx` | 正文段落、表格，选择文档部分 | 不保证原版式；当前正文段落与表格分区展示，不保证段落与表格的交错顺序；图片/页眉页脚等不显示 |
| PPT `.pptx` | 按幻灯片选择，展示文字与表格 | 不还原动画、图形布局、图片和图表 |
| Excel `.xlsx`、`.xls` | 按工作表选择，展示单元格表格 | 不执行公式或宏；XLSX 读取缓存值，缓存为空可能显示空白；XLS 的日期/数字可能按底层值显示 |
| Markdown / TXT | 保持已有安全预览与原文阅读 | UTF-8，512 KB，正文最多 100000 字符 |

PDF/Office 最大 10 MB，原件仍以字节保存在 MySQL，下载保持原件。Office 的预览为可读内容，不是完整 Office 编辑器。旧 `.ppt`、`.doc` 暂不支持：本机没有 LibreOffice 转换程序，请先另存为 `.pptx`、`.docx` 或 PDF。没有使用第三方在线文档服务，不发送私人文件到外部预览站点。

## 文件清单

新增 4 个代码/测试文件：

- [backend/app/services/document_preview.py](/D:/FocusNest/backend/app/services/document_preview.py)：解析、限制、预览结构构造及 PDF 页图片生成。
- [backend/alembic/versions/0010_document_formats.py](/D:/FocusNest/backend/alembic/versions/0010_document_formats.py)：扩展类型和大小约束、增加 preview_data JSON 列。
- [backend/tests/test_document_formats.py](/D:/FocusNest/backend/tests/test_document_formats.py)：真实五种文件样例、分页权限、损坏/加密文件、Excel 截取与公式、XML/宏拒绝测试。
- [frontend/src/components/DocumentContent.vue](/D:/FocusNest/frontend/src/components/DocumentContent.vue)：PDF 图片翻页、Word/PPT/Excel 部分选择与表格呈现。

修改 11 个源代码/测试/依赖文件：

| 文件 | 修改 |
| --- | --- |
| [backend/app/models/document.py](/D:/FocusNest/backend/app/models/document.py) | 增加 preview_data JSON、扩充 kind 和最大字节约束 |
| [backend/app/schemas/document.py](/D:/FocusNest/backend/app/schemas/document.py) | DocumentKind、PreviewSection、DocumentPreview，详情增加 preview |
| [backend/app/services/documents.py](/D:/FocusNest/backend/app/services/documents.py) | 扩展格式与分级体积限制，上传提取并保存预览，二进制类型不再按 UTF-8 直接解码 |
| [backend/app/api/v1/endpoints/documents.py](/D:/FocusNest/backend/app/api/v1/endpoints/documents.py) | 扩展筛选类型、新增 PDF 页图片接口 |
| [backend/tests/test_documents.py](/D:/FocusNest/backend/tests/test_documents.py) | 更新格式已支持后的旧测试预期，保持其他回归 |
| [backend/requirements.txt](/D:/FocusNest/backend/requirements.txt) | 新增 PyMuPDF、python-docx、python-pptx、openpyxl、xlrd、defusedxml |
| [backend/requirements-dev.txt](/D:/FocusNest/backend/requirements-dev.txt) | xlwt 仅用于生成真实 XLS 测试样例 |
| [frontend/src/types/document.ts](/D:/FocusNest/frontend/src/types/document.ts) | 扩展类型联合及预览结构类型 |
| [frontend/src/api/documents.ts](/D:/FocusNest/frontend/src/api/documents.ts) | 抽取 binary() 共用 Blob 请求及错误解析，增加 getPdfPage() |
| [frontend/src/views/DocumentsView.vue](/D:/FocusNest/frontend/src/views/DocumentsView.vue) | 扩展上传文件、限制提示、筛选与格式标签，引入预览组件 |
| [frontend/src/api/client.ts](/D:/FocusNest/frontend/src/api/client.ts) | 新格式、体积与 42207 预览失败的中文提示 |

另更新 README、PROJECT_SPEC 和原 Phase 6 说明，新增本说明、资料库入口截图与组件验收截图。没有改动 Notes 导入功能；笔记导入仍只支持 Markdown/TXT。

## 数据库和接口

已应用迁移 `0009_documents → 0010_document_formats`：

- kind 增加 pdf、word、presentation、spreadsheet。
- 最大原件大小约束从 512 KB 扩为 10 MB；Service 继续限制文本文件最大 512 KB。
- 新增 nullable preview_data JSON。旧 Markdown/TXT 记录及原件保持不变。
- JSON 保存提取后的 sections、pages、truncated，上传时解析一次，后续详情读取缓存；PDF 图片按请求生成，不长期保存。
- 降级迁移会先检查是否还有新格式或大文件，存在则拒绝降级，防止丢失资料。

新增：`GET /api/v1/documents/{id}/preview?page=1`，仅 PDF 可用，返回 image/png。继续使用 CurrentUser 和本人资源校验，no-store 与 nosniff 生效。他人资料返回 404，不提供公共图片 URL。

详情仍返回原字段；文本 content 保持原用法，二进制 content 为空字符串，preview 返回结构化内容。下载 API 不变，所有格式均保留原件字节。

## 代码流程与知识点

### 上传与提取

文件 → 原 upload 路由 → validate_file 检查名称、格式和体积 → extract_preview 解析 → 保存原字节 + preview_data → 返回详情。

PDF 使用 PyMuPDF 检查文件头、密码和页数，预览请求加载指定页，将最长边控制到约 1400 像素，输出 PNG。前端用带认证的 Axios 请求得到 Blob，再创建本机 Blob URL 显示 img，不依赖浏览器 PDF 插件。该预览没有执行 PDF JavaScript、外部链接或 PDF 表单的浏览器上下文。

DOCX/PPTX/XLSX 本质是 ZIP/XML 包。check_archive 在解析前限制条目数（3000）、总解压尺寸（40 MB）、单条目（10 MB），拒绝加密条目、vbaProject、DOCTYPE 和 ENTITY。文件在内存中处理，不按包内路径解压到磁盘。

解析库分别负责 Word 段落/表格、PPT 幻灯片/组合形状文字与表格、Excel 工作表。openpyxl 使用 read_only=True、data_only=True、keep_links=False；xlrd 读取旧 XLS，不执行宏。

### 预览大小

PreviewBuilder 限制总文本约 100000 字符、单段/单元格 2000 字符，超过时标记 truncated。Word 最多 1000 段、30 个表格；PPT 最多 100 页；Excel 最多 20 张工作表。表格通常截取至 200 行、30 列，PPT 表格单次最多取 100 行。预览会注明截取，原件保持完整。

这避免大表格无限铺满页面，但不等于整个解析过程的进程级内存或耗时隔离。PDF/Office 复杂文件仍可能消耗较多资源；尚无解析任务队列、独立沙箱进程、全局容量和并发配额。

### 前端

- DocumentContent 接收 WorkspaceDocument，通过 kind 决定 PDF 或 Office 内容分支。
- PDF loadPage() 维护页码、加载状态、错误和请求序号；旧响应不覆盖新请求，卸载时失效并释放 Blob URL。
- Office 使用 select 切换当前 section，Vue 插值显示 paragraphs 与 rows；不会把 Office 提取结果当 HTML 注入。
- 数据类型 DocumentKind 使用 TypeScript 联合类型；DocumentPreview 明确 sections、pages、truncated。
- JSON 列与二进制原件分开：结构化预览容易供网页消费，原字节用于精确下载。
- `BytesIO(raw)` 把字节包装成库可读取的文件对象，`with` / finally 关闭文档和工作簿。
- `data_only=True` 读取工作簿已保存的计算缓存，不负责重新计算；新写入但未被 Excel 计算的公式可能没有值。

## 实际验证

2026-11-01：

- Ruff、pip check、Alembic upgrade/check 通过，current 为 0010_document_formats。
- 新格式与原文档模块初次定向测试 26 项通过；补充宽表截取校验后，新格式专项 11 项通过。
- 最终 MySQL 全量 **158 passed**；SQLite **150 passed / 8 skipped**。
- 前端类型检查与生产构建通过，原前端测试 10 项通过。
- 五种真实生成的样例分别验证上传、结构化预览/图片、原件精确下载；PDF 两页 PNG、越界页码、权限隔离、损坏/加密文件、旧 DOC/PPT 拒绝、Excel 截取、XML 外部实体与宏拒绝均有自动测试。
- 独立临时账号经 Vite 代理验证五种新格式的上传、预览数据、下载原字节，以及 PDF 第 2 页图片；临时账号、原件和会话已清理。
- 浏览器通过临时组件验收页，使用真实解析样例验证 Word 正文/表格切换、PPT 文字/表格、Excel 两个工作表切换；控制台未发现 error。提取的 `<script>` 内容作为文字显示。
- 临时组件验收页已删除；截图 `docs/screenshots/office-preview-component.png` 为生成的测试样例，不是私人文件；`docs/screenshots/document-formats.png` 为实际资料库格式入口。
- PDF 在页面内的 img 翻页按钮尚未单独浏览器点击验收；PDF 渲染和权限通过自动测试与真实 HTTP 验证。不能将组件 Office 测试写成完整资料库所有交互均已验收。
- 原有两条 Starlette/httpx、AnyIO 提示仍存在。官方包索引大文件下载停滞，改用清华 PyPI 镜像成功安装，未改写全局 pip 配置。

## 使用和下一步

保存草稿后刷新资料库，上传新格式即可。已有上传文件仍可正常读取；下载保留原件。图片型 PPT 或 Word 扫描图片目前可能没有可提取文字，推荐导出 PDF 后浏览原页。

如需旧 DOC/PPT 或 Office 排版完整还原，可后续单独配置 LibreOffice 转 PDF；本次没有安装该系统软件，也没有承诺将动画或电子表格交互完整搬到网页。

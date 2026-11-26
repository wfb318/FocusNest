# 隐私改造第一步：存储契约与模式入口

实施日期：2026-11-05

状态：第一步已实现并完成下述验证。本地目录读写、导入迁移、服务器内容加密仍未实现。

## 1. 这次页面行为有什么变化

- 设置页和日记页新增“日记隐私与存储”，区分仅本地、云端加密、普通云端历史记录三种状态。
- 日记默认来源为 `local`，但当前处于 `unbound`。目录读写尚未实现，所以暂不能新建或保存日记；不会继续使用旧云端接口替用户保存。
- 进入日记页不会自动请求某天日记或历史列表。只有用户点击“查看历史云端日记（只读）”才读取旧记录；选择一篇后才读取正文。
- 尚未主动查看时显示“历史记录尚未检查”；读取后根据实际数量显示“待迁移”或“没有历史云端日记”，不猜测旧账号一定有数据。
- 关闭历史查看、离开页面或切换账号会清理已加载内容，并拒绝旧请求的迟到结果。
- 新版工作台不再获取旧日记标题，显示“目录未接入”，不把未知本地状态当作“今天未写”。

普通笔记、任务、日程、计时与文档保持现有保存方式。本次没有启用任何内容加密，也没有迁移或删除用户数据。

## 2. 存储接口与默认值

`frontend/src/types/journalStorage.ts` 定义公共接口，避免页面直接依赖某种保存位置：

| 成员 | 职责 |
| --- | --- |
| `StorageMode` | `cloud` 普通云端、`cloud_encrypted` 云端加密、`local` 本地 |
| `JournalStorageOperations.getDay(date)` | 读取某个日期 |
| `today()` | 根据当前存储来源的日期规则读取今天 |
| `list(query)` | 列出日记，支持日期、分页及后续的本地搜索 |
| `save(date, input)` | 新建或更新，使用 `expected_revision` 防止覆盖 |
| `delete(date, revision)` | 校验版本后删除 |
| `mode / availability / writable` | 明确来源、可用状态和是否允许写入 |

`DEFAULT_JOURNAL_STORAGE_MODE = 'local'`，其他普通业务仍为 `cloud`。本次所有账号使用统一的日记默认值，不持久化任何目录、路径、日记内容或伪造的“已绑定”状态，不新增账号设置表。

`createJournalStorage()` 是存储策略入口：

1. 本地未绑定：全部操作抛出 `LOCAL_DIRECTORY_UNBOUND`，不会调用云端。
2. 云端加密尚未实现：全部操作抛出 `CLOUD_ENCRYPTION_UNAVAILABLE`，不会降级为明文云端。
3. 普通云端：只有调用方明确指定 `purpose: 'legacy-migration'`，并提供账号/页面生命周期检查 `isCurrent()`，才开放只读查询。
4. 历史云端的 `save()`、`delete()` 始终拒绝，错误码 `LEGACY_READ_ONLY`。
5. 历史读取在请求前、成功后、失败后检查上下文，账号或页面改变则抛出 `SESSION_CHANGED`，不向新页面返回旧正文或旧错误。

`cloudJournalTransport` 只封装 HTTP；原来的 GET/PUT/DELETE 请求实现被保留。当前页面通过存储策略调用它，不直接使用可写 HTTP 函数。

**边界：前端策略不是后端权限机制。**旧日记 API 和旧客户端的后端写入能力本次尚未关闭；第三步还需要服务端模式约束。本次没有声称“所有客户端都不能向服务器写日记”。

## 3. 本地 Markdown 文件契约 v1

本节定稿后续本地实现的输入输出约定；本次未实现序列化、解析、读写或导入器。

### 3.1 路径与内容格式

- 相对于当前账号绑定的根目录，新建路径固定为 `YYYY/MM/YYYY-MM-DD.md`，例如 `2026/11/2026-11-05.md`。
- 日期范围与现有日记一致：`1000-01-01` 至 `9999-12-31`；一天一篇。不能用标题拼文件路径。
- UTF-8 编码，新建文件不带 BOM，换行使用 LF；导入时允许 UTF-8 BOM 和 CRLF，正文不随意 trim、截断或重新排版。
- 标题可为空，最多 200 个 Unicode 码点；正文非空白，最多 100000 个 Unicode 码点，与现有业务限制对齐。
- 文件使用标准 YAML front matter；平台生成的字符串用 JSON 字符串转义规则编码为 YAML 双引号字符串。后续解析使用受限、安全的解析方式，不执行 YAML 自定义标签或代码。

示例（仅格式示例，不是已保存的用户日记）：

```markdown
---
focusnest_journal_version: 1
entry_date: "2026-11-05"
title: "今天的记录"
timezone: "Asia/Shanghai"
created_at: "2026-11-05T02:00:00+00:00"
updated_at: "2026-11-05T02:00:00+00:00"
---

## 今天完成了什么

在这里写正文。
```

- `entry_date` 是日记日期，`timezone` 是记录时的 IANA 时区；时间戳为带时区的 ISO 8601。缺省日期使用账号时区计算，不能默认使用服务器所在时区。
- 本地读取结果继续适配现有 `JournalDay / Journal / JournalPage` 形状。`id` 可使用本地稳定标识，不需要伪造数据库记录。
- 本地 `revision` 计划使用完整文件原始字节的 SHA-256；`expected_revision = null` 只允许创建不存在的目标文件。已有文件必须读回并核对版本，冲突时不覆盖。此哈希用于版本检测，不是文件加密。

### 3.2 导入规则

1. 首批仅接收 UTF-8 `.md` 文件；不通过后端上传解析，不改动用户选中的原文件。
2. 日期依次取有效的 FocusNest 元信息、严格的 `YYYY-MM-DD.md` 文件名；都没有时交给用户指定，不能用今天替代。
3. 若元信息日期、日期文件名或目标同日文件发生冲突，列出问题并等待用户选择，不静默覆盖。
4. 无平台元信息的普通 Markdown 默认标题为空、全文作为正文，允许导入时补标题；缺失的创建/更新时间在导入时生成。未知平台格式版本和无效元信息进入待处理清单，不假装已成功导入。
5. 导入前展示解析日期与目标；批量操作逐文件报告结果。写入后读回校验，不能仅凭下载或写入调用成功就宣布迁移完成。
6. 附件、已有目录批量扫描和其他编码不在第一步开放；后续接入时不得走云端附件上传路径。

## 4. 浏览器能力与未授权行为

`directoryCapability()` 仅检查安全上下文和 `showDirectoryPicker` 是否存在，不调用目录选择器，不请求授权，不读取浏览器内部缓存或磁盘。

- `supported`：浏览器具备基础 API，页面仍明确提示本次没有授权或绑定。
- `insecure`：安全上下文不满足；正式部署使用 HTTPS，本地开发按实际浏览器行为验证。
- `unsupported`：提示不支持目录绑定；手动导入/导出的降级路径留到后续步骤实现。

缺少权限或功能时停止当前来源的操作，绝不自动把日记上传服务器。API 能力检测不等于已完成目录可写测试。[MDN 目录选择说明](https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker)。

## 5. 新增与修改的文件

下列为实际文件；路径相对于项目根目录 `D:\FocusNest`。

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `frontend/src/types/journalStorage.ts` | 新增 | 存储来源、操作接口、状态及历史访问上下文契约 |
| `frontend/src/services/journalStorage.ts` | 新增 | 默认来源、未实现来源拒绝、只读策略、上下文检查及浏览器能力检测 |
| `frontend/src/components/JournalStorageSettings.vue` | 新增 | 设置页与日记页共用的来源状态、能力说明和后续目录入口 |
| `frontend/src/components/LegacyJournalPreview.vue` | 新增 | 主动打开后的历史列表、分页与只读 Markdown 预览；清理账号状态 |
| `frontend/src/api/journals.ts` | 修改 | 将原有请求封装为云端传输适配器，不再逐个导出页面可直接调用的读写函数 |
| `frontend/src/views/JournalView.vue` | 修改 | 替换默认自动加载的云端编辑器，显示本地过渡状态和显式历史入口 |
| `frontend/src/views/SettingsView.vue` | 修改 | 加入共用存储入口 |
| `frontend/src/api/dashboard.ts` | 修改 | 请求工作台时显式传 `include_journal=false` |
| `frontend/src/views/DashboardView.vue` | 修改 | 日记卡片显示未连接状态，不使用旧云端标题判断本地日记 |
| `backend/app/api/v1/endpoints/dashboard.py` | 修改 | 工作台增加可选查询参数 `include_journal` |
| `backend/app/services/dashboard.py` | 修改 | 参数为 false 时不调用旧日记标题查询 |
| `frontend/tests/journalStorage.test.mjs` | 新增 | 9 项来源、只读、无回退、迟到响应、能力检测及工作台参数测试 |
| `frontend/package.json` | 修改 | 把新测试加入现有测试命令；没有新增依赖 |
| `backend/tests/test_dashboard.py` | 修改 | 验证不查询旧日记且响应不含标题，并检查未登录拒绝 |
| `docs/PRIVACY_STORAGE_STEP1.md` | 新增 | 本文：行为、格式契约、文件清单与验证边界 |
| `docs/PRIVACY_STORAGE_PLAN.md` | 修改 | 更新第一步进度，其他步骤保留待办 |
| `PROJECT_SPEC.md`、`README.md` | 修改 | 标记隐私改造第一步及日记当前的使用限制 |
| `docs/screenshots/privacy-storage-step1.png` | 新增 | 隔离测试账号下的真实页面截图，不含用户日记 |

本次不修改 `frontend/src/types/journal.ts`，继续复用其已有的日记业务类型；不修改用户目录中的原有日记文件。

## 6. 数据库与 API 变化

- 没有建表、改表、Alembic 新迁移或用户数据迁移；当前数据库版本仍为 `0013_note_problem_link`。
- `GET /api/v1/dashboard` 增加 `include_journal: bool = true`。旧客户端省略参数时保留原行为；新版前端传 false，后端直接跳过旧日记查询，返回 `journal_title: null` 和 `journal_written: false`。
- false 返回值表示该请求未包含云端日记信息，新版页面不会将它解释为“本地今天未写”。正式本地状态合并留在第三步。
- 原日记 GET/PUT/DELETE API 未改变。本次只读保证作用于新版前端和存储策略，后端禁写与正式迁移入口是后续工作。

## 7. 新增知识与语法

- `type A = 'local' | 'cloud' | ...`：联合类型，限制程序允许表达的来源；它不会自动实现加密或读取磁盘。
- `interface`：规定每种存储实现必须提供的函数。页面后续可以换实现，而无需自行区分 SQL、HTTP 或文件系统。
- 工厂函数 `createJournalStorage()`：集中创建当前来源的操作对象，把“不能回退”放在同一个边界里。
- `readonly`：TypeScript 的只读提示，不是安全权限控制；实际拒绝写入仍依靠 `denyWrite()`。
- `Promise<T>` 和 `async/await`：等待网络或未来文件 I/O；`read<T>()` 用泛型保留不同读取操作的返回类型。
- `purpose`：显式说明历史访问意图，不是授权 Token；真正的用户访问权限仍由后端鉴权与归属检查负责。
- `isCurrent()` 与请求版本：在异步结果返回后再次判断账号/页面是否还有效，避免退出后旧内容重新出现。
- `watch(..., { flush: 'sync' })`：在账号变化时立即清理历史内容；页面卸载时也执行清理。
- `v-if`：历史组件只在用户点击后创建，所以其 `onMounted()` 不会在日记默认入口执行。
- Markdown front matter：位于文件开头的可读元信息；SHA-256 版本指纹用来检测外部修改，不提供保密性。

## 8. 验证结果及限制

已执行：

- 前端 `npm test`：38 项通过，其中新增 9 项。
- 前端 `npm run build`：类型检查和 Vite 生产构建通过。
- 后端 `pytest tests/test_dashboard.py tests/test_journals.py -q`：23 项通过，使用默认隔离 SQLite 事务；涉及代码 Ruff 检查通过。
- 真实浏览器使用单独的临时 SQLite 测试实例与两个虚构账号，不连接用户 MySQL；验证登录、工作台、日记默认页、设置入口、主动历史列表/正文、离开日记页与退出、另一账号无旧记录。
- 浏览器默认进入工作台和日记页时，后端访问日志中的日记 API 请求数为 0；工作台实际请求带 `include_journal=false`。
- 主动历史查看有 GET 请求；验收期间没有日记 PUT/POST/DELETE。测试正文里的远程图片未创建 `img`，只读区域没有文本编辑器。
- 临时测试服务已经停止，临时脚本、隔离数据库和日志已清理，仅保留验收截图；没有更改用户 MySQL 的内容、结构或运行状态。

未执行 / 未实现：

- 本次没有 MySQL 实例复验；变更没有新增 SQL 或 DDL，查询跳过逻辑已在测试中验证。
- 真实目录授权、读写、导入、文件冲突、账号目录绑定、服务端模式约束、加密及历史迁移均留在对应后续步骤。
- 自动化测试验证了迟到响应被拒绝；浏览器没有人为注入网络延迟来重复这一场景。
- 后端测试有现有 Starlette/httpx 与 anyio 弃用提示，本次不更换无关依赖。

下一步按计划实施目录基础能力与账号绑定，不自动执行，也不把本次过渡入口称为完整的本地日记功能。

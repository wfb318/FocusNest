# 隐私改造第二步：本地目录基础能力与账号生命周期

实施日期：2026-11-05

状态：目录基础能力已实现，自动化测试及浏览器原生文件系统集成检查通过。当前内置浏览器未完成真实用户文件夹的选择授权；该流程仍需在支持的桌面浏览器中人工复验。正式日记编辑、导入和迁移留在第三、四步。

## 1. 本次可以做什么

在日记页或设置页的“日记隐私与存储”区域：

1. 点击“选择日记文件夹”，由浏览器请求用户选择及授权，不自动扫描或修改文件。
2. 绑定保存到当前站点浏览器的 IndexedDB，按稳定用户 ID 区分；其他账号不会自动沿用。
3. 重新进入站点时恢复当前账号的绑定，只查询权限，不自动弹出授权窗口。权限不足时显示“需要重新授权”。
4. 可以检查权限、主动重新授权或更换目录。
5. 点击“生成独立测试文件并验证读写”，在目录内创建随机名称的 `FocusNest-check-<随机ID>.txt`，写入测试文字，再读回确认。
6. 测试文件有简单编辑框，可在其他编辑器修改同一测试文件后检查冲突保护；它不是日记编辑器。
7. 解除绑定只移除浏览器中的绑定，不删除目录和文件。

本地目录名、目录路径、文件内容、版本指纹及测试输入不发送给后端。MySQL、数据库迁移和云端日记 API 本次没有变化。云端加密仍未开放。

## 2. 状态及保存在什么位置

| 信息 | 保存位置 | 生命周期 |
| --- | --- | --- |
| 账号与目录句柄的绑定 | 当前浏览器 IndexedDB：`focusnest-journal-storage / directories`，键为用户 ID | 刷新后可恢复；解绑删除该账号记录 |
| 目录权限 | 浏览器管理 | 每次实际访问前检查；恢复时不自动请求授权 |
| 目录名称、操作提示、测试输入和文件版本 | 当前页面应用内存 | 退出、会话失效或切换账号时清空 |
| 独立测试文件 | 所选目录中的真实文件 | 解绑不删除；由用户自行处理 |
| 正式日记内容 | 本次尚未新增本地日记编辑 | 不把测试写入当作日记已经本地化 |

目录状态分为：`signed_out` 未登录、`unbound` 未绑定、`restoring` 恢复中、`permission_required` 需授权、`ready` 已连接、`unavailable` 暂不可用。

`ready` 表示读写权限当前可用，不代表已经验证磁盘可写，也不代表正式日记存储接口已经可用。第一步的 `createJournalStorage('local')` 仍保持不可写，第三步再接入完整日记实现。

如果浏览器不能保存句柄，当前选择可仅在本次会话使用，页面明确提示下次重新确认；不上传云端作为替代。不支持目录 API 的环境显示限制，不提供虚假的“已绑定”。

## 3. 代码流程

### 登录或切换账号

```text
auth.accept() / auth.clear()
    → configureJournalAccount(用户ID或空字符串)
    → controller.configure()
    → 使旧操作失效、清空句柄和测试输入
    → 从 IndexedDB 读取当前账号的句柄
    → queryPermission() 查询权限
    → 更新目录状态
```

身份不变的正常 Token 刷新不会清空当前绑定。身份改变或会话失效时，旧的 `AbortSignal` 立即取消，未完成的绑定事务尝试中止，迟到的目录/文件结果不能回填新账号状态。

### 选择与保存绑定

```text
用户点击选择按钮
    → choose()
    → showDirectoryPicker({ mode: 'readwrite', ... })
    → 查询所选目录权限
    → 按当前账号写入 IndexedDB
    → 仅在账号及操作上下文仍有效时更新界面
```

选择器与 `requestPermission()` 都直接由用户点击发起，避免先等待其他异步任务导致浏览器的用户激活条件失效。取消选择保留旧绑定；绑定本身不测试写盘。

### 文件读写与冲突

`readLocalFile()` 和 `writeLocalFile()` 是供后续日记实现复用的单文件基础函数，本次仅用于独立测试文件：

- 只接收目录句柄内的单个文件名，拒绝绝对路径、路径分隔符、`..` 等越界输入。
- 每次检查当前账号上下文与读写权限，不自动请求授权。
- 单文件限制 1 MiB，读取严格校验 UTF-8；SHA-256 对完整原始字节计算版本。
- 创建时 `expectedRevision = null`，若目标已经存在则拒绝覆盖；更新必须匹配原版本，原文件已删除也不会按旧版本悄悄重建。
- 同源页面通过 Web Locks 的统一锁串行写入，即使两个账号主动选择同一目录也不能由应用同时写入。缺少写入锁时停止写盘。
- 写入使用 `createWritable({ mode: 'exclusive' })` 暂存流，在打开流后和提交前再次检查版本；冲突或上下文失效时尝试 `abort()`。
- `close()` 完成后再次读回，文字一致才提示成功。
- 保存失败保留输入；“读取最新磁盘版本”展示对照并更新校验版本，不直接替换编辑框。用户可比较后再次主动保存。

边界：这不是操作系统级的原子 compare-and-swap。外部编辑器不受网站 Web Locks 管理，仍可能在最后校验和提交之间修改文件；提交已开始后也不能保证因退出账号就撤销磁盘提交。代码防止迟到结果回填界面，并提供版本检查、独占流及读回验证，不承诺完全消除外部竞态。

绑定变更通过支持的 `BroadcastChannel` 通知同源其他标签页恢复该账号的绑定。该通知只含用户 ID，不含目录或文件内容；浏览器禁用广播时不阻止账号登录。

## 4. 新增与修改文件

相对于 `D:\FocusNest`：

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `frontend/src/types/localJournal.ts` | 新增 | 文件/目录句柄、绑定仓库、目录状态及文件快照类型 |
| `frontend/src/services/localJournalStorage.ts` | 新增 | 文件名与权限检查、版本校验、文件读写、账号上下文控制、绑定与测试文件流程 |
| `frontend/src/services/journalDirectoryBindings.ts` | 新增 | IndexedDB 句柄保存/恢复/解绑，事务完成及中止处理，校验损坏记录 |
| `frontend/src/stores/journalStorage.ts` | 新增 | Vue 状态桥接、浏览器目录选择、当前账号配置、跨标签页绑定变更通知 |
| `frontend/src/components/LocalJournalDirectorySettings.vue` | 新增 | 目录选择/权限/解绑按钮、测试文件读写及磁盘对照 |
| `frontend/src/stores/auth.ts` | 修改 | 接入登录接受结果、登出清理及会话失效时的目录上下文切换 |
| `frontend/src/components/JournalStorageSettings.vue` | 修改 | 共用隐私设置区域接入目录组件，更新实际功能状态 |
| `frontend/src/views/DashboardView.vue` | 修改 | 改为“编辑待接入”，避免已可绑定目录却仍显示“目录未接入” |
| `frontend/tests/localJournalStorage.test.mjs` | 新增 | 16 项权限、冲突、账号隔离、迟到操作、解绑、失败保留输入及真实磁盘测试 |
| `frontend/tests/browser/localJournalStorage.html` | 新增 | 开发用原生 OPFS/IndexedDB 集成验收页，不是产品入口，不进入生产构建 |
| `frontend/package.json` | 修改 | 新测试加入 `npm test`；没有新增依赖 |
| `docs/PRIVACY_STORAGE_STEP2.md` | 新增 | 本文：使用说明、代码清单、知识点和验证边界 |
| `docs/PRIVACY_STORAGE_PLAN.md`、`PROJECT_SPEC.md`、`README.md` | 修改 | 同步第二步状态及下一步范围 |
| `docs/screenshots/privacy-storage-step2.png` | 新增 | 产品目录入口截图 |
| `docs/screenshots/privacy-storage-step2-conflict.png` | 新增 | 浏览器原生文件句柄冲突保护验收截图 |

## 5. 新增知识与语法

- 文件系统句柄：浏览器授权后的访问能力，既不是任意磁盘路径字符串，也不是把文件上传到服务器。
- `queryPermission()` 只查询；`requestPermission()` 会请求授权，后者需要用户主动操作触发。
- IndexedDB 的结构化克隆可保存受支持的原生句柄；不能用 JSON/localStorage 序列化文件系统句柄。
- `AbortController / AbortSignal`：账号切换时通知尚未完成的操作失效，并尝试中止 IndexedDB 事务。
- `generation` 操作版本：即使底层 I/O 无法取消，也用版本检查拒绝旧结果。
- `shallowRef`：仅让界面状态快照响应式更新；实际文件句柄保留在控制器内部，避免被 Vue 深层代理。
- `transaction.oncomplete`：请求排队成功不等于整个事务已提交，绑定保存需要等待事务完成。
- `createWritable / close / abort`：暂存写入、提交和放弃；必须处理失败，不能只调用 `write()` 就报告已保存。
- `crypto.subtle.digest('SHA-256', bytes)`：计算文件版本指纹，用于检测修改，不是加密。
- `navigator.locks.request()`：串行处理同源多标签页写入；`BroadcastChannel` 用于通知绑定变化，两者职责不同。
- `Promise<T>`、依赖注入：控制器可以接真实浏览器 API，也可以在测试中注入延迟、拒绝授权、失败磁盘等条件验证边界。

## 6. 已实际验证

- `npm test`：54 项通过，其中本次新增 16 项。
- `npm run build`：Vue/TypeScript 类型检查与 Vite 生产构建通过。
- 自动化覆盖：目录外路径拒绝、授权不足、取消选择、账号分离、迟到选择/恢复、排队后账号切换、提交前失效、外部修改、写入失败保留输入、解绑不删文件、并发写入冲突。
- 真实磁盘：通过 Node 文件系统测试适配器在独立临时目录写入、读回、外部改写及拒绝覆盖；测试结束清理该临时文件和目录。该适配器检查真实磁盘字节，不代表浏览器的目录选择授权已验收。
- 真实浏览器：产品页面的未绑定状态和取消选择；原生 OPFS 句柄写入并读回，IndexedDB 持久化、刷新恢复、A/B 账号绑定隔离、冲突保留草稿、解绑后原文件仍存在。
- OPFS 集成页使用浏览器私有文件系统，不是用户可见目录，也不是产品本地目录的降级方案；只用于验证原生句柄、事务和文件写入逻辑。
- 临时浏览器后端使用独立 SQLite 与虚构账号；验收使用 5174/8001，保留原有 5173/8000 服务，不连接或修改用户 MySQL。
- 临时服务已停止，临时后端脚本、代理配置、隔离数据库和日志已清理；保留正式测试用例、开发验收页及截图。
- 后端访问日志未发现测试目录、测试文件名或测试正文，没有日记写入/删除请求。整个交互日志含 1 条旧日记列表只读 GET，因此不把本次整段交互记录成“云端读取总数为 0”。本地文件服务及绑定仓库没有 HTTP 调用。

## 7. 尚未验证或未实现

- 内置浏览器未完成真实用户文件夹的系统选择与授权，点击选择后返回取消。需要在支持 File System Access 的桌面浏览器中人工选择一个测试目录，验证绑定、刷新后权限状态及真实文件可见性。
- 用户可见文件夹的真实授权撤销和目录移动尚未人工验证；对应失败路径已有模拟测试与界面处理。
- 多标签页广播变更通知已实现；测试验证了串行锁策略，但未在两个实际浏览器标签页中人为制造同时提交。
- 不支持目录 API 时只提供说明；真正的手动日记导入/导出、日记文件解析、日期列表、正文编辑、工作台本地状态合并及云端迁移留在后续步骤。
- 本次没有后端业务修改、数据库迁移或密钥配置，不重跑与本次无关的后端测试，也不声称 MySQL 加密已经生效。

开发验收页可以在 Vite 开发环境访问 `/tests/browser/localJournalStorage.html`；必须在隔离测试站点使用，避免把测试键与真实账号混淆。OPFS 中的少量无私密内容测试文件保留用于验证解绑不删除，测试绑定已解除。

下一步为第三步“日记页面与工作台切换到本地来源”。目录已连接并不等于现在已经可以写正式日记。

## 8. 技术依据

- [MDN queryPermission](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle/queryPermission)：查询权限。
- [MDN requestPermission](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle/requestPermission)：主动请求授权。
- [MDN createWritable](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemFileHandle/createWritable)：写入流、独占模式与提交。
- [Chrome File System Access](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)：句柄使用、保存与权限行为。浏览器支持以实际环境为准。

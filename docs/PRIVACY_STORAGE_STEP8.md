# 隐私改造第八步 · 验收和部署检查

验收日期 2026-11-11。已完成本地代码、隔离浏览器和自动化验收。正式域名、代理、数据库网络和 Windows 文件夹授权仍需在实际环境确认。

## 隐私行为

- **本地日记**默认保存到用户选择的目录，文件按 `YYYY/MM/YYYY-MM-DD.md` 排列。日记标题、正文、目录名、文件路径、搜索词和本地列表在浏览器内处理。工作台只从本地读取今天的日记状态，向服务器请求工作台时排除云端日记信息。日记预览中的 Markdown 链接和图片以文本形式显示。笔记和资料库的 Markdown 预览保留普通链接。
- **云端加密**由用户主动选择。云端日记的日期可用于筛选，标题和正文在服务端加密保存。加密笔记保护标题和正文，加密文档保护原件、标题、文件名和预览。服务器在授权请求时解密所需内容，HTTPS 负责保护传输。历史云端日记可通过专用入口查看并按第四步迁移；已经存在的副本按第七步的恢复和保留规则处理。
- **标签页与账号**在同一浏览器、同一站点中，其他标签页登录或退出时，旧工作区清除账号状态和目录连接。通知只传递随机变化标记或失效事件。访问令牌仍在内存中。旧请求即使收到成功响应也会被丢弃；同一会话中到期的请求可刷新后重试。主动退出所在页仍会提示处理未保存的日记草稿。被其他标签页结束的会话会立即关闭工作区，草稿只存在于当时的页面内存。

## 验收结果

前端 79 项测试通过，类型检查和生产构建通过。后端 254 项测试通过、9 项跳过，Ruff 检查通过。最终 Chrome 复验检查了 63 个页面请求。

| 范围 | 实际验证 | 发布环境补验 |
| --- | --- | --- |
| 页面网络 | Chrome 隔离配置、虚构账号、生产前端构建和临时 SQLite。编辑、预览、保存、磁盘读回与搜索期间，所记录的页面请求均为测试站点同源请求，无日记 API 调用，标题、正文、目录名和搜索词未进入请求。隔离库两张日记表行数均为 0。 | 用正式域名和合成标记复核 Network 及实际代理、应用、数据库审计和监控日志。 |
| 账号隔离 | 两个 Chrome 标签页打开同一虚构账号的日记，在其中一个退出后两页都离开工作区；切到另一账号时未读取旧账号日记。自动测试覆盖旧会话的迟到响应、迟到 401、同会话重试和迁移上下文失效。 | 在发布目标浏览器复核多标签页和目录授权状态。 |
| 文件保护 | Chrome OPFS 原生句柄写入、读回及 IndexedDB 绑定恢复。临时真实磁盘适配器覆盖外部编辑、目录移动和版本冲突；授权失效、写入失败和导入目标冲突由自动测试覆盖。 | 在 Windows 的 Chrome 或 Edge 中手动选择一个空测试文件夹，确认授权、保存并用文件管理器核对文件。刷新后检查是否需重新授权，再用测试目录检查拒绝授权、移动目录和编辑冲突。OPFS 是浏览器的私有文件系统，系统选择器的实际授权需要由操作人完成。 |
| 云端加密 | 后端测试覆盖笔记、日记、文档的账号隔离、篡改、缺密钥、版本冲突、文档预览和原件。密钥轮换兼容旧密文，第七步已用合成备份验证独立密钥恢复、密文损坏和旧明文拦截。 | 对生产配置单独演练密钥备份和 MySQL 恢复，核实历史备份与日志保留规则。 |
| 应用错误日志 | 使用带合成正文的异常验证 500 响应、应用日志和异常堆栈输出不含正文。数据库引擎关闭绑定参数展示。 | 检查生产采集器、反向代理、数据库日志和监控平台是否记录请求内容或 SQL 参数。 |

## 发布检查顺序

1. **域名和 TLS**。通过同一 HTTPS 域名托管 `frontend/dist` 和 `/api/v1/`。页面刷新时前端路由回退到 `index.html`，API 路径直接转发给后端。前端构建使用 `VITE_API_BASE_URL=/api/v1`。开启从 HTTP 到 HTTPS 的跳转，核验证书和 API 路径。Chrome 的目录选择依赖安全上下文与用户操作；正式发布时按所选浏览器版本重新验证。 [Chrome 文件系统访问说明](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access) · [MDN 目录选择器](https://developer.mozilla.org/en-US/docs/Web/API/Window/showDirectoryPicker) · [Nginx 代理配置](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
2. **会话设置**。后端生产配置设 `COOKIE_SECURE=true`、`DEBUG=false`，`CORS_ORIGINS` 按实际 HTTPS 来源配置，移除开发来源。检查登录响应 Cookie 有 `Secure`、`HttpOnly`、`SameSite=Strict`，路径为 `/api/v1/auth`；验证刷新和退出。后端端口仅代理可访问，代理转发正确的 Host 与协议，Uvicorn 仅信任实际代理地址的转发头。
3. **权限与数据**。MySQL 位于回环或受限内网，应用用户只拥有运行所需的数据库权限，升级由有权限的运维账号执行。发布前查看 Alembic 版本，当前开发目标为 `0017_content_migration_receipts`。服务使用独立账号运行，内容密钥位于项目外的受限文件，通过 `CONTENT_KEYRING_FILE` 配置路径。签名密钥与内容密钥分别管理，内容密钥备份与数据库备份分开放置。 [密钥管理](PRIVACY_STORAGE_STEP5.md) · [备份与恢复](PRIVACY_STORAGE_STEP7.md)
4. **日志和缓存**。启动 Uvicorn 时可使用 `--no-access-log`，用反向代理保留必要的状态、耗时和请求方法。核对访问日志、错误日志和 APM，避免收集请求体、查询字符串、Cookie、Authorization、密钥和文件名；禁用会打印内容参数的数据库日志配置。验证私有 API 的 `Cache-Control: no-store` 未被代理或 CDN 覆盖。
5. **用合成内容验收后切换**。在桌面 Chrome 或 Edge 手动确认系统选择器读写，在发布环境演练账号退出、搜索、失败日志和备份恢复。验收记录保留版本、环境、结论与未通过项。真实迁移或副本清理由经过核对的运维批次单独执行。

## 本次代码清单

| 文件 | 修改 |
| --- | --- |
| [auth.ts](../frontend/src/stores/auth.ts) | 用 Web Locks 串行化登录、刷新和退出的 Cookie 操作，用 storage 事件和 BroadcastChannel 通知同源标签页失效，检查异步操作的会话版本。 |
| [client.ts](../frontend/src/api/client.ts) · [AppLayout.vue](../frontend/src/layouts/AppLayout.vue) | 为私有请求绑定发出时的会话版本，丢弃已失效响应并限制重试。未登录时卸载工作区，切换账号重建页面。 |
| [markdown.ts](../frontend/src/utils/markdown.ts) · [LocalJournalEditor.vue](../frontend/src/components/LocalJournalEditor.vue) · [LegacyJournalPreview.vue](../frontend/src/components/LegacyJournalPreview.vue) | 日记使用专用 Markdown 预览，禁用 HTML、图片、链接和自动链接。 |
| [main.py](../backend/app/main.py) · [exceptions.py](../backend/app/core/exceptions.py) · [session.py](../backend/app/db/session.py) | 通用异常在 HTTP 中间件内转换为不含异常详情的 500，仅记录异常类型，保留 CORS 和私有响应缓存头。隐藏 SQLAlchemy 绑定参数。 |
| [authTransport.test.mjs](../frontend/tests/authTransport.test.mjs) · [package.json](../frontend/package.json) · [markdown.test.mjs](../frontend/tests/markdown.test.mjs) · [localJournals.test.mjs](../frontend/tests/localJournals.test.mjs) · [test_privacy_errors.py](../backend/tests/test_privacy_errors.py) | 增加会话失效、正常重试、预览外部资源、移动目录及日志回归。 |

本次没有数据库架构变更。部署运行手册已更新，正式服务器配置、历史用户内容及备份尚待按发布流程处理。

# FocusNest 第六步收尾 日记与文档云端加密

实施日期为 2026-11-08。本批交付日记的可选云端加密、文档原件和预览加密，以及笔记真实本地目录评估。

## 使用方法

| 模块 | 操作 |
| --- | --- |
| 日记 | 日记页默认打开「仅本地」。点击「打开云端加密日记」进入独立视图。按日期编辑后，点击「保存加密日记」并确认发送标题和正文 |
| 日记复制 | 打开一篇已保存的日记，使用「复制到云端加密」或「复制到本地」。复制到本地需先授权目录。同一日期在目标已有记录时停止，来源保留 |
| 文档 | 在「上传保存方式」选「云端加密」，点击「上传并加密」选择文件。已有文档可打开详情后单独确认切换 |
| 查找内容 | 加密日记按日期查找，加密文档按类型和时间浏览。列表及工作台用占位标题，详情授权后显示内容。文档关键词查询覆盖普通云端 |

本机 MySQL 已升级至 `0016_document_encryption`，已验证现有开发密钥可读取。启动项目即可使用。其他环境先执行 Alembic 升级并配置项目外的密钥文件。云端模式由服务器加密落库，生产环境的传输保护依赖 HTTPS。

## 日记数据流程

1. `JournalView.vue` 默认挂载本地编辑器。显式打开加密视图后，`LocalJournalEditor.vue` 使用 `createJournalStorage()` 的加密适配器。它和历史只读适配器分别绑定当前账号。
2. 加密保存或复制的确认窗口显示日期与数据范围。确认后，`frontend/src/api/journals.ts` 请求加密接口。标题和正文随保存请求体发送，关键词留在本地查询。
3. `encrypted_journals.py` 按账号和日期锁定记录，校验编辑版本。新记录要求目标日期为空。密文绑定账号、对象 ID、字段及版本，日期也写入受认证的载荷。
4. 保存先写入再从事务内读回解密。日期、标题和正文均核对成功后提交。复制回本地使用现有 `importEntry()`，按日期创建并读回校验。需要移除来源时，在来源视图执行对应删除操作。

新表 `encrypted_journals` 保存记录 ID、归属账号、日期、密文、版本和时间。普通历史日记保存在原表，通过既有只读入口访问。工作台的今日日记卡片读取本地状态。

## 文档数据流程

1. 普通上传保留原入口。加密上传使用 `application/octet-stream`，编码后的文件名放在专用请求头。服务端在鉴权后分块读入内存并限制总大小，预览解析沿用现有文件类型和内容限制。普通 multipart 上传的文件对象可溢写临时磁盘，加密入口使用请求流绕开这条路径。 [Starlette 请求与文件上传](https://starlette.dev/requests/)
2. 原件加密到 `encrypted_file`，标题、文件名和结构化预览加密到 `encrypted_metadata`。数据库约束要求加密模式下四个明文字段为 SQL NULL。大小、类型、时间和归属仍用于组织记录。
3. 详情先验证归属。Markdown 和 TXT 解密原件后显示内容。Office 解密结构化预览。PDF 按需解密原件并渲染指定页面。下载解密原件并返回原文件名，响应使用 `no-store`。
4. 切换模式通过独立接口读取旧版本，再在同一事务内写入、读回并核对原件和元数据。通过才提交。重命名加密元数据时沿用原件密文，因为同一文档 ID 对应的原件字节固定。

10 MiB 原件的 Base64 密文约为 13.3 MiB，存入 MEDIUMTEXT。本机 MySQL 的 `max_allowed_packet` 实测为 64 MiB。正式环境以实际服务端和客户端配置为准。 [MySQL 数据包限制](https://dev.mysql.com/doc/refman/8.0/en/packet-too-large.html)

## 数据库和接口变化

| 变更 | 用途 |
| --- | --- |
| `0015_encrypted_journals` | 创建独立加密日记表，限制每个账号每天一篇加密记录 |
| `0016_document_encryption` | 增加文档保存方式、原件和元数据密文列。通过 `ck_documents_storage_payload` 约束明文与密文字段 |
| `GET /api/v1/journals/encrypted` 和 `GET .../today` | 查询当前账号的日期摘要或当日详情 |
| `GET/PUT/DELETE /api/v1/journals/encrypted/{date}` | 查看、保存及删除加密记录。上述日记接口均要求 `X-FocusNest-Journal-Access: cloud-encrypted` 和登录鉴权 |
| `POST /api/v1/documents/encrypted-upload` | 直接加密上传。文件名通过 `X-FocusNest-Filename` 传递 |
| `POST /api/v1/documents/{id}/storage` | 用目标 `storage_mode` 和 `expected_revision` 显式切换 |
| 现有文档列表、详情、重命名、预览和下载 | 支持当前记录的保存方式。摘要返回 `storage_mode` |

HTTP 客户端在请求上记录发起账号。遇到 401 时，只有刷新后的账号相同才重试，避免跨账号重发正在提交的正文或原件。

## 修改文件清单

| 位置 | 主要修改 |
| --- | --- |
| `backend/alembic/versions/0015_encrypted_journals.py`、`0016_document_encryption.py` | 两条迁移和加密记录的降级保护 |
| `backend/app/models/journal.py`、`models/document.py`、`models/__init__.py` | 加密日记、文档存储字段及模型注册 |
| `backend/app/schemas/journal.py`、`schemas/document.py` | 日记加密载荷、文档元数据和模式切换契约 |
| `backend/app/services/encrypted_journals.py`、`services/documents.py` | 鉴权后的加解密、版本检查、写入与回读 |
| `backend/app/api/v1/endpoints/encrypted_journals.py`、`endpoints/documents.py`、`api/v1/router.py`、`main.py` | 新接口注册、内存上传、预览下载和跨域请求头 |
| `backend/app/repositories/documents.py`、`repositories/dashboard.py` | 加密文档摘要占位和检索范围 |
| `frontend/src/views/JournalView.vue`、`components/LocalJournalEditor.vue`、`components/JournalStorageSettings.vue` | 加密入口、保存和复制确认、日期列表 |
| `frontend/src/api/journals.ts`、`services/journalStorage.ts`、`types/journalStorage.ts` | 明确区分本地、加密和历史只读的数据源 |
| `frontend/src/views/DocumentsView.vue`、`api/documents.ts`、`types/document.ts` | 上传方式、切换确认、保存模式状态及上传请求 |
| `frontend/src/api/client.ts`、`stores/auth.ts` | 将登录刷新后的请求重试绑定至发起账号 |
| `backend/tests/test_encrypted_workspace.py`、`frontend/tests/journalStorage.test.mjs` | 加密读写、越权和冲突、预览和原件一致性、数据源保护 |
| `README.md`、`PROJECT_SPEC.md`、`docs/PRIVACY_STORAGE_PLAN.md` | 同步第六步状态 |

## 笔记真实本地目录评估

浏览器端可沿用日记已有的目录绑定、权限和版本校验能力。笔记与日记的主要差别在于文件身份和组织关系。日记可用日期确定路径，笔记标题、文件夹名称和层级都会变化。

如果后续加入此模式，建议使用单独授权的笔记目录，以稳定 ID 标识 Markdown 文件，并将文件夹归属、置顶等元数据保存在本地。第一次实现适合覆盖创建、编辑、浏览和导出，再单独决定真实目录重命名与移动、问题关联及外部修改的处理。迁移仍应读回校验目标，并保留源记录直到用户独立处理。当前的笔记文件夹仍是云端逻辑分类，本批完成评估。

## 验证与后续范围

- 隔离后端 250 项通过、9 项跳过。前端 75 项通过，生产构建与 Ruff 检查通过。
- 本机 MySQL 8.0.44 已应用两条迁移，原有 2 篇历史日记保留。表结构一致性检查通过。MySQL 定向回归 53 项通过，测试数据回滚。
- 隔离浏览器验证日记默认本地、确认后加密保存并回读，以及加密文档上传和预览。使用虚构数据截图，文件位于项目的 `docs/screenshots/privacy-storage-encrypted-journal.png` 和 `privacy-storage-encrypted-document.png`。
- 桌面浏览器的真实目录授权和日记双向复制仍需实机验收。复制复用已有本地写入、禁止覆盖与读回校验，云端版本冲突由接口测试覆盖。
- 第七步处理用户选择的历史迁移和旧明文副本。第八步处理隐私与权限验收、密钥恢复演练及部署检查。

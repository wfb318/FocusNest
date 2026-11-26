# FocusNest 第六步首批 笔记云端加密

实施日期为 2026-11-08。本批交付笔记的保存方式选择。笔记可使用普通云端或云端加密，已有笔记可逐篇切换。日记、文档及笔记本地目录各自保留在后续接入范围中。

## 使用方法

1. 启动 FocusNest 后进入「笔记」。新建或导入到草稿后，在「保存方式」中选择「云端加密」，再保存。
2. 打开已有笔记，先保存或放弃草稿，点击「切换保存方式」。确认窗口会说明目标的存储行为。
3. 在笔记列表或工作台点击「加密笔记」打开详情。标题和正文会在当前账号打开时解密。
4. 用文件夹、置顶和更新时间浏览加密笔记。输入关键词时，查询范围为普通云端笔记的标题和正文。

本机开发库已经应用迁移 `0014_note_encryption`。后端首次加密读写时会从 `CONTENT_KEYRING_FILE` 加载项目外的受限开发密钥文件。其他环境需先运行 Alembic 迁移，再按第五步的密钥管理说明配置独立密钥并重启后端。加密保存遇到密钥不可用时会报错，编辑器保留草稿。

## 存储与切换

| 字段或操作 | 普通云端 | 云端加密 |
| --- | --- | --- |
| 在线标题、正文 | `title`、`content` 保存明文 | 两个字段均为 SQL NULL |
| 密文列 | `encrypted_payload` 为 SQL NULL | 加密后的标题和正文 JSON 存入 MEDIUMTEXT |
| 内容版本 | `content_revision` 为 SQL NULL | 用于绑定密文到对应内容版本 |
| 列表和工作台标题 | 返回普通标题 | 返回「加密笔记」占位 |
| 文件夹、置顶、问题关联 | 用于组织笔记 | 同样保留这些元数据及账号归属、对象 ID、更新时间 |

新建笔记默认普通云端，迁移时现有笔记采用普通云端模式。选择某篇进行切换时，后端校验账号归属和编辑版本，读取原内容，写入目标模式并从事务内读回校验。校验成功才提交同一行，保留笔记 ID、创建时间和组织关系。校验失败会回滚。切回普通云端会把标题、正文以明文存回数据库，确认窗口会提前说明。

数据库通过 `ck_notes_storage_payload` 检查两种模式下的字段互斥。加密笔记的旧明文可能出现在切换前形成的备份及数据库日志中，历史副本处理属于后续阶段。加密发生在服务器，服务端授权后解密正文。 [MySQL CHECK 约束说明](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html)

## 一次保存经过哪些代码

1. `NotesView.vue` 的 `save()` 把标题、正文、文件夹、关联问题、置顶及保存方式交给 `frontend/src/api/notes.ts`。
2. `endpoints/notes.py` 用 `NoteCreate` 或 `NoteUpdate` 验证参数，把当前登录账号和数据库会话传给 `services/notes.py`。
3. `create()` 或 `update()` 核对所属文件夹、问题归属及编辑版本。旧客户端更新时省略保存方式，服务会沿用数据库中的模式。
4. `write_body()` 生成新版本。加密模式将标题和正文序列化为字节，通过第五步的 `ContentCrypto.encrypt()` 加密，关联账号、笔记 ID、字段和内容版本。
5. `persist()` 先 `flush()` 再 `refresh()`，从数据库读回目标内容。验证通过后提交并返回详情。列表和工作台只查询摘要。

切换走 `changeNoteStorage()` → `POST /api/v1/notes/{note_id}/storage` → `change_storage()`。请求体只包含目标 `storage_mode` 和 `expected_revision`，由服务器从原笔记读取标题和正文。普通编辑接口收到与当前记录不同的模式时会返回 `40932`，提示走专用入口。

## 修改文件清单

| 文件 | 修改内容 |
| --- | --- |
| `backend/alembic/versions/0014_note_encryption.py` | 新增 MySQL 迁移，增加三列和检查约束。存在加密记录时拒绝降级 |
| `backend/app/models/note.py` | 对应新增字段、可空明文列和模式约束 |
| `backend/app/schemas/note.py` | 增加模式联合类型、正文校验和切换请求模型 |
| `backend/app/services/notes.py` | 接入加解密、提交前回读及单篇切换 |
| `backend/app/api/v1/endpoints/notes.py` | 增加专用切换 API |
| `backend/app/repositories/notes.py` | 摘要使用加密占位，限定关键词检索范围 |
| `backend/app/repositories/dashboard.py`、`backend/app/schemas/dashboard.py` | 最近笔记复用摘要规则并返回保存方式 |
| `frontend/src/views/NotesView.vue` | 新建选择器、状态标签、切换确认、搜索范围提示 |
| `frontend/src/api/notes.ts`、`frontend/src/api/client.ts` | 切换请求及相关错误提示 |
| `frontend/src/types/note.ts`、`frontend/src/types/dashboard.ts` | 增加保存方式类型 |
| `backend/tests/test_note_encryption.py`、`backend/tests/test_dashboard.py` | 加密 CRUD、回滚、跨账号拒绝、摘要及文件夹移动验证 |
| `README.md`、`PROJECT_SPEC.md`、`docs/PRIVACY_STORAGE_PLAN.md` | 同步本次交付状态 |

本机配置另增加了独立开发密钥目录和 `backend/.env` 中的 `CONTENT_KEYRING_FILE` 路径。密钥值由管理命令随机生成，存于受限文件。该文件需要与将来使用它的密文配套恢复，备份应放到独立的受控位置。

## 这次用到的知识

| 概念 | 在本次代码中的用途 |
| --- | --- |
| `Literal` | 将保存方式限定为 `cloud` 和 `cloud_encrypted` |
| `model_fields_set` | 区分客户端主动提供保存方式与采用默认字段值 |
| SQL `CHECK` 和 `CASE` | 分别约束可写字段组合、控制摘要中显示的标题 |
| `flush()`、`refresh()`、`commit()` | 在提交前将更改发给数据库并读回，校验失败时整次事务可回滚 |
| 编辑版本与内容版本 | 文件夹删除会让打开的编辑器版本过期。密文内容未改，因此保持原来的内容版本，解密仍然有效 |
| 关联数据 AAD | 将密文绑定到用户、笔记、字段和内容版本。跨对象替换会使认证失败 |

## 验证记录

- 后端全量 244 项通过、9 项跳过。前端 74 项通过，生产构建和 Ruff 检查通过。
- 本机 MySQL 8.0.44 已应用 `0014_note_encryption`，检查约束处于启用状态。迁移前后原有 4 篇普通笔记数量一致，`alembic check` 无额外变更。
- MySQL 定向回归 42 项通过，已核对用户、笔记、文件夹、会话的测试事务全部回滚。
- 本机开发密钥文件通过加载、加密与解密自检。浏览器在隔离 SQLite 和虚构账号下验证加密创建、重开及普通笔记切换为加密。截图位于 `D:/FocusNest/docs/screenshots/privacy-storage-step6.png`。
- 业务开放范围为笔记标题与正文。笔记真实本地目录、日记可选加密、文档原件与预览加密，以及历史备份处置分别留待后续交付。

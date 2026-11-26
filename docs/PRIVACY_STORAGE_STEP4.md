# 隐私改造第四步：日记导入、历史迁移与独立副本清理

实施日期：2026-11-05。对应 [隐私保护计划](PRIVACY_STORAGE_PLAN.md) 第四步。

本次实现 UTF-8 Markdown 日记导入，以及当前账号的历史云端日记复制到本地。复制完成后逐篇读回验证，保留来源；只有本地验证和进度写入都成功，才提供逐篇清理在线云端副本的独立操作。第五步云端加密尚未开始。

这是功能说明和代码清单，不是当天工作记录。没有自动迁移、删除用户数据，没有修改 MySQL 表结构，也没有新增 Alembic 版本。

## 1. 怎么使用

1. 在日记页绑定并授权自己的真实日记文件夹，先保存或放弃编辑器中的草稿。
2. 展开“导入 Markdown 日记 / 迁移历史云端日记”。
3. 导入文件：选择 `.md` 文件；检查识别出的日期，无日期文件手动填写日期，可填写普通文件的标题，再重新预览。点击“复制可处理项到本地并校验（保留来源）”。
4. 迁移旧云端记录：主动加载历史云端日记，选择当前页要迁移的记录，预览后复制并校验。列表每页 20 篇，可分批处理。
5. 成功项显示“本地已验证”，云端项同时显示在线副本仍保留。本地列表会刷新，可以直接打开导入的日记。
6. 离开页面后，可“读取本地迁移进度”；要继续核对云端，单独点击“恢复未清理的云端迁移检查”。后者每次检查最多 100 条已记录的未清理迁移。
7. 确实需要清理某篇在线云端副本时，点击该篇的独立清理按钮，核对弹窗、勾选确认，再提交。取消不执行清理。

复制、预览和读取本地进度不会触发云端删除。没有绑定目录时不能导入或迁移到本地，但仍可主动查看当前账号的历史云端列表。

## 2. 导入规则与文件格式

| 项目 | 实际行为 |
| --- | --- |
| 支持格式 | 非空、有效 UTF-8 的 `.md`；允许 UTF-8 BOM 和 CRLF；拒绝无效编码与 NUL 二进制字符 |
| 数量和大小 | 每批最多 100 个文件、合计 50 MiB，单文件最多 1 MiB；日记正文最多 100000 个字符、标题最多 200 个字符 |
| 普通 Markdown 日期 | 从严格的 `YYYY-MM-DD.md` 文件名识别，否则需要手动指定；不默认归到今天 |
| 普通 Markdown 内容 | 原正文保留，包括普通 YAML front matter；标题初始为空，可在预览中填写；新副本生成创建/修改时间 |
| FocusNest v1 文件 | 从受控元信息读取日期、标题、时区、创建时间、修改时间；锁定元信息编辑；不执行通用 YAML 或任何脚本 |
| 日期冲突 | 文件名日期与平台元信息日期不符时拒绝；本批多篇指向同一天时全部标为冲突，移除重复项后重新预览 |
| 目标目录 | `所选目录/YYYY/MM/YYYY-MM-DD.md`；不沿用来源路径，不访问授权范围以外的目录 |
| 本地已有记录 | 相同内容可跳过重复写入；不同内容停止覆盖；平台文件还检查时间元信息及其时区 |
| 解析失败 | 保留文件名和逐篇错误结果；其他有效项仍可处理；原文件不修改、不上传 |

沿用第三步确定的 v1 格式：

```markdown
---
focusnest_journal_version: 1
entry_date: "2026-11-05"
title: "示例"
timezone: "Asia/Shanghai"
created_at: "2026-11-05T01:02:03+00:00"
updated_at: "2026-11-05T01:02:03+00:00"
---

这里是正文。
```

平台文件中的日期与路径日期必须一致；未知版本、重复元信息、缺少字段或非法时区会停止导入。普通正文后面的示例代码即使提到版本字段，也不会误判为平台元信息。

旧云端日记表没有历史时区字段，迁移时使用当前账号的时区；原有标题、正文、日期及创建/修改时间原样保留。恢复已记录的迁移时沿用已验证本地文件的时区，不因用户后来修改个人时区就重写文件。

## 3. 从点击按钮到写入文件

### 文件导入

```text
JournalTransferPanel.selectFiles()
  → journalTransfer.parseImportFile()：本地读取、格式与日期识别
  → journalTransfer.previewTransfers()：检查批次重复、现有目标及元信息
  → 用户检查结果，必要时补日期/标题并重新预览
  → JournalTransferPanel.copy()
  → journalTransfer.copyAndVerify()
  → localJournalRepository.importEntry()：只创建不存在的目标
  → localJournalStorage.writeLocalFile()：版本比较、写入、读回
  → copyAndVerify() 再读取文档、逐项核对
  → journalTransferProgress.save()：写本地进度
  → 页面显示已验证并刷新本地列表
```

整个文件导入过程不调用日记 HTTP 接口。选择的源文件保持不变，目标是绑定目录中的新副本。预览后若其他编辑器或标签页创建/修改了目标，复制阶段再次检查，遇到不同内容仍停止覆盖。

### 历史云端迁移

```text
JournalTransferPanel.loadCloud()：用户主动加载当前账号列表
  → prepareCloud()：逐篇读取全文并核对列表中的 id/revision
  → cloudTransferItem() → previewTransfers()
  → copy()：与文件导入共用本地复制、读回和进度流程
```

列表和全文读取仍要求登录、数据归属校验，以及 `X-FocusNest-Journal-Access: legacy-migration` 历史访问头。日常编辑和 Dashboard 沿用第三步的本地来源，不自动查询这些旧记录。

### 独立清理在线云端副本

```text
requestCleanup()：打开单篇确认窗口，初始未勾选
  → cleanup()：核对当前目录的迁移进度
  → verifyBeforeCleanup()
      读取本地：版本、日期、标题、正文、时区及时间必须一致
      读取云端：id、revision、来源摘要必须一致
      再次读取本地：防止等待云端响应期间本地被修改
  → removeMigratedCloudCopy()：只发送版本、摘要和确认标识
  → 后端 cleanup_migrated_copy()：锁定当前用户及其记录，重新检查来源
  → 删除匹配的在线行；将本地进度记为 cloud_removed
```

云端已经不存在时按可重试结果处理，不重复删除。源内容即使被直接修改而没有更新 revision，摘要不一致也会拒绝清理。任何本地校验失败都不会发出清理请求；云端版本变化返回 `409 / 40922`。

## 4. 本地迁移进度

绑定目录根部新增账号专属文件：

```text
FocusNest-migration-<稳定用户ID>.json
```

结构为 `{ version: 1, userId, records }`。每条记录包含来源类型、来源键、目标日期、来源版本/摘要、本地文件版本、验证时间和清理状态。平台写入的进度不保存标题、正文或本地绝对路径，不上传服务器。

- 文件来源键使用原文件字节摘要；云端来源键使用原记录 ID 与版本。
- `sourceHash` 是来源内容摘要，`localRevision` 是整个目标文件的字节摘要，两者用途不同。
- 每复制并读回成功一篇就写一次进度；中途失败可以重新选源文件或恢复云端检查。
- 目标已存在相同内容时不重新写入；已被编辑的目标不会被旧迁移覆盖。
- 进度 JSON 损坏时停止覆盖该文件并提示处理，不能默默重建而丢弃已有记录。
- 进度最多 2000 条，沿用 1 MiB 文件限制。达到上限时保留来源并提示，不能继续获得清理资格。
- 若日记副本已写入但进度写入失败，页面明确提示“本地可能已有副本”，重新预览可以识别它；不会因此清理来源。
- 账号切换、目录变更或组件卸载会清理当前批次内存；正在处理时阻止页面内跳转和退出，并提示刷新/关闭。

读取进度只核对本地版本，不推断当前云端状态。“上次记录云端已无副本”表示历史检查结果；恢复操作才会主动访问云端。

## 5. 新增文件清单

| 文件 | 作用与主要函数 |
| --- | --- |
| `frontend/src/types/journalTransfer.ts` | `TransferItem` 表示预览和逐篇结果，`TransferRecord` 表示进度；`TransferStorage` 增加保留元信息的导入和文档读取 |
| `frontend/src/services/journalTransfer.ts` | `parseImportFile` 解析，`previewTransfers` 检查冲突，`copyAndVerify` 复制校验，`verifyBeforeCleanup` 清理前复核，`sourceDigest` 生成来源摘要 |
| `frontend/src/services/journalTransferProgress.ts` | `createTransferProgress` 在绑定目录中按账号读写进度；使用文件版本比较与现有 Web Lock |
| `frontend/src/components/JournalTransferPanel.vue` | 文件选择、云端分页选择、逐篇结果、进度恢复和单篇清理确认；与编辑器互锁 |
| `frontend/tests/journalTransfer.test.mjs` | 导入解析、重复日期、文件不覆盖、时区与时间保留、进度损坏、清理前变化等回归测试 |
| `frontend/tests/fixtures/journalTransferDigest.json` | 包含中文、emoji、特殊字符和微秒时间的固定测试向量，确保前后端摘要一致；均为虚构内容 |
| `backend/tests/test_journal_migration.py` | 校验清理接口的鉴权、显式意图、参数、版本/摘要、用户隔离与重复请求 |

## 6. 修改文件清单

| 文件 | 具体变化 |
| --- | --- |
| `frontend/src/services/journalMarkdown.ts` | 抽出 `parseJournalDocument` 返回正文对象及元信息时区；保留原 `parseJournal` 接口 |
| `frontend/src/services/localJournalRepository.ts` | 新增 `readDocument` 和 `importEntry`，保留来源时间/时区，只创建不存在的目标；普通编辑行为继续沿用现有接口 |
| `frontend/src/stores/journalStorage.ts` | 提供 `progress()`，绑定当前账号及当前目录生命周期 |
| `frontend/src/api/journals.ts` | 新增 `removeMigratedCloudCopy`；旧普通写入接口没有恢复 |
| `frontend/src/api/client.ts` | 增加云端来源已变化的中文错误提示 |
| `frontend/src/views/JournalView.vue` | 接入迁移面板，协调目录设置、编辑器和迁移互锁，更新旧记录入口说明 |
| `frontend/src/components/LocalJournalEditor.vue` | 迁移时暂停编辑/保存/删除及页面内离开，完成后刷新本地记录 |
| `frontend/src/components/JournalStorageSettings.vue` | 更新导入、迁移和独立清理的实际能力说明 |
| `frontend/src/components/LegacyJournalPreview.vue` | 保持只读查看，指向迁移入口，移除“迁移尚未提供”的旧提示 |
| `frontend/package.json` | 将新增导入迁移测试加入 `npm test` |
| `frontend/tests/browser/localJournals.html` | 允许第四步虚构测试账号准备 OPFS 目录；仅开发验收使用，不进入生产构建 |
| `backend/app/schemas/journal.py` | 新增 `JournalMigrationCleanup`，只接受版本、摘要、本地版本和显式确认字段 |
| `backend/app/services/journals.py` | 新增 `source_digest` 与 `cleanup_migrated_copy`；锁定、归属检查、版本复核及幂等清理 |
| `backend/app/api/v1/endpoints/journals.py` | 新增独立 POST 清理端点；原 PUT/DELETE 继续拒绝 |
| `README.md`、`PROJECT_SPEC.md`、`docs/PRIVACY_STORAGE_PLAN.md` | 同步第四步实施状态与限制 |

验收截图：`docs/screenshots/privacy-storage-step4.png`、`docs/screenshots/privacy-storage-step4-cleanup.png`。

## 7. 数据库和 API

没有新增表、字段或迁移，版本仍为 `0013_note_problem_link`。现有 MySQL 配置、数据目录和用户数据均未调整。

新增：`POST /api/v1/journals/{entry_date}/migration-cleanup`。要求 Bearer 登录鉴权、历史访问头和以下 JSON：

```json
{
  "expected_revision": "原云端记录的版本UUID",
  "verified_source_digest": "64位SHA256十六进制摘要",
  "local_revision": "64位本地文件SHA256摘要",
  "confirmation": "DELETE_CLOUD_COPY"
}
```

字段示例用于说明格式；真实版本需为 36 字符 UUID，摘要需为 64 位小写十六进制。请求不包含日记正文、标题、文件名或目录路径，拒绝额外字段。成功返回 `{ removed: true, already_missing: false }`；记录已无则 `already_missing: true`。

来源摘要约定：固定顺序的 `entry_date, title, content, created_at, updated_at` 对象，紧凑 JSON、UTF-8、中文不转义后 SHA-256。保留时间字符串的原始精度，不能先转为 JavaScript Date 而截断微秒。使用固定测试向量验证 Python 与 TypeScript 结果一致。

## 8. 验证结果和实际边界

已实际执行：

- 前端 `npm test`：74 项通过；类型检查与生产构建通过。
- 后端完整 `pytest -q`：185 项通过、9 项跳过；跳过项需要 MySQL 等额外条件。本次未连接用户 MySQL 复验。Ruff 检查及涉及后端文件的格式检查通过。
- 隔离浏览器验收使用独立前后端端口、SQLite、两个虚构账号及 OPFS 的原生目录句柄，没有替换产品目录选择 API。
- 两篇 Markdown 导入成功，其中一篇必须手动指定日期；导入后两份源文件的 SHA-256 均未改变。主动加载云端前，服务访问日志没有日记 API 请求。
- 两篇虚构云端日记成功复制并读回，列表显示共四篇本地日记；刷新后从本地进度恢复并重新核对成功。
- 打开清理窗口时确认按钮默认禁用，取消后未发送清理 POST；浏览器验收没有执行永久删除。接口删除、重复请求与隔离行为通过后端自动测试验证。
- 第二账号未继承第一账号的目录、四篇本地日记或迁移批次；主动云端列表仅显示其自己的一篇记录。
- 隔离 SQLite 只读复查仍有全部三篇云端原件；访问日志没有日记 PUT/DELETE 或迁移清理 POST。

尚未完成或需要正确理解的边界：

- 原生“选择用户可见真实文件夹”的授权交互仍需在支持的桌面 Chrome/Edge 中复验。本次 OPFS 验收验证实际页面和文件句柄操作，不能等同于用户真实磁盘目录授权通过；产品没有自动改用 OPFS 的降级路径。
- 本地文件与服务器之间没有跨系统原子事务。客户端在清理前复读本地，服务端只验证账号归属、云端版本及摘要；服务端不能独立证明用户磁盘上的副本实际存在，也不能阻止最后一次复核之后的外部编辑或删除。
- 清理只删除当前账号指定日期的在线数据库行，不清理备份、数据库日志、系统快照或第三方同步副本；备份保留期限和正式部署清理策略尚未实施。
- 未批量迁移或清理任何用户真实数据；没有导入附件、PDF、Word、图片等日记格式，没有云端内容加密或跨设备同步。
- 后端测试仍显示依赖库的两项弃用警告，不影响本次测试结果。

## 9. 本次新增知识和语法

| 写法 / 概念 | 在这里解决什么问题 |
| --- | --- |
| `File.arrayBuffer()`、`TextDecoder('utf-8', { fatal: true })` | 本地读字节并拒绝错误编码，避免把乱码当作成功导入 |
| `crypto.subtle.digest('SHA-256', bytes)` | 给来源和目标生成版本指纹；它是摘要，不是加密，不能还原也不能声称内容已加密 |
| `type Status = TransferItem['status']` | 通过索引访问类型取出“待日期、可复制、冲突、已验证、失败”等状态联合类型，配合模板显示明确结果 |
| `interface TransferStorage extends JournalStorage` | 在已有存储接口上增加导入和元信息读取，普通编辑器继续使用原接口 |
| `try / catch` 放在逐文件循环内 | 一篇失败仍保留其他项的处理结果，不以整批异常掩盖具体失败 |
| 版本比较与再次读取 | 预览不是写入许可；复制和清理时都重新检查，保护外部修改 |
| 原始文本摘要与字段摘要 | 前者检测任何文件变化，后者确认云端内容与来源快照是否一致；二者不能互相代替 |
| `Literal['DELETE_CLOUD_COPY']`、`extra='forbid'` | 后端只接受明确确认值和规定字段，避免把私密内容当成清理参数 |
| 数据库行锁与幂等 | 并发时复核同一用户的记录；重试已完成的清理返回已不存在，不误删别的数据 |
| `epoch`、账号 ID、目录版本 | 异步结果返回时确认仍属于发起操作的账号和目录，避免旧结果进入新会话 |

下一步为计划中的第五步“云端加密基础与密钥管理”，需用户继续授权后实施。本步不会自动启动加密开发或 Phase 8 Statistics。

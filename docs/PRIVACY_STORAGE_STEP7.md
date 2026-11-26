# 隐私改造第七步 · 历史内容迁移和恢复

实施日期 2026-11-11。

## 迁移范围

| 对象 | 读回验证和在线副本处理 |
| --- | --- |
| 普通云端笔记 | 保留原笔记 ID、文件夹和问题关联。加密标题和正文，读回比对成功后提交，原明文字段为空。 |
| 普通云端文档 | 保留原文档 ID。加密原件、标题、文件名和预览，逐字节校对原件并比对元数据，原明文字段为空。 |
| 历史云端日记 | 保留 ID、日记日期和创建、更新时间，写入加密日记表并读回比对。通过后在同一事务删除历史表中的源记录。若当天已有加密日记，保留两份现状并报告冲突。 |

日记默认仍存本地。已有本地迁移流程的日记按第四步核对本地文件和清理在线副本。只把账号所有者明确选择继续留在云端的日记列入本批。

## 执行迁移

运维命令读取当前后端数据库配置和内容密钥文件。执行前确认环境、账号和迁移授权，限制选择文件与运行结果的访问权限。下面从 `D:\FocusNest\backend` 执行，把示例路径、账号 ID 和记录 ID 替换为实际批准值。

```powershell
$Python = '.\.venv\Scripts\python.exe'
$Account = '已批准的账号 UUID'
$Id = '已批准的笔记 UUID'
$Selection = 'X:\受限目录\note-selection.json'

& $Python scripts/migrate_private_content.py list --account $Account --kind note
& $Python scripts/migrate_private_content.py plan --account $Account --kind note --id $Id --output $Selection
& $Python scripts/migrate_private_content.py apply --selection $Selection
```

- `--kind` 取 `note`、`document` 或 `journal`。每次 `list` 按 ID 返回最多 100 条，使用上一页最后一个 ID 作为 `--after` 继续。列表只返回记录 ID、版本、模式、更新时间以及适用的日记日期。
- `plan` 可重复传入 `--id`，每份最多 100 条。它校验记录属于指定账号，冻结每条记录当前版本，且只创建新文件。核对选择后运行 `apply`，保留原选择文件以便续跑。
- `apply` 逐条提交。每条变更及回执写在同一事务内，输出仅含账号和记录标识、版本、结果或错误码。出现单条失败时本批继续，最后退出码为 `1`。中断时当前未提交事务回滚，退出码为 `130`。使用同一文件续跑，已提交条目显示 `already_applied`；若发现来源版本已变更，先重新核对，再按新版本生成新选择。
- `already_applied` 表示该次迁移曾经提交。需要确认当前模式时重新运行 `list`，因为用户之后可能切换了保存方式。`already_encrypted` 表示所选版本已经使用云端加密。退出码 `0` 表示本次没有失败项。

## 备份保留和过期处理

1. 为每套部署确定恢复窗口和保留期限。对完整备份、增量备份、MySQL 二进制日志、复制到其他位置的归档以及恢复演练产生的副本建立台账。记录位置、覆盖的时间点、依赖的备份或日志、是否可能含历史明文、到期日和清理结果。在线迁移只处理表中的可查询记录，历史快照、日志和数据库底层存储可能仍含早期明文。 [MySQL 备份策略](https://dev.mysql.com/doc/refman/8.0/en/backup-policy.html) · [MySQL 二进制日志](https://dev.mysql.com/doc/refman/8.0/en/binary-log.html)
2. 完成一轮实际迁移后，在冻结写入的检查点生成一份受限数据库备份及其恢复清单。保管备份、密钥和可信清单时使用独立位置及相应访问权限。清单含账号和记录元数据，需与其他敏感运维文件同等保护。为备份与清单记录时间点和校验值。
3. 按当前恢复窗口审查到期副本。先确认保留的备份与增量日志能够恢复所需时间点，且最近一次演练通过，再通过对应存储平台或 MySQL 的保留策略清理到期副本并登记结果。依赖链仍在使用的副本继续保留并限制访问。项目代码无法清理已散落在外部的导出文件、快照或日志。 [MySQL 备份与恢复](https://dev.mysql.com/doc/refman/8.0/en/backup-and-recovery.html)

## 隔离恢复演练

1. 从冻结写入的权威库导出可信清单，并在同一检查点备份数据库。以下是 MySQL 8.0 的逻辑备份示例，`focusnest-backup` 是提前配置好的登录路径。备份文件路径应使用新的受限位置。 [mysqldump 参数](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)

   ```powershell
   & $Python scripts/migrate_private_content.py export-catalog --output 'X:\受限清单\catalog-本次检查点.json'
   mysqldump --login-path=focusnest-backup --single-transaction --no-tablespaces --result-file='Y:\数据备份\focusnest-本次检查点.sql' focusnest
   & $Python scripts/manage_content_keys.py backup --file 'Z:\运行密钥\content.keys' --output 'W:\独立密钥备份\content-本次检查点.keys'
   ```

2. 将数据恢复到隔离实例或库，应用该版本需要的架构。若从更早的备份开始，在隔离环境回放日志至受信任的检查点，覆盖之后发生的加密迁移、删除和在线副本清理。发布前应比对即将替换的权威状态；若期间有新的删除或存储选择，需把这些变更纳入恢复结果和可信清单。权威来源不可用、变更无法核对时，保持隔离。使用旧快照自己导出的清单会掩盖旧副本重新出现的问题。
3. 在隔离后端运行以下命令。先检查其 `MYSQL_*` 设置确实指向恢复库，以及 `CONTENT_KEYRING_FILE` 指向单独恢复的密钥文件。

   ```powershell
   & $Python scripts/migrate_private_content.py verify-restore --catalog 'X:\受限清单\catalog-本次检查点.json'
   ```

   命令先比对笔记、文档、历史日记和加密日记的账号、记录 ID、版本、存储模式及适用的日记日期，再逐条解密受保护的内容，包括文档原件和预览元数据。清单多一条或少一条、模式变化、密钥缺失、密文异常都会返回非零退出码。只有清单可信、状态匹配且解密通过，才能通过这项切换前检查。脚本只读，发现差异时由运维在隔离环境调查。

## 代码清单

| 文件 | 作用 |
| --- | --- |
| [migrate_private_content.py](../backend/scripts/migrate_private_content.py) | 运维入口，负责参数解析、选择文件、逐条事务与恢复验证输出。 |
| [content_migration.py](../backend/app/services/content_migration.py) | 校验账号、记录与版本，处理日记源记录，保存迁移回执，构建和验证恢复清单。 |
| [notes.py](../backend/app/services/notes.py) · [documents.py](../backend/app/services/documents.py) | 将存储切换的写入、读回与提交拆开，让迁移能在同一事务写回执。常规业务入口负责自身提交。 |
| [encrypted_journals.py](../backend/app/services/encrypted_journals.py) | 提取加密写入与读回校验，供日记保存和历史迁移共同调用。 |
| [migration_receipt.py](../backend/app/models/migration_receipt.py) · [模型注册](../backend/app/models/__init__.py) · [0017 迁移](../backend/alembic/versions/0017_content_migration_receipts.py) | 新增回执表。复合主键由账号、对象类型、来源 ID 和来源版本构成，另存目标版本和完成时间。存在回执时拒绝直接降级丢弃回执表。 |
| [test_content_migration.py](../backend/tests/test_content_migration.py) | 覆盖原文读回、在线明文清理、账号隔离、未选中对象、失败回滚、断点续跑和隔离备份恢复。 |

无新增公开 API 或前端入口。日记正文、笔记内容、文档原件、密码和密钥均不进入命令输出。

## 验证边界

完整后端测试 253 项通过、9 项跳过，Ruff 检查通过。本机 MySQL 上执行 18 项相关测试，测试前后七张业务及回执表的行数一致。隔离恢复复验覆盖三类加密内容，同时验证缺密钥、密文损坏和旧明文日记重新出现均会被拦截。

本机 FocusNest 开发库 MySQL 8.0.44 已升级到 `0017_content_migration_receipts`。仅对合成记录执行批量迁移和恢复验证。本轮没有迁移真实用户内容，也没有清理现有备份或日志。隔离恢复演练使用合成数据的 SQLite 备份和独立密钥备份。正式 MySQL 备份链的演练、保留期限配置和真实旧副本盘点留待部署验收。

# 隐私改造第五步：云端加密基础与平台密钥管理

实施日期：2026-11-05。对应 [隐私保护计划](PRIVACY_STORAGE_PLAN.md) 第五步。

本次完成可独立验证的内容加密组件、外部密钥文件加载、平台管理命令、轮换及备份恢复测试，并明确下一步业务字段接入方案。没有接入笔记、日记或文档的保存接口；现有云端内容不会因此自动变成密文，本地日记仍默认仅本地。

未创建正式平台密钥，未修改实际 `backend/.env`、MySQL 表、迁移版本或用户数据。本说明是技术交付文档，不是当天工作记录。

## 1. 本次实际完成什么

- 新增 AES-256-GCM 认证加密：密文被修改、密钥错误、对象归属或版本错误时拒绝解密，不返回未经认证的正文。
- 每次写入生成新的 256 位数据密钥 DEK 和 12 字节随机 nonce；使用独立的 256 位平台主密钥 KEK，通过标准 AES Key Wrap 包裹 DEK。
- 密文记录包含版本、算法、主密钥标识、包裹后的 DEK、nonce 和带认证标签的密文，不包含明文主密钥或 DEK。
- 将账号、对象类型、对象 ID、字段名、业务版本与密文头一起纳入 AAD 校验，防止跨账号、跨记录、跨字段替换密文，也拒绝同对象旧版本的直接替换。
- 主密钥只能从项目目录外的受限文件加载；缺配置、文件损坏、权限过宽、缺少旧密钥等情况均停止加密操作，不生成临时替代密钥、不尝试明文保存。
- 平台命令支持创建、检查、生成新轮换文件和备份；只创建新文件，不覆盖原密钥，不向终端打印密钥。
- 验证旧密钥读取、新密钥重加密、独立备份恢复、10 MiB 容量和安全错误响应。

采用的算法由维护中的 `cryptography` 实现，本项目负责封装格式和调用流程，不实现 AES 算法。[AESGCM 官方文档](https://cryptography.io/en/50.0.1/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM)、[AES Key Wrap 官方文档](https://cryptography.io/en/50.0.1/hazmat/primitives/keywrap/)。

## 2. 新增和修改文件

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| `backend/app/core/content_crypto.py` | 新增 | `ContentContext` 定义归属上下文；`ContentCrypto.encrypt/decrypt/rotate` 处理加解密与轮换；`get_content_crypto` 按配置加载并缓存组件 |
| `backend/app/core/content_keyring.py` | 新增 | 密钥环格式、严格校验、文件权限、外部路径限制、只创建新文件；密钥值不进入对象 repr 或错误信息 |
| `backend/scripts/manage_content_keys.py` | 新增 | 平台线下管理命令：`create`、`check`、`rotate`、`backup`，每次校验结果，不输出密钥 |
| `backend/tests/test_content_crypto.py` | 新增 | 文本/二进制往返、认证篡改、上下文替换、格式拒绝、大小边界和密钥轮换等测试 |
| `backend/tests/test_content_keyring.py` | 新增 | 文件权限、配置缺失、JWT 复用拒绝、备份恢复、不覆盖、文件替换及错误响应脱敏测试 |
| `backend/app/core/config.py` | 修改 | 新增可选 `content_keyring_file`；空配置视为未启用，只保存位置，不保存密钥材料 |
| `backend/.env.example` | 修改 | 增加空的 `CONTENT_KEYRING_FILE` 示例和外部路径说明；实际 `.env` 未修改 |
| `backend/requirements.txt` | 修改 | 显式声明 `cryptography>=50.0.1,<51`；本机已有 50.0.1，本次未安装或升级软件包 |
| `.gitignore` | 修改 | 补充常见密钥文件名忽略规则；加载器仍会拒绝项目内的密钥文件，不能只依赖忽略规则 |
| `README.md`、`PROJECT_SPEC.md`、`docs/PRIVACY_STORAGE_PLAN.md` | 修改 | 同步第五步基础能力、业务尚未接入和后续范围 |

没有前端页面、API、数据库模型或 Alembic 文件变更，当前数据库版本仍为 `0013_note_problem_link`。

## 3. 加密和解密流程

```text
未来业务服务先校验登录及记录归属
  → 从可信数据库行构造 ContentContext
  → get_content_crypto()：加载外部主密钥环，首次使用后在进程内缓存
  → encrypt(plaintext_bytes, context)
      生成全新 DEK 和 nonce
      使用活动 KEK 包裹 DEK
      将密文头及 context 编码为 AAD
      AESGCM.encrypt() 生成密文和 16 字节认证标签
      输出 v1 密文 JSON
  → 未来业务事务只保存密文和明确保留的元数据
```

解密时先严格解析格式和大小，再按 `key_id` 查找对应主密钥、解包 DEK，使用业务服务提供的可信上下文进行认证解密。未知格式、额外字段、重复 JSON 键、错误 Base64、截短数据或认证失败全部拒绝；不会把输入当成旧明文返回。

底层组件接收和返回 `bytes`，因此可以处理 UTF-8 文本、序列化 JSON 和二进制文件。它不处理登录、数据库、上传或文件解析，也不代替对象归属鉴权。业务代码必须在有权访问后才调用解密；不能接受客户端随意指定另一个账号的 `ContentContext`。

### 密文格式 v1

以下仅展示字段结构，省略号不是可用密钥或合法密文：

```json
{
  "version": 1,
  "algorithm": "A256GCM",
  "key_wrap": "A256KW",
  "key_id": "content-2026-11-a",
  "wrapped_key": "Base64编码的40字节已包裹DEK",
  "nonce": "Base64编码的12字节随机值",
  "ciphertext": "Base64编码的密文与16字节认证标签"
}
```

`key_id` 是公开版本标识，不能填写密码或密钥。DEK 只以包裹形式随密文保存，KEK 不进入这个 JSON。算法、版本、key_id、wrapped_key、nonce 及业务上下文共同参与认证，正文无需携带账号或本地目录信息。

### 业务上下文

`ContentContext` 包含：

| 字段 | 含义 |
| --- | --- |
| `owner_id` | 当前记录所属的稳定用户 UUID |
| `object_type` | `note`、`journal`、`document` 等对象类型 |
| `object_id` | 业务对象 UUID |
| `field_name` | `payload`、`raw_content`、`preview` 等字段标识 |
| `revision` | 当前业务版本 UUID，阻止同一对象的旧密文直接替换新版本 |

三个 UUID 使用标准小写连字符形式，对象类型和字段名使用受限 ASCII 标识。上下文不会被整体写进密文，但会影响认证结果。备份恢复必须保留相应数据库 ID、版本及应用字段约定；只有一段密文和密钥而没有正确上下文，无法完成认证解密。

示例调用仅用于说明下一步服务如何接入，本次业务接口尚未调用它：

```python
context = ContentContext(
    owner_id=note.user_id,
    object_type="note",
    object_id=note.id,
    field_name="payload",
    revision=note.revision,
)
crypto = get_content_crypto()
encrypted_payload = crypto.encrypt(payload_bytes, context)
original_bytes = crypto.decrypt(encrypted_payload, context)
```

每次加密使用新 DEK，避免把大量内容反复放在同一个 GCM 数据密钥下；nonce 仍由系统安全随机源生成。随机方案的碰撞概率极低，并非数学上绝无碰撞的承诺。平台主密钥用于 AES Key Wrap，不直接反复作为正文 GCM 数据密钥使用。[信封加密与独立 DEK 的说明](https://docs.cloud.google.com/kms/docs/envelope-encryption)。

## 4. 密钥加载和权限

密钥环 v1 结构为 `{ version: 1, active_key_id, keys }`。`keys` 将公开 key ID 映射到 32 字节主密钥的规范 Base64；最多 32 把、文件不超过 64 KiB。重复 key ID、相同材料使用不同 ID、未知活动 ID 或额外字段均拒绝。

本次采用平台受限密钥文件方案，暂未接入 KMS/HSM。加载器限制：

- 必须为绝对路径，解析后位于 `D:\FocusNest` 项目之外；拒绝相对路径和直接符号链接。
- 必须是普通文件，不能是目录或硬链接副本；打开时校验文件身份，并检查读取期间是否发生长度或修改时间变化。
- Windows 检查受保护 DACL，允许的读取主体限定为运行账号、SYSTEM、Administrators；宽泛用户组或继承权限会拒绝加载。创建时先去继承并收紧 ACL，之后才写密钥字节。
- Windows 权限读取使用系统 Windows PowerShell 的 .NET ACL API，子进程隐藏窗口，不依赖 `Get-Acl` 模块自动加载。无法核实权限时拒绝使用文件。
- POSIX 分支要求文件归当前运行账号或 root，且组和其他用户均无权限。此分支本次未在 Linux 实机验收。
- 运行工厂拒绝把 JWT 原始材料、标准 Base64、URL-safe Base64 或十六进制表示复用为内容主密钥；登录密码哈希和 JWT 生成逻辑未修改。
- 不打印文件路径、Base64 密钥、正文或底层异常详情；缺少密钥返回通用错误。

密钥文件所在的父目录、操作系统账号和备份位置也必须由平台收紧权限，避免目录替换、同步或被全盘备份带走。程序不修改既有父目录权限；文件自身的 ACL 不能代替服务器整体访问控制。正式部署优先评估独立密钥服务，不能把“文件在项目外”解释为已经实现 KMS 隔离。[OWASP 的密钥与数据分离、受限权限建议](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)。

## 5. 平台配置和管理命令

以下是供后续启用时执行的操作说明，本次没有在用户机器上创建正式目录或正式密钥。

先由平台准备专用外部目录，例如 `D:\FocusNest-secrets`，限制父目录权限，并确保密钥管理命令与后端使用同一个受控系统账号。目录需已存在；脚本不会自动创建父目录。Windows 由另一个个人账号生成的文件可能无法通过后端账号的权限检查，需要运维调整并重新验证。

在 `D:\FocusNest\backend` 中执行：

```powershell
# 生成正式密钥环，不输出密钥，不覆盖任何已有文件。
.\.venv\Scripts\python.exe scripts\manage_content_keys.py create --file D:\FocusNest-secrets\content-keyring.json --key-id content-2026-11-a

# 检查格式、权限，并逐把密钥进行加解密自检。
.\.venv\Scripts\python.exe scripts\manage_content_keys.py check --file D:\FocusNest-secrets\content-keyring.json
```

之后在实际 `backend/.env` 中只填写文件位置：

```dotenv
CONTENT_KEYRING_FILE=D:/FocusNest-secrets/content-keyring.json
```

不要将 JSON 密钥材料复制进 `.env`，不要沿用 JWT_SECRET 或用户密码。当前尚无业务模块启用加密，不配置此项不会影响现有普通功能；任何代码一旦请求加密组件而配置缺失，会明确失败。

### 轮换

```powershell
.\.venv\Scripts\python.exe scripts\manage_content_keys.py rotate --file D:\FocusNest-secrets\content-keyring.json --output D:\FocusNest-secrets\content-keyring-next.json --key-id content-2026-12-a
```

命令保留源文件不动，生成包含全部旧密钥和新活动密钥的新文件。验证新文件后再修改配置路径，并重启所有后端 worker；组件按进程缓存，不提供隐式热加载或 HTTP 密钥管理端点。

切换活动密钥只影响后续新加密。`ContentCrypto.rotate(envelope, context)` 可以验证原密文、用新 DEK 和当前活动 KEK 重加密，再读回验证；它不写数据库。后续维护服务应在事务中比较原版本及原密文，成功才替换，并保留失败原件。本次没有执行历史记录批量重加密。

旧密钥必须保留，直到在线数据已经迁移，而且仍需恢复的旧备份也有可用密钥。脚本没有删除旧密钥的命令；达到 32 把上限会停止，不自动淘汰。退役前需由平台核对在线引用、备份保留和恢复演练，再在独立存档及活动密钥环中安排处理。

### 备份与恢复

```powershell
# 目标应位于独立、受控的密钥备份位置，且不能已存在。
.\.venv\Scripts\python.exe scripts\manage_content_keys.py backup --file D:\FocusNest-secrets\content-keyring.json --output E:\FocusNest-key-backups\content-keyring-20261105.json

# 恢复前先检查备份；也可用 backup 命令将其复制到新的受限文件。
.\.venv\Scripts\python.exe scripts\manage_content_keys.py check --file E:\FocusNest-key-backups\content-keyring-20261105.json
```

备份文件包含真实主密钥，仍然是敏感材料。以上命令只保证受限文件写入与自检，不替代离线加密备份或专用密钥服务。密钥备份与普通数据库备份分开保存，相关目录、介质和访问由平台负责。恢复时使用包含所需历史 key ID 的有效备份，配置路径后重启全部 worker；再结合对应数据库备份验证实际密文。

如果最新密钥丢失，而备份只包含更旧密钥，新密文无法靠用户登录密码或 JWT 恢复。平台必须在启用新密钥前完成该版本的独立备份。此次测试已实际模拟源密钥文件丢失后，通过另一份受限备份解密原密文；尚未进行正式服务器灾备演练。

## 6. 字段保护范围与下一步数据库方案

以下是本步确定的接入方案，**尚未修改模型、表或 API**。第六步按授权模块实施时再分配实际 Alembic 编号。

| 对象 | 计划纳入密文 | 仍保留或需明确说明的元数据 |
| --- | --- | --- |
| 加密笔记 | 标题和正文合为 JSON `payload` 后加密；不保留同内容明文副本 | 用户/对象 ID、模式、版本、创建/修改时间、置顶、逻辑文件夹和问题关联 ID；现有文件夹名称、关联问题内容不因笔记加密而加密 |
| 可选加密日记 | 标题、正文、需要保密的业务元信息作为 payload；只有用户明确选择时接入 | 日期、归属、版本等查询元数据是否保留明文，在具体开放时显示；默认继续本地，不自动上传 |
| 加密文档原件 | 原始二进制独立加密，title/filename 进入加密元信息 | 对象 ID、用户 ID、模式、版本、时间、必要的类型和大小仍可能可见 |
| 加密文档预览 | 提取文本、预览 JSON、缩略图及持久缓存也需保护，不能沿用明文 `preview_data` | 预览生成时的临时文件、日志和缓存必须一并处理后才能开放功能 |
| 文件夹、标签、问题等 | 本步没有加密；标签不是本次接入项 | 必须在 UI 中说明实际保护范围，不能将关联对象统称为“全部加密” |

先接入笔记时，计划新增明确的 `storage_mode` 和 `encrypted_payload`（MySQL MEDIUMTEXT）；加密模式下现有明文 `title`、`content` 应允许置空，并通过数据库约束确保明文和密文来源互斥。普通笔记继续原样保存。未来如增加可索引的加密版本/key ID 元数据，读取仍须验证密文头，不能将索引当作认证结果。

普通标题字段为 `VARCHAR(200)`，不能直接改存密文。加密正文也不能继续以明文参与全文搜索或预览缓存；首版优先按更新时间分页，明确限制 SQL 标题/正文搜索。是否提供受限的解密搜索要在第六步独立评估，不通过保留明文影子字段维持旧查询。

文档后续需要将在线明文 `raw_content`、`title`、`filename` 与加密来源分开，给原件和预览安排合适的密文列并校验模式互斥。当前 10 MiB 限制应继续指原始文件大小，不能把加密后大小套回旧原件字段约束。业务接入还需逐一检查 Dashboard、下载、预览和导出路径。

### 实际容量验证

使用 64 字符 key ID（允许的最长 ID），只输出大小、不输出测试密钥或密文，实际测得：

| 明文 | 明文字节数 | v1 JSON 密文字节数 |
| --- | ---: | ---: |
| 空字节串（仅底层组件允许） | 0 | 271 |
| 200 个 emoji 标题 + 100000 个 emoji 正文，紧凑 UTF-8 JSON | 400825 | 534703 |
| 10 MiB 二进制文档 | 10485760 | 13981283 |

GCM 增加 16 字节标签，Base64 约膨胀三分之一，还要加上已包裹 DEK 和格式头。当前最大文档的 v1 文本密文低于 MEDIUMTEXT/MEDIUMBLOB 的 16777215 字节容量；上述笔记载荷也在范围内。不能因此推断所有未来附件组合或预览都一定符合限制；组件对单个明文载荷严格限制 10 MiB，业务层仍须单独验证。

## 7. 错误、测试和验证边界

| 错误码 | 含义 |
| --- | --- |
| `503 / 50330` | 内容密钥不可用或非法，包括缺文件、权限不合格、缺旧 key ID、拒绝复用 JWT 材料 |
| `422 / 42230` | 密文/上下文不合规，或认证失败；不向调用者区分错误密钥、篡改、错误对象等细节 |
| `422 / 42231` | 明文载荷类型不是 bytes 或超过 10 MiB |

验证实际结果以最后回归为准：

- 新增加密及密钥管理测试共 54 项；覆盖文本/二进制/空载荷、随机性、独立库解密验证、nonce/密文/DEK 篡改、跨用户/对象/字段/版本替换、损坏格式、错误和缺失密钥、大小边界。
- 密钥文件测试在 Windows 真实临时文件上执行：先限制 ACL 再写入、过宽/继承权限拒绝、已有文件不覆盖、检查过程中替换文件拒绝、JWT 各种表示复用拒绝、源文件丢失后从受限备份解密。
- 已有 API 异常处理器测试确认，密钥路径、密钥值及输入明文不出现在错误响应或捕获日志中。测试路由仅在测试内构造，没有加入产品 API。
- 最终完整后端测试：239 项通过、9 项跳过；跳过项需要 MySQL 并发等额外条件。Ruff 代码检查与格式检查通过。
- 依赖使用本机现有 `cryptography 50.0.1`，Python 3.14；没有变更前端，本步未重复前端构建或浏览器页面验收。

仍未执行：业务模块加密接入、真实用户历史内容重加密、数据库结构迁移、KMS/HSM 接入、Linux 实机权限检查、正式服务器密钥部署/备份灾备演练。没有创建正式密钥或加密用户内容，因而也不能宣称“目前数据库中的日记、笔记、文档已经加密”。

这属于服务器端静态内容加密：授权的服务进程会解密，有服务器权限的运营者仍可能读取；它不提供端到端加密或对已完全失陷服务器的保护。Python 进程内会暂时持有明文和密钥，未提供可验证的内存清零或 HSM 隔离。

## 8. 新增知识和语法

| 知识 / 写法 | 本次用途 |
| --- | --- |
| AES-GCM 与认证标签 | 同时保护内容和检测篡改；解密认证完成后才返回数据 |
| 信封加密、DEK、KEK | 每次用独立数据密钥加密正文，平台主密钥负责包裹数据密钥 |
| AAD | 不加密账号/对象标识，但将它们与密文绑定；换个账号或字段就无法认证 |
| `@dataclass(frozen=True)` | 固定上下文与密钥环属性，减少意外修改；不等同于安全隔离 |
| `field(repr=False)`、`Field(repr=False)` | 避免对象常规打印带出密钥或配置路径；不会自动保护所有手工导出 |
| `MappingProxyType` | 将复制后的密钥映射设为只读，防止外部字典后续修改影响组件 |
| `@lru_cache` | 每个进程只加载一次组件；更换密钥文件后需要重启 worker |
| `object_pairs_hook` | JSON 解析时识别重复字段，避免相同名字被悄悄覆盖 |
| `O_CREAT | O_EXCL`、`fsync` | 只创建新密钥文件、拒绝覆盖，并要求操作系统同步写入 |
| `raise ... from None` | 对外保留统一错误，避免底层解析异常展示输入或内部信息；不是内存擦除 |
| 活动密钥与历史密钥 | 新写入使用活动 key ID；旧数据仍按各自 key ID 解密，不能换新后立即丢弃旧钥 |

下一步为第六步“业务模块接入保存方式选择”，优先实现笔记加密模式及相应字段/接口。需要继续授权后实施；第五步不会自动改变任何现有内容的保存方式。

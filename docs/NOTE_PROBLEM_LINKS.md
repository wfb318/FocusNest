# 笔记关联问题：修改清单与代码说明

日期：2026-11-04。范围为用户要求的笔记关联扩展，未推进 Phase 8。

## 使用

笔记编辑器上方新增“关联问题”：

1. **问题类型**：全部问题、今日问题、历史问题、已解决，用于筛选候选问题。
2. **问题选择**：选择具体问题，也可选择“不关联问题”。每篇笔记可关联一个问题，一个问题可被多篇笔记关联。
3. 点击原有“保存笔记”后生效；新建、导入、放弃修改和未保存提示沿用笔记原有流程。

支持内容搜索及分页加载更多，候选项每次 20 条；不会只允许选择第一页的问题。切换类型或搜索不会自动清除已经选好的关联，筛选结果以外的当前关联会单独保留为选项。

阅读模式展示关联问题原文、当前类型、创建时间及适用时的解决时间，可点击“刷新问题状态”重新读取。问题归入历史或标记解决后，笔记仍关联同一条问题。类型是问题当前状态/日期的分类，不额外存一份容易过期的类型标签。

关联不会自动解决问题，也不会改写问题内容。解除关联只修改笔记的关联 ID，不删除笔记或问题。

## 新增文件（3 个源代码/测试文件）

| 文件 | 作用 |
| --- | --- |
| [0013_note_problem_link.py](/D:/FocusNest/backend/alembic/versions/0013_note_problem_link.py) | 笔记增加可空问题外键及索引；已有笔记默认不关联 |
| [NoteProblemLink.vue](/D:/FocusNest/frontend/src/components/NoteProblemLink.vue) | 类型筛选、问题选择、搜索、加载更多、关联详情和只读展示 |
| [test_note_problems.py](/D:/FocusNest/backend/tests/test_note_problems.py) | 保存/读取/列表、解除、旧客户端兼容、账号隔离、版本冲突、跨日/解决后保留关联、外键行为 |

## 修改文件（9 个源代码文件）

| 文件 | 主要修改 |
| --- | --- |
| [models/note.py](/D:/FocusNest/backend/app/models/note.py) | `problem_id` 可空外键，索引及 ON DELETE SET NULL |
| [schemas/note.py](/D:/FocusNest/backend/app/schemas/note.py) | 创建/更新请求和详情/列表响应增加 problem_id |
| [repositories/notes.py](/D:/FocusNest/backend/app/repositories/notes.py) | 精简列表查询包含 problem_id |
| [services/notes.py](/D:/FocusNest/backend/app/services/notes.py) | 创建/修改关联前校验问题属于当前用户；省略字段时保留旧关联 |
| [services/problems.py](/D:/FocusNest/backend/app/services/problems.py) | 新增 get_problem，读取自己的一条问题 |
| [endpoints/problems.py](/D:/FocusNest/backend/app/api/v1/endpoints/problems.py) | 新增 GET /problems/{problem_id} |
| [types/note.ts](/D:/FocusNest/frontend/src/types/note.ts) | NoteInput/NoteSummary 增加关联字段 |
| [api/problems.ts](/D:/FocusNest/frontend/src/api/problems.ts) | 新增 getProblem 详情请求 |
| [NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 接入关联组件；表单、dirty 判断、apply/reset/save 包含关联字段 |

另新增本说明与截图，同步 README、PROJECT_SPEC 功能与迁移入口。没有新增依赖。

## 数据库和 API

已执行迁移：`0012_problem_memos` → `0013_note_problem_link`。

- `notes.problem_id`：String(36)，允许 NULL，外键指向 problems.id。
- `ix_notes_problem_id`：关联索引。
- `fk_notes_problem`：问题被移除时清空关联，保留笔记；当前问题页面仍未提供删除入口。
- 若还有关联数据，迁移降级会拒绝静默丢掉关联列，需先解除关联。

原有笔记 POST/PUT 接受 `problem_id: "问题 UUID"` 或 null。PUT 中省略该字段时保持原值，兼容旧版本客户端；明确传 null 才解除。类型筛选值不发送给笔记保存接口。

新增 `GET /api/v1/problems/{id}`，只允许读取当前账号的问题，返回内容、状态、日期和 revision，沿用 no-store 响应与登录校验。候选列表继续复用原有 GET /problems 的 bucket/q/page 参数。

后端不只依赖前端候选项：创建和修改关联会锁定用户行，核对问题所属用户并加锁读取；不存在或属于他人的问题返回 404。旧 revision 修改笔记仍返回 409。读取问题解决状态不会改写笔记 revision。

## 流程与知识点

```text
选择问题类型 → NoteProblemLink.load → listProblems(bucket, query, page)
选择问题 → update:modelValue → NotesView.form.problem_id → dirty=true
保存笔记 → 原 createNote/updateNote → NoteCreate/NoteUpdate
  → check_problem 所有权校验 → notes.problem_id → MySQL

重新打开笔记 → apply 恢复 problem_id
  → NoteProblemLink.refreshSelected → getProblem → 当前内容/状态/日期
```

- **可空外键**：用一个问题 ID 建立关系，避免把问题正文复制到每篇笔记后产生不一致。
- **`model_fields_set`**：区分“没提交字段”和“提交 null”；旧客户端编辑与显式解除关联语义不同。
- **组件 v-model**：`modelValue` 为父级当前值，`update:modelValue` 把选择结果交回笔记表单，统一走手动保存。
- **筛选状态与业务关联分离**：切换分类只改变候选列表，实际选择 ID 不被悄悄清空。
- **异步版本号**：列表和详情各用请求版本，避免快速切换类型/笔记时旧响应覆盖新结果；卸载后丢弃迟到响应。
- **按需读取**：笔记列表只包含问题 ID，打开笔记才读取问题详情，避免列表逐条查询正文。
- **纯文本展示**：问题内容通过 Vue 插值展示，不以 HTML 插入。

## 已实际验证

- 原有笔记 SQLite 测试 **19 项通过**，新增关联测试 **4 项通过**。
- MySQL 全量 **197 项通过**，包括旧业务及新增关联用例；前端 **29 项通过**，类型检查和生产构建通过。
- Alembic 已应用，`alembic check` 确认模型与数据库没有遗漏操作；修改的后端文件 Ruff 检查通过。
- 浏览器临时账号实测：20/24 分页加载更多、历史问题筛选、选择后切换“已解决”仍保留关联、保存后刷新并重新打开、阅读模式展示、解除关联后正文保留。
- 验收页未记录到 console error。所有窄屏/字体组合、离线下所有请求返回时序未逐项人工测试。
- 临时账号使用 localhost 来源隔离用户正在使用的 127.0.0.1 登录和外观，未修改用户真实笔记或问题。临时账号、测试业务记录、脚本和元数据已清理。

截图：[笔记问题选择界面](/D:/FocusNest/docs/screenshots/note-problem-link.png)。

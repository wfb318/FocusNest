# 笔记导入：功能、代码与知识点

日期：2026-11-01。属于 Notes 的追加能力，未开始独立的 Phase 6 Documents 资料库。

## 使用

笔记页右上角点击“导入文档”，选择一个 UTF-8 编码的 `.md`、`.markdown` 或 `.txt` 文件。文件名（去扩展名）作为标题，原文填入编辑器，默认归入选择文件时的当前文件夹；全部笔记或未分类视图下默认未分类。

导入只生成一篇新草稿，不会直接覆盖原有已保存笔记。预览、修改标题与文件夹后点击“保存笔记”，才会经现有 POST /notes 接口写入数据库。有未保存修改时先确认，取消继续保留原草稿。

限制：单个文件最大 512 KB，正文最多 100000 Unicode 码点，不能全为空白。超过上限会拒绝，不会截断正文。标题超过 200 码点时取前 200，导入后可编辑。编码不支持时提示另存为 UTF-8。

本次没有实现 PDF、Word、图片、附件、批量导入、目录导入或 Obsidian 图片资源同步。用户可先将其他文档导出为 Markdown/TXT。导入的本地文件不作为附件上传，只有点击保存后笔记文本才发送至现有业务 API。预览共用受限 Markdown 渲染器，原 HTML 不执行、图片不自动加载；TXT 原文保留，但预览也按 Markdown 解释。

## 新增和修改文件

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| 新增 | [utils/noteImport.ts](/D:/FocusNest/frontend/src/utils/noteImport.ts) | `readNoteFile` 校验并读取文件，生成标题与正文；导出文件大小限制和 accept 配置 |
| 新增 | [tests/noteImport.test.mjs](/D:/FocusNest/frontend/tests/noteImport.test.mjs) | 5 项导入测试，覆盖文本保持、格式、编码、大小、Unicode 边界与读取失败 |
| 修改 | [views/NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 导入按钮、隐藏 file input、说明、`importFile()`、未保存确认及文件夹关联 |
| 修改 | [package.json](/D:/FocusNest/frontend/package.json) | npm test 增加新测试文件，不增加依赖 |

另新增本说明，README 添加使用说明；验收截图为 `docs/screenshots/note-import.png`，截图中的导入内容为未保存测试草稿。

后端、数据库模型、迁移、认证、文件夹接口均未改动。

## 代码流程

1. `importPicker` 引用文件控件，点击按钮调用 click 打开选择框。
2. input change 触发 `NotesView.importFile(event)`，取得第一个文件后清空 input.value，支持重复选择同一文件。
3. 记录选择时的 targetFolder，设置 busy，调用 `readNoteFile(file)`。
4. `readNoteFile` 依次检查扩展名和字节数、读取 arrayBuffer、严格解码 UTF-8、检查不支持的控制字符、非空正文和长度，再生成标题。
5. 文件通过校验后才调用 `mayDiscard()`。文件无效时不会弹出放弃修改确认，也不会清空原内容。
6. 用户允许继续，且页面没有卸载，则 `apply(null)` 清除旧笔记身份，填入新标题、正文和 folder_id，进入编辑模式。
7. 此时 saved 为 null、dirty 为 true。点击保存沿用原 `save()` → `createNote()`；如果不保存，导入草稿仍受原路由离开和关闭页面提示约束。
8. catch 显示文件错误，finally 恢复 busy。disposed 检查防止文件读取完成后更新已卸载的页面。

特别注意：`apply(null)` 在校验和确认之后才执行，并且将 saved 置空，所以导入不会对原笔记 id 发 PUT 更新。

## 关键知识与语法

### 文件选择与本地读取

`<input type="file">` 只允许读取用户主动选择的文件。accept 是选择框提示，不能代替代码校验，因此 `readNoteFile()` 还检查扩展名。文件不进入 localStorage 或 IndexedDB，没有自动保存本地草稿。

```typescript
const file = input.files?.[0]
input.value = ''
```

可选链在用户取消选择时安全返回 undefined。清空 input.value 只重置控件，不会删除磁盘文件。

### 字节、编码与字符

```typescript
const content = new TextDecoder('utf-8', { fatal: true })
  .decode(await file.arrayBuffer())
```

arrayBuffer 得到文件原始字节，TextDecoder 按 UTF-8 转为字符串；fatal:true 遇到非法字节就失败，防止乱码被默默保存。UTF-8 BOM 可正常处理。GBK、UTF-16 文本需先另存编码。

`file.size` 是字节数，正文上限是字符数，两者不同。`Array.from(content).length` 按 Unicode 码点计数，和 Python len 的常见 Unicode 计数对应；JavaScript 普通 string.length 按 UTF-16 单元计数，一个 emoji 往往占两个单元。页面原字符计数及 maxlength 仍沿用旧实现，含 emoji 时可能比接口上限更保守。

正文原样保留，不调用 trim 后再保存；trim 仅用于检查是否全为空白。因此 Markdown 缩进、CRLF 和行尾空格不被去除。控制字符检查会拒绝 NUL 等二进制特征，保留制表符和正常换行。

### 扩展名和标题处理

`/\.(md|markdown|txt)$/i` 以结尾扩展名匹配，i 表示忽略大小写。移除末尾扩展名、路径分隔部分和控制字符后，将文件名作为标题；空标题回退为“导入的笔记”。只截断标题，不截断正文。

### 异步操作与草稿保护

`await readNoteFile()` 先完成文件校验，再 `await mayDiscard()` 等待用户选择。busy 阻止重复导入、保存等操作，避免异步读文件时互相覆盖。取消确认时不执行 apply；读取失败只写 error，保留表单。

文件夹 id 在开始处理时记录，避免异步读取期间点击其他目录使目标突然变化。若目标文件夹后来被另一页面删除，保存时由既有后端归属/存在性校验拒绝，输入仍保留，用户可以改选目录。

## 实际验证

- vue-tsc 与 Vite 生产构建通过。
- npm test 共 **10 项通过**：原 Markdown 3 项、目录树 2 项、新增导入 5 项。
- 新增测试包括：Markdown 缩进/换行/HTML 文本保持；TXT、markdown 扩展名和 BOM；空白、非法格式、二进制控制字符、UTF-16、文件过大、正文过长；10 万 emoji 上限和长标题；读取失败与空文件名回退。
- 浏览器验证导入 Markdown、显示预览、归入当前已有文件夹、显示“尚未保存”提示；TXT 导入前出现草稿确认；取消保留 Markdown；重复选择同一 TXT 并确认后读入 TXT。
- 浏览器检查未记录到控制台 error。临时 Markdown/TXT 文件已经清理，测试草稿已放弃，没有点击保存，没有新建或修改服务器笔记。
- 导入后的实际持久化保存沿用原流程，本次没有再次在浏览器执行保存/刷新读回；拖拽和批量导入不在范围内。

后续如需 PDF/Word 解析，可在明确格式需求后独立扩展，不把二进制文件当纯文本读取。

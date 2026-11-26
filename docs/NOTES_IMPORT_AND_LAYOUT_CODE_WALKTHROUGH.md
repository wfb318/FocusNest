# 笔记文档导入与左右布局：修改总结和代码整理

日期：2026-11-01。

本次记录范围：上一份界面与磨砂总结之后追加的**笔记文档导入**和**左侧文档列表、右侧限高内容区**。不重复把前面的文件夹和外观模块记为新开发。整理依据当前源码及本次对话中可核实的执行结果。

## 1. 完成了哪些修改

### 文档导入

- 右上角新增“导入文档”，支持 UTF-8 编码的 `.md`、`.markdown`、`.txt`。
- 文件名生成标题，文件原文填入编辑器，默认归入选择文件时选中的文件夹。
- 导入生成一篇新草稿，预览确认并点击保存后才写入数据库。
- 原来有未保存的输入时先确认；取消保留输入，无效文件不会清空原草稿。
- 单文件最大 512 KB、正文最多 100000 Unicode 码点；过大、非法编码、空白内容等明确报错，正文不静默截断。

### 布局和阅读体验

- 把原本位于编辑器下方的笔记列表移到左侧文件夹栏下方。
- 搜索、只看置顶和分页跟随列表一起移到左侧。
- 点击目录后显示该目录的直属笔记；全部笔记仍可跨文件夹显示。
- 正在打开的笔记高亮，同时添加 aria-current，便于识别当前项。
- 右侧阅读/编辑区高度受限，长文在容器内滚动，不再把整个页面撑成长文长度。
- 切换笔记回到新文档顶部，仍沿用原来的未保存修改确认。
- 文本框和预览也限制高度；保存/放弃按钮在编辑区域内使用 sticky 定位。

## 2. 新增、修改文件清单

功能代码：新增 **2 个文件**，修改 **2 个文件**。没有新增依赖。

| 类型 | 文件 | 作用 |
| --- | --- | --- |
| 新增 | [utils/noteImport.ts](/D:/FocusNest/frontend/src/utils/noteImport.ts) | 文件格式、字节数、编码、控制字符、正文长度校验，以及生成标题 |
| 新增 | [tests/noteImport.test.mjs](/D:/FocusNest/frontend/tests/noteImport.test.mjs) | 导入逻辑的 5 项自动测试 |
| 修改 | [views/NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 导入入口和事件处理；左侧列表；限高滚动；文档切换复位 |
| 修改 | [package.json](/D:/FocusNest/frontend/package.json) | npm test 加入导入测试文件 |

说明与截图：

- README 新增笔记导入入口和格式说明。
- [NOTE_IMPORT.md](/D:/FocusNest/docs/NOTE_IMPORT.md) 记录导入实现。
- [PHASE5_NOTE_FOLDERS.md](/D:/FocusNest/docs/PHASE5_NOTE_FOLDERS.md) 追加列表布局说明，历史章节仍保留。
- 本文件统一整理这两轮修改。
- `docs/screenshots/note-import.png`：导入测试草稿的页面截图。
- `docs/screenshots/notes-sidebar-layout.png`：左侧列表和右侧阅读区截图。

后端代码、数据库结构、Alembic 迁移和 API 契约均未修改。背景和磨砂参数也没有因本次笔记布局而改动。

## 3. 文件导入代码分解

### 3.1 noteImport.ts：单独负责读取文件

```typescript
export const MAX_IMPORT_BYTES = 512 * 1024
export const IMPORT_ACCEPT = '.md,.markdown,.txt'
export interface ImportedNote { title: string; content: string }
```

MAX_IMPORT_BYTES 是文件体积上限；IMPORT_ACCEPT 用在文件选择框；ImportedNote 说明读取成功后返回标题和正文，不包含数据库 id、版本或用户信息。

`readNoteFile(file)` 的处理顺序：

1. 正则检查扩展名，忽略大小写。
2. 判断 file.size 是否超过 512 KB。
3. 读取 ArrayBuffer，严格按 UTF-8 解码。
4. 拒绝 NUL 等二进制/不支持的低位控制字符，允许正常换行和制表符。
5. 检查正文非空、长度不超过 100000 码点。
6. 从文件名去除扩展名、路径分隔部分、控制字符和首尾空白，生成标题。
7. 标题最多 200 码点，空标题回退为“导入的笔记”；正文返回原文。

```typescript
new TextDecoder('utf-8', { fatal: true })
  .decode(await file.arrayBuffer())
```

file.arrayBuffer() 得到二进制字节，TextDecoder 将字节解释为文本。fatal:true 在遇到非法编码时抛出错误，避免把乱码保存成笔记。UTF-8 BOM 可以处理，GBK/UTF-16 文件需要先另存为 UTF-8。

这里没有调用后端，也没有保存文件。读取成功只产生一个普通对象，页面决定如何使用它。

### 3.2 NotesView.vue：导入行为与草稿保护

新增 `importPicker` 模板引用，按钮调用文件 input 的 click 打开选择框：

```vue
<input ref="importPicker" type="file"
       :accept="IMPORT_ACCEPT" @change="importFile">
```

accept 是选择框过滤提示，实际是否合法仍由 readNoteFile 检查。

`importFile(event)` 主要做五件事：

1. 获取选中的第一个文件并重置 input.value，支持重复选择同一个文件。
2. 保存当前 targetFolder，设置 busy，避免重复导入或同时保存。
3. 先校验和读取文件，成功后才调用 mayDiscard 询问是否放弃未保存修改。
4. 用户允许后执行 apply(null)，清除旧笔记身份，再填写标题、正文和文件夹。
5. 切回编辑模式、滚到顶部，提示“新笔记草稿，尚未保存”；finally 解除 busy。

关键顺序：

```typescript
const imported = await readNoteFile(file)
if (disposed || !(await mayDiscard()) || disposed) return
apply(null)
form.title = imported.title
form.content = imported.content
form.folder_id = targetFolder
```

先校验、再确认、最后替换表单。无效文件和用户取消时不会执行 apply(null)，所以不会丢失原输入。两次 disposed 检查分别覆盖文件读取完成及等待用户确认完成的时刻。

`apply(null)` 将 saved 置空。之后点击保存时会进入原有 createNote 分支，创建新笔记；不会拿原笔记 id 发更新请求。

### 3.3 保存沿用原有业务

```text
用户选择文件
  → importFile()
  → readNoteFile()
  → 必要时 mayDiscard()
  → 填写新草稿
  → 用户点击“保存笔记”
  → 原有 save()
  → api/notes.ts 的 createNote()
  → 后端原有 POST /api/v1/notes
  → 原有用户、文件夹与字段校验
  → 原有数据库保存流程
```

导入阶段只在本机读取文件；点击保存后，笔记标题和正文才发送给现有 API。不会把原文件作为附件上传，也没有自动保存导入草稿。

## 4. 左侧列表和右侧滚动代码分解

### 4.1 页面结构调整

原布局：

```text
左：文件夹       右：编辑器
                    ↓
                  笔记列表
```

当前布局：

```text
左：文件夹       右：限高的编辑/阅读容器
    搜索             长内容在内部滚动
    笔记列表
    分页
```

列表仍使用原 records、page、total、filters 和 loadList，没有重新实现一套数据请求。

左侧宽度从 230px 调整为 290px，给文档标题和搜索框留空间。标题、更新时间、打开状态采用纵向紧凑排列。选中文档的判断是：

```vue
:class="{ current: saved?.id === note.id }"
:aria-current="saved?.id === note.id ? 'true' : undefined"
```

current 决定高亮，aria-current 向辅助技术标明当前项。点击还是调用原 openNote(note.id)，所以保存状态和离开确认继续生效。

### 4.2 高度与滚动

```css
.notes-content .editor-panel {
  height: clamp(420px, calc(100dvh - 280px), 900px);
  overflow: auto;
  overscroll-behavior: contain;
  overflow-anchor: none;
  scrollbar-gutter: stable;
}
```

- clamp：内容区高度最低 420px，优先使用动态视口高度减 280px，最高 900px。
- overflow:auto：内容超出时由这个容器滚动。
- overscroll-behavior:contain：滚到容器边缘时减少滚动继续传给外层页面。
- overflow-anchor:none：避免浏览器自动锚定旧内容而干扰滚动复位。
- scrollbar-gutter:stable：预留滚动条位置，减少出现滚动条时左右跳动。

左侧栏也有视口相关最大高度和内部滚动；文件夹分类区域单独限高。小于等于 1100px 使用上下单栏，左栏最大 48dvh、内容区最大 80dvh。420px 下限意味着特别矮的桌面视口仍可能需要滚动外层页面，不应理解成所有屏幕都完全没有页面滚动。

正文 textarea 最小高度 240px、优先 32dvh、最高 55dvh；预览最大 55dvh。保存按钮区使用 position:sticky 和 bottom，停留范围受所在表单区域约束，并不是固定在整个窗口上。

### 4.3 为什么换文档能回到顶部

模板增加：

```vue
<section ref="editorPanel"
         :key="saved?.id ?? 'draft'"
         tabindex="0"
         class="panel editor-panel">
```

每篇已保存文档有不同 id，key 改变时 Vue 重建对应的内容容器，避免旧文档滚动状态被复用。草稿使用 draft 这个固定 key。

openNote 中更新数据和模式后：

```typescript
await nextTick()
editorPanel.value?.scrollTo({ top: 0 })
```

nextTick 等 Vue 把新文档对应的 DOM 更新完成，再取得当前容器并滚到顶部。导入也是同样处理，因此在不同新草稿间切换也能复位。

tabindex=0 让阅读容器可通过键盘聚焦并滚动。它不会修改文档内容。

## 5. 本次知识与语法速查

| 代码/知识 | 含义与用途 |
| --- | --- |
| File / ArrayBuffer / TextDecoder | 用户选中文件 → 原始字节 → 可显示字符串 |
| `file.size` | 文件字节数，不是正文字符数 |
| `Array.from(content).length` | 按 Unicode 码点计数；emoji 与 JavaScript string.length 的结果可能不同 |
| `content.trim()` | 这里只用来检测全空白，没有把 trim 后的文本替代正文 |
| `/\.(md|markdown|txt)$/i` | 匹配结尾扩展名，忽略大小写 |
| `input.files?.[0]` | 用户取消选择时安全返回 undefined |
| `input.value = ''` | 重置文件选择控件，不删除磁盘文件 |
| `await mayDiscard()` | 等待用户在确认框选择，再决定是否替换草稿 |
| `ref<HTMLElement \| null>` | 保存容器 DOM 引用，挂载前可以为空 |
| `await nextTick()` | 等待 Vue 完成当前 DOM 更新 |
| `:key="saved?.id ?? 'draft'"` | 根据笔记身份决定复用或重建容器；空值使用 draft |
| `scrollTo({ top: 0 })` | 让容器滚动到顶部 |
| `:class="{ current: ... }"` | 按条件添加高亮样式 |
| `clamp()` / `calc()` / `dvh` | 上下界约束、尺寸计算和动态视口高度 |
| `minmax(0,1fr)` | Grid 中让内容列可收缩，减少长内容撑破布局 |
| `repeat(auto-fit,minmax(...))` | 按可用空间自动安排正文和预览列 |
| `position:sticky` | 元素在所属滚动区域中滚动到指定位置后保持可见，受父容器边界约束 |

## 6. 实际验证结果

### 已执行

- 文档导入代码完成后运行前端构建，vue-tsc 和 Vite 通过。
- npm test **10 项通过**：Markdown 3 项、目录树 2 项、文档导入 5 项。
- 导入测试覆盖缩进/CRLF/行尾空格/HTML 文本保持、TXT 与 BOM、错误格式/编码/空白/二进制/过大/过长、Unicode 边界、读取失败及空标题回退。
- 浏览器验证 Markdown 导入、预览、归入当前文件夹、未保存提示、取消替换保留草稿、重复选择 TXT 并确认替换。
- 临时文件和未保存验收草稿已清理；没有点击保存，没有创建或修改服务器中的测试笔记。
- 布局最终修改后再次运行构建，vue-tsc 和 Vite 通过。
- 浏览器确认列表位于左侧栏；只读打开现有长文，正文容器约 438px、内部内容高度超过 37000px。
- 把第一篇滚到底部后从左侧切换另一篇，最终读取到新容器 scrollTop=0，证明切换复位生效。
- 布局验收只读取现有文档，没有修改或提交正文。

### 尚未验证或未实现

- 未在本轮浏览器中再次测试导入后实际保存、刷新后读回；保存复用既有 API，但不能把复用记成此次已验收。
- 窄屏样式已实现，未单独进行手机视觉验收。
- 文档超过一页的实际多页列表交互未在本轮浏览器中重新验收；原分页逻辑继续使用。
- PDF、Word、图片、附件、批量和拖拽导入，以及 Obsidian 资源目录同步未实现。
- 本次整理文档没有重新运行代码测试，也没有再次操作用户笔记。

## 7. 使用方式与下一步

先保存当前草稿，再刷新笔记页。左边选文件夹和具体笔记，右边阅读或编辑。导入文档后检查标题、正文及所属目录，再手动保存。

下一步可以由用户决定是否增加批量导入、PDF/Word 解析或目录拖拽；本次没有自动进入新阶段。新的工作记录只在明确要求或结束当天对话时生成。

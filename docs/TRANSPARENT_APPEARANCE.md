# 透明导航、极浅磨砂和文字样式设置

日期：2026-11-01。本次为外观调整，没有新增业务模块、API 或 MySQL 迁移。

## 实现效果

- 左侧主导航、文件夹栏、资料列表栏及右侧页面标题使用纯透明背景，取消模糊、阴影和块状选中底色。
- 当前页面/文档通过加粗和细线标记；悬停通过下划线反馈，不再出现磨砂按钮底。
- FocusNest 品牌区域保留约 12% 底色、2px 模糊，适度突出。
- 正文与功能面板降到约 14% 底色、2px 模糊，输入框使用 20% 底色；弹窗由更高不透明度降至 40%、3px 模糊。
- 普通按钮、操作工具栏、提示条、标签和页头背景透明；编辑器保存区改为正常文档流，避免透明悬浮按钮与正文重叠。
- 新增字号比例 80%–150%、文字颜色、磨砂背景颜色，提供局部样式预览、保存与恢复默认。
- 字号保留原有主标题、正文、小字层级；标题、按钮、输入框、Markdown、代码块等按比例变化。
- 大字号时侧栏宽度适度增长，手机端仍使用全宽导航布局。

设置位置：“设置与外观” → “文字与磨砂样式”。选择后点击“保存文字与磨砂样式”；“恢复默认文字与磨砂”只恢复字号与两种颜色，不删除背景。

颜色选择改变普通文字、链接及磨砂表面；危险操作/部分业务状态保留语义色。深色背景可选浅色文字，浅色背景可选深色文字。没有自动保证任意背景和颜色组合的对比度，保存前可看预览。

## 文件清单

新增 2 个文件：

- [utils/appearanceStyle.ts](/D:/FocusNest/frontend/src/utils/appearanceStyle.ts)：DEFAULT_STYLE、StylePreferences、normalizeStyle、styleVariables。
- [tests/appearanceStyle.test.mjs](/D:/FocusNest/frontend/tests/appearanceStyle.test.mjs)：默认值、比例边界、颜色校验、CSS 变量生成测试。

修改 11 个已有源代码/配置文件：

| 文件 | 修改 |
| --- | --- |
| [stores/appearance.ts](/D:/FocusNest/frontend/src/stores/appearance.ts) | 字号/颜色状态与持久化，saveStyle，兼容旧设置；换背景或重置背景时保留文字样式 |
| [App.vue](/D:/FocusNest/frontend/src/App.vue) | watchEffect 将样式映射为根元素 CSS 变量 |
| [components/AppearanceSettings.vue](/D:/FocusNest/frontend/src/components/AppearanceSettings.vue) | 字号滑块、颜色控件、预览与保存/恢复按钮 |
| [assets/main.css](/D:/FocusNest/frontend/src/assets/main.css) | 透明导航、轻磨砂、字体缩放、主题颜色、侧栏尺寸与控件样式 |
| [views/NotesView.vue](/D:/FocusNest/frontend/src/views/NotesView.vue) | 既有字体尺寸/颜色改为变量表达式，业务逻辑不变 |
| [views/JournalView.vue](/D:/FocusNest/frontend/src/views/JournalView.vue) | 同上 |
| [views/TasksView.vue](/D:/FocusNest/frontend/src/views/TasksView.vue) | 同上 |
| [views/FocusView.vue](/D:/FocusNest/frontend/src/views/FocusView.vue) | 同上，计时数字也按比例缩放 |
| [views/DocumentsView.vue](/D:/FocusNest/frontend/src/views/DocumentsView.vue) | 同上 |
| [components/DocumentContent.vue](/D:/FocusNest/frontend/src/components/DocumentContent.vue) | 预览文字/表格字号和普通颜色使用变量 |
| [package.json](/D:/FocusNest/frontend/package.json) | 测试脚本加入 appearanceStyle 测试，无新依赖 |

相关文档 README、APPEARANCE 更新入口说明。没有改动用户内容、背景文件、视频播放逻辑、文档解析或数据库。

## 设置保存流程

1. 组件 draftStyle 保存正在选择的字号与颜色，只影响局部预览。
2. 保存时调用 appearance.saveStyle(draftStyle)。
3. normalizeStyle 将字号限制在 0.8–1.5，只允许完整 #RRGGBB 颜色；非法/缺失值回退默认，避免把任意字符串拼进 CSS。
4. 读取已有 IndexedDB 记录，保留 image、poster、kind、paused、veil，只追加/更新 fontScale、textColor、glassColor。
5. 事务完成后更新 stylePreferences，不重新调用媒体 apply，因此不重建背景 URL、不重启视频。
6. App 的 watchEffect 调用 styleVariables，使用 document.documentElement.style.setProperty 更新 CSS 自定义属性。
7. 页面和各组件使用变量立即重绘；刷新时 initialize 读取并 normalize 旧记录，没有新字段的记录使用默认值。

默认：fontScale=1，textColor=#263c34，glassColor=#ffffff。现有背景仍沿用同一个 IndexedDB 库与数据键，没有版本升级要求。

## 字体缩放代码

```css
:root { font-size: calc(16px * var(--ui-font-scale, 1)); }
/* 原来的 14px 仍保留其字号层级，只增加统一比例。 */
.example { font-size: calc(14px * var(--ui-font-scale, 1)); }
```

仅修改根字号不足以缩放原来写死 px 的组件，因此同时将这些字号表达式改为 calc。没有字号规则的文字继承缩放后的根字号。部分 Element Plus 组件通过 --el-font-size-base 等变量同步。

原有 clamp 标题的上下界和视口值也乘同一个比例，代码块 font 简写同样处理。颜色使用 --text-primary 和 --text-muted，后者由所选颜色生成 88% 不透明度。

## 磨砂颜色与透明区域

styleVariables 将选中颜色转为 RGB 数字，例如 #aaccdd → `170,204,221`。

```css
--glass-panel: rgba(var(--glass-rgb), .14);
```

磨砂底色和底色不透明度分开管理：用户改变 RGB，仍使用较轻的 14% 表面。透明导航不使用该表面，无论选什么颜色都保持透明。品牌区域可以使用同一颜色，但只有 12% 底色。

高优先级的工作台样式覆盖历史页面内部的按钮底色，避免某页仍残留独立白色块。浏览器不支持模糊时保留浅底回退；系统明确要求减少透明度时，正文面板会使用更实的底色以遵从该偏好，导航与标题仍保持透明。

## 知识点

- CSS 自定义属性把跨组件的字号、文字颜色和表面颜色统一管理。
- ref 保存已应用值，reactive draft 保存未提交的预览；watch 同步外部恢复的设置。
- watchEffect 自动追踪偏好变化，将 Vue 状态应用到根样式。
- 正则 `^#[0-9a-f]{6}$` 只允许六位十六进制颜色；字号使用有限数判断和上下界约束。
- rgba 的透明度只影响表面，不降低字体透明度；backdrop-filter 只模糊背后画面。
- transparent、backdrop-filter:none、box-shadow:none 分别去掉底色、模糊和阴影，需要一起处理。
- 对象展开保留旧记录的背景媒体字段，避免保存文字样式时丢失视频或封面。

## 实际验证

- 前端类型检查和 Vite 构建通过，测试 **16 项通过**（本次新增 3 项）。
- 实际笔记页读取计算样式：主导航、文件夹栏、页面标题和当前导航项均为透明底、无模糊；品牌 12% / 2px，正文 14% / 2px。
- 独立端口 5174 的临时页面使用真实 App、AppearanceSettings 与样式状态，避免覆盖用户 5173 来源偏好。
- 浏览器保存 125% 字号、#445588 文字、#aaccdd 磨砂底色后，根字号示例为 20px、表单标签 16.25px、正文颜色 rgb(68,85,136)、面板底色 rgba(170,204,221,0.14)；刷新后仍恢复。
- 恢复默认后根比例、文字色、磨砂色回到默认；没有记录到控制台 error。
- 截图：docs/screenshots/transparent-navigation.png 为实际笔记页，appearance-font-colors.png 为独立测试设置页。
- 测试页面和额外服务已清理；没有保存笔记、修改账号或覆盖用户当前外观。

窄屏、大字号下的所有页面组合及任意颜色/背景对比度尚未逐项浏览器验收。已做媒体查询与文本换行处理，但不能记为所有组合都验证通过。后端业务未修改，本次未重复运行后端回归。

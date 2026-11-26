# 自定义背景与磨砂玻璃外观

> 最新样式已改为透明导航与标题、14% / 2px 正文面板，并支持字号、文字色和磨砂底色。当前说明见 [透明外观与字体设置](TRANSPARENT_APPEARANCE.md)。后续段落中“最新”指各次历史调整时的状态。

> 2026-11-01 后续已降低磨砂强度：当前普通按钮模糊为 4px，面板白底不透明度为 36%；最新参数与验证见 [多格式预览与更轻磨砂记录](DOCUMENT_FORMATS_AND_LIGHTER_GLASS.md)。下文浏览器结果和截图属于初版。完整修改对比、代码清单与语法见 [界面优化代码整理](UI_APPEARANCE_CODE_WALKTHROUGH.md)。

> 动态背景追加：现已支持 GIF、MP4/WebM/OGV、暂停状态和封面。最新实现与验证边界见 [动态背景说明](DYNAMIC_BACKGROUNDS.md)。下文图片流程为初始实现记录。

实现日期：2026-11-01。入口：侧栏“设置与外观” → “背景与外观”。

支持本地 JPG、PNG、WebP（最大 10 MB），背景柔化 10%–80%，恢复默认。设置自动保存到当前来源的浏览器 IndexedDB；不同设备、浏览器和来源不共享，同一浏览器来源中的账号共用。没有上传接口或 MySQL 迁移。清除网站数据后背景消失。其他已打开标签页刷新后读取新设置。

## 文件清单

- 新增 `frontend/src/stores/appearance.ts`：共享响应式状态、初始化、IndexedDB 读写、图片解码和缩小、应用和释放 Blob URL、柔化保存、恢复默认及错误处理。
- 新增 `frontend/src/components/AppearanceSettings.vue`：选择图片、示例预览、柔化滑块、恢复默认与状态反馈。
- 修改 `frontend/src/App.vue`：在路由之外添加固定背景层和柔化遮罩，切换页面时保持背景。
- 修改 `frontend/src/views/SettingsView.vue`：引入外观组件，宽屏双栏、窄屏单栏排列外观与个人资料。
- 修改 `frontend/src/layouts/AppLayout.vue`：设置入口命名为“设置与外观”。
- 修改 `frontend/src/assets/main.css`：统一玻璃变量、按钮、面板、侧栏、表单、弹窗；保留主要操作与危险操作颜色，支持焦点样式与减少动效/透明度偏好，并提供无模糊支持时的实色回退。
- 更新 README；新增本说明与 `docs/screenshots/appearance-settings.png` 验收截图。

## 调用过程

1. App 调用 `initialize()`，从 IndexedDB 读取图片 Blob 和 veil，生成临时 Blob URL 显示背景。
2. 组件 `selectImage()` 取得 File，调用 `setBackground()`。
3. `compress()` 校验类型和大小，解码图片，限制总像素，最长边缩至不超过 2560，Canvas 以 JPEG 0.86 质量输出。透明图片使用浅色底，处理会改变原图格式及尺寸，仅用于背景。
4. 等待 IndexedDB 事务成功后，`apply()` 更新共享状态，页面自动重绘，并释放旧 URL。
5. `saveVeil()` 保存柔化值；拖动时示例实时预览，结束调节后应用到整个页面。
6. `reset()` 写入空图片与默认 38% 柔化值，释放旧 URL，显示默认渐变。

## 知识与语法

- IndexedDB 能保存 Blob，适合背景图片；localStorage 只能保存字符串且容量较小。本模块不存令牌或用户业务数据。
- `ref()` / `readonly()`：内部可更新响应式状态，对调用者暴露只读引用；组件解构引用仍保持响应性。
- `initialized ??=`：只初始化一次，多个调用共用同一个 Promise。
- 事务 `oncomplete`：确认存储成功后再显示“已保存”；失败保留当前背景。
- `URL.createObjectURL()` 为 Blob 创建本地可显示地址；`revokeObjectURL()` 释放旧资源，不把 URL 当永久配置保存。
- `Image.decode()` 等待图片可解码，Canvas `drawImage()` 缩放，`toBlob()` 输出压缩数据。
- `v-model.number` 将滑块输入转成数值；`watch()` 在恢复默认或初始化完成后同步滑块。
- CSS `rgba()` 提供半透明底；`backdrop-filter: blur()` 模糊元素背后的背景；细边框和阴影增加层次。模糊能力与半透明需要同时存在，纯不透明底会遮住效果。
- 固定背景使用 `pointer-events:none`，不阻挡按钮；`isolation:isolate` 管理层叠上下文，使背景位于路由内容之下。
- `@supports` 给无模糊能力的浏览器提供实色底；媒体查询适配窄屏、减少透明度与动效偏好。

## 验证

- TypeScript 检查与 Vite 生产构建通过。
- 浏览器实测临时 PNG 选择、保存成功提示、刷新后图片恢复、柔化调至 55% 并成功保存、恢复默认至 38%，未记录到控制台 error。
- 读取实际按钮计算样式，确认 backdrop-filter 为 blur(12px) saturate(1.3)；截图检查实际显示。
- 验收后已恢复默认背景，临时色块图已删除，未保存或修改账号资料。
- 超大图片、存储满、隐私模式及无模糊支持的浏览器有处理分支，但未逐项模拟验收；窄屏未单独截图验收。

本次只调整外观，没有进入下一个业务模块。工作记录仍按 AGENTS.md 在明确要求或结束当天对话时统一生成。

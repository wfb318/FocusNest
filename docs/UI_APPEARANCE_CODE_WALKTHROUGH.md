# 界面优化总结、代码清单与知识点

整理日期：2026-11-01。

范围：2026-10-30 的页面宽度调整，以及 2026-11-01 的自定义背景、磨砂玻璃和浅磨砂调整。本次整理仅更新文档，没有重构业务代码，也没有开始下一个业务模块。

## 1. 修改内容总结

| 用户需求 | 实际修改 |
| --- | --- |
| 右侧留白太多 | 取消主内容区 1200px 上限，填满侧栏之外的剩余空间，桌面左右边距限制为 24–48px |
| 使用自己的背景图片 | 设置页增加选择图片、预览、背景柔化、恢复默认；图片保存在当前浏览器 |
| 按钮使用磨砂玻璃底色 | 普通按钮、主要操作、导航、面板、侧栏、弹窗采用协调的半透明与模糊效果 |
| 磨砂再浅一些 | 降低面板/按钮底色不透明度，减少模糊与阴影，让背景更明显 |
| 设置页布局更合理 | 宽屏将外观设置与个人资料分为两栏，1100px 以下改为单栏 |

原有数据与业务接口不变。没有新建 MySQL 表、执行新迁移或新增后端 API；当前已有业务迁移仍为 `0008_note_folders`，本次外观开发没有重新核验数据库状态。

## 2. 新增与修改文件清单

本轮界面功能新增 **2 个源代码文件**、修改 **4 个已有源代码文件**。另更新 README，编写说明文档并保存初版验收截图。

| 类型 | 文件 | 职责 |
| --- | --- | --- |
| 新增 | [stores/appearance.ts](/D:/FocusNest/frontend/src/stores/appearance.ts) | 外观状态、图片处理、浏览器存储和背景应用 |
| 新增 | [components/AppearanceSettings.vue](/D:/FocusNest/frontend/src/components/AppearanceSettings.vue) | 外观设置面板、文件选择、滑块、操作提示 |
| 修改 | [App.vue](/D:/FocusNest/frontend/src/App.vue) | 在路由外放置固定背景层和遮罩，初始化外观 |
| 修改 | [views/SettingsView.vue](/D:/FocusNest/frontend/src/views/SettingsView.vue) | 引入外观组件，设置页双栏布局及窄屏适配 |
| 修改 | [layouts/AppLayout.vue](/D:/FocusNest/frontend/src/layouts/AppLayout.vue) | 导航入口改为“设置与外观” |
| 修改 | [assets/main.css](/D:/FocusNest/frontend/src/assets/main.css) | 页面宽度、默认渐变、全局玻璃样式、焦点/悬停/兼容性处理 |

相关文档：[README](/D:/FocusNest/README.md)、[外观实现说明](/D:/FocusNest/docs/APPEARANCE.md)、本清单。

未新增依赖，未修改 package.json、后端认证与笔记业务。`appearance.ts` 虽然放在 stores 目录，但本模块使用 Vue 模块级 ref 共享状态，没有调用 Pinia 的 defineStore。

## 3. 每个文件中的关键代码

### 3.1 appearance.ts：状态与操作集中在这里

| 状态 | 用途 |
| --- | --- |
| backgroundUrl | 当前显示图片的临时 Blob URL，空字符串表示默认渐变 |
| veil | 背景浅色遮罩的不透明度，默认 0.38，限制 0.1–0.8 |
| busy | 图片处理或存储中，避免重复触发操作 |
| error / notice | 失败信息与成功反馈 |
| initialized | 缓存初始化 Promise，多个调用共用一次初始化 |

| 函数 | 主要处理 |
| --- | --- |
| openDatabase() | 打开 `focusnest-appearance` IndexedDB 数据库，首建时创建 preferences 对象仓库 |
| storage(write?) | 不传参数读取；传 Appearance 对象则写入。等待事务完成，最后关闭数据库连接 |
| apply(value) | 创建新的图片 URL、限制柔化范围、更新状态并释放旧 URL |
| initialize() | 读取保存的外观，失败显示提示，仍可显示默认背景 |
| compress(file) | 校验、解码、缩放并输出背景图片 Blob |
| setBackground(file) | 处理文件 → 保存设置 → 应用背景 → 提示成功 |
| saveVeil(value) | 保留已有图片，仅更新并保存柔化值 |
| reset() | 保存空图片和默认柔化值，恢复默认渐变 |
| useAppearance() | 返回只读状态以及可调用的操作函数 |

图片处理限制：仅 JPG/PNG/WebP，文件最大 10 MB；解码后超过 8000 万像素则拒绝；最长边缩小至不超过 2560px，不放大小图；输出 JPEG，质量参数 0.86。透明图片先铺浅色底，作为背景使用。它不会修改用户电脑中的原图片。

关键顺序：

```typescript
await storage(value)
apply(value)
```

先确认本机存储事务完成，再应用新背景和显示成功信息。存储失败时，保留原来的显示背景。

### 3.2 AppearanceSettings.vue：用户交互

`picker` 是文件控件的模板引用，“选择背景图片”按钮触发它的 click。`selectImage(event)` 取得文件，调用 `setBackground()`；处理后清空控件 value，以便再次选择同一个文件也能触发 change。

`draftVeil` 是滑块上的待应用值，拖动时更新示例预览；结束调节触发 change 后调用 `saveVeil()`，成功后全局背景同步。`watch(veil, ...)` 在初始化、恢复默认后同步滑块。

按钮根据 busy 禁用；没有自定义图片时“恢复默认背景”禁用。所有错误与成功信息就地显示。

### 3.3 App.vue：背景不跟着路由重建

```vue
<div class="workspace-background" ...></div>
<div class="workspace-veil" ...></div>
<RouterView />
```

背景、遮罩与路由内容分开：background 层显示图片或默认渐变，veil 层加浅色遮罩，RouterView 显示任务、笔记、日记等页面。切换路由时背景继续存在。

这也意味着背景会出现在登录页；图片按浏览器来源保存，不按账号隔离，退出登录不会清除背景。设置面板已明确说明同一浏览器账号共用。

### 3.4 SettingsView.vue 与 AppLayout.vue

设置页引入独立的 `<AppearanceSettings />`，个人资料仍使用原来的保存逻辑。两部分使用独立的 busy 与提示，选择背景不会提交昵称、时区或头像。

```css
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 24px;
}
```

两个等宽列，minmax 的 0 允许列在窄空间下收缩；小于等于 1100px 改为一列。导航名称改为“设置与外观”，路径仍是 `/settings`。

### 3.5 main.css：宽度、背景和玻璃表面

内容区当前样式：

```css
.main {
  flex: 1;
  min-width: 0;
  width: 100%;
  padding: 36px clamp(24px, 3vw, 48px);
}
```

flex:1 分配侧栏之外的剩余空间；min-width:0 允许内容区收缩，降低长文本挤出布局的风险。clamp 控制边距下限 24px、首选值 3vw、上限 48px。手机端原规则继续使用 26px 20px 边距。

背景使用 position:fixed、inset:0 覆盖窗口，background-size:cover 填满视口（可能裁切图片边缘），background-position:center 居中显示。pointer-events:none 避免装饰层截获点击；isolation:isolate 配合负层级，让背景位于路由之下。

磨砂效果由三部分组成：半透明底色、backdrop-filter 背景模糊、边框与轻阴影。保存等主要操作仍使用绿色，删除文字仍使用危险色。输入框保留较清楚的浅底和边界。

## 4. 初版与“更浅”之后的参数对比

这里的百分比是**底色不透明度**，越低越透明，不代表整个元素或文字一起变淡。

| 表面 | 初版 | 当前 |
| --- | --- | --- |
| 面板白底 | 76% | 58% |
| 普通按钮白底 | 58% | 36% |
| 侧栏浅底 | 80% | 60% |
| 页头白底 | 55% | 38% |
| 输入框白底 | 68% | 56% |
| 玻璃边框白色 | 80% | 60% |
| 主要按钮绿色底 | 87% | 80% |
| 面板模糊 | 20px | 12px |
| 普通按钮模糊 | 12px | 8px |
| 侧栏模糊 | 24px | 14px |
| 页头模糊 | 16px | 10px |

面板阴影也由 0 8px 30px / 7% 降至 0 6px 24px / 4.5%。弹窗仍保持较高不透明度，以便清楚阅读确认内容。

“背景柔化”滑块调整的是全屏背景遮罩，和上表各个面板、按钮的底色透明度是不同参数。想显示更鲜明的背景，可以降低柔化；想修改玻璃表面本身，需要改 CSS 变量。

## 5. 用户操作到页面更新的完整流程

```text
进入设置页
  → AppearanceSettings.vue / selectImage()
  → appearance.ts / setBackground(file)
  → compress(file)：校验与缩放
  → storage(value)：保存 Blob 与 veil
  → apply(value)：更新响应式状态、释放旧 URL
  → App.vue 的背景样式更新
  → main.css 的半透明面板和按钮透出背景
```

刷新流程：App.vue → initialize() → storage() 读取 → apply() → 显示已保存图片。

恢复默认流程：按钮 → reset() → 写入 image:null / veil:0.38 → apply() → CSS 默认渐变。

## 6. 新增与复习的知识、语法

| 写法/概念 | 本次用途与理解 |
| --- | --- |
| `type Appearance = { image: Blob \| null; veil: number }` | TypeScript 对象类型：保存一张图片或空值，以及一个数值 |
| 模块级 ref | 多个组件 import 同一个模块，读取同一份响应式状态 |
| readonly(ref) | 对外暴露只读引用，通过模块提供的函数更新 |
| `Promise<void> \| undefined` | 初始化结果可能还不存在；存在时可等待它完成 |
| `initialized ??=` | 当前为 null/undefined 才赋值，避免重复启动初始化 |
| `write?: Appearance` | 可选参数；本模块用是否提供参数决定读/写事务 |
| `new Promise(resolve, reject)` | 将 IndexedDB、Canvas 回调 API 包装为可以 await 的操作 |
| `await` | 等待解码或存储结果后继续后续操作 |
| `try/catch/finally` | 执行工作、报告错误，并保证关闭连接/释放临时 URL/恢复按钮状态 |
| File 与 Blob | File 是用户选取的文件；Blob 是图片二进制数据，可存入 IndexedDB |
| Blob URL | 当前页面显示二进制图片的临时地址，不是服务器上传地址，也不适合当永久配置存储 |
| IndexedDB 事务 | oncomplete 代表事务完成；不能只看到某次 put 成功就认为整个事务完成 |
| Canvas | 将解码后的图像按指定尺寸绘制，再编码成新的图片数据 |
| `Math.min` / `Math.max` | 限制缩放比例、尺寸和柔化数值的上下界 |
| `ref<HTMLInputElement \| null>` | 保存模板中的文件 input 引用，挂载前可能为空 |
| `input.files?.[0]` | 安全读取第一个选中文件，取消选择时可能不存在 |
| `v-model.number` | 将滑块值转成数值而非字符串 |
| `watch()` | 服务器无关的本地状态变化后，同步设置面板的滑块 |
| `:style` | 将响应式背景 URL 和透明度绑定到 DOM 样式 |
| CSS 自定义属性 `--glass-panel` | 统一管理面板底色，多个页面复用同一配置 |
| `rgba()` | 最后一项控制底色不透明度，不会降低文字本身的不透明度 |
| `backdrop-filter` | 模糊元素后面的背景；filter:blur 则会模糊元素自身内容 |
| `@supports` | 浏览器不支持模糊时，切换到清楚的实色底 |
| `prefers-reduced-transparency` / `prefers-reduced-motion` | 遵从用户减少透明度或动画的系统偏好（取决于浏览器支持） |

## 7. 存储与接口边界

- IndexedDB 数据库名 `focusnest-appearance`，版本 1，对象仓库 preferences，键 workspace。
- 只保存图片 Blob 与 veil；没有保存背景图片的 HTTP 请求，也没有新后端 API。
- 设置按浏览器来源保存，127.0.0.1 和 localhost 的存储互不通用，不同端口也不同。
- 不跨设备同步；同一来源的不同账号共用。清除网站数据会移除图片。
- 其他已打开标签页需要刷新，尚未加入跨标签页实时同步。
- 外观文件没有读取笔记、日记或任务内容，也没有将图片发送给 AI。

## 8. 实际验证与尚未验证部分

| 时间/修改 | 已验证 |
| --- | --- |
| 2026-10-30 页面宽度调整 | TypeScript 与 Vite 构建通过；当次未进行浏览器视觉验收 |
| 2026-11-01 初版背景与磨砂 | 构建与类型检查通过；浏览器选择临时 PNG、保存、刷新恢复、柔化 55%、恢复默认 38% 通过，控制台未发现 error |
| 初版玻璃样式 | 浏览器读取普通按钮计算样式为 blur(12px) saturate(1.3)，并查看页面截图 |
| 2026-11-01 更浅磨砂 | 构建与类型检查通过；最终 8px 按钮模糊版本尚未再次做浏览器截图/视觉验收 |
| 本次文档整理 | 已核对当前源码和历史执行输出，没有重新运行功能测试 |

初版截图 `docs/screenshots/appearance-settings.png` 保存于降低磨砂强度之前，不能当作最终浅磨砂版截图。截图中包含用户资料区域，工作记录不重复抄录个人信息。

超大图片、存储不足、隐私模式、不支持模糊的浏览器和窄屏视觉效果未逐项实测，不能记为全部通过。没有为纯样式变化新增重复性测试。

验收使用的临时色块图已经删除，浏览器背景已恢复默认；没有修改或提交个人资料。之后由用户自行选择的背景不属于测试清理范围。

## 9. 当前结论与后续

界面宽度、自定义本地背景与浅磨砂代码已实现。现有页面入口仍为 `/tasks`、`/notes`、`/journals` 和 `/settings`。保存当前草稿后刷新可加载最新样式。

如果后续继续优化外观，可单独增加磨砂强度滑块、暗色主题、图片位置或按账号保存的外观；这些尚未实现，本次不自动开发。

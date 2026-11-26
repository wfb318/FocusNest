# GIF 与视频背景：实现及代码说明

日期：2026-11-01。入口：“设置与外观” → “选择/更换背景文件”。

## 支持与行为

- JPG、PNG、WebP 静态图片沿用压缩处理，GIF 保留动画原文件；图片/GIF 最大 10 MB。
- 视频支持 MP4、WebM、OGV，最大 50 MB；必须是当前浏览器支持的视频编码。推荐 H.264 MP4 或 WebM，扩展名本身不保证可解码。
- GIF/视频像素总数不超过 3840×2160；静态图仍按原有规则缩小至最长边 2560。
- 视频背景静音、循环、居中铺满；页面不可见时暂停，可见且用户未暂停时继续。
- GIF 和视频都提供播放/暂停。GIF 暂停显示静态封面，恢复时不保证从暂停前的精确帧继续；视频暂停时停止当前播放。
- 记住背景文件、柔化和暂停状态；刷新后不记忆播放时间。设置页的视频示例只显示封面，避免多开一个视频同时解码。
- 新选动态背景或没有保存过播放偏好时，检测系统 prefers-reduced-motion，偏好减少动效则默认暂停；用户可以主动播放。
- 自动播放失败时退回封面，并提供重试播放或更换文件的提示。
- 文件仅保存到当前来源的 IndexedDB，不上传服务器；不同来源/浏览器/设备不共享，同来源不同账号共用。清除网站数据会清除背景。
- 不支持 MOV/AVI/MKV 的通用播放或转码；APNG、动态 WebP 没有专门保留动画的处理，当前按静态图处理。没有新增后端、数据库迁移或运行时依赖。

## 文件清单

新增 3 个源代码/测试文件：

| 文件 | 作用 |
| --- | --- |
| [utils/backgroundMedia.ts](/D:/FocusNest/frontend/src/utils/backgroundMedia.ts) | BackgroundKind、选择格式、分级大小限制、文件签名检查、解码验证、压缩和封面生成 |
| [components/BackgroundLayer.vue](/D:/FocusNest/frontend/src/components/BackgroundLayer.vue) | 根据媒体类型显示图片/GIF/video，静音循环、可见性暂停、失败回退、生命周期清理 |
| [tests/backgroundMedia.test.mjs](/D:/FocusNest/frontend/tests/backgroundMedia.test.mjs) | 新格式、类型推断、大小边界、文件头和伪装文件校验测试 |

修改 4 个已有源代码/配置文件：

| 文件 | 修改 |
| --- | --- |
| [stores/appearance.ts](/D:/FocusNest/frontend/src/stores/appearance.ts) | 增加类型、封面、暂停和播放失败状态，兼容旧设置，持久化播放状态 |
| [components/AppearanceSettings.vue](/D:/FocusNest/frontend/src/components/AppearanceSettings.vue) | 背景文件选择、GIF/视频暂停和重试按钮、封面示例与格式说明 |
| [App.vue](/D:/FocusNest/frontend/src/App.vue) | 原背景 div 替换为 BackgroundLayer，柔化遮罩仍位于其上 |
| [package.json](/D:/FocusNest/frontend/package.json) | npm test 加入背景媒体测试，没有新增 npm 包 |

另新增本说明、更新 README/APPEARANCE 说明，保存 `docs/screenshots/dynamic-background.png` 的独立测试页面截图。

## 处理流程

1. selectMedia 取得文件，调用 appearance.setBackground。
2. backgroundInfo 检查扩展名、非空和不同大小上限；不依赖浏览器是否正确填充 File.type。
3. validateSignature 检查前 16 字节的格式标识，拒绝将 HTML/SVG 等仅改后缀伪装成 GIF/视频。文件头只是初筛，后面还必须通过真实解码。
4. prepareBackground 创建临时本机 URL：静态图解码后压缩；GIF 解码验证、保留原件并生成静态封面；视频通过 canPlayType 和 loadeddata 验证可读取画面后生成封面。
5. 视频解码等待最多 15 秒；不支持的编码、损坏、尺寸过大或超时都报错，保留旧背景。
6. IndexedDB 事务完成后 apply 更新全局状态，释放旧媒体和封面 URL。
7. BackgroundLayer 监听媒体 URL、暂停状态和播放尝试编号；等待 nextTick 取得当前 video 元素，再 play/pause。
8. 页面隐藏时暂停视频；播放失败显示封面；卸载时移除 visibilitychange 监听。旧媒体产生的错误会检查是否属于当前 video，避免覆盖新媒体状态。

## 浏览器存储兼容

继续使用 `focusnest-appearance` / preferences / workspace，数据库版本仍为 1。

```typescript
type Appearance = {
  image: Blob | null
  veil: number
  kind?: 'image' | 'gif' | 'video'
  poster?: Blob | null
  paused?: boolean
}
```

image 字段沿用原名，如今也可保存 GIF/视频二进制，避免抛弃旧记录。旧记录没有 kind/poster/paused 时可以继续读取；已有 JPG 背景不需要重新选择。

saveVeil 使用对象展开保留新字段，保存后只更新 veil，不重建背景 URL；因此调整柔化不会使正在播放的视频重新加载。savePaused 只修改播放状态，保留媒体和封面。reset 写入空媒体，撤销旧 URL，移除 video 并恢复默认渐变。

## 关键知识和语法

- `File.slice(..., mime)`：为已检查类型的媒体 Blob 设置标准 MIME；浏览器无法填写 File.type 时也能处理。
- 格式头：JPEG/PNG/GIF、MP4 ftyp、WebM EBML、OGV OggS，用于初步识别；不能替代解码检查。
- `canPlayType()`：浏览器对容器格式的初步支持判断；loadeddata 成功更接近实际编码可播放的验证。
- `muted / loop / playsinline`：静音、循环、尽量内联显示。实际 play Promise 仍可能失败，需要捕获。
- Canvas drawImage：既可画 Image，也可画 video 当前画面，因此可统一生成 JPEG 静态封面。
- `watch(..., {flush:'post'})` + nextTick：在 Vue 更新到新的媒体 DOM 后控制播放。
- visibilitychange：响应当前文档可见性，减少后台视频运行；GIF 未专门增加页面隐藏逻辑，暂停按钮会切换到封面。
- `URL.createObjectURL` / revokeObjectURL：本机二进制媒体显示地址及资源释放，不是上传 URL。
- `playbackAttempt`：即使 paused 已经为 false，点击重试也能触发一次新的 play 尝试。
- Promise、定时器与 finally：视频读取超时可失败退出，并清除监听、临时 URL 和临时视频资源。

## 已执行验证

- 最终 vue-tsc、Vite 构建通过；前端测试 **13 passed**（原 10 项 + 新增 3 项）。
- 独立端口 5174 的临时组件页使用实际 BackgroundLayer、AppearanceSettings、appearance store，和用户 5173 页面保持独立 IndexedDB，避免覆盖用户背景。
- 实际生成 GIF、H.264 MP4、WebM 和 PNG 测试样例。
- 浏览器验证 GIF 选择、播放/暂停控件、刷新恢复暂停；MP4 实际 paused=false、muted=true、loop=true，播放时间有推进。
- 调整柔化前后，MP4 的 src 保持相同，证明没有重载视频；暂停后 video.paused=true，刷新后仍为暂停状态。
- WebM 实际静音循环播放；恢复默认后 video 元素数量为 0；PNG 仍可设置背景且不显示动态控制按钮。
- 验收时未记录到控制台 error。用户原有背景和业务内容未被测试页面改写。
- 临时测试端口服务已停止，测试页面、媒体样例和临时下载的 imageio-ffmpeg 生成工具已清理；该工具没有进入 requirements 或应用运行依赖。

尚未逐项验证：OGV 实际播放、浏览器自动播放被拒绝的交互、系统减少动效偏好切换、页面隐藏/恢复的浏览器行为、存储配额用尽和 50 MB 大文件的完整写入。代码包含相应处理或限制，不能记为这些情况全部已实测。

WebM/MP4 可否播放还取决于编码、浏览器和系统。较大的动态背景可能增加内存、存储和耗电，当前提供大小/分辨率限制与暂停控制，没有自动转码或视频压缩。

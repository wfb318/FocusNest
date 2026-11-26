# FocusNest 工作记录 · Phase 8 统计模块

实施日期为 2026-11-18，时区为 Asia/Shanghai。用户要求继续开发统计模块，并保存修改文档。

## 已实现的功能

左侧导航新增「统计」，地址为 `http://127.0.0.1:5173/statistics`。

- 可切换本周、本月或自选起止日期，显示所用账号时区。
- 汇总专注时长、完成次数、进行中或暂停的会话数。
- 每日专注柱状图可切换时长与完成次数，点击或用键盘选择一天后显示具体数值。
- 按番茄钟、倒计时、正计时和定时专注分别汇总时长和次数。
- 展示期间新建任务的待办、进行中、已完成、当前逾期数量及完成率。
- 提供空数据、加载和失败提示，明细可展开查看。可见页面约每分钟刷新，切回页面或恢复网络时也会刷新。正在编辑日期范围时暂停自动刷新，点击「查询」后采用新范围。

## 统计口径

### 专注按开始日归属

专注开始时间按账号 IANA 时区换算为日期，整段有效时长归入该日。跨午夜的会话同样按开始日归属，与现有工作台一致。例如 11 月 17 日 23:50 开始、11 月 18 日 00:10 结束，有效时长 20 分钟计入 11 月 17 日。

原记录保存累计有效秒数和当前运行段的开始时间。暂停期间不累计，恢复后的运行段继续计时。统计直接复用 `focus.elapsed()` 计算已有记录，因此能够读取此前创建的会话。休息和取消的会话不纳入专注汇总。

倒计时已到期但计时接口尚未结算时，统计将其视为完成并限制时长上限。定时专注最多累计到其结束时间。查询统计时只计算结果，数据库记录由现有计时流程结算。尚未开始的等待计时不累计。

当前专注显示的是本次刷新时的有效时长。查询过去的开始日，也会包含属于该日的会话截至本次刷新的有效时长。旧数据只有累计时间，无法据此准确还原每一段暂停在午夜两侧的分布，本版采用开始日归属。

### 任务按创建日期筛选

所选范围内新建的任务组成一个统计集合，待办、进行中和已完成反映该集合的当前状态。完成率为「当前已完成数量 ÷ 期间新建任务总数」，四舍五入到一位小数。没有任务时显示横线。

逾期指集合内截止日期早于账号今天、且尚未完成的任务。任务以后完成、恢复或删除，会改变之前日期范围的结果。页面显示的是当前任务数据的汇总，原系统未记录每一次任务状态变化的历史事件。

### 日期边界

本周为周一至周日，本月为自然月。范围包含首尾日期，最多 366 天。后端把首日零点与结束日次日零点分别从账号时区换算为 UTC，按左闭右开区间查询，可覆盖夏令时发生时长变化的日期。没有记录的日子补零。

## 新增代码及作用

| 文件 | 主要内容 |
| --- | --- |
| `D:/FocusNest/backend/app/schemas/statistics.py` | 定义 `FocusSummary`、`DailyFocus`、模式汇总、任务汇总和完整响应。服务时间序列化为 UTC ISO 时间。 |
| `D:/FocusNest/backend/app/repositories/statistics.py` | `focus_sessions()` 按当前账号和开始时间范围读取计算所需字段，分批遍历。通过 `task_counts()` 在数据库聚合任务状态与逾期数量。 |
| `D:/FocusNest/backend/app/services/statistics.py` | `overview()` 校验范围、换算日期边界、生成每日零值、复用计时函数并填充每日及模式汇总，计算任务完成率。 |
| `D:/FocusNest/backend/app/api/v1/endpoints/statistics.py` | 新增认证后的只读统计接口，把日期参数交给 Service。 |
| `D:/FocusNest/backend/tests/test_statistics.py` | 新增 17 项参数化测试，覆盖归属、计时、任务、权限、隐私数据表、夏令时、闰年和范围校验。 |
| `D:/FocusNest/frontend/src/types/statistics.ts` | 定义日期范围及统计响应的 TypeScript 类型。 |
| `D:/FocusNest/frontend/src/api/statistics.ts` | `getStatistics()` 封装统计请求，复用现有认证传输层。 |
| `D:/FocusNest/frontend/src/utils/statistics.ts` | `statisticsRange()` 计算本周和本月，`durationLabel()` 格式化时长。 |
| `D:/FocusNest/frontend/src/views/StatisticsView.vue` | 筛选、汇总卡、每日图表、模式分布、任务状态、明细与自动刷新。请求版本校验阻止旧范围响应覆盖新范围，页面卸载后停止更新。 |
| `D:/FocusNest/frontend/tests/statistics.test.mjs` | 新增 2 项测试，覆盖跨年周、周日、闰月和 12 月的范围计算。 |

## 修改的现有文件

| 文件 | 修改 |
| --- | --- |
| `D:/FocusNest/backend/app/api/v1/router.py` | 注册统计路由。 |
| `D:/FocusNest/backend/app/main.py` | 为统计 API 响应设置 `Cache-Control: no-store`。 |
| `D:/FocusNest/frontend/src/router/index.ts` | 注册 `/statistics` 路由，复用原有登录保护。 |
| `D:/FocusNest/frontend/src/layouts/AppLayout.vue` | 将「统计」接入可用导航。 |
| `D:/FocusNest/frontend/src/api/client.ts` | 增加统计日期校验的中文错误提示。 |
| `D:/FocusNest/frontend/package.json` | 将统计日期测试加入测试命令。 |
| `D:/FocusNest/README.md`、`D:/FocusNest/PROJECT_SPEC.md` | 更新统计模块进度和下一业务阶段。 |

页面验收截图保存在 `D:/FocusNest/docs/screenshots/statistics.png`，其中展示的是合成测试数据。

## API、数据库与调用流程

新增 `GET /api/v1/statistics?start_date=2026-11-16&end_date=2026-11-22`。同时省略两个日期时默认返回账号本周；只传一个日期、倒序或超出长度的范围会被拒绝。响应包含 `start_date`、`end_date`、`timezone`、`today`、`server_now`、`focus`、`tasks`、`daily` 和 `modes`。

接口复用现有任务和专注表及按账号、时间建立的索引。本次无需数据库迁移，开发库仍为 `0018_schedule_templates`。统计输出为数字和日期，计算过程中不查询日记、笔记或文档内容。

```text
点击「统计」或提交日期范围
  → StatisticsView.vue 的 load()
  → getStatistics()
  → GET /api/v1/statistics
  → 当前账号认证
  → statistics.overview()
  → Repository 查询当前账号的任务和专注
  → 复用 focus.elapsed()，按日与模式累计
  → 返回 JSON
  → 更新汇总、图表与明细
```

运行中的旧后端进程需加载更新后的代码。开发模式在项目的 backend 中运行 Uvicorn，在 frontend 中运行 `npm run dev`，登录后点击「统计」。

## 本次涉及的知识

- **时区与查询区间**。前端日期表达用户本地的一天，数据库时间使用 UTC。先换算边界，再使用 `>= start` 和 `< end`，可避免重复计算末端，也避免把一天固定成 24 小时。
- **条件聚合**。`CASE WHEN` 将符合状态的任务映射成 1，其余映射成 0，`SUM` 得到每种状态的数量。`COALESCE` 让空集合返回 0。
- **分组累计**。Service 预先为每个日期建立零值对象，每读一条会话就同时加入总汇总、所属日期和对应模式，确保这些统计使用相同口径。
- **只读计算**。复用已有计时函数计算尚未结算的状态，可以展示到期结果，同时保持查询接口的只读行为。
- **异步响应与响应式视图**。`computed` 根据返回数据计算柱高、选中日和进度条；请求版本号与卸载标记使迟到响应失效。

## 已执行的验证

- 完整后端测试 274 项通过、9 项跳过，Ruff 通过。
- 本机 MySQL 的统计与工作台测试 24 项通过，事务测试前后六张表的记录数一致。
- 前端 82 项测试通过，TypeScript 检查和生产构建通过。
- 隔离 Chrome 使用虚构账号和临时 SQLite 验证了有数据与空数据、每日选择、图表指标切换、本月及自选范围、390px 窄屏布局。已查看截图，页面显示正常。
- 后端测试验证了统计接口不查询日记、笔记和文档表，且未结算专注在统计后保持原数据库状态。

测试依赖仍有 TestClient 与 AnyIO 的弃用提示。本轮验证使用合成数据。

## 后续范围

下一业务阶段为 Phase 9 Tools，需按用户下一次指示推进。正式环境的 HTTPS、日志、真实文件夹授权和生产备份恢复验收，继续按隐私验收文档处理。

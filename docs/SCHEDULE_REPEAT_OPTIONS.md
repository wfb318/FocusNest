# 日程重复方式与移除范围

实现日期：2026-11-26。本次是用户授权的日程扩展，不推进 Phase 9，也不恢复已撤回的任务时分修改。

## 页面行为

- 创建日程时选择“临时日程（仅所选日期）”或“每周重复”。默认临时日程，每次打开新建表单都会恢复默认。
- 每周重复从所选日期开始，在之后每周同一天、同一时段执行；页面卡片持续显示类型，单次调整或跳过状态单独标注。
- 编辑仍只修改所选日期，不改变已保存模板。
- 移除每周重复日程时，默认“仅移除本次”：只跳过所选日期，可以重新编辑恢复。
- 选择“永久移除（本次及以后）”：从所选日期起停止此条规则的所有后续重复，之前的历史安排及已有计时记录保留。
- 临时日程只有一个日期，移除弹窗不提供无意义的后续范围。
- 关闭弹窗再打开时，移除范围重置为“仅移除本次”，不会沿用上次的永久选择。

已有模板仍然作为快照保存。单次或永久移除不会改写模板；以后应用或自动沿用仍含该项目的模板，可以生成新的同名安排。新增在模板之外的每周规则会在自动沿用模板时继续保留。主动应用模板仍按原有规则替换目标周尚未开始的安排。

## 新增和修改代码

| 文件 | 作用 |
| --- | --- |
| `frontend/src/views/ScheduleView.vue` | `form.repeat_weekly` 保存创建选择；`save()` 传递布尔值。`removalScope` 保存移除选择；`askRemove()` 重置为 single；`remove()` 传递 single 或 future。新增对应下拉框、范围说明和成功提示。 |
| `backend/app/services/schedule_templates.py` | 自动沿用时查询历史模板替换记录。已被模板接管的旧规则保持原行为；另外添加的重复规则保留，并通过已有指纹计数避免与模板相同项目重复生成。 |
| `backend/tests/test_schedules.py` | 检查 repeat_weekly=false 只出现一次、true 在之后各周出现。 |
| `backend/tests/test_schedule_templates.py` | 检查新增重复规则在模板沿用后保留，永久移除后不再出现，而先前历史仍存在。 |
| `frontend/tests/scheduleOptions.test.mjs` | 验证真实页面脚本的创建参数、表单重置、两种移除范围、临时日程保护和失败提示。 |
| `frontend/package.json` | 将新增 6 项前端行为测试接入 npm test。 |
| `deploy/install_schedule_options.py` | 现有 Ubuntu 服务器的代码备份、更新、后端自动重启和健康检查；失败时恢复此前代码。 |

后端原来已经提供 `repeat_weekly` 与 `scope`，本次复用这些 API：

- `POST /api/v1/schedules`：`repeat_weekly: false/true`。
- `POST /api/v1/schedules/{id}/remove`：`scope: single/future`，同时发送所选日期和 revision，继续执行账号归属及并发版本检查。
- 不新增数据库表或列；数据库版本仍为 `0019_admin_and_presence`。

## 涉及的语法

- Vue `reactive`：保存表单状态；`ref<'single' | 'future'>` 将范围限制为两个允许值。
- `<option :value="true">` / `:value="false"`：绑定真正的布尔值，避免字符串 `"false"` 被误当成真值。
- `v-if`：仅为新建显示重复选择，仅为重复规则显示永久移除选项。
- SQLAlchemy `select(...).where(...).distinct()`：读取已经被模板替换过的规则编号，避免自动沿用覆盖额外新增的每周规则。
- Python `Path.replace()`：完整复制新文件后再切换入口，保留旧 assets 供尚未刷新的页面使用。

## 验证结果

- 后端日程与模板相关 24 项测试通过。
- 本机真实 MySQL 的新增方式及模板兼容 3 项专项测试通过，虚构数据在事务结束后回滚。
- 前端 91 项测试通过，包含本次新增的 6 项；类型检查和生产构建通过，Ruff 通过。
- 隔离 SQLite 与虚构账号的页面检查：每周日程出现在下一周；临时日程未出现在下一周；永久移除说明和确认按钮正确，每次重新打开默认单次范围。没有在浏览器里实际提交永久移除，永久范围由后端及前端行为测试验证。
- 本机及线上真实业务记录没有迁移或删除；服务器更新尚待用户执行。

## 更新服务器

上传 `focusnest-schedule-options-20261126.zip` 到 `/home/ubuntu`，然后执行：

```bash
cd /home/ubuntu
unzip -n focusnest-schedule-options-20261126.zip
sudo /srv/focusnest/backend/.venv/bin/python /home/ubuntu/focusnest-schedule-options/install_schedule_options.py
```

成功标志为 `SCHEDULE_OPTIONS_READY`。该脚本只替换模板服务文件和已构建的前端，先备份到 `/var/backups/focusnest/schedule-options-...`，自动重启 FocusNest 后端并检查数据库连接健康；不修改数据库结构、`.env`、内容密钥或管理员账号，不需要输入 MySQL 密码。

完成后用 Ctrl+F5 刷新网站。此工具针对已运行管理员版本的现有 `/srv/focusnest` 布局，通过本机语法及静态检查，尚未在生产服务器执行。

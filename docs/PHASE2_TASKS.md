# Phase 2 Tasks 实施说明

实施日期：2026-10-11。用户已明确授权在总结 Phase 1 问题后进入下一阶段；本次范围为 PROJECT_SPEC.md 的 Tasks，不包含 Focus 或 AI。

## 已实现功能

- 创建、分页列表、详情、编辑、删除任务。
- 标记完成、恢复待办；可编辑为进行中。
- 标题、说明、优先级、计划日期、截止日期、预计耗时。
- 今日任务、状态/优先级/计划日期/截止日期组合筛选。
- 后端严格限定当前用户，前端路由需要登录。
- 空列表、加载、错误、成功提示，删除前页面内确认。

## 数据约定

| 字段 | 规则 |
| --- | --- |
| id | 服务端生成 UUID |
| user_id | 从 CurrentUser 获取，客户端不能提交或修改 |
| title | 去除两端空格后不能为空，最多 200 字符 |
| description | 可空，最多 10000 字符 |
| status | todo 待办、doing 进行中、done 已完成；默认 todo |
| priority | low 低、medium 中、high 高；默认 medium |
| scheduled_date | 可空的计划日期，YYYY-MM-DD |
| due_date | 可空的截止日期，YYYY-MM-DD，不含具体时刻 |
| estimated_minutes | 可空，1–10080 整数；单位为分钟 |
| completed_at | 进入 done 时由后端设置，离开 done 时清空 |
| created_at / updated_at | 数据库存无时区 UTC，API 输出带 +00:00 的 ISO 字符串 |

重复完成保留原 completed_at。创建时可以指定 done。PATCH 只修改提供的字段：可空字段传 null 表示清空；title/status/priority 显式传 null 返回 422。空 PATCH 不改变 updated_at。

计划和截止日期可以独立填写，允许安排过期任务，不强制二者先后关系。今日按用户 IANA 时区计算：scheduled_date 等于今天 **或** due_date 等于今天；不自动排除已完成任务，可用 status 继续筛选。多个筛选条件之间是 AND。

任务列表按 created_at 降序、id 降序稳定排序；API 默认每页 20 项，最大 100 项；前端每页 10 项。

## API

全部要求 Authorization: Bearer，统一返回 ApiResponse，带 Cache-Control: no-store。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | /api/v1/tasks | 列表，data={items,total,page,page_size} |
| POST | /api/v1/tasks | 创建，201 |
| GET | /api/v1/tasks/{task_id} | 详情 |
| PATCH | /api/v1/tasks/{task_id} | 部分更新，恢复待办传 status=todo |
| POST | /api/v1/tasks/{task_id}/complete | 完成任务 |
| DELETE | /api/v1/tasks/{task_id} | 删除，200 且 data=null |

列表参数：page、page_size、status、priority、scheduled_date、due_date、today。示例：`/api/v1/tasks?today=true&status=todo&priority=high&page=1&page_size=10`。

未登录 401，字段/查询参数错误 422，他人或不存在任务统一 404/code 40401，不透露他人任务是否存在。

## 文件与调用流程

后端：

- app/models/task.py：Task 表模型、用户外键、检查约束与索引。
- app/schemas/task.py：创建/更新/输出/分页类型，标题与空值校验。
- app/repositories/tasks.py：find_owned、list_owned、add、remove；查询均由服务端限定 user_id。
- app/services/tasks.py：get_task、list_tasks、create_task、update_task、complete_task、delete_task；local_today 按用户时区计算日期，Service 管理事务与完成时间。
- app/api/v1/endpoints/tasks.py：六个 REST 接口，CurrentUser 身份认证。
- app/api/v1/router.py、app/models/__init__.py：注册路由和模型。
- app/main.py：任务响应禁用缓存。
- alembic/versions/0003_tasks.py：新增 tasks 表，upgrade 创建，downgrade 删除该表。
- tests/test_tasks.py：任务生命周期、用户隔离、字段校验、分页筛选、时区边界与未登录拒绝。

前端：

- src/types/task.ts：TaskInput、Task、TaskPage、筛选类型。
- src/api/tasks.ts：六类请求的封装，复用现有 Axios 认证刷新机制。
- src/views/TasksView.vue：列表、筛选、编辑和确认删除；load 使用请求序号忽略过期响应；删除导致末页变空时回到有效页。
- src/router/index.ts：/tasks 路由，复用登录守卫。
- src/layouts/AppLayout.vue：启用任务导航。
- src/views/DashboardView.vue：提供任务入口。
- src/api/client.ts：任务不存在及任务参数校验的中文提示。

创建：TasksView.save → api.createTask → endpoints.create_task → schemas.TaskCreate / CurrentUser → services.create_task → repositories.add → commit → TaskRead → 刷新列表。

列表：TasksView.load → api.listTasks → endpoints.list_tasks → services.list_tasks → repositories.list_owned → 按 user_id 与筛选条件查询、计数、分页 → TaskPage。

完成：TasksView.toggle → api.completeTask → endpoints.complete_task → services.complete_task → update_task → get_task 检查所属关系 → 更新状态和完成时间 → commit。

删除：requestDelete 打开页面 dialog；取消只关闭 dialog；确认调用 remove → api.deleteTask → endpoints.delete_task → services.delete_task → get_task 验证所有者 → repositories.remove → commit → 重新加载列表。

## 迁移与启动

已在本机开发 MySQL 应用 0003_tasks，Alembic check 没有检测到模型与数据库结构差异。本次迁移新增表，不修改已有用户与认证会话结构。

新环境仍需运行：

```powershell
cd D:\FocusNest\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另一个终端：

```powershell
cd D:\FocusNest\frontend
npm run dev
```

登录后打开 http://127.0.0.1:5173/tasks 。

## 验证结果与边界

- MySQL：57 passed，包含原认证回归及并发刷新、新增 21 项任务测试；事务测试回滚，独立并发测试自行清理。
- SQLite：56 passed、1 skipped（并发刷新仅在 MySQL 执行）。
- Ruff、前端 TypeScript 与 Vite 生产构建通过。
- Alembic upgrade head、check 通过。
- 浏览器使用独立临时用户验证创建、详情编辑、完成、恢复、组合筛选及新标签页恢复登录后任务仍保留。
- 原生 window.confirm 曾阻塞浏览器控制工具，已改为页面内 dialog。后续浏览器复核已确认：删除对话框正常打开、取消后任务保留。
- 实际删除额外通过前端开发代理发送真实 HTTP 请求验证：DELETE 成功、详情 404、列表为空。没有通过浏览器点击最终确认删除，不将该步骤记为已点击。
- 浏览器临时用户、任务和登录会话已按唯一用户 ID 清理，未修改真实用户数据；最终核实迁移版本为 0003_tasks。
- 桌面页面截图：screenshots/phase2-tasks.jpg；截图展示的是临时测试数据。
- 测试存在两条原有上游弃用提示（Starlette/httpx、AnyIO），未改变依赖。

仍未实现：任务项目分组、重复任务、子任务、提醒、拖拽排序、批量操作、回收站和专注计时。下一阶段为 Phase 3 Focus，尚未开始。

本次原 PROJECT_SPEC.md 与 README.md 已归档在 docs/archive/2026-10-11-phase2，Obsidian 产品原文未覆盖。历史问答总结已单独保存到用户指定 Obsidian 目录。

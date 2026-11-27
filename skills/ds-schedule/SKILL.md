---
name: ds-schedule
version: 1.0.0
keywords:
  - DolphinScheduler
  - DS
  - 调度
  - 工作流
  - 定时任务
  - 补数
  - 任务实例
  - ds_create_workflow
  - ds_create_schedule
  - ds_run_workflow
mcp_required:
  - lakeinsight-mcp
description: |
  使用 LakeInsight 的 ds_* 工具操作 DolphinScheduler：查询工作空间和项目、管理工作流/定时、
  运行和补数、暂停/恢复/停止实例、查看任务实例。
  当用户说“建一个调度工作流”“每天 2 点跑”“补一下昨天数据”“停掉这个实例”时触发。
  Keywords: DolphinScheduler, DS, 调度, 工作流, 定时任务, cron, 补数, 实例
---

# DolphinScheduler 调度

所有操作都通过 `ds_*` MCP 工具走后端 `/dsSchedule`，不要直接调 DS API，也不要向用户索要 `ds_token`。

35 个工具的请求样本见 [references/tool-requests.md](references/tool-requests.md)。

## 开始前

1. 调 `ds_list_workspaces`。
2. 检查目标 workspace 的 `canRead`、`canSchedule`、`hasDsToken`；顶层 `defaultTimezone` / `defaultTimezoneSource` 表示创建定时不传时区时用的默认值和来源。
3. `hasDsToken=false` 时提示用户先初始化 DS Token，不要继续调用 DS 工具。
4. 不是当前工作空间时，把目标 `workspaceId` 传给工具；工具会转成 `X-Target-Workspace-Id`。

`ds_list_workspaces` 本身也要求当前工作空间有 `taskPublishing` read 权限。

## 查询顺序

```text
工作空间 → 项目 → 工作流 → 定时/实例/任务实例 → 日志
```

- `ds_list_projects` 只返回目标 workspace 对应的 DS 项目。
- 项目名必须精确唯一；找不到或多条时后端返回 `10105`。
- 不要自己猜 `projectCode`，工具会按 workspace name 解析。

## 分页和搜索

- 列表默认 `pageNo=1`、`pageSize=100`，最大 100。
- 返回 `total`、`hasMore`；用户没有明确说继续时，只展示第一页。
- 用户问“有没有 XX”时，不能只看第一页：
  1. 先服务端搜索；
  2. 没命中就继续翻页；
  3. 命中立即停止；
  4. 未命中必须翻到 `hasMore=false` 才能回答“没有”；
  5. 某一页失败返回错误，不能当成“没有”。
- 实例/任务实例不传时间范围时，由调用方决定；需要全量扫描时不要加默认 7 天窗口。

## 工作流

- 只支持 `LAKEINSIGHT` 通用任务节点和 `DEPENDENT` 逻辑节点。
- 创建：`ds_create_workflow`。
  - 先调 `ds_list_task_nodes`，把返回的 `id` / `job_name` 给用户选择。
  - 节点名固定取 `job_name`，不要自定义。
  - 参数是 `name` + `nodes`：
    - `lakeinsightTaskId`：`ds_list_task_nodes` 返回的 `id`；
    - `predecessorIndex`：可选，指向 `nodes` 中更早节点的下标；不传表示入口节点。
  - 工具会自动生成 task code、关系、坐标和 `isCache`，用户不需要知道 code。
  - 示例见 [references/tool-requests.md](references/tool-requests.md)。
- 已有工作流追加节点：`ds_add_lakeinsight_node`。
  - 节点名同样取 `job_name`。
  - `preTaskCode` 可选；不传表示入口节点。
  - 工作流必须 OFFLINE；在线先调 `ds_offline_workflow`。
- 追加 DEPENDENT 逻辑节点：`ds_add_dependent_node`。
  - 节点名由用户指定。
  - `dependItems` 指定被依赖工作流/任务：`definitionCode`、`depTaskCode`、`cycle`、`dateValue`。
  - `depTaskCode`：`0`=整个工作流，`-1`=所有任务，其他=指定 task code。
  - `cycle` / `dateValue` 必须同组；`cycle` 不传时按 `dateValue` 自动推断。
  - `checkInterval` 单位秒（默认 10），`failureWaitingTime` 单位分钟（仅 `..._WAITING` 生效）。
  - 只支持同一 workspace 内依赖：被依赖工作流必须和当前工作流在同一个 workspace。
  - `ds_list_workflows` 只能看到当前 workspace 的工作流，不要向用户索要其他 workspace 的 `workflowCode`。
  - 工作流必须 OFFLINE。
- 查询已有工作流节点：`ds_get_workflow`，数据在 `taskDefinitionList`。
- 高级全量更新：`ds_update_workflow`；只接收 DS 原生 JSON，正常新增节点不要用这个。
  - DEPENDENT 的 `definitionCode` 必须属于当前 workspace 的项目，且不能是当前工作流自身；后端会按项目查一次，跨项目或自依赖会被拒绝（10106）。
- `ds_get_workflow` 的 `data` 是 `{processDefinition, taskDefinitionList, processTaskRelationList}`。
- 创建/追加前 MCP 会先校验，不通过直接报错、不发请求：
  - taskType 只能是 `LAKEINSIGHT` / `DEPENDENT`（大小写不敏感，MCP 提交前会统一转大写）；
  - 节点名来自 `job_name`；
  - 前置下标只能指向更早的节点；
  - `ds_add_dependent_node` 会校验被依赖工作流存在、`depTaskCode` 属于该工作流、`dateValue` 在允许枚举内，且 `definitionCode` 不能是当前工作流本身。
- 单次创建最多 50 个节点；`ds_add_dependent_node` 每个节点最多 20 个依赖项。
- 删除工作流：`ds_delete_workflow`；DS 还要求当前用户是创建者或 DS 管理员，否则返回 `10103`。
- 上线/下线：`ds_release_workflow` / `ds_offline_workflow`。
- 运行：`ds_run_workflow`。
  - 工作流必须已上线；MCP 会先查状态，OFFLINE 时直接提示先调 `ds_release_workflow`。
  - `startParams` 传对象，工具会序列化。
  - `tenant` / `workerGroup` / `environment` 只有工作空间管理员可显式指定，普通用户省略即可。
- 写操作都要用户明确确认后传 `confirm=true`。

## 定时

- 创建：`ds_create_schedule`，`cron` 使用 Quartz 格式，例如 `0 0 2 * * ? *`。
  - 创建前工作流必须已上线：DS 的 `insertSchedule` 会校验 `PROCESS_DEFINE_NOT_RELEASE`；MCP 会先查状态并提示。
- 时间格式 `yyyy-MM-dd HH:mm:ss`。
- 未传默认值：开始时间按 `timezone` 生成当前时间，结束时间 `2099-12-31 23:59:59`。
- 时区不传时只从运行环境取：优先 MCP 进程的 `TZ`，没有 `TZ` 时用 Node 解析出的系统时区；都不行就报错，要求显式传 `timezone`，不写死默认值。
- `timezone` 对应 DS 的 `schedule.timezoneId`，决定 cron 和起止时间按哪个时区解释；不是 worker 的 `TZ`，也不是任务的 `environment`。
- 上线定时前，工作流必须已上线；MCP 会先查状态并提示。
- 更新定时前先查现有值再合并，避免把未传字段重置。
- **修改 `timezone` 时必须同时传 `startTime` 和 `endTime`**：已有时间是按旧时区存的墙钟，只换时区会让窗口整体平移。
- 删除定时前建议先下线。
- `tenant` / `workerGroup` / `environment` 只有工作空间管理员可以显式指定；普通用户请省略（更新定时时保持现有值），否则返回 `10105`。

## 实例和任务

- 实例：`ds_list_instances` / `ds_get_instance`。
- 重跑：`ds_rerun_instance` 或 `ds_rerun_from_failure`。
- 暂停/恢复/停止：`ds_pause_instance` / `ds_resume_instance` / `ds_stop_instance`。
- 状态限制（MCP 会按 DS 的 `checkExecuteType` 提前校验）：

| 操作 | 允许的实例状态 |
|---|---|
| 暂停 | `RUNNING_EXECUTION` |
| 恢复 | `PAUSE` / `STOP`，**`READY_PAUSE` 不行** |
| 停止 | `RUNNING_EXECUTION` / `READY_PAUSE` |
| 重跑 | `SUCCESS` / `FAILURE` / `STOP` / `PAUSE` / `BLOCK` |
| 失败重跑 | `FAILURE` |
| 删除 | 已结束的实例 |

`READY_PAUSE` 是“正在暂停”，DS 不认作 `PAUSE`。遇到它只能等它落到 `PAUSE`，或先 `stop` 再 `resume`。
- 删除实例：仅已结束实例。
- 补数：`ds_complement_data`，传 `startDate`、`endDate`。
  - 支持 `yyyy-MM-dd` 或 `yyyy-MM-dd HH:mm:ss`；只传日期时开始时间补 `00:00:00`、结束时间补 `23:59:59`。
  - `runMode` 只能是 `RUN_MODE_SERIAL` / `RUN_MODE_PARALLEL`。
  - `startNodeList` 可选，指定补数起始任务的 task code（多个用逗号分隔）。
  - 补数前工作流必须是 ONLINE；MCP 会先查状态并提示。
- 任务实例：`ds_list_task_instances`。
- 强制成功：`ds_force_task_success`；仅 `FAILURE` / `KILL` 的任务实例、且所属流程实例已结束时可调用。
- 停止任务：`ds_stop_task`；DS 3.2.2 目前主要支持流式任务实例。

## 错误处理

| code | 含义 | 处理 |
|---|---|---|
| 10104 | 身份/SA/Header 不匹配 | 读一次 code-token 重试；仍失败让用户重新打开 Notebook |
| 10105 | 无权限、非成员、项目不存在/不唯一、需要工作空间管理员 | 告知用户没有目标工作空间权限、项目未初始化，或该操作需要管理员 |
| 10106 | 参数非法 | 修正参数，不要盲目重试 |
| 10101 | DS Token 缺失 | 提示用户初始化 DS Token |
| 10103 | DS 401/403，或 DS 业务码 30001/30002（无用户/项目权限） | 提示 DS Token 过期、无项目授权，或不是工作流/定时的创建者 |
| 10102 | DS 其他错误 | 展示简短错误，不展示 DS 原始 body |

MCP 客户端对 `10104` 会自动重试一次（发生在任何写副作用之前）；模型不要额外重试写操作。

## 禁止

- 不要向用户索要或展示 `ds_token`。
- 不要把 `code-token`、`ds_token` 写进日志。
- 不要直接调用 DS 的 `/projects/...` API。
- 不要在没有 `confirm=true` 时执行写操作。
- 不要在跨 workspace 操作时修改 `current-workspace-id`；只传 `workspaceId`。

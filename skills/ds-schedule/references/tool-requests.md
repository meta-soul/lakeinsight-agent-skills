# 35 个 ds_* 工具请求样本

所有工具都可能带：

```json
{"workspaceId": 3}
```

- `workspaceId` 可选；不传就是当前工作空间。
- 访问其他 workspace 时只加 `workspaceId`，不要改 `current-workspace-id`。
- 非 read 操作必须由用户确认后传 `"confirm": true`。
- `tenant` / `workerGroup` / `environment` 只有工作空间管理员可显式指定；普通用户省略（更新定时时保持现有值）。

下面样本里为简洁起见，只在需要时写 `workspaceId`。

## 工作空间与项目

| Tool | 请求样本 |
|---|---|
| `ds_list_workspaces` | `{}` |
| `ds_list_projects` | `{"workspaceId":3}` |

## 工作流

| Tool | 请求样本 |
|---|---|
| `ds_list_workflows` | `{"pageNo":1,"pageSize":100,"searchVal":"etl"}` |
| `ds_get_workflow` | `{"workflowCode":"1677489723993600000"}` |
| `ds_list_task_nodes` | `{"workspaceId":84}` → `{"items":[{"id":135,"job_name":"flink-demo"}]}`（`id` 为数字；`lakeinsightTaskId` 字符串/数字均可） |
| `ds_create_workflow` | `{"name":"my_workflow","nodes":[{"lakeinsightTaskId":135},{"lakeinsightTaskId":10,"predecessorIndex":0}],"confirm":true}` |
| `ds_add_lakeinsight_node` | `{"workflowCode":"1677489723993600000","lakeinsightTaskId":135,"preTaskCode":"1677489723993600001","confirm":true}` |
| `ds_add_dependent_node` | 见下方 |
| `ds_update_workflow` | 高级全量更新，见 [workflow-json.md](workflow-json.md)；正常追加节点用 `ds_add_lakeinsight_node` |
| `ds_delete_workflow` | `{"workflowCode":"1677489723993600000","confirm":true}` |
| `ds_release_workflow` | `{"workflowCode":"1677489723993600000","confirm":true}` |
| `ds_offline_workflow` | `{"workflowCode":"1677489723993600000","confirm":true}` |
| `ds_run_workflow` | 见下方 |

追加 DEPENDENT 节点：

```json
{
  "workflowCode": "1677489723993600000",
  "name": "wait_upstream",
  "preTaskCode": "1677489723993600001",
  "dependItems": [
    {
      "definitionCode": 182668220891520,
      "depTaskCode": 0,
      "cycle": "day",
      "dateValue": "last1Days"
    }
  ],
  "relation": "AND",
  "checkInterval": 10,
  "failurePolicy": "DEPENDENT_FAILURE_FAILURE",
  "confirm": true
}
```

如果 `failurePolicy` 是 `DEPENDENT_FAILURE_WAITING`，再加 `"failureWaitingTime": 30`（分钟）。

运行工作流：

```json
{
  "workflowCode": "1677489723993600000",
  "scheduleTime": "",
  "failureStrategy": "CONTINUE",
  "warningType": "NONE",
  "startParams": {
    "biz_date": "2026-11-24"
  },
  "confirm": true
}
```

## 定时

| Tool | 请求样本 |
|---|---|
| `ds_list_schedules` | `{"workflowCode":"1677489723993600000","pageNo":1,"pageSize":100}` |
| `ds_create_schedule` | 见下方 |
| `ds_update_schedule` | 见下方 |
| `ds_delete_schedule` | `{"scheduleId":"123","confirm":true}` |
| `ds_online_schedule` | `{"scheduleId":"123","confirm":true}` |
| `ds_offline_schedule` | `{"scheduleId":"123","confirm":true}` |

创建定时：

```json
{
  "workflowCode": "1677489723993600000",
  "cron": "0 0 2 * * ? *",
  "startTime": "2026-11-24 00:00:00",
  "endTime": "2099-12-31 23:59:59",
  "timezone": "Asia/Shanghai",
  "failureStrategy": "CONTINUE",
  "warningType": "NONE",
  "confirm": true
}
```

更新定时只传要改的字段，工具会先查现有值再合并：

```json
{
  "scheduleId": "123",
  "workflowCode": "1677489723993600000",
  "cron": "0 0 3 * * ? *",
  "confirm": true
}
```

## 流程实例

| Tool | 请求样本 |
|---|---|
| `ds_list_instances` | `{"workflowCode":"1677489723993600000","state":"SUCCESS","startTime":"2026-11-01 00:00:00","endTime":"2026-11-24 23:59:59","pageNo":1,"pageSize":100}` |
| `ds_get_instance` | `{"instanceId":"1001"}` |
| `ds_rerun_instance` | `{"instanceId":"1001","confirm":true}` |
| `ds_rerun_from_failure` | `{"instanceId":"1001","confirm":true}` |
| `ds_pause_instance` | `{"instanceId":"1001","confirm":true}` |
| `ds_resume_instance` | `{"instanceId":"1001","confirm":true}` |
| `ds_stop_instance` | `{"instanceId":"1001","confirm":true}` |
| `ds_delete_instance` | `{"instanceId":"1001","confirm":true}` |
| `ds_complement_data` | 见下方 |

补数：

```json
{
  "workflowCode": "1677489723993600000",
  "startDate": "2026-11-01 00:00:00",
  "endDate": "2026-11-03 23:59:59",
  "runMode": "RUN_MODE_SERIAL",
  "failureStrategy": "CONTINUE",
  "warningType": "NONE",
  "confirm": true
}
```

- `runMode` 只有 `RUN_MODE_SERIAL` / `RUN_MODE_PARALLEL`。
- 只传 `yyyy-MM-dd` 时开始时间补 `00:00:00`、结束时间补 `23:59:59`；DS 本身接受 `yyyy-MM-dd HH:mm:ss`。
- 补数前工作流必须是 ONLINE。

## 任务实例

| Tool | 请求样本 |
|---|---|
| `ds_list_task_instances` | `{"instanceId":"1001","state":"FAILURE","pageNo":1,"pageSize":100}` |
| `ds_force_task_success` | `{"taskInstanceId":"2001","confirm":true}` |
| `ds_stop_task` | `{"taskInstanceId":"2001","confirm":true}` |

## 全局资源（管理员）

| Tool | 请求样本 |
|---|---|
| `ds_list_worker_groups` | `{"pageNo":1,"pageSize":100}` |
| `ds_list_tenants` | `{"pageNo":1,"pageSize":100}` |
| `ds_list_environments` | `{}` |
| `ds_list_alert_groups` | `{"pageNo":1,"pageSize":100}` |

- 这 4 个工具要求当前工作空间管理员。
- `ds_list_alert_groups` 只返回 `id` / `groupName` / `description`，插件参数不下发；`warningGroupId` 用这里的 `id`。
- `ds_list_environments` 只返回 `id` / `code` / `name` / `description`，不含 environment `config`；`environment` 用 `code`。

## 列表返回

分页工具统一返回：

```json
{
  "total": 250,
  "pageNo": 1,
  "pageSize": 100,
  "hasMore": true,
  "items": []
}
```

用户明确说继续时才查下一页。搜索/存在性查询要一直翻到 `hasMore=false`。

## 错误返回

```json
{"code": 10105, "message": "target workspace forbidden", "data": null}
```

- `10104`：读一次 code-token 重试；仍失败停止。
- `10105`：无权限/非成员/项目不存在，或该操作需要工作空间管理员。
- `10106`：参数错误，不要盲目重试。
- `10101`：DS Token 缺失。
- `10103`：DS 401/403，或 DS 业务码 30001/30002（无用户/项目权限）。
- `10102`：DS 其他错误。

MCP 客户端对 `10104` 会自动重试一次（发生在任何写副作用之前）；模型不要额外重试写操作。

# 工作流 JSON（仅高级全量更新）

正常创建/追加节点请用：

```text
ds_list_task_nodes → ds_create_workflow
ds_add_lakeinsight_node
ds_add_dependent_node
```

本文只描述 `ds_update_workflow` 的高级全量更新格式。该工具直接接收 DS 原生 JSON 字符串，正常业务不要手写。

## 1. 允许的节点类型

只允许：

```text
LAKEINSIGHT
DEPENDENT
```

其他 taskType 会被 MCP 和后端拒绝，返回 `10106`。

## 2. 必填字段

每个 task 至少要有：

```text
code
name
taskType
taskParams
isCache
```

| 字段 | 说明 |
|---|---|
| `code` | task code，必须非 0；全量更新时已有节点复用原 code |
| `name` | 节点名；LAKEINSIGHT 节点必须使用 `job_name` |
| `taskType` | `LAKEINSIGHT` / `DEPENDENT` |
| `taskParams` | 对象或 JSON 字符串 |
| `isCache` | `YES` / `NO`；缺失会导致 DS 500，MCP 会自动补 |

`version` 建议传 `1`，已有节点沿用原版本。  
task 级 `projectCode`、`userId` 由服务端按路径项目和登录用户覆盖；`taskParams` 里的 `userName` / `projectName` **不会**被覆盖，按下面 LAKEINSIGHT 规则填写。  
`taskType` 使用大写 `LAKEINSIGHT` / `DEPENDENT`；MCP 会在提交前自动转大写。  
`ds_update_workflow` 会给缺失的 `environmentCode` 补 `-1`、`workerGroup` 补空串。

## 3. LAKEINSIGHT 节点

```json
{
  "code": "1677489723993600002",
  "name": "flink-demo",
  "version": 1,
  "description": "",
  "taskType": "LAKEINSIGHT",
  "taskParams": {
    "localParams": [],
    "resourceList": [],
    "lakeinsightTaskId": "135",
    "projectName": "lake-public",
    "userName": "001"
  },
  "isCache": "NO"
}
```

| 字段 | 来源 |
|---|---|
| `name` | `ds_list_task_nodes` 返回的 `job_name`，不要自定义 |
| `lakeinsightTaskId` | 返回的 `id` |
| `projectName` | 目标 workspace name |
| `userName` | 当前平台用户名 |

后端还会做二次校验：

- `lakeinsightTaskId` 必须是当前用户 `ds_list_task_nodes` 返回的 `id`；
- `projectName` 必须等于目标 workspace name；
- `userName` 必须是当前平台用户；已有节点不允许修改 `userName` / `lakeinsightTaskId`；
- `localParams` / `resourceList` 必须为空数组；
- task 级 `workerGroup` / `environmentCode` 为非默认值时，只有工作空间管理员可以提交；更新时保持原值不受限。

## 4. DEPENDENT 节点

DS 的 DEPENDENT 参数必须放在 `taskParams.dependence` 里，不是直接放 `taskParams` 顶层：

```json
{
  "code": "1677489723993600003",
  "name": "wait_upstream",
  "version": 1,
  "taskType": "DEPENDENT",
  "taskParams": {
    "localParams": [],
    "dependence": {
      "relation": "AND",
      "dependTaskList": [
        {
          "relation": "AND",
          "dependItemList": [
            {
              "projectCode": 154529377915840,
              "definitionCode": 182668220891520,
              "depTaskCode": 0,
              "cycle": "day",
              "dateValue": "today"
            }
          ]
        }
      ],
      "checkInterval": 10,
      "failurePolicy": "DEPENDENT_FAILURE_WAITING",
      "failureWaitingTime": 30
    }
  },
  "isCache": "NO"
}
```

关键字段：

| 字段 | 说明 |
|---|---|
| `dependence.relation` | 依赖组之间的关系：`AND` / `OR` |
| `dependence.dependTaskList` | 依赖组列表 |
| `dependTaskList[].relation` | 组内依赖项之间的关系：`AND` / `OR` |
| `dependItemList[].projectCode` | 被依赖工作流所在项目，建议用数字 |
| `dependItemList[].definitionCode` | 被依赖工作流 code，建议用数字 |
| `dependItemList[].depTaskCode` | 依赖的任务 code；`0`=依赖整个工作流，`-1`=依赖工作流内所有任务，其他值=依赖单个任务，建议用数字 |
| `dependItemList[].cycle` | 依赖周期：`hour` / `day` / `week` / `month`；必须与 `dateValue` 同组 |
| `dependItemList[].dateValue` | 时间范围，如 `today`、`last1Days`、`last24Hours` |
| `dependence.checkInterval` | 检查间隔，单位**秒**（源码 `Duration.ofSeconds`） |
| `dependence.failurePolicy` | `DEPENDENT_FAILURE_FAILURE` / `DEPENDENT_FAILURE_WAITING` |
| `dependence.failureWaitingTime` | 失败后继续等待多久，单位**分钟**（源码 `Duration.ofMinutes`），仅 `..._WAITING` 生效 |

`cycle` 与 `dateValue` 必须同组，DS 前端按 cycle 渲染 dateValue 下拉：

| cycle | dateValue |
|---|---|
| `hour` | `currentHour`、`last1Hour`、`last2Hours`、`last3Hours`、`last24Hours` |
| `day` | `today`、`last1Days`、`last2Days`、`last3Days`、`last7Days` |
| `week` | `thisWeek`、`lastWeek`、`lastMonday` … `lastSunday` |
| `month` | `thisMonth`、`thisMonthBegin`、`thisMonthEnd`、`lastMonth`、`lastMonthBegin`、`lastMonthEnd` |

注意：
- `depTaskCode` 不是 task code 时不要乱填，`0` / `-1` 是保留值；
- `dateValue` 只影响运行时区间计算，`cycle` 只影响前端展示，但两者不同组会让 DS 页面上该下拉显示为空；
- `projectCode` / `definitionCode` / `depTaskCode` 建议用**数字**，因为 DS 前端把这几个值直接和下拉选项做匹配；只有超过 JS 安全整数（`2^53-1`）时才用字符串；
- `failureWaitingTime` 只在 `failurePolicy = DEPENDENT_FAILURE_WAITING` 时才有意义，其它策略下可以整个省略。

`dateValue` 常见值：

```text
currentHour
last1Hour / last2Hours / last3Hours
last24Hours
today
last1Days / last2Days / last3Days / last7Days
thisWeek / lastWeek
lastMonday ... lastSunday
thisMonth / thisMonthBegin / thisMonthEnd
lastMonth / lastMonthBegin / lastMonthEnd
```

注意：`conditionResult`、`waitStartTimeout`、`switchResult` 不是 DEPENDENT 的必需字段。DS UI 可能会带，但实际创建时只传 `localParams` + `dependence` 也能保存。

## 5. taskRelationJson

```json
[
  {
    "preTaskCode": 0,
    "preTaskVersion": 0,
    "postTaskCode": "1677489723993600002",
    "postTaskVersion": 1,
    "conditionType": "NONE",
    "conditionParams": {}
  },
  {
    "preTaskCode": "1677489723993600002",
    "preTaskVersion": 1,
    "postTaskCode": "1677489723993600003",
    "postTaskVersion": 1,
    "conditionType": "NONE",
    "conditionParams": {}
  }
]
```

- 入口节点用 `preTaskCode=0`；
- `postTaskCode` 必须出现在 task 列表；
- `preTaskVersion` / `postTaskVersion` 必须与对应 task 的 `version` 一致；
- 全量更新必须提交完整关系，不能只传新增部分。

## 6. locations

必须是数组：

```json
[
  {"taskCode": 190700000000002, "x": 200, "y": 100},
  {"taskCode": 190700000000003, "x": 500, "y": 100}
]
```

- 每个 task 都要有坐标；
- 缺坐标的节点会落在 `(0,0)`；
- `taskCode` 用**数字**：DS 前端是 `locations.find(l => l.taskCode === task.code)` 严格比较，字符串会匹配不上；
- 对象格式 `{"tasks-xxx":...}` 不是标准格式，MCP 会尝试转换，但不要主动使用。

## 7. 更新注意

- `ds_update_workflow` 是全量替换，task 列表里没有的节点会消失；
- 先 `ds_get_workflow` 取 `taskDefinitionList` / `processTaskRelationList` / `locations`；
- 已有节点复用原 `code`、`version`、`isCache`；
- 新增节点优先用 `ds_add_lakeinsight_node`，不要手写 code/relation；
- 工作流必须 OFFLINE 才能更新；
- 单次最多 200 个 task；DEPENDENT 依赖项最多 200 个、引用的被依赖工作流最多 30 个；请求体不超过 2 MB。

## 8. 常见错误

| 现象 | 原因 |
|---|---|
| `10106 unsupported taskType` | 出现 `LAKEINSIGHT` / `DEPENDENT` 之外的类型 |
| `10106 existing LAKEINSIGHT task cannot change userName or lakeinsightTaskId` | 更新时改了已有节点的 `userName` / `lakeinsightTaskId` |
| `10105 only workspace admin can select ...` | 非管理员指定了 task 级/定时级 `workerGroup`、`environmentCode`、`tenant` |
| `10106 taskDefinitionJson contains too many tasks` | 超过 200 个节点 |
| `10102` 且 DS body 为 NPE | task 缺 `isCache` |
| `10102` | taskType 没有对应插件，或 taskParams 校验失败 |
| 节点全叠在左上角 | locations 缺失、格式错误或 taskCode 对不上 |
| 运行直接失败 | relation 引用了不存在的 code，或版本不一致 |

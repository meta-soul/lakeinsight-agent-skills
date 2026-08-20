# 当前 OpenMetadata Metric MCP 参考

本参考以当前已探测到的 `openmetadata-mcp-server` Schema 为准。服务版本或权限变化时，以运行时工具 Schema 为准。

## 目录

- 已验证能力与 `create_metric` 字段
- 当前不应承诺的能力
- 已验证的表级血缘
- 设计检查清单与安全示例

## 已验证能力

| 场景 | 当前工具 | 说明 |
|---|---|---|
| 搜索指标、表、术语 | `search_metadata` | 先查重、发现 FQN |
| 读取指标或表详情 | `get_entity_details` | 核验 Metric 属性与表字段 |
| 发现近义资产 | `semantic_search` | 仅作辅助，不据此直接写入 |
| 创建单个指标 | `create_metric` | 创建 Metric 定义，不执行表达式 |
| 创建来源表到指标的表级血缘 | `create_lineage` | 已验证 `table → metric`，参数使用双方实体 ID |
| 双向核验指标血缘 | `get_entity_lineage` | 表 downstream 与 Metric upstream 应出现同一条边 |

## `create_metric` 字段

```text
name                     必填，不能含 ::
description              必填，Markdown 描述
displayName              可选
metricExpressionLanguage 必填：SQL | Java | JavaScript | Python | External
metricExpressionCode     必填：SQL 或其他表达式代码
metricType               可选，见下表
granularity              可选，见下表
unitOfMeasurement        可选，见下表
customUnitOfMeasurement  仅 unitOfMeasurement=OTHER 时填写
owners                   可选，用户或团队名称/FQN 列表
reviewers                可选，用户或团队名称/FQN 列表
relatedMetrics           可选，已存在 Metric FQN 列表
tags                     可选，已存在 Tag/Glossary Term FQN 列表
domains                  可选，已存在 Domain FQN 列表
```

| 字段 | 当前枚举 |
|---|---|
| `metricType` | `COUNT`、`SUM`、`AVERAGE`、`RATIO`、`PERCENTAGE`、`MIN`、`MAX`、`MEDIAN`、`MODE`、`STANDARD_DEVIATION`、`VARIANCE`、`OTHER` |
| `granularity` | `SECOND`、`MINUTE`、`HOUR`、`DAY`、`WEEK`、`MONTH`、`QUARTER`、`YEAR` |
| `unitOfMeasurement` | `COUNT`、`DOLLARS`、`PERCENTAGE`、`TIMESTAMP`、`SIZE`、`REQUESTS`、`EVENTS`、`TRANSACTIONS`、`OTHER` |

## 当前不应承诺的能力

| 能力 | 原因与处理方式 |
|---|---|
| 修改或删除 Metric | 当前没有专用 MCP 工具；不要假定 `patch_entity` 对 Metric 已验证 |
| 字段级指标血缘 | 当前 `create_lineage` 只有实体 type/id，没有 `columnsLineage` 参数 |
| 直接把 Metric 绑定到表、列、看板或 Pipeline | 表级来源关系可使用血缘；其他直接绑定没有对应 MCP 写入工具，Tag 只是标签标注 |
| 创建 Table Custom Metric / Profiler Metric | 与治理 Metric 不同，当前没有 MCP 入口 |
| 执行 `metricExpressionCode`、返回指标结果 | `create_metric` 仅登记定义；使用 LakeSoul/BI/任务执行层 |
| 创建定时刷新、告警或调度 | 使用调度任务或 Ingestion Pipeline；当前 MCP 无此工具 |
| 批量创建 | 当前仅单条创建；经用户确认后顺序执行单条操作 |

## 已验证的表级血缘

当前实例已验证以下调用形式：

```json
{
  "fromEntity": {"type": "table", "id": "<source-table-id>"},
  "toEntity": {"type": "metric", "id": "<metric-id>"}
}
```

正确方向始终是：

```text
来源表 → 指标
```

写入前先查重；写入后分别验证来源表 downstream 和指标 upstream。不要另外创建反向边。当前结果中的 `columnsLineage` 为空是正常的，表示只建立表级血缘。

## 设计检查清单

创建前检查：

1. 名称、中文显示名和完整业务定义是否明确？
2. 统计对象、来源 FQN、列、行粒度、过滤条件和时间窗口是否可验证？
3. 预聚合或快照字段是否会因重复汇总而失真？
4. 单位是否正确：金额才用 `DOLLARS`；件数用 `COUNT`；比例用 `PERCENTAGE`；无法表达则使用 `OTHER` 加自定义单位。
5. SQL 方言是否属于实际执行引擎，而非凭空假定？本 MCP 不会执行它，所以必须让业务/数据工程师复核。
6. 是否已找到等价已有 Metric？相同名称不同口径时，是否已确定版本策略？

## 安全示例

用户说：“登记每日销量指标，来源是 `dws_sales_day.sales_qty`。”

先读取 `dws_sales_day` 的真实 FQN、字段与日期字段；如果确认 `sales_qty` 是成功出库数量且 `dt` 为业务日期，则可预览：

```text
name: daily_sales_qty
displayName: 每日销量
metricType: SUM
granularity: DAY
unitOfMeasurement: COUNT
metricExpressionLanguage: SQL
metricExpressionCode: SELECT dt, SUM(sales_qty) AS daily_sales_qty
  FROM <verified-table-fqn>
  GROUP BY dt
```

若 `sales` 字段到底是金额还是数量未知，不得把它命名为 GMV 后直接用 `DOLLARS` 创建；应先要求确认字段语义与币种/汇率口径。

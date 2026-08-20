---
name: openmetadata-metrics
description: 通过已连接的 OpenMetadata MCP，发现、预览、去重创建并核验业务指标定义及其来源表血缘。用于 GMV、销量、转化率、复购率等指标的名称、口径、SQL/表达式、类型、粒度、单位、负责人、标签、关联指标和 table→metric 血缘治理；也用于查询已有指标或解释当前指标 MCP 的能力边界。
---

# OpenMetadata 指标治理

使用 `openmetadata-mcp-server` 管理 **Metric 指标定义**。创建指标只登记元数据和计算表达式，既不会执行 SQL，也不会产生指标值或配置定时任务。

## MCP 范围

1. 开始时先读取当前 MCP 实际提供的工具和参数 Schema；运行时 Schema 高于本文件。当前已验证的核心工具是 `search_metadata`、`get_entity_details`、`create_metric`、`create_lineage` 和 `get_entity_lineage`；`semantic_search` 仅用于发现相关资产或术语。
2. 只在需要核对来源表、字段、数据类型或业务语义时，使用 `lakeinsight-mcp-server` 或 `LakeSoul-Mcp` 做只读查询。禁止 DDL、DML、任务管理、连接管理，以及 `LakeInsight-Mcp` 的写入能力。
3. 不读取、索取、显示或保存 Token、Cookie、Authorization Header。MCP 认证或连接失败时停止并提示用户修复连接。
4. `create_metric` 当前只能逐条创建。没有经验证的批量创建、指标删除、专用修改、字段级血缘、表/字段/看板/流水线直接绑定、SQL 执行、结果查询或调度工具；不要伪称已完成这些操作。
5. 当前实例已验证 `create_lineage` 可用实体 ID 创建 `table → metric` 表级血缘，并可从表的 downstream 与指标的 upstream 双向查询。它不会自动从 SQL 解析来源，也不支持当前 Schema 中不存在的 `columnsLineage` 参数。

## 指标类型边界

区分下面三类能力，不能混用：

- **Metric 指标定义**：本 Skill 的对象。记录口径、公式/SQL、粒度、单位、Owner、标签和关联指标。
- **Table Custom Metric / Profiler Metric**：针对表或列计算统计值的另一类对象；当前 MCP 未提供其创建或绑定入口。
- **实际指标计算与调度**：由 LakeSoul 查询、BI、dbt、任务编排或 Ingestion Pipeline 完成，不由本 Skill 或 `create_metric` 自动执行。

## 授权模式

### 默认：预览

除非用户明确说“确认创建”“直接创建”或给出等价写入授权，否则只读取、分析和输出候选指标。不要以“创建一个 GMV 指标”为默认写入授权；先给出可审核预览。

### 已授权创建

仅对用户确认的候选逐条调用 `create_metric`。如果预览已明确列出来源表血缘且用户一并确认，创建指标后调用 `create_lineage`；确认中未包含血缘时不要追加。不得删除或修改已有指标，不得自动新建术语、标签、Owner/Reviewer、数据质量测试或任务。

## 标准流程

### 1. 收集可验证的口径

1. 明确指标名称、业务目的、统计对象、来源表/字段、聚合方式、过滤条件、时间窗口与粒度、单位和维度。信息不足时列为待确认，不编造 SQL。
2. 用 `search_metadata` 查找同名或近似 Metric、相关表和 Glossary Term；对候选 Metric/表调用 `get_entity_details`，读取真实 FQN、列、描述、已有 tags 和 Owner。
3. 对于用户只给出自然语言需求的场景，生成指标草案并显式区分“事实”“推断”“待确认”。仅在来源和口径明确时生成可创建的 SQL/表达式。
4. 对宽表快照、累计字段或预聚合字段，先确认行粒度和是否允许跨行 `SUM`。不得把 `mtd_sales_qty`、`avg_7d_sales_qty` 等预计算值随意再次汇总后称为全局指标。

### 2. 设计与去重

每个候选都应包含下列内容：

| 字段 | 要求 |
|---|---|
| `name` | 稳定英文标识；不得包含 `::`；与现有 Metric 去重 |
| `displayName` | 面向业务用户的中文显示名 |
| `description` | 写清统计对象、公式、过滤/排除规则、时间范围和来源 |
| `metricExpressionLanguage` / `metricExpressionCode` | 明确的表达式语言和可审核代码；`External` 时说明外部计算位置 |
| `metricType` / `granularity` / `unitOfMeasurement` | 采用当前 Schema 允许的枚举；自定义单位仅配合 `OTHER` |
| `owners` / `reviewers` / `domains` | 仅使用用户提供或已读取验证的 FQN/名称 |
| `tags` | 仅使用已存在且已核实的 Tag 或 Glossary Term FQN；它只是标签标注，不等于表字段绑定 |
| `relatedMetrics` | 仅引用已存在并验证过的 Metric FQN |

同名或定义等价的指标应复用并报告，不得新增重复定义。名称相同但口径、粒度、单位或来源不同，必须暂停并请用户指定版本策略，而不是覆盖或猜测。

输出预览并等待确认：

| 动作 | 指标 | 核心口径 | 来源与拟建血缘 | 状态/风险 |
|---|---|---|---|---|
| 创建候选 | `daily_sales_qty` | 最新业务日有效销量总和 | `dws_sales_day.sales_qty`；拟建 `dws_sales_day → daily_sales_qty` | 需确认业务日字段 |
| 复用 | `gmv_monthly` | 与候选口径一致 | 已有 Metric；复用已有血缘 | 不创建 |
| 待确认 | `GMV_Annual` | `sales` 是否金额未知 | `ev_sales_by_country.sales`；暂不建血缘 | 不能确定单位为 DOLLARS |

同时列出预计创建数、复用数、拟建/已存在血缘数、待确认项，以及不会执行的动作（字段级血缘、计算、调度、资产直接绑定等）。SQL 引用多张表时，为每张已验证来源表分别提出一条上游表级血缘；不要为子查询中未实际参与计算的表建立血缘。

### 3. 创建与核验

1. 用户确认后，逐条再次查询同名 Metric，防止并发重复。
2. 按运行时 `create_metric` Schema 填入必填参数；不要凭空填 Owner、Reviewer、Tag、Domain 或关联指标。
3. 每创建一条，立即用 `get_entity_details(entityType="metric", fqn="...")` 核验名称、表达式、类型、粒度、单位和标签；如果无法读取，报告“写入结果未核验”，不要声称成功。
4. 对已确认的表级血缘，重新读取每张来源表与 Metric 的真实 ID，并先用 `get_entity_lineage` 检查现有边。存在相同 `table → metric` 边时跳过；不要创建反向 `metric → table` 边。
5. 调用 `create_lineage(fromEntity={type:"table",id:"..."}, toEntity={type:"metric",id:"..."})`。如果接口报错，先查询血缘是否实际落库，再决定是否报告失败；不要盲目重试。
6. 创建后双向核验：来源表的 downstream 必须出现 Metric，Metric 的 upstream 必须出现来源表。仅当两端一致时报告成功；`columnsLineage` 为空时明确说明只是表级血缘。
7. 单项失败时如实记录原因并继续处理互不依赖的已确认项；不要以重试覆盖或修改已有 Metric。

## 交付与后续动作

完成后报告新建/复用的 Metric FQN、已核验属性、未创建原因和口径待确认项，并明确指出：

1. 已确认的来源表可通过表级血缘显示为 Metric 上游；字段级血缘以及表、字段、Dashboard、Pipeline 的直接绑定仍需 OpenMetadata UI/REST API 或后续 MCP 增强实现。当前 `tags` 不替代直接资产关联。
2. 如需产生数值，应在 LakeSoul/BI/dbt/任务中实现并运行对应 SQL 或代码。
3. 如需定时刷新与告警，应在数据任务、调度器或相应的 Ingestion Pipeline 中配置；当前 MCP 不会创建或启动调度。
4. 如需监控表列的计算统计，改用 Table Custom Metric/Profiler 的流程，不能把此 Metric 当作已运行的质量监控。

需要精确参数、枚举、命名示例或能力矩阵时，读取 [references/metric-capabilities.md](references/metric-capabilities.md)。

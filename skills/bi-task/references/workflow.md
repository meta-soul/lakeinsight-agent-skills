# MCP 工具规范与执行流程

## 依赖的 MCP Server

| 用途     | Lakesoul-Mcp（查数据）   | LakeInsight-Mcp（功能） |
| -------- | ------------------------ | ----------------------- |
| 列 Schema | `get_datasource_schemas` |                         |
| 列表     | `get_datasource_tables`  |                         |
| 列字段   | `get_datasource_fields`  |                         |
| 获取模板 |                          | `bi_task_get_full_app`  |
| 发布任务 |                          | `bi_task_publish`       |
| 启动任务 |                          | `bi_task_start`         |

## 第一步：获取信息

向用户确认：

- **Schema 名称**（如 `public`、`analytics`）
- **需求**（想分析什么？哪些表？）

## 第二步：数据探测与结构画像

用 Lakesoul-Mcp 查 `get_datasource_schemas` → `get_datasource_tables` → `get_datasource_fields`，**重试最多 5 次，仍查不到就告知用户并停止，不生成代码**。Token 已内置，无需用户提供。

### 结构画像

只对**候选表**（与需求相关）做结构画像，不要全量分析整个 Schema（表多时性能差）。基于 `get_datasource_fields` 返回的表名、字段名、字段类型，识别：

- 表的业务对象候选
- 主键 / 外键候选
- 指标字段候选、维度字段候选、时间字段候选
- 多表关联候选

**当前 MCP 不提供示例值、唯一值、NULL 比例、数据范围等统计信息**，不得声称已验证这些数据特征。字段名只能作为初步线索，不能单独决定字段角色，必须结合类型和业务语义综合判断。

## 第三步：业务语义与多表关系发现

### 3.1 识别业务对象

根据表名、字段名、字段类型以及用户需求，判断每张表描述什么业务对象（如 `users`→用户、`orders`→订单、`order_items`→订单明细、`products`→商品）。形成业务语义理解，而非机械罗列字段。

### 3.2 识别数据粒度

判断每张表中"一行数据"代表的业务粒度：

- `users`：一个用户
- `orders`：一个订单
- `order_items`：一个订单中的一个商品明细
- `products`：一个商品

优先根据主键候选、字段结构、表名和业务语义推断粒度。数据粒度用于：

- 判断表之间的关系
- 判断 JOIN 后是否可能产生数据膨胀
- 决定指标应在哪个粒度聚合
- 避免重复计算 SUM / COUNT 等指标

**典型数据膨胀**：`orders`（一行=订单）JOIN `order_items`（一行=明细），若再 `SUM(orders.total)` 会把同一订单金额重复累计。聚合前必须明确粒度。

当前 MCP 无法通过实际数据验证粒度，粒度属结构性推断，不得表述为已验证。

### 3.3 发现候选表关系

当存在多张相关表时，寻找潜在关系，来源包括：

- 字段名匹配：`orders.user_id` ↔ `users.user_id`
- 外键模式：`<entity>_id` ↔ `id`
- 表名 + 字段名语义匹配
- 数据类型兼容

### 3.4 关系可行性检查

仅字段名相似不能认定关系。检查：

- 字段是否真实存在
- 数据类型是否兼容
- 字段语义是否匹配
- 是否符合常见主键 / 外键结构

当前 MCP 无法检查实际数据匹配率和数据库约束，因此关系只能标记为**候选关系**，不得表述为已通过实际数据验证的外键关系。

### 3.5 关系可信度

根据可获得的结构信息，为候选关系判断可信度：

- **高**：字段语义明确匹配，符合主键/外键模式，类型兼容
- **中**：字段语义基本匹配，但缺少明确主键/外键结构
- **低**：主要依赖字段名相似，业务语义不明确

关系可信度决定使用范围：

- **高**：允许用于 JOIN、Analysis Planning 和关系可视化
- **中**：允许用于 Analysis Planning 和关系可视化；生成 JOIN 时需谨慎，优先避免承担核心指标计算
- **低**：仅作为候选关系保留，不得用于 JOIN、指标计算或业务结论

### 3.6 推断关系基数

根据字段语义、实体标识模式和表结构**推断**关系基数（1:1 / 1:N / N:1 / N:N）。例如 `users.user_id` ← `orders.user_id` 可推断为 `users 1:N orders`。

由于当前 MCP 无法获取唯一性和实际关联统计，关系基数属**推断结果**，不得表述为已通过数据统计验证。

### 3.7 建立业务关系模型

将识别到的关系整理为实体关系模型，例如：

```text
users
  │ 1:N
  ▼
orders
  │ N:1
  ▼
products
  │ N:1
  ▼
categories
```

同时识别关系的**业务语义**，区分关系性质：

- 用户 → 订单：用户产生订单
- 订单 → 商品：订单包含商品
- 商品 → 品类：商品属于品类

关系模型既用于判断可执行的 JOIN，也用于后续判断是否存在有价值的业务分析关系。

**关键：发现关系 ≠ 必须做关系分析。只有当关系能回答有价值的业务问题时，才进入最终分析。**

## 第四步：Analysis Planning

基于数据画像、业务语义、多表关系、用户需求，生成候选分析。

### 第 1 层：字段语义识别

对字段识别角色和推荐聚合方式。**以下为默认推荐，不是强制规则，最终聚合必须结合字段业务语义和数据粒度判断**：

| 字段名特征 | 角色 | 默认推荐聚合 |
|-----------|------|---------|
| `amount`/`revenue`/`sales`/`total` | 金额指标 | `SUM` |
| `price`/`unit_price` | 单价指标 | `AVG` |
| `quantity`/`qty` | 数量指标 | `SUM` |
| `user_id`/`customer_id` | 用户实体 | `COUNT(DISTINCT)` |
| `order_id`/`id`/`no` | 实体标识 | `COUNT(DISTINCT)` |
| `rate`/`ratio`/`pct` | 比率 | `AVG` |
| `status`/`type`/`category`/`region`/`channel` | 维度 | `GROUP BY` + 计数 |
| `date`/`time`/`ts`/`created_at` | 时间 | `GROUP BY` 时间粒度 |

注意：`price` 默认 `AVG`，但 `order.total_price` 这类单条金额应 `SUM`——以业务语义为准，不要机械套用。

### 第 2 层：业务语义识别

判断数据集描述的业务对象（订单/用户行为/商品/日志/静态统计），明确主实体、业务指标、维度，后续分析围绕这些展开。

### 第 3 层：字段、业务对象与表关系 → 分析问题

走「字段 → 语义 → 业务对象 → 实体关系 → 分析问题 → 数据变换 → 图表」思维链，**表关系要接入分析推理**：

| 组合/关系 | 分析问题 | 数据变换 | 图表 |
|----------|---------|---------|------|
| 时间 + 指标 | 指标随时间如何变化？ | `GROUP BY` 时间 + `SUM/AVG` | Line / Area |
| 维度 + 指标 | 哪些维度贡献了最多的指标值？ | `GROUP BY` 维度 + `SUM` + 排序 | Bar / Donut / Treemap |
| 时间 + 维度 + 指标 | 各维度随时间走势？ | 双 `GROUP BY` | Multi-line / Stacked |
| 维度 + 维度 + 指标 | 交叉维度谁差异最大？ | 透视 | Heatmap |
| 状态 + 时间 | 各环节转化如何？ | 状态先后累计 | Funnel / Waterfall |
| 用户 + 订单 | 哪些用户贡献了最多订单/金额？ | `JOIN` + `GROUP BY user` | Bar |
| 商品 + 订单 | 哪些商品贡献了最多销售额？ | `JOIN` + `GROUP BY product` | Bar / Treemap |
| 用户 + 商品 | 用户买了哪些商品？哪些商品组合更常见？ | `JOIN` + 交叉聚合 | Heatmap |
| 用户→订单→商品 | 用户购买行为如何流向商品？ | 多表 `JOIN` 聚合 | Sankey |
| 指标 + 正负值 | 增减来自哪里？ | 累计贡献 | Waterfall |

### 第 4 层：自动生成派生分析（必须满足数据条件）

满足条件才生成，**禁止虚构不存在的比较**：

- **占比**：`amount / SUM(amount)`，配合 TOP N 看集中度
- **TOP N + 其他**：类别 ≤8 全展示；9~20 取 TOP10；>20 取 TOP8；TOP3 已占 80% 则只取 TOP3 + 其他
- **环比**：时间粒度 ≥ 天 + 至少 2 个连续周期才做
- **同比**：数据覆盖足够历史周期才做（如 2026-08 vs 2025-08），不足则跳过
- **人均/单均**：`SUM(amount) / COUNT(DISTINCT user_id)` 派生指标
- **异常**：时间序列显著偏离均值的点，或某维度远低于其他维度

### 第 5 层：分析价值评分与筛选

保留约 6~10 个高价值分析。**数量是软约束，不是硬性要求**：

- 数据简单时允许少于 6 个，禁止为凑数量而生成低价值或重复分析
- 数据复杂且有足够高价值分析时接近 10 个

筛选标准：业务相关性高、数据条件满足、分析深度足、与其他分析不重复。

### 参考映射（仅作兜底）

当 Analysis Planning 无法从业务语义、用户需求和数据关系中确定合适分析时，才参考以下映射。**该表仅提供候选方向，不是页面生成规则，也不是必须生成的图表集合**：

| 字段特征               | 候选分析方向 |
| ---------------------- | ------------ |
| category / type 类字段 | 品类/分类分析 → Bar / Treemap |
| price / amount 类字段  | 金额分析 → Gauge / Waterfall |
| region / area 类字段   | 地域分布 → Treemap / Horizontal Bar |
| gender / age 类字段    | 用户画像 → Radar / Donut / Box |
| date / time 类字段     | 趋势分析 → Line / Heatmap |
| 主键+外键关联          | 关联明细 → Sankey / Table |
| 多维度字段             | 多维分析 → Parallel / Radar / Heatmap |
| 转化流程               | 转化分析 → Funnel / Sankey |

最终分析仍必须经过「业务价值 → 数据条件 → 重复性 → 图表适配性」筛选。

### Analysis Plan 最终结构

第四步结束时，应形成结构化的 Analysis Plan（作为后续页面生成的中间层）：

```text
Analysis Plan
├── Dataset Understanding（数据集理解）
│   ├── 业务对象
│   ├── 数据粒度
│   ├── 核心指标
│   └── 核心维度
├── Relationship Model（关系模型）
│   ├── 用户 → 订单
│   ├── 订单 → 商品
│   └── 商品 → 品类
├── Analysis Candidates（候选分析）
│   ├── 销售趋势
│   ├── 商品贡献
│   └── 用户-商品关系
└── Selected Analyses（已筛选分析）
    ├── Overview Candidates（总览候选：KPI / 趋势 / 贡献 / 关系 / 明细）
    └── Detail Candidates（专项候选：需要更大空间或更深入的专题分析）
```

该结构是思考框架，不必输出 JSON，但要据此决定页面内容。

## 第五步：获取模板

调用 `bi_task_get_full_app` 获取完整 Python 应用（组件注册 + 总览页 + 浏览器页 + 导航 + 默认样式），**原样使用，禁止改写基座**。

## 第六步：生成 Dashboard

```
Analysis Plan
     ├── 总览页：业务全局视图（从 Plan 中挑最重要的分析）
     └── 分析页：专项分析（承载剩余分析，按主题分组）
```

两个页面职责明确区分：

- **总览页（page_overview）**：回答"这批数据说明了什么？"——业务全局视图，由 Analysis Plan 动态生成
- **数据概览（page_browser）**：回答"原始数据长什么样？"——保留模板原有逻辑，用于查看表结构和数据预览

总览页**不是固定图表集合**，而是数据集最值得用户先看到的内容；分析页承载专项，不重复总览页已有分析。

### 总览页生成规则

总览页不是固定模板，也不是固定图表集合。必须基于 Analysis Plan 动态生成，核心目标是：

> 用户打开 Dashboard 后，能够快速理解这批数据的核心业务状况、主要趋势、主要贡献来源、关键关系和重要明细。

总览页应在保证可读性和业务价值的前提下，**尽可能覆盖 Analysis Plan 中的高价值分析**，而不是追求固定数量。

#### 1. 核心 KPI
从 Analysis Plan 核心指标中选择最重要的，最多 6 个；指标必须有明确业务意义，无核心指标则跳过，不得用普通字段计数凑数。

调用示例（多个独立查询用 `query_many` 并发执行，不同卡片不同 `color` 和唯一 `key`）：

```python
kpis = query_many({
    "sales": "SELECT SUM(amount) AS v FROM lakesoul.xxx.orders",
    "orders": "SELECT COUNT(DISTINCT order_id) AS v FROM lakesoul.xxx.orders",
    "users": "SELECT COUNT(DISTINCT user_id) AS v FROM lakesoul.xxx.orders",
    "aov": "SELECT SUM(amount)/COUNT(DISTINCT order_id) AS v FROM lakesoul.xxx.orders",
})

cols = st.columns(4)
with cols[0]: kpi_card("销售额", f"{kpis['sales'].iloc[0]['v']:,.0f}", color="blue", key="kpi_sales")
with cols[1]: kpi_card("订单数", f"{kpis['orders'].iloc[0]['v']:,}", color="purple", key="kpi_orders")
with cols[2]: kpi_card("用户数", f"{kpis['users'].iloc[0]['v']:,}", color="cyan", key="kpi_users")
with cols[3]: kpi_card("客单价", f"{kpis['aov'].iloc[0]['v']:,.0f}", color="green", key="kpi_aov")
```

注意：多个相互独立的查询（尤其 KPI 卡片）统一用 `query_many` 并发执行，不要逐个串行 `query()`；查询结果取标量格式化后传入 `value`，不同卡片用不同 `color`。

**KPI 取值安全**：取标量前检查 DataFrame 非空，避免空结果导致 `IndexError`；每个 KPI 独立判空，无数据时该卡片直接不渲染（禁止显示 `"--"` 占位）：

```python
df = kpis["sales"]
if df.empty or df.iloc[0]["v"] is None:
    pass  # 无数据，不渲染该 KPI 卡片
else:
    kpi_card("销售额", f"{df.iloc[0]['v']:,.0f}", color="blue", key="kpi_sales")
```

**numpy 类型转换**：`query()` 返回的数值是 `numpy` 类型（`numpy.int64` / `numpy.float64`），组件 `data` 序列化 JSON 时不兼容，会导致整卡数据丢失。凡是传给组件 `data` 的派生值（尤其 `delta` 和 `delta_positive`），必须先转原生 Python 类型：

```python
pct = (last7 - prev7) / prev7 * 100   # numpy.float64
delta = f"{pct:+.1f}%"
kpi_card("近7日销售额", f"{last7:,.0f}", delta=delta, delta_positive=bool(pct >= 0), color="pink", key="kpi_7d")
```

`delta_positive` 必须是原生 `bool`（`bool(pct >= 0)`），禁止直接传 `numpy.bool_`。

#### 2. 业务关系
Relationship Model 中存在高/中可信度且有业务价值的关系时生成，最多 1~2 个关系类组件。按语义选图（Relationship Graph / Sankey / Treemap）。禁止仅因有外键就生成关系图，禁止把 Schema → Table 当业务关系。

#### 3. 核心分析
从 Selected Analyses 选高价值分析：默认 4~6 个，数据复杂时可扩展到 6~8 个。优先覆盖不同分析视角（趋势/贡献/TOP N/占比/用户表现/商品表现/地域/多维交叉/关系/转化/异常），禁止多个高度相似的分析（如"销售额趋势"和"销售额月趋势"回答同一问题，只留一个）。

#### 4. 关键明细
选择 1~2 个帮助理解核心分析的表格（TOP N 汇总、核心对象排名、关键指标明细、关系汇总），禁止直接展示完整原始大表。

#### 5. 总览页丰富度
推荐容量：KPI 0~6、关系 0~2、核心分析 4~8、明细 1~2，总组件通常 8~15 个。数据简单可少于此范围，数据复杂可接近上限。**组件数量是软约束，宁可少也不能凑数。**

#### 6. 分析覆盖策略
优先覆盖不同类型的高价值分析，避免连续生成多个同类图表（如 5 个相似的 Bar Chart）。

#### 7. 总览页与分析页去重
同一分析只出现一次。已进总览页的分析，专项页可做更深的下钻，但必须回答不同的问题。总览页是业务入口，专项页负责深入。

### Relationship Graph 数据生成

关系图必须基于第三步的业务关系模型，仅展示：

- 已识别的业务实体（节点用业务名，如 `用户`/`订单`/`商品`，不用数据库技术名 `users`/`orders`）
- 高/中可信度关系、推断的基数、关系语义

禁止直接将 Schema → Table 作为业务关系图。

编写分析页示例：

```python
def page_commodity():
    df = query("SELECT category, COUNT(*) AS cnt FROM lakesoul.<schema>.<table> GROUP BY category")
    ...
    cols = chart_cols(len(df))
    render_chart_row(cols, [
        ("标题A", plot_bar(df, "x", "y")),
        ("标题B", plot_pie(df, "label", "value")),
    ])

pages["商品分析"] = page_commodity
```

要点：

1. 页面标题 `st.markdown("# 标题")`，≤15 字，不加描述性后缀
2. 每个分析页函数开头**必须调 `sync_page_colors()`**
3. 图表标题用 `st.markdown("##### 标题")`，渲染用 `st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)`
4. **图表排布**统一用 `chart_cols(n_items)` + `render_chart_row`：>10 项独占一行，≤10 项并排且高度自动对齐 440；禁止 `st.columns(2)` 硬编码
5. 空表 `df.empty` 时跳过展示
6. **数据加载提示**：页面内多个 `query()` 调用用统一的 `with st.spinner("加载中..."):` 包裹，避免每个查询各自弹出提示

### Relationship Visualization（关系可视化规则）

根据关系语义选择图表：

- **Relationship Graph**：展示业务实体之间的关联结构，不表达数据流量和业务路径（如 `users ─ orders ─ products`）
- **Sankey**：展示具有明确方向和数量意义的业务流动（如用户→商品购买金额流向）
- **Treemap**：展示层级归属及指标规模/占比（如品类下各商品份额）

边界示例：
- `users ─── orders ─── products` 纯结构 → Relationship Graph
- `Users → Orders → Products` 表示购买金额/数量流动 → Sankey
- `Category ├ Product A 40% ├ Product B 30%` → Treemap

禁止：仅因存在外键就生成 Sankey、把纯数据结构关系伪装成业务流、为展示复杂图表而虚构业务关系。

## 第七步：Validation（发布前检查）

### 数据
- SQL 中的表和字段真实存在，JOIN 字段真实存在
- JOIN 基于已识别的候选关系
- 没有引用不存在的数据

### JOIN / 聚合
- 检查 JOIN 是否可能产生一对多数据膨胀（如订单金额因 JOIN order_items 被重复累计）
- 检查指标聚合是否因 JOIN 被重复计算
- 明确聚合发生在 JOIN 前还是 JOIN 后，明确 JOIN 前后数据粒度
- 不得根据字段名相似随意 JOIN

### 分析
- 没有虚构业务关系，没有为丰富图表而加无价值分析
- 分析数量合理（通常 6~10 个），不得为了满足数量要求而增加低价值分析
- 派生分析满足数据条件

### 页面
- 总览页来自 Analysis Plan，分析页没覆盖原有 pages
- 每个页面开头调 `sync_page_colors()`
- 图表统一用 `chart_cols` + `render_chart_row`，空 DataFrame 不展示

### 图表
- 图表字段真实存在，不对高基数字段直接生成全量分类图
- 时间粒度合理，图表类型与分析问题匹配

## 第八步：发布任务

写入 `.py` 文件后调用 `bi_task_publish`。暗色主题已内置，默认无需处理；如需自定义主题，传 `theme_config` 参数（TOML 字符串，上传后覆盖默认配置）：

```toml
[theme]
base = "light"
primaryColor = "#409eff"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans-serif"
```

## 第九步：启动任务（若自动启动失败）

发布后自动启动；若返回"启动失败"，调用 `bi_task_start` 手动启动。

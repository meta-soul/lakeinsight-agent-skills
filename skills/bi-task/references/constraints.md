# 异常处理与硬性禁止项

## 异常处理

### 数据库连接失败

```python
try:
    df = query(sql)
except Exception as e:
    st.error(f"查询失败: {e}")
    st.info("请检查 Token 是否过期，或联系管理员确认 Presto 服务状态。")
    return
```

### 空表 / 无数据

```python
if df.empty:
    st.warning("该表暂无数据，跳过展示。")
    return
```

### Token 过期

症状：`401 Unauthorized` 或 `Connection refused` → 提示用户重新生成看板

---

## 硬性禁止项

1. **页面标题规范** — 每页只有一个标题（`st.markdown("# xxx")`），标题来自对该页数据的总结，不超过 15 个字。禁止拼接"数据分析看板"、"数据源: xxx (Presto)"等描述。例：`st.markdown("# 商品品类分布")`。
2. **禁止虚构字段名** — 必须用 `get_datasource_fields` 返回的真实字段名。
3. **禁止跳过数据查询** — 先调 MCP 查数据再写代码；无数据重试最多 5 次后退出，不要调 `bi_task_get_full_app`。
4. **禁止只放两个页面** — 必须根据数据特征生成额外分析页。
5. **懒加载 Schema 发现** — 不在模块顶层执行，避免启动延迟。
6. **组件体系（强制）** — 必须用模板内置的 `st.components.v2.component` 组件（`bi_kpi_card` / `bi_background` / `bi_tz_offset`），禁止手写 HTML/CSS 自定义组件。组件 JS 必须 `export default function` 语法，调用时传 `data` 和唯一 `key`，禁止传 `props`。
7. **禁止手写图表样式** — 图表用模板内置 `plot_xxx` 函数；禁止手写颜色（`marker=dict(color=...)`、`colorscale=...`），颜色由 `_paint` 自动管理。
8. **每页统一色组** — 页面函数开头调 `sync_page_colors()`，该页所有图表自动使用同一色组，图表边框光晕自动同步。
9. **图表布局** — 用 `chart_cols(n_items)` + `render_chart_row(cols, charts)` 决定并排/独占（>10 项独占，≤10 项并排），禁止硬编码 `st.columns(2)`。
10. **SQL/Python 引号规范** — Presto 用双引号 `"` 包裹含关键字的表名（如 `"user"`）。SQL 写在 Python 三引号 `"""` 内最安全。**Presto 不支持反引号**，会报 `backquoted identifiers are not supported`。**含中文/非 ASCII 的列名必须用双引号**。
11. **`@st.cache_data` 参数命名** — 不能接 `query_fn` 作普通参数名，必须加前导下划线：`def func(_query_fn)`。
12. **Presto information_schema 限制** — `information_schema.tables` 没有 `cardinality` 列，行数通过每表 `SELECT COUNT(*) FROM lakesoul.<schema>.<table>` 获取。
13. **多系列数据格式** — `plot_line` / `plot_grouped_bar` 等的 `y_cols` 是 DataFrame 列名；数据来自 `groupby().reset_index()` 时必须先 `pivot_table` 转宽表。
14. **单列也必须传列表** — `plot_line` / `plot_multi_line` 的 `y_cols` 即使一列也要用列表包裹，否则逐字符迭代 KeyError。
15. **图表透明背景** — 模板 `tech_template` 自动处理，不要手设 `paper_bgcolor` / `plot_bgcolor`。
16. **Token 管理** — Token 由 `bi_task_get_full_app` 自动通过 `/user/getPrestoInfo` 获取并注入，禁止手动生成或覆盖。
17. **禁止裁剪模板基础设施** — `bi_task_get_full_app` 返回的模板代码中，以下部分必须原样保留：
   - 所有组件注册代码（KPI Card / Background / 时区探测的完整 CSS/JS/HTML）
   - `sync_page_colors()` 调用、全局 CSS 块、Plotly helpers 全系列函数
   - `pages` 字典声明、`st.sidebar.radio` 导航路由
   - `st.set_page_config(...)` 调用及 `page_title` 固定为 "湖仓数据智能中台-LakeInsight"，禁止修改
   只允许：`pages` 字典追加新条目、修改页面函数体内部业务逻辑。
18. **图表标题必须在 chart_cols 列内** — 并排图表时，每个图表的 `st.markdown("##### 标题")` 必须放在 `with cols[i]:` 块内，禁止放在 `chart_cols()` 调用之前。
19. **禁止虚构表关系** — 多表 `JOIN` 前必须验证：字段真实存在、类型兼容、语义匹配、数据匹配覆盖。仅字段名相似不能认定关系。
20. **禁止因有外键就做关系分析** — 发现关系 ≠ 必须做关系分析。只有关系能回答有价值业务问题时才进入分析，否则单表分析即可。
21. **关系可视化按语义选图** — `Sankey` 仅用于有方向性/流动性/路径意义的关系；`Treemap` 用于层级归属。禁止把纯数据结构关系伪装成业务流。
22. **禁止虚构派生分析** — 环比需时间粒度 ≥ 天且 ≥2 个连续周期；同比需覆盖足够历史周期。数据不足时跳过，禁止为丰富图表而虚构不存在的比较。
23. **分析数量软约束** — 总览页约 8~15 个组件（KPI 0~6 / 关系 0~2 / 分析 4~8 / 明细 1~2），专项页适量。禁止为凑数量生成低价值或重复分析，多个图表表达同一信息只留一个。
24. **JOIN 字段重名用别名** — 多表 `JOIN` 后同名字段必须用 `AS` 起别名，避免结果列名冲突。
25. **JOIN 防数据膨胀** — 多表 `JOIN` 后聚合指标时，检查一对多关系是否导致重复累计（如订单金额因 JOIN 明细表被重复求和）。明确聚合发生在 JOIN 前还是后。
26. **时间窗口基准** — 查询必须先取 `MAX(dt)` 拿到数据最新日期，近 N 天 / 环比都基于该最新日期计算，禁止直接用 `current_date`（离线/demo 数据常滞后数月）。
27. **日期类型处理** — 该 Presto 驱动返回的 DATE 是字符串 → 解析用 `pd.Timestamp(v)`，格式化用 `strftime('%Y-%m-%d')`；禁止 `isoformat()`（会带 `T00:00:00`，被 `date '...'` 字面量拒绝）。
28. **Treemap 数据规范** — 模板 `plot_treemap` 不自动补根节点，父节点必须出现在 `labels` 中，生成数据时需补齐父节点行。
29. **KPI 空值策略** — 无数据的 KPI 卡片直接不渲染，禁止显示 `"--"` 占位。

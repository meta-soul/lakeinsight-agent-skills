# Streamlit 组件规范

## 主题

- **默认深色主题**：背景组件自动显示极光深空效果
- **切换浅色主题**：用户在 Streamlit 设置中切换主题时，背景组件自动隐藏，文字颜色自动适配
- CSS 已内置 `[data-theme="light"]` 规则，无需手动处理主题切换逻辑
- 如需自定义主题，在 `bi_task_publish` 时传入 `theme_config` 参数

## 新增页面样式约束

新增分析页时必须遵守以下规则，避免样式与深空主题不兼容：

### 标题
- 所有页面标题一律用 `st.markdown("# 标题")`，禁止 `st.title()`、`st.header()`
- 模板内置 h1 全局样式（3D 立体文字效果），其他标签不受影响

### 背景与颜色
- 禁止硬编码浅色背景：不要写 `style="background: white"` 或 `style="background: #fff"`
- 禁止黑色/深灰文字：不要用 `color: #000`、`color: #333`
- 深色主题下文字自动为 `rgba(255,255,255,0.9)`，无需手动设色
- 如需高亮色，推荐 `#409eff`（蓝）`#00d4ff`（青）`#409eff80`（半透明蓝）

### 分割线
- 用 `st.markdown("<hr>", unsafe_allow_html=True)`，模板内置动画光效分隔线
- 不要用 `st.divider()`（样式不统一）

### 图表布局
- 用模板内置的 `chart_cols(n_items)` + `render_chart_row(cols, charts)` 自动判定并排/独占
- 每张图都加 `st.markdown("##### 标题")` 作为图表标题
- `st.plotly_chart(fig, use_container_width=True)` — 模板 Plotly 默认透明背景，不要手动设 `paper_bgcolor` 或 `plot_bgcolor`

### 组件
- `st.components.v2.component()` 返回可调用对象，调用时传 `data` 和 `key`
- 禁止传 `props`，每个实例需唯一 `key`

### KPI 卡片（kpi_card）

```python
kpi_card(label, value, delta="", delta_positive=True, color="blue", key="xxx")
```

参数：
- `label`：指标名（如"销售额"）
- `value`：指标值（字符串，如 `"1,234,567"` 或 `"¥98.5万"`）
- `delta`：变化量（可选，如 `"+12.5%"`）
- `color`：卡片配色，可选 `blue` / `purple` / `cyan` / `pink` / `green` / `orange`
- `key`：唯一标识，每个卡片必须不同

**关键约束**：
- 不同 KPI 卡片必须用不同的 `color`，禁止全部用默认 `blue`
- `value` 是显示字符串，数字较大的先用 `format()` 或手动加千分位/单位，不要直接传原始数字
- 每个卡片 `key` 必须唯一（如 `kpi_sales`、`kpi_orders`）
- **`delta_positive` 必须是原生 `bool`，禁止传 `numpy.bool_`**（`numpy` 类型序列化 JSON 会丢数据）。计算得到的 `numpy` 数值必须转原生类型：`float(pct)`、`bool(pct >= 0)`
- 每个 KPI 独立判空，无数据时该卡片直接不渲染（禁止显示 `"--"` 占位）

```python
df = kpis["sales"]
if df.empty or df.iloc[0]["v"] is None:
    pass  # 无数据，不渲染该 KPI 卡片
else:
    kpi_card("销售额", f"{df.iloc[0]['v']:,.0f}", color="blue", key="kpi_sales")
```

### 消息横幅
- 成功用 `st.success(...)`，警告用 `st.warning(...)`，错误用 `st.error(...)`，信息用 `st.info(...)`
- 这些组件自动适配主题，禁止用 `st.markdown` 代替

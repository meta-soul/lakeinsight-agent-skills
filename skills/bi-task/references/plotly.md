# Plotly 图表规范

```python
from core.plotly_helpers import (
    plot_bar, plot_stacked_bar, plot_grouped_bar,
    plot_line, plot_multi_line, plot_pie, plot_donut_with_label,
    plot_scatter, plot_heatmap, plot_box, plot_violin, plot_table,
    plot_treemap, plot_sunburst, plot_funnel, plot_gauge,
    plot_waterfall, plot_radar, plot_sankey, plot_parallel,
)
```

常用示例：

```python
fig = plot_treemap(df, "label", "parent", "value")
fig = plot_sunburst(df, "label", "parent", "value")
fig = plot_funnel(df, "stage", "count")
fig = plot_gauge(value=78.5, title="完成率 %", min_val=0, max_val=100)
fig = plot_waterfall(df, "item", "amount")
fig = plot_radar(df, "dimension", ["current", "target"])
fig = plot_sankey(df, "source", "target", "value")
st.plotly_chart(fig, use_container_width=True)
```

颜色由 `_paint(fig)` 自动管理：每页通过 `sync_page_colors()` 从 GROUPS（12 组配色）中选取一组，该页所有图表统一重涂。禁止手写颜色。

---

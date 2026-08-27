---
name: daft-lakesoul
version: 1.0.0
keywords:
  - Daft
  - LakeSoul Daft
  - to_daft
  - write_daft
  - LakeSoul
  - Ray runner
  - filter pushdown
  - 谓词下推
  - Daft 写入
mcp_required:
  - lakeinsight-mcp
description: |
  使用 Daft 读取、过滤、写入 LakeSoul 表，或排查 Daft/LakeSoul/Ray runner 集成问题时使用。
  覆盖 LakeSoul scan.to_daft()、谓词下推、Daft Native/Ray runner、write_daft()、分区与小文件。
---

# LakeSoul Daft 开发与排障

## 使用边界

本 Skill 针对 LakeSoul Python API 的 Daft 集成：

```python
from lakesoul import LakeSoulCatalog
import lakesoul.daft

catalog = LakeSoulCatalog.from_env()
df = catalog.scan("orders", namespace="default").to_daft()
```

`import lakesoul.daft` 用于注册 LakeSoul 的 Daft 扩展；不要省略。只有需要分布式 Daft 执行时才配置 Ray runner。

## 读取和过滤

优先在 `collect()` 前写选择列和过滤条件，让 Daft 优化器有机会下推：

```python
scan = catalog.scan("orders", namespace="default").options(
    batch_size=8192,
    thread_count=4,
)
df = (
    scan.to_daft()
    .select("o_orderkey", "o_orderdate", "o_totalprice")
    .where((daft.col("o_orderdate") >= "1995-01-01") & (daft.col("o_totalprice") > 1000))
)
result = df.collect()
```

规则：

- 需要 LakeSoul 谓词下推时，应在首次 `collect()` 前添加过滤。`collect()` 返回已物化的 Daft DataFrame，之后仍可继续过滤，但该过滤只作用于已读取的数据，不能再下推到原始 LakeSoul scan。
- 仅把 LakeSoul reader 能表达的谓词下推；Daft Python UDF 或无法转成 PyArrow expression 的过滤必须保留给 Daft 执行，不能因为下推转换失败而让读取失败。
- 用 `df.explain(show_all=True)` 检查过滤是否进入 LakeSoul source 计划。
- `to_batches()` 是同步迭代接口；它以 batch 流式产生数据，不会一次把完整表物化到 Python 内存，但 batch、预读数量和并发仍决定峰值内存。

## Native runner 与 Ray runner

默认 Daft Native runner：适合单进程本地开发和集成测试。

Ray runner：先连接现有 Ray 集群，再由 Daft 复用该上下文：

```python
import ray
from daft.runners import set_runner_ray

ray.init(address="auto")
set_runner_ray(address="auto", noop_if_initialized=True)
```

不要把 `ray.init(address="auto")` 当成创建集群；它只连接由 RayJob 创建的 Head。Ray worker 资源、镜像和自动扩缩容由 RayJob 配置控制。

## 写入 LakeSoul

```python
table = catalog.table("target", namespace="default")
result = table.write_daft(
    df.into_partitions(4),
    format="parquet",
    batch_size=8192,
    max_file_size=128 * 1024 * 1024,
)
print(result.files, result.row_count)
```

写入前必须确认：

1. DataFrame 列名和 LakeSoul 表 schema 一致；对不兼容类型先显式 `cast`。
2. `string`/`large_string`、`binary`/`large_binary` 的 Arrow 表示差异可归一化；不能把其他类型不匹配静默放过。
3. 控制 `into_partitions()` 数量。当前写入模型是一个 MicroPartition 至少对应一个 writer，因此过多 MicroPartition 会直接制造小文件。
4. `max_file_size` 只会拆分过大的单个 writer 输出，不会把多个小 MicroPartition 合并成大文件。

若 LakeSoul 按 `dt` 分区，应在写入前让相同 `dt` 尽量聚集；不要指望 sink 自动全局重分区。

## 正确性验证

读取下推测试应同时验证：

1. `explain()` 中源算子包含预期 filter/projection；
2. Daft 结果与 LakeSoul Native Arrow reader 使用等价 PyArrow filter 的结果逐行一致。

比较时允许 Arrow 的 `string` 与 `large_string` 表示不同，但必须比较列名、行值、排序语义及其余数据类型；不要仅比较行数。

写入测试分两层：

- 单元测试：Mock LakeSoul Writer/元数据提交，覆盖 `abort()`、结果聚合、空输入和 `max_file_size` 传递。
- 集成测试：真实 `df.write_sink()` + Native runner，写入测试库路径后用 Native reader 与 Daft reader 回读验证。

Ray 集成测试需要真实可访问的 Ray 集群和对象存储；CI 未提供这些依赖时，不应伪造为普通单元测试成功。

## 故障定位

| 现象 | 优先检查 |
| --- | --- |
| 过滤报 PyArrow 转换异常 | 不支持的 Daft 谓词应跳过 native pushdown，保留给 Daft |
| 结果正确但没有下推 | `explain(show_all=True)`、谓词列是否在 source schema 中 |
| 小文件过多 | `into_partitions()` 数量、LakeSoul 分区基数、每个 MicroPartition 大小 |
| Ray 中只跑 Head | `ray.init(address="auto")`、worker pod 资源、任务 `num_cpus` 请求 |
| 写入类型错误 | DataFrame Arrow schema 与 LakeSoul schema；先做显式 cast |

## 不能承诺的语义

对象存储文件写入和 LakeSoul PostgreSQL 元数据提交不是跨系统原子事务。

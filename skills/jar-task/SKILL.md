---
name: jar-task
version: 1.0.0
keywords:
  - JAR任务
  - 程序包任务
  - Flink JAR
  - Spark JAR
  - create jar task
  - 创建JAR任务
mcp_required:
  - lakeinsight-mcp
description: |
  创建 Flink/Spark 程序包任务（JAR 任务），基于已上传的程序包快速配置和创建任务。
  Keywords: JAR任务, 程序包任务, Flink JAR, Spark JAR, create jar task, 创建JAR任务
---

# LakeInsight 程序包任务（JAR 任务）

## 使用场景

将已上传的程序包（Flink AppJar、Spark AppJar、UDFJar 等）关联到任务，
配置运行资源和参数后，将任务提交到生产环境运行。

## 完整流程

```
第一步：upload_package     → 上传程序包文件
第二步：get_packages_by_type → 确认包已上传（可选）
第三步：create_jar_task     → 创建 JAR 任务并关联程序包
第四步：apply_online_jar_task → 申请上线（可选）
```

---

## 参数说明

### 基础参数（必填）

| 参数         | 类型   | 说明                                                   |
| ------------ | ------ | ------------------------------------------------------ |
| name         | string | 任务名，平台唯一标识                                   |
| package_name | string | 已上传的程序包名称，对应 upload_package 时的 name 字段 |
| sql_engine   | number | 处理引擎：0=Flink, 1=Spark（默认 0）                   |

### 基础参数（可选）

| 参数                    | 类型     | 说明                                                        |
| ----------------------- | -------- | ----------------------------------------------------------- |
| description             | string   | 任务描述                                                    |
| spark_type              | 2 \| 5   | Spark 包类型。2=Spark AppJar, 5=PySpark Main File（默认 2） |
| main_class              | string   | 主类全限定名（如 com.example.App）                          |
| dependent_package_names | string[] | 依赖的 UDF JAR 包名称列表                                   |
| archives_package_name   | string   | PySpark 的 Archives 依赖包名（仅 spark_type=5 时）          |
| params                  | string   | 自定义运行参数，格式 `--key value --key2 value2`            |

### Flink 资源参数 (`flink` 对象, sql_engine=0 时)

| 参数                | 类型             | 默认值   | 说明                  |
| ------------------- | ---------------- | -------- | --------------------- |
| job_type            | "stream"/"batch" | "stream" | 运行模式              |
| checkpoint_interval | string           | "300000" | Checkpoint 间隔（ms） |
| parallelism         | number           | 1        | 并行度                |
| slots               | number           | 2        | 槽位数                |
| memory_process_size | number           | 2048     | 进程内存（MB）        |
| memory_offheap_size | number           | 128      | 堆外内存（MB）        |
| resource            | string           | ""       | 自定义配置项          |

### Spark 资源参数 (`spark` 对象, sql_engine=1 时)

| 参数            | 类型          | 默认值   | 说明                |
| --------------- | ------------- | -------- | ------------------- |
| num_executors   | number        | 4        | 执行器数量          |
| executor_cores  | number        | 2        | 每个执行器 CPU 核数 |
| executor_memory | [number, "G"] | [4, "G"] | 执行器内存          |
| driver_cores    | number        | 1        | 驱动器 CPU 核数     |
| driver_memory   | [number, "G"] | [2, "G"] | 驱动器内存          |
| resource        | string        | ""       | 自定义配置项        |

---

## 调用 Tool

参数确认后，调用 `create_jar_task` Tool 执行。

### 包类型对照

| type | 标签              | 文件扩展名   | 说明                    |
| ---- | ----------------- | ------------ | ----------------------- |
| 0    | Flink AppJar      | .jar         | Flink 应用主 JAR        |
| 1    | Flink UDFJar      | .jar         | Flink 自定义函数 JAR    |
| 2    | Spark AppJar      | .jar         | Spark 应用主 JAR        |
| 3    | Spark UDFJar      | .jar         | Spark 自定义函数 JAR    |
| 4    | PySpark Archives  | .zip/.tar.gz | PySpark 虚拟环境/依赖包 |
| 5    | PySpark Main File | .py          | PySpark 主入口文件      |
| 6    | Python Archives   | .zip/.tar.gz | Python 依赖包           |

---

## 典型场景

### 场景 A：创建 Flink JAR 任务（最简单）

```json
{
  "name": "flink-realtime-demo",
  "sql_engine": 0,
  "package_name": "flink-app-1.0",
  "description": "Flink 实时数据处理 Demo"
}
```

### 场景 B：创建带主类和自定义并行的 Flink 任务

```json
{
  "name": "flink-custom-job",
  "sql_engine": 0,
  "package_name": "flink-app-1.0",
  "main_class": "com.example.FlinkApp",
  "params": "--nummarkEnd 40000 --nummarkLimit 36000",
  "flink": {
    "job_type": "batch",
    "parallelism": 4,
    "memory_process_size": 4096,
    "checkpoint_interval": "600000"
  }
}
```

### 场景 C：创建 Spark JAR 任务

```json
{
  "name": "spark-batch-demo",
  "sql_engine": 1,
  "package_name": "spark-app-1.0",
  "main_class": "com.example.SparkApp",
  "spark": {
    "num_executors": 8,
    "executor_cores": 4,
    "executor_memory": [8, "G"],
    "driver_memory": [4, "G"]
  }
}
```

### 场景 D：创建 PySpark 任务

```json
{
  "name": "pyspark-ml-demo",
  "sql_engine": 1,
  "spark_type": 5,
  "package_name": "pyspark-main",
  "archives_package_name": "pyspark-env",
  "spark": {
    "num_executors": 4,
    "executor_cores": 2
  }
}
```

---

## 常见问题

| 问题               | 原因                         | 解决方案                                   |
| ------------------ | ---------------------------- | ------------------------------------------ |
| 找不到程序包       | 包名与 upload_package 不一致 | 用 get_packages_by_type 确认包名和类型     |
| UDF 依赖找不到     | 依赖包未上传                 | 先用 upload_package 上传依赖 JAR           |
| archives 包找不到  | PySpark Archives 包未上传    | 先用 upload_package(type=4) 上传           |
| 上传后无法创建任务 | 创建任务使用了错误的包名     | 包名必须和 upload_package 的 name 完全一致 |

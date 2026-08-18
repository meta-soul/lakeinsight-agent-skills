# Python 任务配置参考

> sql_engine = 2，固定 job_type = "batch"

## 完整参数说明

| 参数             | 类型          | 默认值   | 说明                                                                                                                                                                                                    |
| :--------------- | :------------ | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| resource         | string        | ""       | 其他资源配置，通常留空。                                                                                                                                                                                |
| job_type         | "batch"       | "batch"  | 任务类型。**固定为 `batch`（批处理）**，不支持流处理。                                                                                                                                                  |
| sql_details      | string        | ""       | 脚本内容详情。**通常保持留空 `""`**。系统会自动根据 `node_path` 读取文件内容并注入，调用端无需关注和传递具体代码文本。                                                                                  |
| archives_package | string\|null  | null     | Python 依赖包名称或 ID，`null` 表示使用平台内置 Python 环境。                                                                                                                                           |
| executor_cores   | number        | 2        | 最大运行 CPU 核心数。                                                                                                                                                                                   |
| executor_memory  | [number, "G"] | [4, "G"] | 最大运行内存。格式为固定数组，如 `[4, "G"]`。                                                                                                                                                           |
| driver_cores     | number        | 1        | 驱动/运行 CPU 核心数。                                                                                                                                                                                  |
| driver_memory    | [number, "G"] | [2, "G"] | 驱动/运行内存。格式为固定数组，如 `[2, "G"]`。                                                                                                                                                          |
| params           | string        | ""       | 自定义运行参数与动态配置透传项。Python 脚本内通常通过 `sys.argv` 或 `argparse` 解析。<br>**格式要求**：`--key value`，多个配置项之间用**空格**分隔。<br>例如：`--nummarkEnd 40000 --nummarkLimit 36000` |
| node_path        | string        | 可选     | `.py` 或 `.ipynb` 文件路径。**新建任务**时系统会自动读取文件内容，并从中自动提取文件名作为任务名（若未显式指定 `name`）。对于前端和 Tool 调用而言，**无需感知也无需传递 `sql_details` 字段**。          |
| node_label       | string        | 可选     | 文件名标签，通常与 `node_path` 中的文件名保持一致（如 `script.py`）。                                                                                                                                   |

---

## archives_package 说明

Python 任务依赖自定义包时，需要先通过 `upload_package` 上传，再在此填写包名或 ID。

```
upload_package（先执行）→ 获得包名 → create_task 填入 archives_package
```

如果使用平台内置 Python 环境，设置为 `null`。

## .ipynb 文件支持

提供 `.ipynb` 文件路径时，系统自动：

1. 解析 Notebook JSON 格式
2. 提取所有 `cell_type = "code"` 的单元格
3. 拼接为可执行的 Python 脚本

Markdown cell 和 output 会被自动忽略。

## 示例

```json
{
  "app_info": {
    "sql_engine": 2,
    "sql_info": {
      "node_path": "/scripts/ml_training.py",
      "node_label": "ml_training.py",
      "sql_details": "",
      "resource": "",
      "archives_package": "sklearn-env",
      "job_type": "batch",
      "executor_cores": 2,
      "executor_memory": [4, "G"],
      "driver_cores": 1,
      "driver_memory": [2, "G"],
      "params": "--nummarkEnd 40000 --nummarkLimit 36000"
    }
  }
}
```

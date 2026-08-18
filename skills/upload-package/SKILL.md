---
name: upload-package
version: 1.0.0
keywords:
  - upload
  - package
  - 上传
  - 程序包
  - Python包
  - JAR
  - 依赖
  - archives_package
mcp_required:
  - lakeinsight-mcp
description: |
  上传程序包文件到 LakeInsight 平台，支持 Python 环境包、JAR 包等类型。
  上传完成后自动注册包元数据，供数据开发任务通过 archives_package 字段引用。
  当用户说"上传包"、"上传文件"、"上传 Python 环境"、"上传 JAR"、
  "传程序包"、"添加依赖包"、"上传依赖"时触发。
  Keywords: upload, package, 上传, 程序包, Python包, JAR, 依赖, archives_package
---

# LakeInsight 程序包上传

## 使用场景

Python 任务需要自定义依赖（如 scikit-learn、pandas 特定版本），
或 Flink/Spark 任务需要自定义 JAR 时，先上传程序包，再创建任务引用。

```
第一步：upload_package 上传包 → 获得包名
第二步：submit_approval 创建任务 → archives_package 填包名
```

---

## 参数说明

| 参数                    | 必填 | 类型          | 说明                                         |
| ----------------------- | ---- | ------------- | -------------------------------------------- |
| name                    | ✓    | string        | 包名，平台唯一标识，创建任务时通过此名称引用 |
| type                    | 否   | number        | 包类型，固定为 6（Python 包），默认 6        |
| resource_info.file_name | ✓    | string        | 上传的文件名，含扩展名，如 env.tar.gz        |
| description             | 否   | string        | 包描述，建议填写版本和用途                   |
| fileContent             | ✓    | Buffer/string | 文件内容，Buffer 或 base64 字符串            |

---

## 上传流程（内部实现，对用户透明）

系统采用分片上传，每片 3MB，默认 5 个并发，大文件稳定可靠。

阅读 [references/upload-internals.md](references/upload-internals.md) 了解分片上传细节。

```
1. 获取 uploadID    → /resourceManager/getUploadID
2. 文件切片         → 每片 3MB
3. 并发上传分片     → /resourceManager/multipartUpload（5 并发）
4. 通知合并         → completeUpload
5. 注册元数据       → /resourceManager/create
```

---

## 调用 Tool

参数确认后，调用 upload_package Tool 执行。

---

## 典型场景

### 场景 A：上传 Python 环境包

用户说："上传一个 Python 包，名字叫 sklearn-env，文件是 sklearn-env.tar.gz"

```json
{
  "name": "sklearn-env",
  "type": 6,
  "resource_info": { "file_name": "sklearn-env.tar.gz" },
  "description": "scikit-learn 1.3 + pandas 2.0 机器学习环境",
  "fileContent": "<Buffer 或 base64>"
}
```

上传成功后，在 submit_approval 中这样引用：

```json
{
  "app_info": {
    "sql_engine": 2,
    "sql_info": { "archives_package": "sklearn-env" }
  }
}
```

### 场景 B：上传自定义 JAR 包

```json
{
  "name": "custom-udf",
  "type": 6,
  "resource_info": { "file_name": "udf-1.0.jar" },
  "description": "自定义 UDF 函数库 v1.0",
  "fileContent": "<Buffer 或 base64>"
}
```

---

## 常见问题

| 问题                           | 原因                                  | 解决方案                         |
| ------------------------------ | ------------------------------------- | -------------------------------- |
| 获取 uploadID 失败             | 网络或权限问题                        | 检查网络连接和账户权限           |
| 分片上传失败（code !== 10039） | 网络超时或文件损坏                    | 重新上传                         |
| 包名已存在                     | 包名重复                              | 换一个包名，或先在平台删除已有包 |
| Python 任务找不到包            | archives_package 与上传时 name 不一致 | 确认 name 字段拼写完全一致       |

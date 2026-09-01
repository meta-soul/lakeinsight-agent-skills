# 分片上传内部实现参考

> 本文档说明 upload_package Tool 内部的分片上传机制，供调试和排错使用。

## 分片上传流程

```
initUpload
    ↓
文件切片（每片 3MB）
    ↓
并发上传分片（默认 5 并发，TaskQueue 控制）
    ↓ 所有分片上传完成
completeUpload（通知后端合并）
    ↓
uploadPackageMeta（注册元数据）
```

## 关键参数

| 参数        | 值                     | 说明                   |
| ----------- | ---------------------- | ---------------------- |
| CHUNK_SIZE  | 3MB（3 _ 1024 _ 1024） | 每个分片大小           |
| concurrency | 5                      | 默认并发上传数         |
| 成功状态码  | 10039                  | 分片上传成功的 code 值 |

## API 端点

| 步骤        | 端点                                  | 说明                                                     |
| ----------- | ------------------------------------- | -------------------------------------------------------- |
| 初始化上传  | POST /resourceManager/initUpload      | 参数：file_name, file_type                               |
| 上传分片    | POST /resourceManager/multipartUpload | 参数：file, file_type, file_name, part_number, upload_id |
| 完成上传    | POST /resourceManager/completeUpload  | 参数：parts[], file_name, file_type, upload_id           |
| 注册元数据  | POST /resourceManager/create          | 参数：name, type, resource_info, description             |

## 错误处理

分片上传失败时（code !== 10039），TaskQueue 会立即 reject，
整个上传任务终止，不会继续上传剩余分片。
重新上传时系统会重新初始化 uploadID，从第一片开始重传。

## TaskQueue 说明

`TaskQueue` 来自项目现有的 `src/utils/taskQueue`，
控制并发数量，避免同时发起过多请求导致服务端压力过大。

- `onTaskComplete`：单个分片完成时记录结果到 `parts[]`
- `onTaskError`：任一分片失败时终止整个上传
- `onAllComplete`：所有分片完成后触发 `completeUpload`

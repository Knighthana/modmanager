# Backup Dir Builder Design

## 目标
将备份目录字符串生成过程与 `backup_ops` 解耦。

## 设计原则
- `backup_ops` 只消费目录字符串并做合法性/完整性检查。
- builder 负责命名规则、id 查找、时间转换、路径拼装。

## 输入
- `bakprefix`（默认建议 `kmmbackup_`）
- 标识来源（appid/contentid/custom_id）
- 更新时间（可转 hex）
- 可选 base path

## 输出
- 最终目录字符串（可绝对路径或相对路径）

## 处理流程
1. 解析配置与标识选择。
2. 查询 id。
3. 获取更新时间并转换为 `updatetimehex`。
4. 按 `{prefix}{id}_{updatetimehex}` 拼接名称。
5. 结合可选 base path 形成最终目录字符串。

## bakignore 接入点
- 由编排层/扫描层使用 `bakignore` 过滤路径。
- builder 不承担扫描，只提供命名产物。

## 错误处理
- id 缺失、时间转换失败、路径非法时返回结构化错误。
- 不在 builder 内做文件系统写操作。

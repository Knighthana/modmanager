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

## 2026-04-30 设计确认

### 时间戳来源

| 来源类型 | 时间源 | 说明 |
|----------|--------|------|
| common（游戏本体目录） | `appmanifest_{appid}.acf` → `LastUpdated` → hex | 已实现 `get_game_backup_id()` |
| workshop（已发布 mod） | `appworkshop_{appid}.acf` → `timeupdated` → hex | 已实现 ✅ |
| custom mod（本地 mod） | 文件 mtime（fallback） | 长期计划：kmm 标准自述文件 |

### 备份目录位置

| 类型 | 位置 |
|------|------|
| common 中的文件 | `<steamapps>/common/<GameName>/kmmbackup_{appid}_{updatetimehex}/` |
| workshop 中的文件 | `<steamapps>/workshop/content/<appid>/<contentid>/kmmbackup_{contentid}_{updatetimehex}/` |

### user_config 配置项

- `bakprefix`：备份目录名前缀（默认 `kmmbackup_`）
- `bakignore`：备份/恢复扫描时忽略的路径/通配规则集合

### 硬编码防护

- `backup_ops` 内部硬编码始终忽略 `kmmbackup_` 前缀的目录（即使 user_config 缺失）
- 备份目录下检测 `.kmmbakignore` 文件（仿 `.gitignore` 语法）作为额外的忽略规则

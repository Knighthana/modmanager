# dry_run 文件列表输出规范

> Last-Updated: 2026-05-18

## 目标

规定 backup / apply / restore 在 `dry_run=true` 时返回的文件列表结构，以及前端表格展示规范。

## 输出结构

### backup dry_run

`run_differential_backup` 在 `dry_run=True` 时，`backed_up` 列表中每条记录的字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | `"copy"` | 操作类型，备份均为拷贝 |
| `path` | `str` | 源文件绝对路径 |
| `backup_path` | `str` | 文件在备份目录内的完整相对路径，格式 `{dir_basename}/{rel}`。例：`2606099273.69fc415f.kmmbackup/some/file.mod` |
| `size` | `int` | 文件字节数 |
| `mtime` | `float` | 修改时间（unix timestamp） |
| `is_dir` | `bool` | 是否为目录 |

`skipped` 列表中每条记录：

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | `str` | 源文件绝对路径 |
| `reason` | `str` | 跳过原因 |

### apply dry_run

`apply_final_mapping` 在 `dry_run=True` 时，`applied` 列表中每条记录：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | `"create"` / `"replace"` / `"delete"` | 来自 `final_mapping[].request.action` |
| `source` | `str` | 源路径（delete 时为空） |
| `target` | `str` | 目标绝对路径 |
| `size` | `int` | 源文件字节数 |
| `mtime` | `float` | 修改时间 |
| `is_dir` | `bool` | 是否为目录 |

### restore dry_run

`restore_from_backup` 在 `dry_run=True` 时，`restored` 列表中每条记录：

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | `str` | 原始绝对路径（目标位置） |
| `size` | `int` | 备份文件字节数 |
| `mtime` | `float` | 修改时间 |
| `is_dir` | `bool` | 恒为 `false`（备份均为文件） |

## 前端表格列

### backup dry_run 表格

| 列 | 字段 | 宽度 | 说明 |
|---|---|---|---|
| 操作 | `action` → "拷贝" | 80 | 显式映射，不再显示"备份" |
| 类型 | `is_dir` → "目录" / "文件" | 80 | |
| 备份位置 | `backup_path` | 300 | **主视觉列**——文件在备份目录内路径 |
| 源路径 | `path` | 200 | 参考信息 |
| 大小 | `size` → 格式化 | 100 | |
| 修改时间 | `mtime` → 格式化 | 180 | |

### apply dry_run 表格

| 列 | 字段 | 宽度 | 说明 |
|---|---|---|---|
| 操作 | `action` → 标签（创建/替换/删除） | 80 | |
| 类型 | `is_dir` → "目录" / "文件" | 80 | |
| 目标路径 | `target` | 300 | |
| 源路径 | `source` | 200 | |
| 大小 | `size` | 100 | |
| 修改时间 | `mtime` | 180 | |

### restore dry_run 表格

| 列 | 字段 | 宽度 | 说明 |
|---|---|---|---|
| 操作 | — → "恢复" | 80 | |
| 类型 | `is_dir` → "目录" / "文件" | 80 | |
| 目标路径 | `path` | 300 | |
| 大小 | `size` | 100 | |
| 修改时间 | `mtime` | 180 | |

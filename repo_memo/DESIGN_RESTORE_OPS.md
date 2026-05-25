# DESIGN_RESTORE_OPS — Restore 执行设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 restore 如何消费当前 mapping、backupinfo 与 backup_dir 执行恢复
> Supersedes: DESIGN_BACKUP.md
> Last update: 2026-05-21 — 重新规定 restore 流程：批量操作列表、树上无结点则删除源文件、严格按 tree 状态判断

## 一、职责边界

本文档只描述 restore 如何执行。

本文档不负责定义：
- `backup_dir` 的目录结构
- `backupinfo` 的 schema 结构
- 如何执行 backup

这些问题分别由 `DESIGN_BACKUP_DIR.md`、`DESIGN_BACKUP_OPS.md` 负责。

## 二、总原则

### 2.1 restore 是执行原语

- restore 不负责检查更高层状态，不负责判断用户是否"应该先 backup"。
- restore 只消费当前可见输入并执行恢复：当前 mapping、对应 backup_dir、`backupinfo.json`。

### 2.2 mapping 只决定 scope，backupinfo 只决定 truth

- 当前 mapping 只用于判定这次 restore 里哪些文件「被命中过」。
- `backupinfo.json` 只用于提供这些文件的 schema 与 hash 权威。
- 二者职责不可混用。

### 2.3 Ignore 规则缓存

ignore 的计算非常常用。Planner 在 `plan_fileops()` 阶段计算出的 ignore 结果必须以某种形式缓存并提供给 restore 原语直接消费，不允许 restore 原语重新计算 ignore 规则。

## 三、执行输入

- 当前 mapping（来自 Planner 构建的 `CleanContext.final_mapping`）
- 对应 backup_dir
- `backupinfo.json`

## 四、Restore 执行流程

1. 根据 mapping 所确定的 scope（被命中的文件），在 ignore 的基础上，获取要操作的文件列表。

2. 将 `backupinfo.json` 中的树加载进内存。

3. 如果 tree 上根本就没有对应的文件结点，那么直接删除源目录中的对应文件。

4. 如果 tree 上的对应文件的 `isbackuped` 为 `false`，那么跳过这个操作并记录一条详细警告。如果 `hashtype` 和 `hashvalue` 不是有意义的值（即 `hashtype` 为 `"invalid"` 或 `hashvalue` 为 `"0"`），那么同样跳过并记录对应的详细警告。

5. 如果 tree 上有对应文件且 `isbackuped` 为 `true`，并且有有效的 `hashtype` 和 `hashvalue`，那么计算外面目录（源目录）中该文件在对应 `hashtype` 下的 `hashvalue`，并与 `backupinfo.json` tree 上的值对比：
   - 如果相同，跳过。
   - 如果不相同，记录这个文件进入文件批量操作列表。

6. 当 mapping 被 ignore 之后的 scope 确认完毕之后，执行整个文件批量操作列表的工作。从 `backup_dir` 中取对应实体文件复制回目标位置。若父目录不存在，restore 可创建所需父目录后再复制。

## 五、warning 与 error 的边界

restore 不做上层门禁判断，但会在执行过程中产生 warning 或 error。

### 5.1 warning

以下情况记为 warning：

- 某目标在当前 restore scope 内，但树上对应文件的 `isbackuped` 为 `false`
- 某目标在树上存在，但 `hashtype` 为 `"invalid"` 或 `hashvalue` 为 `"0"`（无有效 hash）
- 某个 backup_dir 无法通过可恢复性检查，因此该目录下目标整体跳过
- 存在本次 restore 未命中的外部文件或孤儿文件，需要提示但不阻断其它恢复

### 5.2 error

以下情况记为 error：

- 复制回目标位置时发生不可恢复的 I/O 失败
- 当前 restore 动作无法继续执行该条目
- 已进入执行阶段但关键输入损坏到无法继续工作

具体错误码与默认严重级别以 `TERMS_ERROR_CODES.md` 为准。

## 六、hash 行为

- `force=true` 时，应直接跳过 hash 计算并执行文件操作，不改变 backupinfo 的权威地位。
- `force=false` 时（默认），restore 按照 §四 步骤 5 中的方式做 hash 比对。比对的对象是**源目录中文件的 hash** 与 **tree 上记录的值**。

## 七、当前实现应遵循的最小流程

```text
读取当前 mapping
  -> 根据 mapping 确定 scope（被命中的文件），应用 ignore 规则
  -> 定位对应 backup_dir
  -> 读取 backup_dir/backupinfo.json，将树加载进内存
  -> 遍历 scope 内每个文件：
       树上无对应结点 → 直接删除源目录中的对应文件
       isbackuped=false 或 hash 无效 → skip + warning
       isbackuped=true 且有有效 hash → 计算源文件 hash 与树上值对比
         相同 → skip
         不同 → 加入批量操作列表
  -> scope 确认完毕后，执行批量操作列表（从 backup_dir 复制回目标位置）
  -> 找不到可恢复实体则 warning
  -> 确实执行失败则 error
```

## 八、测试断言

测试组可以据本文档编写正例断言：

- restore 只处理当前 mapping 命中的文件
- 树上无对应结点时：直接删除源目录中的对应文件
- `isbackuped=false` 时：skip 并记录 warning
- `hashtype` 为 `"invalid"` 或 `hashvalue` 为 `"0"` 时：skip 并记录 warning
- `force=true` 时直接跳过 hash 计算并执行文件操作
- hash 相同时 skip，不同时加入批量操作列表并最终执行
- `dry_run=true` 时：不修改文件，但仍产出完整的操作报告（`restored`、`deleted`、`skipped`、`warnings`）
- 找不到可恢复实体时应产生 warning，而不是隐式成功
- 复制失败应产生 error
- `.kmmignore` 还原：restore 时从 backup_dir 各级目录收集 `.kmmignore` 文件，复制回源目录对应位置

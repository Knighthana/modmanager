# work_memo

本目录用于**工作现场的实时状态记录**。

## 用途

**唯一用途**：存放 `states.md`，记录当前工作的 TODO / FINISHED 状态。

不作其他用途。

## 状态文件格式

`states.md` 由实现者自行维护，建议格式：

```markdown
# 工作状态

## FINISHED
- [x] 修复 _ensure_steamapps 尾部斜杠 bug
- [x] DataSourcePage 手动模式 radio 切换

## TODO
- [ ] 空输入校验
- [ ] BackupPage GUI 审查
```

## 日志流程

当 Plan 或用户提示"准备结束工作，记录日志"时：

1. 读取 `work_memo/states.md` 中的 FINISHED 条目
2. 将其记入 `repo_logs/YYYY-MM-DD.md`
3. 从 `states.md` 中清除已记录的 FINISHED 条目
4. 保留所有 TODO 条目

## 维护规则

- 由 implement 自行维护
- 不作为契约或实现依据
- 若与 `repo_memo/` 内容冲突，以 `repo_memo/` 为准

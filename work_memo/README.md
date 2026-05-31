# work_memo

本目录用于**工作现场的实时状态记录**。

## 用途

- 存放`states.md`，记录当前工作的 TODO / FINISHED 状态。
- 其他由user亲自明确交代的用途。

## 状态文件格式

`states.md` 由arch维护，smith可以向其中添加条目，要求格式：

```markdown
# 工作状态

## FINISHED
- [x] TASK2605-0x1F [user] 修复 _ensure_steamapps 尾部斜杠 bug
- [x] TASK2605-0x20 [user] DataSourcePage 手动模式 radio 切换

## TODO
- [ ] (PENDING)TASK2605-0x1 [user] 空输入校验
- [ ] TASK2605-0x21 [arch] BackupPage GUI 审查
```

## 日志流程

当 Plan 或用户提示"准备结束工作，记录日志"时：

1. 读取 `work_memo/states.md` 中的 FINISHED 条目
2. 将其记入 `repo_logs/YYYY-MM-DD.md`
3. 从 `states.md` 中清除已记录的 FINISHED 条目
4. 保留所有 TODO 条目

## 维护规则

- 若与 `repo_memo/` 内容冲突，以 `repo_memo/` 为准

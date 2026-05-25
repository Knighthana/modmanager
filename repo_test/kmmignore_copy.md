# .kmmignore 复制/还原 — 测试断言

> 依据: `DESIGN_BACKUP_OPS.md` §十三、`DESIGN_RESTORE_OPS.md` §八

---

| # | 场景 | 期望 |
|---|------|------|
| T1 | 源目录根存在 `.kmmignore` → backup | backup_dir 根存在 `.kmmignore`（内容一致） |
| T2 | 源目录子目录存在 `.kmmignore` → backup | backup_dir 对应子目录存在 `.kmmignore` |
| T3 | 源目录无 `.kmmignore` → backup | backup_dir 无 `.kmmignore`（不报错） |
| T4 | backup_dir 已存在 `.kmmignore` → restore | 源目录对应位置被还原 `.kmmignore`（覆盖） |
| T5 | backup_dir 无 `.kmmignore` → restore | 源目录无变化（不报错） |
| T6 | `.kmmignore` 复制失败（权限不足）→ backup | 记录 warning，不阻断备份流程 |

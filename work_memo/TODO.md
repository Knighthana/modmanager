# TODO — 待办事项

更新时间：2026-04-30

---

## P0: 森林模型引擎重构 ✅

来源：`work_memo/FOREST_DELETE_FORK_DESIGN.md`
设计文档：`repo_memory/direct/DESIGN_P0_FOREST_IMPLEMENTATION.md`
风险分析：`repo_memory/direct/DESIGN_P0_FOREST_RISK_ANALYSIS.md`

**决策**：激进全栈切换 / delete 失效→跳过+warning / T5 不裂变→祖先检查

**结果**：33 个任务全部完成。Python 296 tests 通过，前端 15 Vitest 通过，构建成功。
W_DELETE_LEAF_PROMOTED 移除，替换为 W_SOURCE_DELETED / W_SOURCE_DIRECTORY_DELETED。
输出 key `"forest"` → `"trees"`。

---

## P1: Backup 实现 ✅

来源：`work_memo/TODO.md` 原始 P1 + `repo_memory/BACKUP_DIR_BUILDER_DESIGN.md`
设计文档：`repo_memory/direct/DESIGN_P1_BACKUP.md`

**目标**：备份目录命名规则自动生成 / workshop 时间源 / .kmmbakignore / 循环防护

详见 TASKLIST.md Phase P1 中的 16 个任务。

---

## P2: 引擎细节修复

| # | 任务 | 说明 |
|---|------|------|
| T1 | same actionlist: delete→create 不警告 | 改为检查同 actionlist 内是否有前序 delete → 有则不产生 W_CREATE_TARGET_EXISTS_OVERWRITE |
| E1 | 术语统一 | 代码变量名/注释中 "节点"→"结点"（tree node），"节点" 保留给 compute node |

---

## P3: GUI（待用户反馈）

| # | 任务 | 说明 |
|---|------|------|
| GUI1 | Forest 全部/仅分岔切换 | 待用户反馈决定是否实现 |
| GUI2 | M4 交互 | hover 高亮、分叉超链接、拖拽选枝 |

---

## 上下文记录

- 2026-04-30：forest 模型讨论（独立根+引用）、backup 设计确认、6 个 bug 修复、2 个操作废弃
- 备份设计 7 原则已确认：`bakprefix=kmmbackup_`、workshop acf 时间源、custom mtime、位置规则、.kmmbakignore、硬编码忽略

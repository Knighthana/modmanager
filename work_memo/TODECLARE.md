# TODECLARE — 待澄清问题

创建：2026-04-30
状态：讨论中

---

## 1. Forest SVG 白色背景 → 透明背景 ✅ 已修复

**修复时间**：2026-04-30
**改动文件**：`src/modmanager/forest_visual.py` — `_render_dot()` 中添加 `bgcolor=transparent;`

**现状**：Forest 矢量图使用了白色背景而非透明背景。

**期望**：输出为透明背景的 SVG。

**排查方向**：`forest_visual.py` 中 Graphviz SVG 渲染是否设置了 `bgcolor`？是否可以通过 `dot` 参数控制背景透明度？

---

## 2. 路径缺少末尾 `/` ✅ 已修复

**修复时间**：2026-04-30
**改动文件**：
- `src/modmanager/paths.py` — 删除 `normalize_posix()` 中的 `rstrip("/")`，保留路径末尾的 `/`
- `src/modmanager/rule_aggregator.py` — 聚合器 Step 4 新增自动补全逻辑：`from_type=path` 且不含 glob 字符的条目、`into_type=path` 的条目若末尾缺少 `/` 则自动补全，并记录 `W_PATH_TRAILING_SLASH_FIXED` 警告

**修复效果**：
- `normalize_posix()` 不再破坏路径末尾 `/`，目录/文件类型标记得以保留
- 聚合器兜底修复规则书写者遗漏的末尾 `/`，保证后续流程不受影响
- 新增 4 个测试用例覆盖补全、glob 跳过、file 类型不处理等场景

---

## 3. `W_DELETE_LEAF_PROMOTED` 的必要性

**现象**：当 Forest 中某个映射链的最终来源是 delete 操作时，引擎输出 `W_DELETE_LEAF_PROMOTED` 警告。

**需要澄清**：
- 如果 action 中明确写了 delete，删除就是预期的行为。为什么需要警告？
- 这个警告何时对用户有实际意义？
- 是否应该降级为 info/debug 级别，或在映射计算完成时不显示？

---

## 4. `W_CREATE_TARGET_EXISTS_OVERWRITE` 不应与 Tree State 冲突

**现象**：
```
W_CREATE_TARGET_EXISTS_OVERWRITE: /mnt/d/Games/steamapps/common/RunningWithRifles/media/packages/vanilla/maps/lobby
```
路径末尾缺少 `/`（同问题 2）。

**核心问题**：规则中前序已有 delete 操作将目标路径标记为删除。既然是一个"前序 delete → 后续 create"的文件到文件映射，且前序文件已挂上 delete 结点，引擎在检查 create 时**应该参考树的状态**（目标已被前序 delete 清空），而不是**参考本地磁盘状态**（目标文件仍然在磁盘上）。

**需要澄清**：
- 引擎的 `compute_mapping` 为什么在 create 检查时用 `Path(target).exists()` 而非参考映射树内部状态？
- 是否需要引入"映射树内状态追踪"机制，使 delete 的副作用对后续 action 可见？

---

## 5. `W_NO_SOURCE_MATCH` 对已存在目录的误报

**现象**：
```
W_NO_SOURCE_MATCH: 270150:一点不战术地图v1.9 TEMP#0:一点不战术地图v1.9 TEMP/时效性附加内容/maps/*/
```

通过 `ls` 可以确认这些目录确实存在，但引擎报告无匹配。

**需要澄清**：
- 是 `_expand_sources` 的 glob 展开有问题，还是路径风格转换（WSL→Windows）导致找错了位置？
- `from_type=path` 的 `*/` glob 是否正确展开？
- WSL 环境下 `Path.glob()` 对 Windows 路径的支持如何？

---

## 6. Backup 理解偏差

**感觉**：当前项目对 backup 的理解似乎出了偏差。

**需要澄清**：
- 最初设计中 backup 的定位是什么（见 `DESIGN_BOOTSTRAP_ORCHESTRATOR.md` 和 `BACKUP_DIR_BUILDER_DESIGN.md`）？
- 当前实现中 backup 的实际行为与设计的差距在哪里？
- "差异备份"的语义是"备份什么"——是备份被替换的目标文件以便恢复，还是备份整个 mapping 的历史状态？
- `backup_dir` 的命名和生命周期应该如何管理？

---

## 讨论顺序

按编号逐条澄清：1 → 2 → 3 → 4 → 5 → 6

---

## 7. Forest 可视化中"全部映射 / 仅分岔"切换

**问题**：是否要在 Forest 可视化中设置一个"切换全部映射/仅保留含有分岔的映射"的按钮？这是否与"冲突裁决"页面的语义有重复？应该留哪个？

**状态**：待讨论

---

## 8. `rename_then_replace` 与 `clear_then_copy` 废弃 ✅ 已处理

**处理时间**：2026-04-30

**决策**：两个操作已被废弃：
- `rename_then_replace`：等价于 `replace` + `from_type=file` + `into_type=file`（重命名即替换）
- `clear_then_copy`：等价于独立 `delete` + 独立 `create`

**改动文件**：
1. `src/modmanager/engine.py` — `VALID_ACTIONS` 移除两个操作；`RuleItem` 移除 `nwname` 字段；删除 `clear_copy_dirs`、`clear_then_copy` 冲突检测和 `nwname`/`rename_then_replace` 处理逻辑；`_target_for` 简化（`nwname` 参数保留但不再使用）
2. `src/modmanager/backup_ops.py` — 删除 `_collect_clear_then_copy_dirs` 函数和预清除循环
3. `src/modmanager/output_schema.json` — ChangeRequest action enum 移除两个操作
4. `tests/` — 所有相关测试用例已改为等价操作
5. `repo_memory/IMPLEMENTATION_BRIEF.md` — L160 标记废弃
6. `repo_memory/RULE_AGGREGATION_DESIGN.md` — L181 标记 `nwname` 废弃

**验收**：python3 -m pytest tests/ -q 全部通过

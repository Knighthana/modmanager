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

## 2. 路径缺少末尾 `/`

**现象**：
```
W_DELETE_LEAF_PROMOTED: /mnt/d/Games/steamapps/workshop/content/270150/2606099273/media/packages/GFL_Castling/maps/1使用方法和图例
```

这条路径是对一个目录的引用，但末尾缺少 `/`。违反了项目约定：**"凡是 path 都必须以 `/` 结尾，否则会被视为文件"**。

**需要澄清**：
- 哪一步导致 `/` 丢失？
- 路径是通过 normalize_posix 处理后丢掉的，还是规则输入时就没有 `/`？
- 这会有什么潜在影响（文件/目录类型误判、glob 匹配行为等）？

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

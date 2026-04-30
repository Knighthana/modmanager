# TODO — 待办事项

更新时间：2026-04-30

---

## P0: 森林模型引擎重构

来源：`work_memo/FOREST_DELETE_FORK_DESIGN.md`

| # | 任务 | 说明 |
|---|------|------|
| G1 | ForestTree 从 mapping dict 构建 | 现有 compute_mapping 产出扁平 forest 列表 → 提取根路径 + 操作 + 引用边，构建 ForestTree 列表 |
| G2 | 引用边从 changerequest 提取 | changerequest.path 是源路径。若该路径也是另一个 target → 形成引用边 |
| G3 | 用户决策反馈给 final_mapping | 各树冲突裁决后重新计算 final_mapping |

---

## P1: Backup 实现

来源：`work_memo/TODECLARE.md` 问题 6

| # | 任务 | 说明 |
|---|------|------|
| B1 | backup_dir builder 模块 | 实现 `{bakprefix}{id}_{updatetimehex}` 命名规则 |
| B2 | workshop time 源 | `appworkshop_{appid}.acf` → `timeupdated` → hex |
| B3 | custom mod time | mtime fallback；长期：kmm 标准自述文件 |
| B4 | backup_dir 位置规则 | common → `common/GameName/`；workshop → `workshop/content/appid/contentid/` |
| B5 | .kmmbakignore | 备份目录下检测，仿 .gitignore 语法 |
| B6 | bakprefix/bakignore 加载 | 从 user_config 读取，backup_ops 硬编码忽略 `kmmbackup_` |
| B7 | 循环备份防护 | backup_ops 扫描/备份时始终跳过 `kmmbackup_` 前缀的目录 |

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

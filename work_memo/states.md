# 工作状态

> arch 维护。smith 可向其中添加条目。

## 悬空待办（按优先级）

### P0 — 阻塞性缺陷 ✅
- [x] **backupinfo tree 扫描源目录**：`backup_ops.py` — `build_dir_tree_with_hashes` 改为扫描 source_root + backup_dir 对照
- [x] **backup `run_differential_backup` 目录处理**：删除 `copytree`，增加 `_assert_is_file` 守卫
- [x] **CLI restore 绕过 orchestrator**：`cli.py` — `_handle_restore` 改为 `dispatch(Intent.RESTORE)`，从 backupinfo 构造 minimal final_mapping

### P1 — `.kmmignore` 升级 ✅
- [x] 新建 `orchestrator/ignore_rules.py`（gitignore-parser 封装 + 三层规则收集）
- [x] 文件名 `.kmmbakignore` → `.kmmignore`（存量文件用户自行重命名）
- [x] `user_config.bakignore` → `user_config.ignore`（schema + 文档 + 代码）
- [x] Planner `_collect_bakignore` → `_collect_ignore_rules`，backup/apply/restore 全量过滤
- [x] 新建 `DESIGN_IGNORE_RULES.md`
- [x] 更新 `DESIGN_BACKUP_DIR.md` §5.4、`DESIGN_BACKUP_OPS.md` §七
- [x] 更新 `user_config.schema.json`

### P2 — 文档残修
- [ ] `DESIGN_BACKUP_OPS.md` §八：字段列表是否有重复定义需精简为引用

### P3 — 测试补全
- [ ] `apply_ops`：file-to-file 正例 + 目录拒绝 + dry_run + 返回契约
- [ ] `restore_ops`：hash 比对 / force 跳过 / 路径映射
- [ ] `planner_fileops`：preflight 决策分支 / 忽略收集 / backup_dir 分组
- [ ] `preflight`：apply gate / restore existence
- [ ] `ignore_rules`：三层收集 + gitignore 解析
- [ ] 恢复被 skip 的 24 个测试（改为测试 `dispatch()` 通路）
- [ ] restore 缺少的 warning：找不到备份实体 → warning 非 skipped；孤儿文件检测

## 已确认决策（本轮新增）

- **D22**: `.kmmbakignore` → `.kmmignore`；语义从「不备份」→「不参与 mod 管理」；归属 Planner 层；独立模块 `orchestrator/ignore_rules.py`
- **D23**: `user_config.bakignore` → `user_config.ignore`
- **D24**: backupinfo `tree` 扫描源目录（非 backup_dir），`isbackuped` 标记对照 backup_dir 副本

## 存量待办

- [ ] (pending)TASK2605-0x1 [user] 前端空输入校验，“待后端端点均符合预期后再开展”
- [ ] (pending)TASK2605-0x2 [user] 统一界面视觉效果: 字体 按钮
- [ ] (pending)TASK2605-0x3 [user] 主题切换，根据日出日落/系统主题自动切换界面亮暗效果
- [ ] (pending)TASK2605-0x4 [user] 自动输出日志文件到规定位置整洁
- [ ] (pending)TASK2605-0x5 [user] 规则概览 — preview 图片加载；设计就绪（`DESIGN_EXT_RESOURCE.md`），待 `ext_resource` 包实现
- [ ] (pending)TASK2605-0x6 [user] 规则概览 — README 文件内容查看；同上
- [ ] (pending)TASK2605-0x7 [user] 规则概览 — author 字段的键含义与展示方式待讨论
- [ ] TASK2605-0x9 [user] 检查bootstrap目前使用什么样的逻辑进行自动发现；提供“steam没有安装在默认目录”场景下手动指定`steam.exe`位置(更推荐，因为主vdf的路径可以通过`steam.exe`位置推算)或手动指定主vdf文件的途径；让bootstrap对macOS进行支持；针对Linux/Windows/macOS三套系统写出详细的“默认路径”方案；

## FINISHED（本轮）

- [x] D1-D21 全部落地
- [x] `preflight.py` `check_backup_gate` 返回值修复
- [x] `resolver.py` `workspace_dir` None 回退修复
- [x] `_execute_backup_plan` `run_differential_backup` 签名修复
- [x] `restore_ops` 路径映射修复（content_root 逻辑）
- [x] 文档：7 个设计文档过期引用清理
- [x] 文档：backupinfo tree 来源修正（3 个文档）
- [x] 测试：import / schema_version 修复（380 passed, 0 failed）
